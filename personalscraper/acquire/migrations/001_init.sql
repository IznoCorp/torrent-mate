-- personalscraper/acquire/migrations/001_init.sql
-- Initial schema for acquire.db (RP3).
-- Conventions: INTEGER PRIMARY KEY (rowid alias), unix-epoch INTEGER timestamps,
-- CHECK IN enums, FKs with ON DELETE, partial indexes WHERE status='...',
-- JSON-as-TEXT *_json columns.
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS followed_series (
    id                   INTEGER PRIMARY KEY,
    media_ref_json       TEXT    NOT NULL,
    title                TEXT    NOT NULL,
    active               INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    quality_profile_json TEXT,
    cadence_json         TEXT,
    added_at             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wanted (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'grabbed', 'done', 'abandoned')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    -- Idempotence guard (RP5b): mark_grabbed persists the torrent info-hash
    -- here so a crash between add() and the status write never double-emits
    -- GrabSucceeded on re-run. NULL until the item is grabbed.
    grabbed_hash    TEXT
);

CREATE INDEX IF NOT EXISTS idx_wanted_pending
    ON wanted (status) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS seed_obligation (
    id               INTEGER PRIMARY KEY,
    info_hash        TEXT    NOT NULL,
    source_tracker   TEXT    NOT NULL,
    dispatched_path  TEXT,
    min_seed_time_s  INTEGER NOT NULL,
    min_ratio        REAL    NOT NULL,
    added_at         INTEGER NOT NULL,
    satisfied_at     INTEGER,
    breached_at      INTEGER,
    released_at      INTEGER,
    -- Defense-in-depth for the HnR guard (T1): a negative floor would make the
    -- seedtime/ratio check trivially true in DeleteAuthority.may_delete.
    CHECK (min_seed_time_s >= 0 AND min_ratio >= 0)
);

CREATE INDEX IF NOT EXISTS idx_seed_dispatched_path
    ON seed_obligation (dispatched_path)
    WHERE dispatched_path IS NOT NULL;

CREATE TABLE IF NOT EXISTS ratio_state (
    tracker_name            TEXT    PRIMARY KEY,
    observed_ratio          REAL    NOT NULL DEFAULT 0.0,
    accumulated_seed_time_s INTEGER NOT NULL DEFAULT 0,
    hnr_count               INTEGER NOT NULL DEFAULT 0,
    updated_at              INTEGER NOT NULL
);

-- Schema-version singleton (PRAGMA user_version is also set in lockstep).
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version(version) VALUES (1);

PRAGMA user_version = 1;
