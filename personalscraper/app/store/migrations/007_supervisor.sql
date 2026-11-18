-- The supervisor's two tables: ``run_request`` (the queue of asked runs, FIFO by ``asked_at``) and
-- ``run_lease`` (the authority that starts a run: at most one row, the supervisor's). Every
-- timestamp is epoch ``time.time()``. Additive: two new tables and an index, no row of an existing
-- table is touched.
--
-- ``PRAGMA user_version`` inside the transaction: the tables and the version commit together.

BEGIN TRANSACTION;

CREATE TABLE run_request (
    uid TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('pipeline', 'rescrape')),
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

CREATE INDEX run_request_state_asked ON run_request (state, asked_at);

CREATE TABLE run_lease (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    holder_pid INTEGER NOT NULL,
    holder_host TEXT NOT NULL,
    taken_at REAL NOT NULL,
    renewed_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

PRAGMA user_version = 7;

COMMIT;
