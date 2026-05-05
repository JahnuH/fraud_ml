BEGIN;

TRUNCATE TABLE behavioral_config;

INSERT INTO behavioral_config (behavior_change_flag, action_mapping)
VALUES
    (FALSE, 'ALLOW'),
    (TRUE, 'ALERT');

COMMIT;
