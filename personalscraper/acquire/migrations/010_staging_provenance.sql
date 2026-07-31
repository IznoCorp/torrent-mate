-- personalscraper/acquire/migrations/010_staging_provenance.sql
-- Acquisition provenance spine (feature `provenance`, F0) — an ADVISORY per-torrent
-- registry that records the journey of a follow-driven acquisition
-- grab → ingest → sort/rename → scrape → dispatch, so the scrape can resolve identity
-- DETERMINISTICALLY (feature #30) instead of re-inferring it from the (renamed) folder.
--
-- Keyed on the torrent info-hash, NOT on a wanted row: a season-pack (one hash) maps
-- to many `wanted` rows but exactly ONE staging folder. `media_ref_json` is the identity
-- KNOWN at grab time (the seed the scrape reuses). `current_path` is kept live by the
-- sort/rename step so a folder rename never breaks the link.
--
-- ADVISORY OVERLAY — the filesystem stays the source of truth. A row is written ONLY for
-- follow-driven grabs; a manual/direct torrent (no wanted) gets NO row and is unaffected.
-- Every consumer is fail-soft: a missing / stale row falls back to today's behaviour
-- (#29 inference → free match). A wiped table degrades the pipeline to exactly its
-- current behaviour — no step's correctness depends on this registry.
--
-- New TABLE (not an ALTER): fully additive, invisible to every predating reader/writer.
-- SAFE on the shared acquire.db — old code never references `staging_provenance`. A
-- rollback simply leaves an unused table. Wrapped in one transaction (like 008/009) so
-- the CREATE + index + user_version bump commit together — no half-applied window.

BEGIN TRANSACTION;

CREATE TABLE staging_provenance (
    info_hash        TEXT PRIMARY KEY,     -- grabbed torrent hash (lowercase hex)
    -- Plain INTEGER back-link, NOT a FOREIGN KEY: this advisory table must never
    -- be able to brick the store. `open_db` runs `PRAGMA foreign_key_check` on every
    -- open and RAISES on any orphan; an operator who hard-deletes a followed_series
    -- row via the sqlite CLI (foreign_keys OFF there — a documented repair habit)
    -- would orphan a followed_id here and make the WHOLE acquire.db fail to open.
    -- No join depends on FK enforcement — followed_id is informational only (review A/C).
    followed_id      INTEGER,
    media_ref_json   TEXT,                 -- identity KNOWN at grab (tvdb/tmdb) — the seed
    kind             TEXT CHECK (kind IN ('movie', 'episode')),
    ingest_path      TEXT,                 -- staging folder the watcher created
    current_path     TEXT,                 -- live folder path (updated by sort/rename)
    scraped_ref_json TEXT,                 -- identity actually scraped (audit / drift)
    dispatch_path    TEXT,                 -- final destination after dispatch
    grabbed_at       INTEGER,
    ingested_at      INTEGER,
    scraped_at       INTEGER,
    dispatched_at    INTEGER,
    status           TEXT CHECK (status IN
                       ('grabbed', 'ingested', 'scraped', 'dispatched', 'reconciled'))
);

-- Consumers resolve a staging folder → its provenance row by path (scrape #30).
CREATE INDEX idx_provenance_current_path ON staging_provenance (current_path);

-- Record the migration + publish the schema version (mirrors 008/009's markers).
INSERT OR IGNORE INTO schema_version(version) VALUES (10);
PRAGMA user_version = 10;

COMMIT;
