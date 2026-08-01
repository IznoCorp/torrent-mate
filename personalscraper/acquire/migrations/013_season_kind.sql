-- personalscraper/acquire/migrations/013_season_kind.sql
-- Widen ``wanted`` CHECK constraints for season-grab (feature season-grab).
--
-- Three additive changes plus one new column, one table rebuild:
--
-- 1. Widen ``kind`` CHECK: ``('movie', 'episode')`` → ``('movie', 'episode', 'season')``.
--    A season wanted row is ``kind='season', season=N, episode=NULL``.
--
-- 2. Widen ``status`` CHECK: add ``'absorbed'`` (episode rows absorbed by a season
--    wanted — R5) and ``'fallback_episodes'`` (season row that degraded to
--    per-episode retry — R6).
--
-- 3. New column ``absorbed_by INTEGER`` — nullable; set on an episode row when
--    it is absorbed by a season wanted. No FK constraint: SQLite cannot rename
--    FK references during a table rebuild (``REFERENCES wanted_new(id)`` would
--    stay pointing at the old name after the rename, breaking all subsequent
--    INSERTs). The store methods enforce referential integrity at the application
--    layer.
--
-- SQLite cannot ALTER a CHECK constraint → full table rebuild (same pattern as
-- 008_wanted_available_state.sql). The rebuild is FK-safe because:
--   - wanted references followed_series (outgoing FK), but no other table
--     references wanted.
--   - FK enforcement is disabled for the swap and restored at the end.
--
-- STATEMENT ORDER IS LOAD-BEARING (mirrors 008). Do not reorder.
-- ``PRAGMA user_version`` inside the transaction so the schema version and the
-- rebuild commit atomically — no window where one is durable and the other is not.

-- ── Step 0: disable FK enforcement for the rebuild (outside any tx) ──────
PRAGMA foreign_keys = OFF;

-- ── The destructive rebuild, all-or-nothing ─────────────────────────────
BEGIN TRANSACTION;

-- Step 1: create the replacement table with the full new schema.
CREATE TABLE wanted_new (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode', 'season')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'available',
                                      'grabbed', 'done', 'abandoned',
                                      'absorbed', 'fallback_episodes')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    grabbed_hash    TEXT,
    last_search_outcome TEXT,
    last_search_found   INTEGER,
    tried_hashes_json TEXT,
    absorbed_by     INTEGER
);

-- Step 2: copy every row; the new column defaults to NULL.
INSERT INTO wanted_new (
    id, followed_id, media_ref_json, kind, season, episode,
    status, criteria_json, enqueued_at, last_search_at, attempts,
    grabbed_hash, last_search_outcome, last_search_found, tried_hashes_json
)
SELECT
    id, followed_id, media_ref_json, kind, season, episode,
    status, criteria_json, enqueued_at, last_search_at, attempts,
    grabbed_hash, last_search_outcome, last_search_found, tried_hashes_json
FROM wanted;

-- Step 3: swap the tables.
DROP TABLE wanted;
ALTER TABLE wanted_new RENAME TO wanted;

-- Step 4: recreate the partial index (same as 001_init.sql + prior rebuilds).
CREATE INDEX IF NOT EXISTS idx_wanted_pending
    ON wanted (status) WHERE status = 'pending';

-- Step 5: record the migration inside the SAME transaction as the rebuild.
INSERT OR IGNORE INTO schema_version(version) VALUES (13);

-- Step 6: publish the new schema version — inside the transaction.
PRAGMA user_version = 13;

COMMIT;

-- ── Step 7: advisory FK probe ───────────────────────────────────────────
PRAGMA foreign_key_check;

-- ── Step 8: restore FK enforcement ──────────────────────────────────────
PRAGMA foreign_keys = ON;
