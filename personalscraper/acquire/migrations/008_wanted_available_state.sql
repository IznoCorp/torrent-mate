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
--
-- STATEMENT ORDER IS LOAD-BEARING — do not reorder:
--
--   * `executescript` is NOT one transaction. It COMMITs whatever is pending,
--     then runs the script; outside an explicit BEGIN each statement
--     auto-commits on its own. So the destructive part (DROP + RENAME) is
--     wrapped in an EXPLICIT `BEGIN … COMMIT`: a crash mid-rebuild then rolls
--     back whole rather than leaving `wanted` dropped and `wanted_new` orphaned.
--   * `PRAGMA user_version = 8` is the LAST statement INSIDE the transaction.
--     It writes the database header, which IS transactional, so it commits with
--     the rebuild — atomically, and only on success. Both other placements are
--     broken: before the BEGIN it auto-commits on its own, so a crash mid-rebuild
--     leaves a DB claiming schema 8 while carrying schema 7 (the applier skips
--     any script whose version <= user_version, so it never runs again to repair
--     it); after the COMMIT it leaves a window where the rebuild is durable but
--     the version is not, and the re-run then dies on the `schema_version`
--     PRIMARY KEY — a permanent brick. Inside the transaction there is no window
--     at all.
--   * `INSERT OR IGNORE` on `schema_version` (belt-and-braces): the version row
--     is a marker, not a constraint to trip over. A DB that somehow already
--     carries it must still be able to complete the rebuild.
--   * `PRAGMA foreign_keys` is a NO-OP inside a transaction, so both toggles sit
--     OUTSIDE the BEGIN/COMMIT (OFF before, ON after).
--
-- The rebuild is FK-safe because:
--   - wanted references followed_series (outgoing FK), but no other table
--     references wanted (verified: 0 matches for REFERENCES wanted across
--     all *.sql files in acquire/migrations/).
--   - FK enforcement is disabled for the swap and restored at the end.

-- ── Step 0: disable FK enforcement for the rebuild (outside any tx) ──────
PRAGMA foreign_keys = OFF;

-- ── The destructive rebuild, all-or-nothing ─────────────────────────────
BEGIN TRANSACTION;

-- Step 1: create the replacement table with the full new schema.
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

-- Step 2: copy every row, new columns default to NULL.
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

-- Step 3: swap the tables.
DROP TABLE wanted;
ALTER TABLE wanted_new RENAME TO wanted;

-- Step 4: recreate the partial index EXACTLY as in 001_init.sql.
CREATE INDEX IF NOT EXISTS idx_wanted_pending
    ON wanted (status) WHERE status = 'pending';

-- Step 5: record the migration inside the SAME transaction as the rebuild.
-- OR IGNORE: the marker row must never be the thing that blocks a rebuild.
INSERT OR IGNORE INTO schema_version(version) VALUES (8);

-- Step 6: publish the new schema version — still INSIDE the transaction, so the
-- version and the schema it describes become durable in the same commit. There
-- is no instant at which one is true and the other is not.
PRAGMA user_version = 8;

COMMIT;

-- ── Step 7: advisory FK probe ───────────────────────────────────────────
-- Advisory ONLY: executescript discards result rows, so a violation reported
-- here is neither seen nor acted upon. It is kept because it still surfaces in
-- a manual `sqlite3 acquire.db < 008_…sql` replay. The real safety is that
-- nothing references `wanted`, plus the all-or-nothing transaction above.
PRAGMA foreign_key_check;

-- ── Step 8: restore FK enforcement (no-op inside a tx, hence out here) ───
PRAGMA foreign_keys = ON;
