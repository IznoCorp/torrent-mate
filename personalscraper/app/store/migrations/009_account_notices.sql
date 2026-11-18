-- An account's notices and its push switches: ``account_notice`` (what the account is told in the
-- application — a new sign-in, first) and ``notification_preference`` (one switch per push type the
-- account turned off or back on; a type with no row is ON). Both belong to the account and go with
-- it (``ON DELETE CASCADE``). A notice holds a code and its parameters, never a sentence: the
-- interface words it in the account's language. Every timestamp is epoch ``time.time()``.
-- Additive: two new tables and an index, no row of an existing table is touched.
--
-- ``PRAGMA user_version`` inside the transaction: the tables and the version commit together.

BEGIN TRANSACTION;

CREATE TABLE account_notice (
    id          INTEGER PRIMARY KEY,
    account_id  TEXT    NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    code        TEXT    NOT NULL,
    params_json TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);

CREATE INDEX account_notice_account ON account_notice (account_id, created_at);

CREATE TABLE notification_preference (
    account_id  TEXT    NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    type        TEXT    NOT NULL,
    enabled     INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    updated_at  REAL    NOT NULL,
    PRIMARY KEY (account_id, type)
);

PRAGMA user_version = 9;

COMMIT;
