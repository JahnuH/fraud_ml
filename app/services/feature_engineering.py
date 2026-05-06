from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.db.postgres import get_sqlalchemy_engine


@dataclass
class FeatureEngineeringResult:
    profile_frame: pd.DataFrame
    model_frame: pd.DataFrame
    baseline_transactions: pd.DataFrame


class BehavioralFeatureEngineer:
    COLD_START_MIN_HISTORY_DAYS = 60
    COLD_START_MIN_TRANSACTIONS = 12

    def __init__(self, account_id: str | None = None) -> None:
        self.account_id = account_id

    def load_raw_transactions(self) -> pd.DataFrame:
        frame = self._load_transactions_frame(account_id=self.account_id, normal_only=False, allow_empty=False)
        if frame.empty:
            raise ValueError("No raw_transactions found for feature engineering.")
        return frame

    def load_account_transactions(self, account_id: str, normal_only: bool = False) -> pd.DataFrame:
        return self._load_transactions_frame(account_id=account_id, normal_only=normal_only, allow_empty=True)

    def assess_cold_start(
        self,
        historical_transactions: pd.DataFrame,
        candidate_timestamp: pd.Timestamp | None = None,
    ) -> dict[str, Any]:
        if historical_transactions.empty:
            return {
                "is_cold_start": True,
                "history_days": 0,
                "transaction_count": 0,
                "meets_time_threshold": False,
                "meets_volume_threshold": False,
            }

        working = historical_transactions.sort_values("event_ts").copy()
        oldest_ts = pd.Timestamp(working["event_ts"].min())
        latest_reference = pd.Timestamp(candidate_timestamp) if candidate_timestamp is not None else pd.Timestamp(working["event_ts"].max())
        history_days = max((latest_reference - oldest_ts).days, 0)
        transaction_count = int(len(working))
        meets_time_threshold = history_days > self.COLD_START_MIN_HISTORY_DAYS
        meets_volume_threshold = transaction_count >= self.COLD_START_MIN_TRANSACTIONS

        return {
            "is_cold_start": not (meets_time_threshold and meets_volume_threshold),
            "history_days": history_days,
            "transaction_count": transaction_count,
            "meets_time_threshold": meets_time_threshold,
            "meets_volume_threshold": meets_volume_threshold,
        }

    def get_latest_transaction_for_account(self, account_id: str, normal_only: bool = False) -> dict[str, Any] | None:
        frame = self._load_transactions_frame(account_id=account_id, normal_only=normal_only, allow_empty=True)
        if frame.empty:
            return None

        row = frame.sort_values("event_ts", ascending=False).iloc[0]
        return {
            "event_id": str(row["event_id"]),
            "event_ts": pd.Timestamp(row["event_ts"]),
            "account_id": str(row["account_id"]),
            "country": str(row["country"]),
            "geo_coordinates": self._normalize_geo_coordinates(row.get("geo_coordinates")),
        }

    def _load_transactions_frame(
        self,
        account_id: str | None,
        normal_only: bool,
        allow_empty: bool,
    ) -> pd.DataFrame:
        query = """
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
                rt.ip,
                rt.device_fingerprint,
                rt.terminal_id,
                rt.txn_type,
                rt.geo_coordinates
            FROM raw_transactions rt
            LEFT JOIN scoring_results sr ON rt.event_id = sr.event_id
            {where_clause}
            ORDER BY rt.event_ts
        """
        filters: list[str] = []
        params: dict[str, object] = {}
        if account_id:
            filters.append("rt.account_id = :account_id")
            params["account_id"] = account_id
        if normal_only:
            filters.append("COALESCE(sr.behavior_change, FALSE) = FALSE")

        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        engine = get_sqlalchemy_engine()
        try:
            frame = pd.read_sql_query(
                text(query.format(where_clause=where_clause)),
                engine,
                params=params or None,
            )
        finally:
            engine.dispose()

        if frame.empty:
            if allow_empty:
                return frame
            raise ValueError("No raw_transactions found for feature engineering.")

        frame["event_ts"] = pd.to_datetime(frame["event_ts"], utc=False)
        frame["amount"] = pd.to_numeric(frame["amount"])
        if "geo_coordinates" in frame.columns:
            frame["geo_coordinates"] = frame["geo_coordinates"].apply(self._normalize_geo_coordinates)
        return frame

    def compute_impossible_travel(
        self,
        current_transaction: dict[str, Any],
        previous_transaction: dict[str, Any] | None,
        max_speed_kmh: float = 900.0,
    ) -> dict[str, Any]:
        result = {
            "impossible_travel": False,
            "distance_km": None,
            "travel_speed_kmh": None,
            "time_diff_hours": None,
        }
        if previous_transaction is None:
            return result

        current_country = str(current_transaction.get("country", ""))
        previous_country = str(previous_transaction.get("country", ""))
        if current_country == previous_country:
            return result

        current_coords = self._normalize_geo_coordinates(current_transaction.get("geo_coordinates"))
        previous_coords = self._normalize_geo_coordinates(previous_transaction.get("geo_coordinates"))
        if current_coords is None or previous_coords is None:
            return result

        current_ts = pd.Timestamp(current_transaction["event_ts"])
        previous_ts = pd.Timestamp(previous_transaction["event_ts"])
        time_diff_hours = (current_ts - previous_ts).total_seconds() / 3600.0
        result["time_diff_hours"] = round(time_diff_hours, 4)
        if time_diff_hours <= 0:
            return result

        distance_km = self._haversine_km(previous_coords, current_coords)
        travel_speed_kmh = distance_km / time_diff_hours
        result["distance_km"] = round(distance_km, 4)
        result["travel_speed_kmh"] = round(travel_speed_kmh, 4)
        result["impossible_travel"] = travel_speed_kmh > max_speed_kmh
        return result

    def build_features(self, transactions: pd.DataFrame) -> FeatureEngineeringResult:
        return self._build_grouped_results(transactions, use_baseline_window=True)

    def build_continuous_profile(self, transactions: pd.DataFrame) -> pd.DataFrame:
        if transactions.empty:
            raise ValueError("No transactions available for continuous profile update.")

        working = transactions.copy()
        if "event_ts" in working.columns:
            working["event_ts"] = pd.to_datetime(working["event_ts"], utc=False, errors="coerce")
        if "amount" in working.columns:
            working["amount"] = pd.to_numeric(working["amount"], errors="coerce")
        working = working.dropna(subset=["event_ts", "amount"])
        if working.empty:
            raise ValueError("No valid transactions available for continuous profile update.")

        profile_result = self._build_grouped_results(working, use_baseline_window=False)
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

    def _build_grouped_results(
        self,
        transactions: pd.DataFrame,
        use_baseline_window: bool,
    ) -> FeatureEngineeringResult:
        if transactions.empty:
            raise ValueError("No transactions available for feature engineering.")

        profile_frames: list[pd.DataFrame] = []
        model_frames: list[pd.DataFrame] = []
        baseline_frames: list[pd.DataFrame] = []

        grouped = transactions.sort_values(["account_id", "event_ts"]).groupby("account_id", sort=True)
        for _, account_transactions in grouped:
            account_frame = account_transactions.copy()
            working_frame = self._baseline_window(account_frame) if use_baseline_window else account_frame
            if working_frame.empty:
                continue

            result = self._build_profile_result(working_frame)
            profile_frames.append(result.profile_frame)
            model_frames.append(result.model_frame)
            baseline_frames.append(result.baseline_transactions)

        if not profile_frames:
            if use_baseline_window:
                raise ValueError("Baseline transaction window is empty.")
            raise ValueError("No valid transactions available for continuous profile update.")

        return FeatureEngineeringResult(
            profile_frame=pd.concat(profile_frames, ignore_index=True),
            model_frame=pd.concat(model_frames, ignore_index=True),
            baseline_transactions=pd.concat(baseline_frames, ignore_index=True),
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

    @staticmethod
    def _normalize_geo_coordinates(value: Any) -> list[float] | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return [float(value[0]), float(value[1])]
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _haversine_km(origin: list[float], destination: list[float]) -> float:
        lat1, lon1 = origin
        lat2, lon2 = destination
        radius_km = 6371.0

        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)

        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return radius_km * c
