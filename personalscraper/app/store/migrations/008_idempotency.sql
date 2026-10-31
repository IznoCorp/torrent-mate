-- ``idempotency_record``: a write's first answer, kept per (account, key, operation) so a replay
-- with the same ``Idempotency-Key`` reads it back instead of applying the write again. ``status``
-- is NULL while the first request runs; ``claim_id`` names that run, so a run taken over after
-- it went stale never completes its successor's row. Every timestamp is epoch ``time.time()``.
-- No account foreign key: a row lives at most the retention and is swept by ``created_at``.
--
-- ``PRAGMA user_version`` inside the transaction: the table and the version commit together.

BEGIN TRANSACTION;

CREATE TABLE idempotency_record (
    account_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    operation TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    status INTEGER,
    body BLOB,
    content_type TEXT,
    PRIMARY KEY (account_id, idempotency_key, operation)
);

CREATE INDEX idempotency_record_created ON idempotency_record (created_at);

PRAGMA user_version = 8;

COMMIT;
