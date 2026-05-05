CREATE TABLE IF NOT EXISTS raw_transactions (
    event_id UUID PRIMARY KEY,
    event_ts TIMESTAMP NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    instrument_id VARCHAR(64) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    country VARCHAR(8) NOT NULL,
    mcc VARCHAR(8) NOT NULL,
    merchant_id VARCHAR(64) NOT NULL,
    entry_mode VARCHAR(32) NOT NULL,
    ip INET NOT NULL,
    device_fingerprint VARCHAR(128) NOT NULL,
    terminal_id VARCHAR(64) NOT NULL,
    txn_type VARCHAR(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS behavioral_profiles (
    account_id VARCHAR(64) PRIMARY KEY,
    avg_amount NUMERIC(12, 2) NOT NULL,
    std_amount NUMERIC(12, 2) NOT NULL,
    txn_frequency NUMERIC(12, 4) NOT NULL,
    active_hours INTEGER[] NOT NULL,
    device_list TEXT[] NOT NULL,
    location_profile TEXT[] NOT NULL
);

CREATE TABLE IF NOT EXISTS behavioral_config (
    behavior_change_flag BOOLEAN NOT NULL,
    action_mapping VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_results (
    event_id UUID PRIMARY KEY REFERENCES raw_transactions(event_id) ON DELETE CASCADE,
    behavior_score DOUBLE PRECISION,
    behavior_change BOOLEAN,
    behavior_reasons TEXT[]
);

CREATE INDEX IF NOT EXISTS idx_raw_transactions_account_ts
    ON raw_transactions (account_id, event_ts);
