from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.security import authenticate
from app.db.postgres import get_sqlalchemy_engine
from app.models.schemas import (
    AccountRequest,
    BehaviorScoringRequest,
    BehaviorScoringResponse,
    BulkSimulationRequest,
    ConfigRuleMapping,
    ResetRequest,
    RulesRetrieveRequest,
    RulesUpdateRequest,
)
from app.services.feature_engineering import BehavioralFeatureEngineer
from app.services.modeling import HybridBehaviorScorer
from app.services.simulator import generate_simulation_batch, persist_simulation_batch


router = APIRouter(tags=["behavior-engine"], dependencies=[Depends(authenticate)])


@router.post("/score-behavior", response_model=BehaviorScoringResponse)
def score_behavior(request: BehaviorScoringRequest) -> BehaviorScoringResponse:
    try:
        scorer = HybridBehaviorScorer(account_id=request.account_id)
        result = scorer.score_realtime_transaction(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BehaviorScoringResponse(
        behavior_score=result["behavior_score"],
        behavior_change=result["behavior_change"],
        reasons=result["reasons"],
    )


@router.post("/simulate/bulk")
def simulate_bulk(request: BulkSimulationRequest) -> dict[str, object]:
    try:
        transactions, summary = generate_simulation_batch(
            months=request.months,
            seed=request.seed,
            customers=request.customers,
            inject_time_shift=request.inject_time_shift,
            inject_amount_spike=request.inject_amount_spike,
            inject_new_ip=request.inject_new_ip,
        )
        persist_simulation_batch(transactions, output=request.output)

        feature_summary: dict[str, object] | None = None
        scoring_summary: dict[str, object] | None = None
        if request.output in {"postgres", "both"}:
            feature_engineer = BehavioralFeatureEngineer()
            loaded_transactions = feature_engineer.load_raw_transactions()
            feature_result = feature_engineer.build_features(loaded_transactions)
            feature_engineer.persist_behavioral_profile(feature_result.profile_frame)
            feature_summary = {
                "baseline_transactions_used": int(len(feature_result.baseline_transactions)),
                "profiles_written": int(len(feature_result.profile_frame)),
            }

            if summary["anomalies_enabled"]:
                scorer = HybridBehaviorScorer()
                artifacts = scorer.run()
                scorer.persist_scoring_results(artifacts.scored_transactions)
                scoring_summary = {
                    "baseline_transactions": int(len(artifacts.baseline_transactions)),
                    "anomalous_transactions": int(len(artifacts.anomalous_transactions)),
                    "monthly_summary": _serialize_rows(artifacts.monthly_summary.to_dict(orient="records")),
                }

        return {
            "summary": _serialize_record(summary),
            "feature_summary": feature_summary,
            "scoring_summary": scoring_summary,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/simulate/reset")
def reset_simulation(request: ResetRequest) -> dict[str, object]:
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Reset confirmation must be true.")

    _execute_write(
        """
        TRUNCATE TABLE raw_transactions, behavioral_profiles, scoring_results
        RESTART IDENTITY CASCADE
        """
    )
    return {"status": "ok", "message": "Simulation tables cleared."}


@router.post("/metrics/summary")
def metrics_summary(request: AccountRequest) -> dict[str, object]:
    summary_rows = _fetch_rows(
        """
        SELECT
            rt.account_id,
            COUNT(*) AS total_transactions,
            ROUND(AVG(rt.amount), 2) AS average_amount,
            SUM(CASE WHEN COALESCE(sr.behavior_change, FALSE) THEN 1 ELSE 0 END) AS flagged_transactions,
            ROUND(AVG(COALESCE(sr.behavior_score, 0)), 4) AS average_behavior_score
        FROM raw_transactions rt
        LEFT JOIN scoring_results sr ON rt.event_id = sr.event_id
        WHERE rt.account_id = :account_id
        GROUP BY rt.account_id
        """,
        {"account_id": request.account_id},
    )
    reason_rows = _fetch_rows(
        """
        SELECT reason, COUNT(*) AS count
        FROM (
            SELECT UNNEST(COALESCE(sr.behavior_reasons, ARRAY[]::TEXT[])) AS reason
            FROM raw_transactions rt
            JOIN scoring_results sr ON rt.event_id = sr.event_id
            WHERE rt.account_id = :account_id
        ) reasons
        GROUP BY reason
        ORDER BY count DESC, reason
        """,
        {"account_id": request.account_id},
    )

    if not summary_rows:
        raise HTTPException(status_code=404, detail=f"No transactions found for account_id={request.account_id}.")

    return {
        "summary": summary_rows[0],
        "reason_counts": reason_rows,
    }


@router.post("/profile/retrieve")
def retrieve_profile(request: AccountRequest) -> dict[str, object]:
    rows = _fetch_rows(
        """
        SELECT
            account_id,
            avg_amount,
            std_amount,
            txn_frequency,
            active_hours,
            device_list,
            location_profile
        FROM behavioral_profiles
        WHERE account_id = :account_id
        LIMIT 1
        """,
        {"account_id": request.account_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No behavioral profile found for account_id={request.account_id}.")
    return {"profile": rows[0]}


@router.post("/transactions/history")
def transaction_history(request: AccountRequest) -> dict[str, object]:
    rows = _fetch_rows(
        """
        SELECT
            rt.event_id,
            rt.event_ts,
            rt.account_id,
            rt.instrument_id,
            rt.amount,
            rt.currency,
            rt.country,
            rt.mcc,
            rt.merchant_id,
            rt.entry_mode,
            HOST(rt.ip) AS ip,
            rt.device_fingerprint,
            rt.terminal_id,
            rt.txn_type,
            rt.geo_coordinates,
            sr.behavior_score,
            sr.behavior_change,
            sr.behavior_reasons
        FROM raw_transactions rt
        LEFT JOIN scoring_results sr ON rt.event_id = sr.event_id
        WHERE rt.account_id = :account_id
        ORDER BY rt.event_ts DESC
        """,
        {"account_id": request.account_id},
    )
    return {"transactions": rows}


@router.post("/scoring-results")
def scoring_results(request: AccountRequest) -> dict[str, object]:
    rows = _fetch_rows(
        """
        SELECT
            rt.account_id,
            sr.event_id,
            rt.event_ts,
            sr.behavior_score,
            sr.behavior_change,
            sr.behavior_reasons
        FROM scoring_results sr
        JOIN raw_transactions rt ON rt.event_id = sr.event_id
        WHERE rt.account_id = :account_id
        ORDER BY rt.event_ts DESC
        """,
        {"account_id": request.account_id},
    )
    return {"scoring_results": rows}


@router.post("/config/rules/retrieve")
def retrieve_config_rules(request: RulesRetrieveRequest) -> dict[str, object]:
    params: dict[str, object] = {}
    where_clause = ""
    if request.behavior_change_flag is not None:
        where_clause = "WHERE behavior_change_flag = :behavior_change_flag"
        params["behavior_change_flag"] = request.behavior_change_flag

    rows = _fetch_rows(
        f"""
        SELECT
            behavior_change_flag,
            action_mapping
        FROM behavioral_config
        {where_clause}
        ORDER BY behavior_change_flag
        """,
        params,
    )
    return {"rules": rows}


@router.post("/config/rules/update")
def update_config_rules(request: RulesUpdateRequest) -> dict[str, object]:
    if not request.rules:
        raise HTTPException(status_code=400, detail="At least one rule mapping is required.")

    records = [rule.model_dump() for rule in request.rules]
    engine = get_sqlalchemy_engine()
    truncate_query = text("TRUNCATE TABLE behavioral_config")
    insert_query = text(
        """
        INSERT INTO behavioral_config (
            behavior_change_flag,
            action_mapping
        ) VALUES (
            :behavior_change_flag,
            :action_mapping
        )
        """
    )
    try:
        with engine.begin() as connection:
            connection.execute(truncate_query)
            connection.execute(insert_query, records)
    finally:
        engine.dispose()

    return {
        "status": "ok",
        "updated_rules": [ConfigRuleMapping(**record).model_dump() for record in records],
    }


def _fetch_rows(query: str, params: dict[str, object] | None = None) -> list[dict[str, object]]:
    engine = get_sqlalchemy_engine()
    try:
        with engine.begin() as connection:
            rows = connection.execute(text(query), params or {}).mappings().all()
    finally:
        engine.dispose()
    return [_serialize_record(dict(row)) for row in rows]


def _execute_write(query: str, params: dict[str, object] | None = None) -> None:
    engine = get_sqlalchemy_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text(query), params or {})
    finally:
        engine.dispose()


def _serialize_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [_serialize_record(row) for row in rows]


def _serialize_record(record: dict[str, object]) -> dict[str, object]:
    return {key: _serialize_value(value) for key, value in record.items()}


def _serialize_value(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value
