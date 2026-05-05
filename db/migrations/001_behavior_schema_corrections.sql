BEGIN;

DROP TABLE IF EXISTS scoring_results;
DROP TABLE IF EXISTS behavioral_profiles;
DROP TABLE IF EXISTS behavioral_config;

CREATE TABLE behavioral_profiles (
    account_id VARCHAR(64) PRIMARY KEY,
    avg_amount NUMERIC(12, 2) NOT NULL,
    std_amount NUMERIC(12, 2) NOT NULL,
    txn_frequency NUMERIC(12, 4) NOT NULL,
    active_hours INTEGER[] NOT NULL,
    device_list TEXT[] NOT NULL,
    location_profile TEXT[] NOT NULL
);

CREATE TABLE behavioral_config (
    behavior_change_flag BOOLEAN NOT NULL,
    action_mapping VARCHAR(16) NOT NULL
);

CREATE TABLE scoring_results (
    event_id UUID PRIMARY KEY REFERENCES raw_transactions(event_id) ON DELETE CASCADE,
    behavior_score DOUBLE PRECISION,
    behavior_change BOOLEAN,
    behavior_reasons TEXT[]
);

COMMIT;
