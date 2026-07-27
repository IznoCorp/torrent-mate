-- personalscraper/acquire/migrations/008_wanted_available_state.sql
-- Persist the verdict of the last tracker search on every wanted row and add
-- the 'available' status — the observable gap between « search found a takeable
-- candidate » and « torrent added to qBittorrent ».
--
-- Three changes, one table rebuild:
--
-- 1. New status 'available' — search and grab used to be one atomic operation,
--    so the « À récupérer » state existed for milliseconds inside a single
--    function call. The UI could never show it. Adding it to the CHECK constraint
--    makes the gap between search and grab visible and actionable.
--
-- 2. last_search_outcome TEXT — the named issue of the last search pass
--    (no_candidates / all_filtered / trackers_unavailable / circuit_open / …).
--    Today the engine computes this at every exit path and discards it. The UI
--    cannot distinguish « searched, nothing takeable » from « never searched »,
--    the exact ambiguity that let a freshly-followed series read « À jour » with
--    3 aired episodes missing from the library (Furious incident, DESIGN.md §1).
--
-- 3. last_search_found INTEGER — number of TAKEABLE candidates (survivors of
--    filter_to_episode + apply_hard_filters + min_seeders floor). NULL = the
--    search did NOT conclude (outage, open circuit, dead swarm) — zero would
--    mean « I looked, there is nothing », which is false.
--
-- NULL on both verdict columns = never searched — the honest default for
-- pre-existing rows (we genuinely do not know their verdict history).
--
-- SQLite cannot ALTER a CHECK constraint, hence the full table rebuild.
-- The rebuild is FK-safe because:
--   - wanted references followed_series (outgoing FK), but no other table
--     references wanted (verified: 0 matches for REFERENCES wanted across
--     all *.sql files in acquire/migrations/).
--   - The apply_migrations runner (core/sqlite/_migrate.py) wraps each script
--     in a single conn.executescript() call = one implicit transaction.
--   - PRAGMA foreign_keys=OFF is set defensively at the start and restored
--     after a PRAGMA foreign_key_check confirms zero violations.
PRAGMA user_version = 8;

-- ── Step 0: disable FK enforcement for the rebuild ──────────────────────
PRAGMA foreign_keys = OFF;

-- ── Step 1: create the replacement table with the full new schema ────────
CREATE TABLE wanted_new (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'available',
                                      'grabbed', 'done', 'abandoned')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    grabbed_hash    TEXT,
    last_search_outcome TEXT,   -- NEW — named issue, NULL = never searched
    last_search_found   INTEGER -- NEW — takeable count, NULL = inconclusive
);

-- ── Step 2: copy every row, new columns default to NULL ──────────────────
INSERT INTO wanted_new (
    id, followed_id, media_ref_json, kind, season, episode,
    status, criteria_json, enqueued_at, last_search_at, attempts,
    grabbed_hash
)
SELECT
    id, followed_id, media_ref_json, kind, season, episode,
    status, criteria_json, enqueued_at, last_search_at, attempts,
    grabbed_hash
FROM wanted;

-- ── Step 3: swap the tables ──────────────────────────────────────────────
DROP TABLE wanted;
ALTER TABLE wanted_new RENAME TO wanted;

-- ── Step 4: recreate the partial index EXACTLY as in 001_init.sql ────────
CREATE INDEX IF NOT EXISTS idx_wanted_pending
    ON wanted (status) WHERE status = 'pending';

-- ── Step 5: verify FK integrity before re-enabling enforcement ───────────
-- foreign_key_check returns one row per violation; empty = clean.
PRAGMA foreign_key_check;

-- ── Step 6: restore FK enforcement ───────────────────────────────────────
PRAGMA foreign_keys = ON;

-- ── Step 7: record the migration ─────────────────────────────────────────
INSERT INTO schema_version(version) VALUES (8);
