-- personalscraper/app/store/migrations/001_baseline.sql
-- Baseline of app.db: the push subscriptions (K1 adds the accounts and the foreign key).
PRAGMA user_version = 1;

CREATE TABLE push_subscription (
    id              INTEGER PRIMARY KEY,
    account_id      TEXT    NOT NULL,
    token           TEXT    NOT NULL UNIQUE,
    platform        TEXT    NOT NULL CHECK (platform IN ('android', 'ios', 'desktop', 'unknown')),
    user_agent      TEXT,
    created_at      REAL    NOT NULL,
    refreshed_at    REAL    NOT NULL,
    last_sent_at    REAL,
    last_outcome    TEXT,
    failure_count   INTEGER NOT NULL DEFAULT 0,
    revoked_at      REAL,
    revoked_reason  TEXT CHECK (revoked_reason IN ('token_dead', 'unregistered', 'signed_out', 'stale'))
);
CREATE INDEX push_subscription_account ON push_subscription(account_id) WHERE revoked_at IS NULL;
