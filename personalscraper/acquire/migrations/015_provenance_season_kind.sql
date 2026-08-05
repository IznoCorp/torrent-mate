-- personalscraper/acquire/migrations/015_provenance_season_kind.sql
-- Widen ``staging_provenance.kind`` to the FULL domain (feature `spine-truth`, cause A).
--
-- 010 declared ``CHECK (kind IN ('movie', 'episode'))``. season-grab (#378) then introduced a
-- third domain kind — ``WantedKind = movie | episode | season`` — and widened ``wanted``
-- (013) WITHOUT widening this table. Every season grab has since been rejected here at write
-- time, and because the provenance writer is ADVISORY (it logs and swallows), the rejection
-- was invisible: the acquisition simply never appeared on the spine. Seven
-- ``acquire.provenance.write_failed`` lines in the PM2 logs, six ``wanted`` rows carrying a
-- hash with kind='season', zero spine rows.
--
-- SQLite cannot ALTER a CHECK constraint → full table rebuild (same pattern as 013). This
-- rebuild is the SIMPLE case:
--   - ``staging_provenance`` declares NO foreign key (010 made ``followed_id`` a plain
--     INTEGER on purpose, so an operator's manual delete can never brick the store), and
--   - no other table references it,
-- so no ``PRAGMA foreign_keys`` toggling is needed — nothing can dangle either way.
--
-- The replacement table carries EVERY column added since 010 (011's resolution projection,
-- 012's per-stage run linkage) in their original order, so ``SELECT *`` keeps yielding the
-- same shape to ``_row_to_provenance``. Both indexes are recreated, including 011's PARTIAL
-- index (a plain recreate would change the query plan of the awaiting-resolution lookup).
--
-- STATEMENT ORDER IS LOAD-BEARING (mirrors 013). ``PRAGMA user_version`` sits INSIDE the
-- transaction so the rebuild and the version bump commit atomically — no window where one
-- is durable and the other is not.

BEGIN TRANSACTION;

-- Step 1: the replacement table — identical to 010+011+012, with the widened CHECK.
CREATE TABLE staging_provenance_new (
    info_hash        TEXT PRIMARY KEY,
    followed_id      INTEGER,
    media_ref_json   TEXT,
    kind             TEXT CHECK (kind IN ('movie', 'episode', 'season')),
    ingest_path      TEXT,
    current_path     TEXT,
    scraped_ref_json TEXT,
    dispatch_path    TEXT,
    grabbed_at       INTEGER,
    ingested_at      INTEGER,
    scraped_at       INTEGER,
    dispatched_at    INTEGER,
    status           TEXT CHECK (status IN
                       ('grabbed', 'ingested', 'scraped', 'dispatched', 'reconciled')),
    resolution_state TEXT CHECK (resolution_state IN ('awaiting', 'resolved', 'dismissed')),
    decision_id      INTEGER,
    resolution_trigger TEXT,
    resolution_at    INTEGER,
    grab_run_uid     TEXT,
    ingest_run_uid   TEXT,
    scrape_run_uid   TEXT,
    dispatch_run_uid TEXT
);

-- Step 2: copy every row, column for column (no defaults, no coercion).
INSERT INTO staging_provenance_new (
    info_hash, followed_id, media_ref_json, kind, ingest_path, current_path,
    scraped_ref_json, dispatch_path, grabbed_at, ingested_at, scraped_at,
    dispatched_at, status, resolution_state, decision_id, resolution_trigger,
    resolution_at, grab_run_uid, ingest_run_uid, scrape_run_uid, dispatch_run_uid
)
SELECT
    info_hash, followed_id, media_ref_json, kind, ingest_path, current_path,
    scraped_ref_json, dispatch_path, grabbed_at, ingested_at, scraped_at,
    dispatched_at, status, resolution_state, decision_id, resolution_trigger,
    resolution_at, grab_run_uid, ingest_run_uid, scrape_run_uid, dispatch_run_uid
FROM staging_provenance;

-- Step 3: swap.
DROP TABLE staging_provenance;
ALTER TABLE staging_provenance_new RENAME TO staging_provenance;

-- Step 4: recreate both indexes (010's path index + 011's PARTIAL resolution index).
CREATE INDEX idx_provenance_current_path ON staging_provenance (current_path);
CREATE INDEX idx_provenance_resolution_state
  ON staging_provenance (resolution_state)
  WHERE resolution_state IS NOT NULL;

-- Step 5: record the migration inside the SAME transaction as the rebuild.
INSERT OR IGNORE INTO schema_version(version) VALUES (15);

-- Step 6: publish the new schema version — inside the transaction.
PRAGMA user_version = 15;

COMMIT;
