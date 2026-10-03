-- ``push_subscription.account_id`` becomes a foreign key to ``account``: deleting an account
-- deletes its subscriptions.
--
-- SQLite adds no foreign key in place → full table rebuild, every column and CHECK of
-- 001_baseline.sql kept. ``foreign_keys`` stays ON (every connection sets it): a surviving row
-- whose account_id names no account fails the copy, the migration fails loud and the runner
-- restores its snapshot — a row is never silently dropped. No table references
-- ``push_subscription``, so the drop and the rename touch nothing else.
--
-- ``PRAGMA user_version`` inside the transaction: the rebuild and the version commit together.

BEGIN TRANSACTION;

CREATE TABLE push_subscription_new (
    id              INTEGER PRIMARY KEY,
    account_id      TEXT    NOT NULL REFERENCES account(id) ON DELETE CASCADE,
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

INSERT INTO push_subscription_new (
    id, account_id, token, platform, user_agent, created_at, refreshed_at,
    last_sent_at, last_outcome, failure_count, revoked_at, revoked_reason
)
SELECT
    id, account_id, token, platform, user_agent, created_at, refreshed_at,
    last_sent_at, last_outcome, failure_count, revoked_at, revoked_reason
FROM push_subscription;

DROP TABLE push_subscription;

ALTER TABLE push_subscription_new RENAME TO push_subscription;

CREATE INDEX push_subscription_account ON push_subscription(account_id) WHERE revoked_at IS NULL;

PRAGMA user_version = 3;

COMMIT;
