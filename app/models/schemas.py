from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TransactionRecord(BaseModel):
    event_id: str
    event_ts: datetime
    account_id: str
    instrument_id: str
    amount: float = Field(..., gt=0)
    currency: str
    country: str
    mcc: str
    merchant_id: str
    entry_mode: str
    ip: str
    device_fingerprint: str
    terminal_id: str
    txn_type: str
    geo_coordinates: list[float] | None = Field(default=None, min_length=2, max_length=2)


class SimulationSummary(BaseModel):
    account_id: str
    baseline_months: int
    baseline_transaction_count: int
    anomalous_month_transaction_count: int
    total_transactions: int
    output_mode: Literal["csv", "postgres", "both", "memory"]


class BehaviorScoringRequest(BaseModel):
    event_id: str | None = None
    event_ts: datetime
    account_id: str
    instrument_id: str | None = None
    amount: float = Field(..., gt=0)
    currency: str | None = None
    country: str | None = None
    mcc: str | None = None
    merchant_id: str | None = None
    entry_mode: str | None = None
    ip: str | None = None
    device_fingerprint: str | None = None
    terminal_id: str | None = None
    txn_type: str | None = None
    geo_coordinates: list[float] | None = Field(default=None, min_length=2, max_length=2)


class BehaviorScoringResponse(BaseModel):
    behavior_score: float
    behavior_change: bool
    reasons: list[str]
