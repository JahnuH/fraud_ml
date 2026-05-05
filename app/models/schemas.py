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


class SimulationSummary(BaseModel):
    account_id: str
    baseline_months: int
    baseline_transaction_count: int
    anomalous_month_transaction_count: int
    total_transactions: int
    output_mode: Literal["csv", "postgres", "both", "memory"]


class BehaviorScoringRequest(BaseModel):
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


class BehaviorScoringResponse(BaseModel):
    behavior_score: float
    behavior_change: bool
    reasons: list[str]
