from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from app.core.config import DEFAULT_CSV_PATH, OUTPUT_DIR
from app.db.postgres import get_postgres_connection, initialize_schema
from app.models.schemas import SimulationSummary


SIMULATION_OUTPUT = Literal["csv", "postgres", "both", "memory"]


@dataclass(frozen=True)
class CustomerContext:
    account_id: str
    instrument_id: str
    currency: str
    country: str
    device_fingerprint: str
    home_ip_prefix: str


class TransactionSimulator:
    def __init__(self, months: int = 4, seed: int = 42) -> None:
        if months < 3 or months > 6:
            raise ValueError("months must be between 3 and 6")

        self.months = months
        self.seed = seed
        self._random = random.Random(seed)
        self._rng = np.random.default_rng(seed)
        self.customer = CustomerContext(
            account_id="ACC1000001",
            instrument_id="CARD5000001",
            currency="INR",
            country="IN",
            device_fingerprint="devfp-0a91cd73",
            home_ip_prefix="49.43.12",
        )

        self.morning_hours = (6, 11)
        self.entry_modes = ["CHIP", "CONTACTLESS", "UPI", "ECOM"]
        self.txn_types = ["PURCHASE", "BILLPAY", "GROCERY", "FUEL", "ECOM"]
        self.mcc_pool = ["5411", "5541", "4900", "5812", "5999"]
        self.merchant_prefixes = ["MERGROC", "MERFUEL", "MERUTIL", "MERDIN", "MERECOM"]
        self.terminal_prefixes = ["TERM", "POS", "KIOSK"]

    def generate(self) -> tuple[pd.DataFrame, SimulationSummary]:
        start_month = self._resolve_start_month()
        frames: list[pd.DataFrame] = []

        for month_offset in range(self.months - 1):
            month_start = self._add_months(start_month, month_offset)
            monthly_target = self._random.randint(8, 20)
            frames.append(self._generate_month(month_start, monthly_target, anomalous=False))

        anomalous_month_start = self._add_months(start_month, self.months - 1)
        anomalous_frame = self._generate_month(anomalous_month_start, 50, anomalous=True)
        frames.append(anomalous_frame)

        transactions = pd.concat(frames, ignore_index=True).sort_values("event_ts").reset_index(drop=True)

        baseline_count = sum(len(frame) for frame in frames[:-1])
        summary = SimulationSummary(
            account_id=self.customer.account_id,
            baseline_months=self.months - 1,
            baseline_transaction_count=baseline_count,
            anomalous_month_transaction_count=len(anomalous_frame),
            total_transactions=len(transactions),
            output_mode="memory",
        )
        return transactions, summary

    def persist(
        self,
        transactions: pd.DataFrame,
        summary: SimulationSummary,
        output: SIMULATION_OUTPUT = "csv",
        csv_path: Path | None = None,
    ) -> SimulationSummary:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = csv_path or DEFAULT_CSV_PATH

        if output in {"csv", "both"}:
            transactions.to_csv(csv_path, index=False)

        if output in {"postgres", "both"}:
            self._write_postgres(transactions)

        return summary.model_copy(update={"output_mode": output})

    def _generate_month(self, month_start: date, txn_count: int, anomalous: bool) -> pd.DataFrame:
        records = []
        days_in_month = self._days_in_month(month_start)

        for idx in range(txn_count):
            txn_dt = self._sample_baseline_timestamp(month_start, days_in_month)
            amount = round(float(self._rng.uniform(120, 2999)), 2)
            records.append(self._build_record(txn_dt, amount))

        if anomalous:
            anomaly_index = self._random.randrange(txn_count)
            anomaly_dt = datetime.combine(month_start + timedelta(days=min(1, days_in_month - 1)), datetime.min.time())
            anomaly_dt = anomaly_dt.replace(hour=1, minute=0, second=0)
            anomaly_amount = round(float(self._rng.uniform(350, 2800)), 2)
            records[anomaly_index] = self._build_record(anomaly_dt, anomaly_amount, anomaly=True)

        return pd.DataFrame.from_records(records)

    def _build_record(self, txn_dt: datetime, amount: float, anomaly: bool = False) -> dict[str, object]:
        merchant_idx = self._random.randrange(len(self.mcc_pool))
        entry_mode = self._random.choice(self.entry_modes)
        txn_type = self._random.choice(self.txn_types)
        ip_suffix = self._random.randint(2, 254)
        ip = f"{self.customer.home_ip_prefix}.{ip_suffix}"

        if anomaly:
            merchant_id = "MERANOM999"
            terminal_id = "TERM-ANOM-01"
        else:
            merchant_id = f"{self.merchant_prefixes[merchant_idx]}-{self._random.randint(100, 999)}"
            terminal_id = f"{self._random.choice(self.terminal_prefixes)}-{self._random.randint(1000, 9999)}"

        return {
            "event_id": str(uuid.uuid4()),
            "event_ts": txn_dt.isoformat(),
            "account_id": self.customer.account_id,
            "instrument_id": self.customer.instrument_id,
            "amount": amount,
            "currency": self.customer.currency,
            "country": self.customer.country,
            "mcc": self.mcc_pool[merchant_idx],
            "merchant_id": merchant_id,
            "entry_mode": entry_mode,
            "ip": ip,
            "device_fingerprint": self.customer.device_fingerprint,
            "terminal_id": terminal_id,
            "txn_type": txn_type,
        }

    def _sample_baseline_timestamp(self, month_start: date, days_in_month: int) -> datetime:
        day = int(self._rng.integers(1, days_in_month + 1))
        hour = int(self._rng.integers(self.morning_hours[0], self.morning_hours[1] + 1))
        minute = int(self._rng.integers(0, 60))
        second = int(self._rng.integers(0, 60))
        return datetime(month_start.year, month_start.month, day, hour, minute, second)

    def _resolve_start_month(self) -> date:
        today = date.today().replace(day=1)
        return self._add_months(today, -self.months + 1)

    @staticmethod
    def _days_in_month(month_start: date) -> int:
        next_month = TransactionSimulator._add_months(month_start, 1)
        return (next_month - month_start).days

    @staticmethod
    def _add_months(base: date, offset: int) -> date:
        month_index = (base.month - 1) + offset
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        return date(year, month, 1)

    def _write_postgres(self, transactions: pd.DataFrame) -> None:
        connection = get_postgres_connection()
        try:
            initialize_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE raw_transactions RESTART IDENTITY CASCADE")
                insert_sql = """
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
                        txn_type
                    ) VALUES (
                        %(event_id)s,
                        %(event_ts)s,
                        %(account_id)s,
                        %(instrument_id)s,
                        %(amount)s,
                        %(currency)s,
                        %(country)s,
                        %(mcc)s,
                        %(merchant_id)s,
                        %(entry_mode)s,
                        %(ip)s,
                        %(device_fingerprint)s,
                        %(terminal_id)s,
                        %(txn_type)s
                    )
                """
                cursor.executemany(insert_sql, transactions.to_dict(orient="records"))
            connection.commit()
        finally:
            connection.close()
