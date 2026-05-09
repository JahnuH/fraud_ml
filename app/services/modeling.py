from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import text

from app.db.postgres import get_postgres_connection, get_sqlalchemy_engine
from app.services.feature_engineering import BehaviouralFeatureEngineer


@dataclass
class ScoringArtifacts:
    baseline_transactions: pd.DataFrame
    anomalous_transactions: pd.DataFrame
    baseline_feature_matrix: pd.DataFrame
    anomalous_feature_matrix: pd.DataFrame
    scored_transactions: pd.DataFrame
    monthly_summary: pd.DataFrame


class HybridBehaviourScorer:
    MODEL_WEIGHT = 0.35
    STATISTICAL_WEIGHT = 0.50
    FEATURE_DEVIATION_WEIGHT = 0.15
    BEHAVIOUR_CHANGE_THRESHOLD = 0.65
    HARD_POISONING_REASONS = {"IMPOSSIBLE_TRAVEL"}
    ACTIVE_HOUR_TOLERANCE = 2

    def __init__(self, account_id: str | None = None, contamination: float = 0.1, random_state: int = 42) -> None:
        self.account_id = account_id
        self.contamination = contamination
        self.random_state = random_state
        self.feature_engineer = BehaviouralFeatureEngineer(account_id=account_id)
        self.model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
        )

    def run(self) -> ScoringArtifacts:
        transactions = self.feature_engineer.load_raw_transactions()
        if self.account_id:
            transactions = transactions.loc[transactions["account_id"].astype(str) == str(self.account_id)].copy()

        all_baseline_frames: list[pd.DataFrame] = []
        all_anomalous_frames: list[pd.DataFrame] = []
        all_baseline_feature_frames: list[pd.DataFrame] = []
        all_anomalous_feature_frames: list[pd.DataFrame] = []
        all_scored_frames: list[pd.DataFrame] = []
        all_monthly_summaries: list[pd.DataFrame] = []

        grouped = transactions.sort_values(["account_id", "event_ts"]).groupby("account_id", sort=True)
        for _, account_transactions in grouped:
            baseline, anomalous = self._split_baseline_and_anomalous(account_transactions.copy())
            if anomalous.empty:
                continue

            baseline_features = self._build_baseline_feature_matrix(baseline)
            anomalous_features = self._build_batch_target_feature_matrix(baseline, anomalous)
            scored_transactions = self._score_transactions(baseline, anomalous, baseline_features, anomalous_features)
            monthly_summary = self._build_monthly_summary(baseline, anomalous, scored_transactions)

            all_baseline_frames.append(baseline)
            all_anomalous_frames.append(anomalous)
            all_baseline_feature_frames.append(baseline_features)
            all_anomalous_feature_frames.append(anomalous_features)
            all_scored_frames.append(scored_transactions)
            all_monthly_summaries.append(monthly_summary)

        if not all_anomalous_frames:
            raise ValueError("No anomalous-month transactions found to score.")

        return ScoringArtifacts(
            baseline_transactions=pd.concat(all_baseline_frames, ignore_index=True),
            anomalous_transactions=pd.concat(all_anomalous_frames, ignore_index=True),
            baseline_feature_matrix=pd.concat(all_baseline_feature_frames, ignore_index=True),
            anomalous_feature_matrix=pd.concat(all_anomalous_feature_frames, ignore_index=True),
            scored_transactions=pd.concat(all_scored_frames, ignore_index=True),
            monthly_summary=pd.concat(all_monthly_summaries, ignore_index=True),
        )

    def score_realtime_transaction(self, transaction_payload: dict[str, Any]) -> dict[str, Any]:
        transaction_payload = self._normalize_realtime_payload(transaction_payload)
        transactions = self.feature_engineer.load_account_transactions(
            account_id=str(transaction_payload["account_id"]),
            exclude_impossible_travel=True,
        )
        candidate_frame = pd.DataFrame([transaction_payload]).copy()
        candidate_frame["event_ts"] = pd.to_datetime(candidate_frame["event_ts"], utc=False)
        candidate_frame["amount"] = pd.to_numeric(candidate_frame["amount"])
        if "geo_coordinates" in candidate_frame.columns:
            candidate_frame["geo_coordinates"] = candidate_frame["geo_coordinates"].apply(
                self.feature_engineer._normalize_geo_coordinates
            )
        candidate_frame = self.feature_engineer.normalize_transaction_frame(candidate_frame)
        candidate_record = candidate_frame.iloc[0]

        if transactions.empty:
            cold_start_status = self.feature_engineer.assess_cold_start(
                historical_transactions=transactions,
                candidate_timestamp=pd.Timestamp(candidate_record["event_ts"]),
            )
            scoring = self._build_cold_start_scoring(None, cold_start_status)
            action = self._lookup_action_mapping(scoring["behaviour_change"])
            self._persist_scored_transaction(
                transaction_payload=transaction_payload,
                scoring=scoring,
                action_mapping=action,
            )

            return {
                "behaviour_score": scoring["behaviour_score"],
                "behaviour_change": scoring["behaviour_change"],
                "reasons": scoring["behaviour_reasons"],
            }

        previous_transaction = self.feature_engineer.get_latest_transaction_for_account(
            transaction_payload["account_id"],
            exclude_impossible_travel=True,
        )
        impossible_travel_context = self.feature_engineer.compute_impossible_travel(
            current_transaction=candidate_record.to_dict(),
            previous_transaction=previous_transaction,
        )
        cold_start_status = self.feature_engineer.assess_cold_start(
            historical_transactions=transactions,
            candidate_timestamp=pd.Timestamp(candidate_record["event_ts"]),
        )
        if cold_start_status["is_cold_start"]:
            scoring = self._build_cold_start_scoring(impossible_travel_context, cold_start_status)
            action = self._lookup_action_mapping(scoring["behaviour_change"])
            self._persist_scored_transaction(
                transaction_payload=transaction_payload,
                scoring=scoring,
                action_mapping=action,
            )
            if self._should_update_behavioural_profile(scoring["behaviour_reasons"]):
                updated_transactions = pd.concat([transactions, candidate_frame], ignore_index=True)
                self._refresh_behavioural_profile(updated_transactions)

            return {
                "behaviour_score": scoring["behaviour_score"],
                "behaviour_change": scoring["behaviour_change"],
                "reasons": scoring["behaviour_reasons"],
            }

        baseline, _ = self._split_baseline_and_anomalous(transactions)
        if baseline.empty:
            scoring = self._build_cold_start_scoring(impossible_travel_context, cold_start_status)
            action = self._lookup_action_mapping(scoring["behaviour_change"])
            self._persist_scored_transaction(
                transaction_payload=transaction_payload,
                scoring=scoring,
                action_mapping=action,
            )
            if self._should_update_behavioural_profile(scoring["behaviour_reasons"]):
                updated_transactions = pd.concat([transactions, candidate_frame], ignore_index=True)
                self._refresh_behavioural_profile(updated_transactions)

            return {
                "behaviour_score": scoring["behaviour_score"],
                "behaviour_change": scoring["behaviour_change"],
                "reasons": scoring["behaviour_reasons"],
            }

        baseline_features = self._build_baseline_feature_matrix(baseline)
        self.model.fit(baseline_features[self._feature_columns(baseline_features)])
        try:
            profile = self._load_behavioural_profile(transaction_payload["account_id"])
        except ValueError:
            self._refresh_behavioural_profile(transactions)
            profile = self._load_behavioural_profile(transaction_payload["account_id"])
        candidate_features = self._build_single_target_feature_matrix(
            baseline_reference=baseline,
            historical_transactions=transactions,
            target_transaction=candidate_frame,
        )
        candidate_row = candidate_features.iloc[0]
        scoring = self._compute_weighted_scores(
            baseline=baseline,
            scored_row=candidate_record,
            feature_row=candidate_row,
            baseline_features=baseline_features,
            profile=profile,
            current_month_count=self._current_month_count(transactions, candidate_record) + 1,
            current_day_count=self._current_day_count(transactions, candidate_record) + 1,
            impossible_travel_context=impossible_travel_context,
        )
        action = self._lookup_action_mapping(scoring["behaviour_change"])
        self._persist_scored_transaction(
            transaction_payload=transaction_payload,
            scoring=scoring,
            action_mapping=action,
        )
        if self._should_update_behavioural_profile(scoring["behaviour_reasons"]):
            updated_transactions = pd.concat([transactions, candidate_frame], ignore_index=True)
            self._refresh_behavioural_profile(updated_transactions)

        return {
            "behaviour_score": scoring["behaviour_score"],
            "behaviour_change": scoring["behaviour_change"],
            "reasons": scoring["behaviour_reasons"],
        }

    def persist_scoring_results(self, scored_transactions: pd.DataFrame) -> None:
        records = scored_transactions[
            ["event_id", "behaviour_score", "behaviour_change", "behaviour_reasons"]
        ].to_dict(orient="records")

        connection = get_postgres_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE scoring_results")
                cursor.executemany(
                    """
                    INSERT INTO scoring_results (
                        event_id,
                        behaviour_score,
                        behaviour_change,
                        behaviour_reasons
                    ) VALUES (
                        %(event_id)s,
                        %(behaviour_score)s,
                        %(behaviour_change)s,
                        %(behaviour_reasons)s
                    )
                    """,
                    records,
                )
            connection.commit()
        finally:
            connection.close()

    def _score_transactions(
        self,
        baseline: pd.DataFrame,
        anomalous: pd.DataFrame,
        baseline_features: pd.DataFrame,
        anomalous_features: pd.DataFrame,
    ) -> pd.DataFrame:
        self.model.fit(baseline_features[self._feature_columns(baseline_features)])
        profile = self._load_behavioural_profile(str(baseline["account_id"].iloc[0]))

        scored = anomalous.copy().reset_index(drop=True)
        scored = scored.merge(anomalous_features, on="event_id", how="left")
        scored["daily_txn_count"] = scored.groupby(scored["event_ts"].dt.date)["event_id"].transform("count")
        scored["monthly_txn_count"] = len(scored)

        results: list[dict[str, Any]] = []
        for _, row in scored.iterrows():
            results.append(
                self._compute_weighted_scores(
                    baseline=baseline,
                    scored_row=row,
                    feature_row=row,
                    baseline_features=baseline_features,
                    profile=profile,
                    current_month_count=int(row["monthly_txn_count"]),
                    current_day_count=int(row["daily_txn_count"]),
                )
            )

        results_frame = pd.DataFrame(results)
        return pd.concat([scored.reset_index(drop=True), results_frame], axis=1)

    def _compute_weighted_scores(
        self,
        baseline: pd.DataFrame,
        scored_row: pd.Series,
        feature_row: pd.Series,
        baseline_features: pd.DataFrame,
        profile: dict[str, Any],
        current_month_count: int,
        current_day_count: int,
        impossible_travel_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        baseline_amount_mean = float(baseline["amount"].mean())
        baseline_amount_std = self._safe_std(float(baseline["amount"].std(ddof=0)))
        baseline_daily_counts = baseline.groupby(baseline["event_ts"].dt.date).size()
        baseline_monthly_counts = baseline.groupby(baseline["event_ts"].dt.to_period("M")).size()
        daily_count_mean = float(baseline_daily_counts.mean())
        daily_count_std = self._safe_std(float(baseline_daily_counts.std(ddof=0)))
        monthly_count_mean = float(baseline_monthly_counts.mean())
        monthly_count_std = self._safe_std(float(baseline_monthly_counts.std(ddof=0)))

        feature_columns = self._feature_columns(baseline_features)
        feature_frame = pd.DataFrame([feature_row[["event_id", *feature_columns]].to_dict()])
        model_raw_score = float(-self.model.decision_function(feature_frame[feature_columns])[0])
        baseline_model_scores = -self.model.decision_function(baseline_features[feature_columns])
        model_score = self._normalize_score(
            value=model_raw_score,
            mean=float(baseline_model_scores.mean()),
            std=self._safe_std(float(baseline_model_scores.std(ddof=0))),
        )
        iforest_anomaly = bool(self.model.predict(feature_frame[feature_columns])[0] == -1)

        amount_zscore = (float(scored_row["amount"]) - baseline_amount_mean) / baseline_amount_std
        daily_frequency_zscore = (current_day_count - daily_count_mean) / daily_count_std
        monthly_frequency_zscore = (current_month_count - monthly_count_mean) / monthly_count_std

        active_hours = set(int(hour) for hour in profile.get("active_hours", []))
        known_devices = set(str(device) for device in profile.get("device_list", []))
        known_locations = set(str(country) for country in profile.get("location_profile", []))
        event_hour = int(pd.Timestamp(scored_row["event_ts"]).hour)
        hour_distance = self._minimum_cyclical_hour_distance(event_hour, active_hours)

        amount_component = min(max(amount_zscore, 0.0) / 3.0, 1.0)
        daily_frequency_component = min(max(daily_frequency_zscore, 0.0) / 3.0, 1.0)
        monthly_frequency_component = min(max(monthly_frequency_zscore, 0.0) / 3.0, 1.0)
        unusual_time_component = 1.0 if hour_distance is not None and hour_distance > self.ACTIVE_HOUR_TOLERANCE else 0.0

        statistical_score = round(
            (
                0.20 * amount_component
                + 0.20 * daily_frequency_component
                + 0.40 * monthly_frequency_component
                + 0.20 * unusual_time_component
            ),
            4,
        )

        feature_deviation_score = round(
            (
                0.15 * (1.0 if str(scored_row["ip"]) not in set(baseline["ip"].astype(str)) else 0.0)
                + 0.35 * (1.0 if str(scored_row["device_fingerprint"]) not in known_devices else 0.0)
                + 0.30 * (1.0 if str(scored_row["country"]) not in known_locations else 0.0)
                + 0.20 * (1.0 if str(scored_row["mcc"]) not in set(baseline["mcc"].astype(str)) else 0.0)
            ),
            4,
        )

        behaviour_score = round(
            (
                self.MODEL_WEIGHT * model_score
                + self.STATISTICAL_WEIGHT * statistical_score
                + self.FEATURE_DEVIATION_WEIGHT * feature_deviation_score
            ),
            4,
        )

        reasons: list[str] = []
        if amount_component >= 0.8:
            reasons.append("AMOUNT_SPIKE")
        if daily_frequency_component >= 0.8 or monthly_frequency_component >= 0.8:
            reasons.append("FREQUENCY_SPIKE")
        if unusual_time_component > 0:
            reasons.append("UNUSUAL_TIME")
        if str(scored_row["device_fingerprint"]) not in known_devices:
            reasons.append("NEW_DEVICE")
        if str(scored_row["ip"]) not in set(baseline["ip"].astype(str)):
            reasons.append("NEW_IP")
        if str(scored_row["country"]) not in known_locations:
            reasons.append("NEW_LOCATION")
        if str(scored_row["mcc"]) not in set(baseline["mcc"].astype(str)):
            reasons.append("NEW_MCC")
        if iforest_anomaly:
            reasons.append("IFOREST_ANOMALY")
        if impossible_travel_context and impossible_travel_context.get("impossible_travel"):
            reasons.append("IMPOSSIBLE_TRAVEL")

        major_reasons = {"AMOUNT_SPIKE", "FREQUENCY_SPIKE", "UNUSUAL_TIME"}
        behaviour_change = bool(
            behaviour_score >= self.BEHAVIOUR_CHANGE_THRESHOLD or any(reason in major_reasons for reason in reasons)
        )
        if impossible_travel_context and impossible_travel_context.get("impossible_travel"):
            behaviour_change = True

        return {
            "model_score": round(model_score, 4),
            "statistical_score": round(statistical_score, 4),
            "feature_deviation_score": round(feature_deviation_score, 4),
            "behaviour_score": behaviour_score,
            "behaviour_change": behaviour_change,
            "behaviour_reasons": reasons,
            "iforest_anomaly": iforest_anomaly,
            "amount_zscore": round(float(amount_zscore), 4),
            "daily_frequency_zscore": round(float(daily_frequency_zscore), 4),
            "monthly_frequency_zscore": round(float(monthly_frequency_zscore), 4),
            "active_hour_distance": hour_distance,
            "impossible_travel": bool(impossible_travel_context.get("impossible_travel", False))
            if impossible_travel_context
            else False,
            "distance_km": impossible_travel_context.get("distance_km") if impossible_travel_context else None,
            "travel_speed_kmh": impossible_travel_context.get("travel_speed_kmh") if impossible_travel_context else None,
            "travel_time_hours": impossible_travel_context.get("time_diff_hours") if impossible_travel_context else None,
        }

    def _build_monthly_summary(
        self,
        baseline: pd.DataFrame,
        anomalous: pd.DataFrame,
        scored_transactions: pd.DataFrame,
    ) -> pd.DataFrame:
        baseline_monthly_counts = baseline.groupby(baseline["event_ts"].dt.to_period("M")).size()
        anomalous_month = str(anomalous["event_ts"].dt.to_period("M").iloc[0])
        reasons = sorted({reason for reasons in scored_transactions["behaviour_reasons"] for reason in reasons})

        return pd.DataFrame(
            [
                {
                    "account_id": str(anomalous["account_id"].iloc[0]),
                    "anomalous_month": anomalous_month,
                    "baseline_avg_monthly_txn_count": float(baseline_monthly_counts.mean()),
                    "anomalous_month_txn_count": int(len(anomalous)),
                    "avg_behaviour_score": float(scored_transactions["behaviour_score"].mean()),
                    "flagged_transactions": int(scored_transactions["behaviour_change"].sum()),
                    "reasons": reasons,
                }
            ]
        )

    def _build_baseline_feature_matrix(self, baseline: pd.DataFrame) -> pd.DataFrame:
        return self._build_feature_matrix_from_context(context_frame=baseline, target_frame=baseline, baseline_reference=baseline)

    def _build_batch_target_feature_matrix(self, baseline: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
        return self._build_feature_matrix_from_context(
            context_frame=target,
            target_frame=target,
            baseline_reference=baseline,
        )

    def _build_single_target_feature_matrix(
        self,
        baseline_reference: pd.DataFrame,
        historical_transactions: pd.DataFrame,
        target_transaction: pd.DataFrame,
    ) -> pd.DataFrame:
        context_frame = pd.concat([historical_transactions, target_transaction], ignore_index=True)
        return self._build_feature_matrix_from_context(
            context_frame=context_frame,
            target_frame=target_transaction,
            baseline_reference=baseline_reference,
        )

    def _build_cold_start_scoring(
        self,
        impossible_travel_context: dict[str, Any] | None,
        cold_start_status: dict[str, Any],
    ) -> dict[str, Any]:
        behaviour_change = bool(impossible_travel_context and impossible_travel_context.get("impossible_travel"))
        reasons = ["IMPOSSIBLE_TRAVEL"] if behaviour_change else []

        return {
            "model_score": 0.0,
            "statistical_score": 0.0,
            "feature_deviation_score": 0.0,
            "behaviour_score": 0.0,
            "behaviour_change": behaviour_change,
            "behaviour_reasons": reasons,
            "iforest_anomaly": False,
            "amount_zscore": 0.0,
            "daily_frequency_zscore": 0.0,
            "monthly_frequency_zscore": 0.0,
            "impossible_travel": behaviour_change,
            "distance_km": impossible_travel_context.get("distance_km") if impossible_travel_context else None,
            "travel_speed_kmh": impossible_travel_context.get("travel_speed_kmh") if impossible_travel_context else None,
            "travel_time_hours": impossible_travel_context.get("time_diff_hours") if impossible_travel_context else None,
            "cold_start": True,
            "cold_start_history_days": int(cold_start_status.get("history_days", 0)),
            "cold_start_transaction_count": int(cold_start_status.get("transaction_count", 0)),
        }

    def _build_feature_matrix_from_context(
        self,
        context_frame: pd.DataFrame,
        target_frame: pd.DataFrame,
        baseline_reference: pd.DataFrame,
    ) -> pd.DataFrame:
        context_frame = context_frame.sort_values("event_ts").copy()
        target_frame = target_frame.sort_values("event_ts").copy()

        known_devices = set(baseline_reference["device_fingerprint"].astype(str))
        known_ips = set(baseline_reference["ip"].astype(str))
        known_countries = set(baseline_reference["country"].astype(str))
        known_mccs = set(baseline_reference["mcc"].astype(str))
        hourly_distribution = baseline_reference["event_ts"].dt.hour.value_counts(normalize=True).sort_index()

        context_frame["event_date"] = context_frame["event_ts"].dt.date
        context_frame["event_week"] = context_frame["event_ts"].dt.to_period("W")
        context_frame["context_daily_txn_count"] = context_frame.groupby("event_date")["event_id"].transform("count")
        context_frame["context_weekly_txn_count"] = context_frame.groupby("event_week")["event_id"].transform("count")
        context_frame["context_txn_gap_hours"] = (
            context_frame["event_ts"].diff().dt.total_seconds().div(3600).fillna(24.0).clip(lower=0.0)
        )

        target_ids = set(target_frame["event_id"].astype(str))
        scoped = context_frame.loc[context_frame["event_id"].astype(str).isin(target_ids)].copy()
        scoped["event_hour"] = scoped["event_ts"].dt.hour
        scoped["day_of_week"] = scoped["event_ts"].dt.dayofweek
        scoped["is_weekend"] = (scoped["day_of_week"] >= 5).astype(int)
        scoped["is_morning"] = scoped["event_hour"].between(6, 11).astype(int)
        scoped["known_device"] = scoped["device_fingerprint"].astype(str).isin(known_devices).astype(int)
        scoped["known_ip"] = scoped["ip"].astype(str).isin(known_ips).astype(int)
        scoped["known_country"] = scoped["country"].astype(str).isin(known_countries).astype(int)
        scoped["known_mcc"] = scoped["mcc"].astype(str).isin(known_mccs).astype(int)
        scoped["hour_probability"] = scoped["event_hour"].map(hourly_distribution).fillna(0.0)

        feature_frame = scoped[
            [
                "event_id",
                "amount",
                "event_hour",
                "day_of_week",
                "is_weekend",
                "is_morning",
                "known_device",
                "known_ip",
                "known_country",
                "known_mcc",
                "hour_probability",
                "context_daily_txn_count",
                "context_weekly_txn_count",
                "context_txn_gap_hours",
            ]
        ].copy()

        return feature_frame.rename(
            columns={
                "amount": "feature_amount",
                "event_hour": "feature_event_hour",
                "day_of_week": "feature_day_of_week",
                "is_weekend": "feature_is_weekend",
                "is_morning": "feature_is_morning",
                "known_device": "feature_known_device",
                "known_ip": "feature_known_ip",
                "known_country": "feature_known_country",
                "known_mcc": "feature_known_mcc",
                "hour_probability": "feature_hour_probability",
                "context_daily_txn_count": "feature_daily_txn_count",
                "context_weekly_txn_count": "feature_weekly_txn_count",
                "context_txn_gap_hours": "feature_txn_gap_hours",
            }
        )

    def _load_behavioural_profile(self, account_id: str) -> dict[str, Any]:
        connection = get_postgres_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        account_id,
                        avg_amount,
                        std_amount,
                        txn_frequency,
                        active_hours,
                        device_list,
                        location_profile
                    FROM behavioural_profiles
                    WHERE account_id = %s
                    """,
                    (account_id,),
                )
                row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            raise ValueError(f"No behavioural profile found for account_id={account_id}.")

        return {
            "account_id": row[0],
            "avg_amount": row[1],
            "std_amount": row[2],
            "txn_frequency": row[3],
            "active_hours": row[4] or [],
            "device_list": row[5] or [],
            "location_profile": row[6] or [],
        }

    def _lookup_action_mapping(self, behaviour_change: bool) -> str:
        connection = get_postgres_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT action_mapping
                    FROM behavioural_config
                    WHERE behaviour_change_flag = %s
                    LIMIT 1
                    """,
                    (behaviour_change,),
                )
                row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            return "ALERT" if behaviour_change else "ALLOW"
        return str(row[0])

    def _persist_scored_transaction(
        self,
        transaction_payload: dict[str, Any],
        scoring: dict[str, Any],
        action_mapping: str,
    ) -> None:
        engine = get_sqlalchemy_engine()
        raw_transaction_params = {
            "event_id": transaction_payload["event_id"],
            "event_ts": pd.Timestamp(transaction_payload["event_ts"]).to_pydatetime(),
            "account_id": transaction_payload["account_id"],
            "instrument_id": transaction_payload["instrument_id"],
            "amount": float(transaction_payload["amount"]),
            "currency": transaction_payload["currency"],
            "country": transaction_payload["country"],
            "mcc": transaction_payload["mcc"],
            "merchant_id": transaction_payload["merchant_id"],
            "entry_mode": transaction_payload["entry_mode"],
            "ip": transaction_payload["ip"],
            "device_fingerprint": transaction_payload["device_fingerprint"],
            "terminal_id": transaction_payload["terminal_id"],
            "txn_type": transaction_payload["txn_type"],
            "geo_coordinates": self.feature_engineer._normalize_geo_coordinates(transaction_payload.get("geo_coordinates")),
        }
        scoring_params = {
            "event_id": transaction_payload["event_id"],
            "behaviour_score": float(scoring["behaviour_score"]),
            "behaviour_change": bool(scoring["behaviour_change"]),
            "behaviour_reasons": list(scoring["behaviour_reasons"]),
        }
        _ = action_mapping

        insert_raw_transaction = text(
            """
            INSERT INTO raw_transactions (
                event_id,
                event_ts,
                account_id,
                instrument_id,
                amount,
                currency,
                country,
                mcc,
                merchant_id,
                entry_mode,
                ip,
                device_fingerprint,
                terminal_id,
                txn_type,
                geo_coordinates
            ) VALUES (
                :event_id,
                :event_ts,
                :account_id,
                :instrument_id,
                :amount,
                :currency,
                :country,
                :mcc,
                :merchant_id,
                :entry_mode,
                :ip,
                :device_fingerprint,
                :terminal_id,
                :txn_type,
                :geo_coordinates
            )
            ON CONFLICT (event_id) DO UPDATE SET
                event_ts = EXCLUDED.event_ts,
                account_id = EXCLUDED.account_id,
                instrument_id = EXCLUDED.instrument_id,
                amount = EXCLUDED.amount,
                currency = EXCLUDED.currency,
                country = EXCLUDED.country,
                mcc = EXCLUDED.mcc,
                merchant_id = EXCLUDED.merchant_id,
                entry_mode = EXCLUDED.entry_mode,
                ip = EXCLUDED.ip,
                device_fingerprint = EXCLUDED.device_fingerprint,
                terminal_id = EXCLUDED.terminal_id,
                txn_type = EXCLUDED.txn_type,
                geo_coordinates = EXCLUDED.geo_coordinates
            """
        )
        upsert_scoring_result = text(
            """
            INSERT INTO scoring_results (
                event_id,
                behaviour_score,
                behaviour_change,
                behaviour_reasons
            ) VALUES (
                :event_id,
                :behaviour_score,
                :behaviour_change,
                :behaviour_reasons
            )
            ON CONFLICT (event_id) DO UPDATE SET
                behaviour_score = EXCLUDED.behaviour_score,
                behaviour_change = EXCLUDED.behaviour_change,
                behaviour_reasons = EXCLUDED.behaviour_reasons
            """
        )

        try:
            with engine.begin() as connection:
                connection.execute(insert_raw_transaction, raw_transaction_params)
                connection.execute(upsert_scoring_result, scoring_params)
        finally:
            engine.dispose()

    def _refresh_behavioural_profile(self, transactions: pd.DataFrame) -> None:
        updated_profile = self.feature_engineer.build_continuous_profile(transactions)
        self.feature_engineer.upsert_behavioural_profile(updated_profile)

    def _should_update_behavioural_profile(self, reasons: list[str]) -> bool:
        return not any(reason in self.HARD_POISONING_REASONS for reason in reasons)

    def _normalize_realtime_payload(self, transaction_payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(transaction_payload)
        normalized["event_id"] = normalized.get("event_id") or str(uuid4())
        normalized["instrument_id"] = self.feature_engineer._normalize_string_field(normalized.get("instrument_id"))
        normalized["currency"] = self.feature_engineer._normalize_string_field(normalized.get("currency"))
        normalized["country"] = self.feature_engineer._normalize_string_field(normalized.get("country"))
        normalized["mcc"] = self.feature_engineer._normalize_string_field(normalized.get("mcc"))
        normalized["merchant_id"] = self.feature_engineer._normalize_string_field(normalized.get("merchant_id"))
        normalized["entry_mode"] = self.feature_engineer._normalize_string_field(normalized.get("entry_mode"))
        normalized["ip"] = self.feature_engineer._normalize_ip_field(normalized.get("ip"))
        normalized["device_fingerprint"] = self.feature_engineer._normalize_string_field(
            normalized.get("device_fingerprint")
        )
        normalized["terminal_id"] = self.feature_engineer._normalize_string_field(normalized.get("terminal_id"))
        normalized["txn_type"] = self.feature_engineer._normalize_string_field(normalized.get("txn_type"))
        normalized["geo_coordinates"] = self.feature_engineer._normalize_geo_coordinates(
            normalized.get("geo_coordinates")
        )
        return normalized

    @staticmethod
    def _minimum_cyclical_hour_distance(event_hour: int, active_hours: set[int]) -> int | None:
        if not active_hours:
            return None
        return min(min(abs(event_hour - hour), 24 - abs(event_hour - hour)) for hour in active_hours)

    @staticmethod
    def _current_month_count(transactions: pd.DataFrame, candidate_row: pd.Series) -> int:
        candidate_ts = pd.Timestamp(candidate_row["event_ts"])
        same_month = transactions["event_ts"].dt.to_period("M") == candidate_ts.to_period("M")
        same_account = transactions["account_id"].astype(str) == str(candidate_row["account_id"])
        return int(transactions.loc[same_month & same_account].shape[0])

    @staticmethod
    def _current_day_count(transactions: pd.DataFrame, candidate_row: pd.Series) -> int:
        candidate_date = pd.Timestamp(candidate_row["event_ts"]).date()
        same_day = transactions["event_ts"].dt.date == candidate_date
        same_account = transactions["account_id"].astype(str) == str(candidate_row["account_id"])
        return int(transactions.loc[same_day & same_account].shape[0])

    @staticmethod
    def _feature_columns(frame: pd.DataFrame) -> list[str]:
        return [column for column in frame.columns if column.startswith("feature_")]

    @staticmethod
    def _normalize_score(value: float, mean: float, std: float) -> float:
        return round(min(max((value - mean) / (3.0 * std), 0.0), 1.0), 4)

    @staticmethod
    def _safe_std(value: float) -> float:
        return value if value > 0 else 1.0

    @staticmethod
    def _split_baseline_and_anomalous(transactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        working = transactions.copy()
        working["event_month"] = working["event_ts"].dt.to_period("M")
        last_month = working["event_month"].max()
        baseline = working.loc[working["event_month"] != last_month].drop(columns=["event_month"])
        anomalous = working.loc[working["event_month"] == last_month].drop(columns=["event_month"])
        return baseline, anomalous
