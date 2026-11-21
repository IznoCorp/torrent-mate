-- The ``run_request`` kind widened: ``CHECK (kind IN ('pipeline', 'rescrape', 'acquisition'))``,
-- where ``007_supervisor.sql`` allowed the first two only. SQLite cannot alter a ``CHECK``, so the
-- table is rebuilt: the new one is created, every row copied column for column, the old one dropped
-- (its ``run_request_state_asked`` index goes with it), the new one renamed and the index created
-- again. Every other column and constraint is as ``007`` left them; no other table is touched
-- (nothing references ``run_request``).
--
-- ``PRAGMA user_version`` inside the transaction: the rebuild and the version commit together.

BEGIN TRANSACTION;

CREATE TABLE run_request_new (
    uid TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('pipeline', 'rescrape', 'acquisition')),
    trigger TEXT NOT NULL,
    options_json TEXT NOT NULL,
    asked_by TEXT NOT NULL,
    asked_at REAL NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'settled')),
    admitted_at REAL,
    worker_pid INTEGER,
    heartbeat_at REAL,
    settled_at REAL,
    settlement TEXT CHECK (settlement IN ('success', 'error', 'killed', 'interrupted', 'abandoned')),
    wait_reason TEXT
);

INSERT INTO run_request_new (
    uid, kind, trigger, options_json, asked_by, asked_at, state, admitted_at, worker_pid,
    heartbeat_at, settled_at, settlement, wait_reason
)
SELECT
    uid, kind, trigger, options_json, asked_by, asked_at, state, admitted_at, worker_pid,
    heartbeat_at, settled_at, settlement, wait_reason
FROM run_request;

DROP TABLE run_request;

ALTER TABLE run_request_new RENAME TO run_request;

CREATE INDEX run_request_state_asked ON run_request (state, asked_at);

PRAGMA user_version = 11;

COMMIT;
