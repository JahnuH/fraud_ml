from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text

from app.db.postgres import get_sqlalchemy_engine


@dataclass
class FeatureEngineeringResult:
    profile_frame: pd.DataFrame
    model_frame: pd.DataFrame
    baseline_transactions: pd.DataFrame


class BehavioralFeatureEngineer:
    def __init__(self, account_id: str | None = None) -> None:
        self.account_id = account_id

    def load_raw_transactions(self) -> pd.DataFrame:
        query = """
            SELECT
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
                txn_type
            FROM raw_transactions
            {where_clause}
            ORDER BY event_ts
        """
        where_clause = ""
        params: dict[str, object] | None = None
        if self.account_id:
            where_clause = "WHERE account_id = :account_id"
            params = {"account_id": self.account_id}

        engine = get_sqlalchemy_engine()
        try:
            frame = pd.read_sql_query(
                text(query.format(where_clause=where_clause)),
                engine,
                params=params,
            )
        finally:
            engine.dispose()

        if frame.empty:
            raise ValueError("No raw_transactions found for feature engineering.")

        frame["event_ts"] = pd.to_datetime(frame["event_ts"], utc=False)
        frame["amount"] = pd.to_numeric(frame["amount"])
        return frame

    def build_features(self, transactions: pd.DataFrame) -> FeatureEngineeringResult:
        baseline = self._baseline_window(transactions)
        if baseline.empty:
            raise ValueError("Baseline transaction window is empty.")

        return self._build_profile_result(baseline)

    def build_continuous_profile(self, transactions: pd.DataFrame) -> pd.DataFrame:
        if transactions.empty:
            raise ValueError("No transactions available for continuous profile update.")

        profile_result = self._build_profile_result(transactions.copy())
        return profile_result.profile_frame

    def upsert_behavioral_profile(self, profile_frame: pd.DataFrame) -> None:
        records = profile_frame.to_dict(orient="records")
        if not records:
            raise ValueError("No profile rows available to persist.")

        engine = get_sqlalchemy_engine()
        upsert_profile = text(
            """
            INSERT INTO behavioral_profiles (
                account_id,
                avg_amount,
                std_amount,
                txn_frequency,
                active_hours,
                device_list,
                location_profile
            ) VALUES (
                :account_id,
                :avg_amount,
                :std_amount,
                :txn_frequency,
                :active_hours,
                :device_list,
                :location_profile
            )
            ON CONFLICT (account_id) DO UPDATE SET
                avg_amount = EXCLUDED.avg_amount,
                std_amount = EXCLUDED.std_amount,
                txn_frequency = EXCLUDED.txn_frequency,
                active_hours = EXCLUDED.active_hours,
                device_list = EXCLUDED.device_list,
                location_profile = EXCLUDED.location_profile
            """
        )
        try:
            with engine.begin() as connection:
                connection.execute(upsert_profile, records)
        finally:
            engine.dispose()

    def _build_profile_result(self, source_transactions: pd.DataFrame) -> FeatureEngineeringResult:
        if source_transactions.empty:
            raise ValueError("Source transaction frame is empty.")

        baseline = source_transactions.copy()
        baseline["event_date"] = baseline["event_ts"].dt.date
        baseline["event_hour"] = baseline["event_ts"].dt.hour
        baseline["event_week"] = baseline["event_ts"].dt.to_period("W").astype(str)

        account_id = str(baseline["account_id"].iloc[0])

        daily_counts = baseline.groupby("event_date").size()
        weekly_counts = baseline.groupby("event_week").size()
        hourly_counts = baseline.groupby("event_hour").size().sort_values(ascending=False)
        device_counts = baseline.groupby("device_fingerprint").size().sort_values(ascending=False)
        ip_counts = baseline.groupby("ip").size().sort_values(ascending=False)
        country_counts = baseline.groupby("country").size().sort_values(ascending=False)
        mcc_counts = baseline.groupby("mcc").size().sort_values(ascending=False)

        active_hours = [int(hour) for hour in hourly_counts.index.tolist()]
        device_list = [str(device) for device in device_counts.index.tolist()]
        location_profile = [str(country) for country in country_counts.index.tolist()]

        profile_frame = pd.DataFrame(
            [
                {
                    "account_id": account_id,
                    "avg_amount": round(float(baseline["amount"].mean()), 2),
                    "std_amount": round(float(baseline["amount"].std(ddof=0)), 2),
                    "txn_frequency": round(float(daily_counts.mean()), 4),
                    "active_hours": active_hours,
                    "device_list": device_list,
                    "location_profile": location_profile,
                }
            ]
        )

        model_frame = pd.DataFrame(
            [
                {
                    "account_id": account_id,
                    "avg_amount": float(baseline["amount"].mean()),
                    "std_amount": float(baseline["amount"].std(ddof=0)),
                    "avg_daily_txn_frequency": float(daily_counts.mean()),
                    "avg_weekly_txn_frequency": float(weekly_counts.mean()),
                    "unique_device_count": int(device_counts.shape[0]),
                    "unique_ip_count": int(ip_counts.shape[0]),
                    "unique_country_count": int(country_counts.shape[0]),
                    "unique_mcc_count": int(mcc_counts.shape[0]),
                    "top_hour": int(hourly_counts.index[0]),
                    "top_hour_ratio": float(hourly_counts.iloc[0] / len(baseline)),
                    "morning_txn_ratio": float((baseline["event_hour"].between(6, 11)).mean()),
                    "top_device_ratio": float(device_counts.iloc[0] / len(baseline)),
                    "top_ip_ratio": float(ip_counts.iloc[0] / len(baseline)),
                    "top_country_ratio": float(country_counts.iloc[0] / len(baseline)),
                    "top_mcc_ratio": float(mcc_counts.iloc[0] / len(baseline)),
                    "amount_min": float(baseline["amount"].min()),
                    "amount_max": float(baseline["amount"].max()),
                    "weekend_txn_ratio": float((baseline["event_ts"].dt.dayofweek >= 5).mean()),
                }
            ]
        )

        return FeatureEngineeringResult(
            profile_frame=profile_frame,
            model_frame=model_frame,
            baseline_transactions=baseline,
        )

    def persist_behavioral_profile(self, profile_frame: pd.DataFrame) -> None:
        records = profile_frame.to_dict(orient="records")
        if not records:
            raise ValueError("No profile rows available to persist.")

        engine = get_sqlalchemy_engine()
        try:
            with engine.begin() as connection:
                connection.execute(text("TRUNCATE TABLE behavioral_profiles"))
        finally:
            engine.dispose()

        self.upsert_behavioral_profile(profile_frame)

    @staticmethod
    def _baseline_window(transactions: pd.DataFrame) -> pd.DataFrame:
        working = transactions.copy()
        working["event_month"] = working["event_ts"].dt.to_period("M")
        last_month = working["event_month"].max()
        return working.loc[working["event_month"] != last_month].drop(columns=["event_month"])
