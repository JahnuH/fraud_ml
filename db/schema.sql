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
    txn_type VARCHAR(32) NOT NULL,
    geo_coordinates DOUBLE PRECISION[]
);

ALTER TABLE raw_transactions
    ADD COLUMN IF NOT EXISTS geo_coordinates DOUBLE PRECISION[];

CREATE TABLE IF NOT EXISTS behavioural_profiles (
    account_id VARCHAR(64) PRIMARY KEY,
    avg_amount NUMERIC(12, 2) NOT NULL,
    std_amount NUMERIC(12, 2) NOT NULL,
    txn_frequency NUMERIC(12, 4) NOT NULL,
    active_hours INTEGER[] NOT NULL,
    device_list TEXT[] NOT NULL,
    location_profile TEXT[] NOT NULL
);

CREATE TABLE IF NOT EXISTS behavioural_config (
    behaviour_change_flag BOOLEAN NOT NULL,
    action_mapping VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_results (
    event_id UUID PRIMARY KEY REFERENCES raw_transactions(event_id) ON DELETE CASCADE,
    behaviour_score DOUBLE PRECISION,
    behaviour_change BOOLEAN,
    behaviour_reasons TEXT[]
);

CREATE INDEX IF NOT EXISTS idx_raw_transactions_account_ts
    ON raw_transactions (account_id, event_ts);
