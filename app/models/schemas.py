from datetime import datetime
from typing import Any, Literal

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


class BehaviourScoringRequest(BaseModel):
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


class BehaviourScoringResponse(BaseModel):
    behaviour_score: float
    behaviour_change: bool
    reasons: list[str]


class BulkSimulationRequest(BaseModel):
    customers: int = Field(5, ge=1, le=50)
    months: int = Field(4, ge=3, le=6)
    seed: int = Field(42, ge=0)
    inject_time_shift: bool = True
    inject_amount_spike: bool = False
    inject_new_ip: bool = False
    output: Literal["csv", "postgres", "both", "memory"] = "postgres"


class ResetRequest(BaseModel):
    confirm: bool = True


class AccountRequest(BaseModel):
    account_id: str


class RulesRetrieveRequest(BaseModel):
    behaviour_change_flag: bool | None = None


class ConfigRuleMapping(BaseModel):
    behaviour_change_flag: bool
    action_mapping: str = Field(..., min_length=1, max_length=16)


class RulesUpdateRequest(BaseModel):
    rules: list[ConfigRuleMapping]


class ApiEnvelope(BaseModel):
    data: Any
