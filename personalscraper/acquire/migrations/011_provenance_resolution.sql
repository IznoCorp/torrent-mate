-- personalscraper/acquire/migrations/011_provenance_resolution.sql
-- Resolution-state projection onto the provenance spine (feature `decisions-spine`, F2).
--
-- Projects the scrape-arbiter DECISION lifecycle onto `staging_provenance` as an ADVISORY
-- mirror: for a follow-driven item the spine records whether its scrape is awaiting an
-- operator resolution, was resolved, or was dismissed — so the acquisition timeline (F1
-- « Parcours », F5 dashboard) shows WHERE each acquisition stands in resolution.
--
-- `scrape_decision` (library.db) stays the AUTHORITATIVE, fail-loud system-of-record. This
-- column is a best-effort projection updated by the decisions flow (`_safe_write`): a
-- wiped table / rolled-back column degrades the pipeline to exactly its F0/F1 behaviour —
-- no decision correctness depends on it. Decisions remain the SUPERSET: a manual/direct
-- item (no spine row) writes NOTHING here and stays resolvable via the decisions UI.
--
-- Fully additive ALTERs (not a table rewrite): every predating reader/writer ignores the
-- new columns; old code never references them. NULL `resolution_state` = no decision was
-- raised (a confident scrape). Wrapped in one transaction (like 008/009/010) so the four
-- ADD COLUMNs + index + user_version bump commit together — no half-applied window.
--
-- ALTER-ADD-COLUMN + CHECK note: the column-level CHECK permits NULL (`NULL IN (...)`
-- evaluates to NULL, and a CHECK only fails on FALSE), so the NULL default is accepted.
-- `decision_id` is a plain INTEGER back-link, NOT a FOREIGN KEY: it points ACROSS databases
-- (into library.db's `scrape_decision`) and, like 010's `followed_id`, must never be able
-- to brick the store via `foreign_key_check`.

BEGIN TRANSACTION;

ALTER TABLE staging_provenance
  ADD COLUMN resolution_state TEXT
    CHECK (resolution_state IN ('awaiting', 'resolved', 'dismissed'));
ALTER TABLE staging_provenance ADD COLUMN decision_id INTEGER;
ALTER TABLE staging_provenance ADD COLUMN resolution_trigger TEXT;
ALTER TABLE staging_provenance ADD COLUMN resolution_at INTEGER;

-- Cheap "what is awaiting resolution" queries — partial index skips the NULL happy path.
CREATE INDEX idx_provenance_resolution_state
  ON staging_provenance (resolution_state)
  WHERE resolution_state IS NOT NULL;

-- Record the migration + publish the schema version (mirrors 008/009/010's markers).
INSERT OR IGNORE INTO schema_version(version) VALUES (11);
PRAGMA user_version = 11;

COMMIT;
