-- personalscraper/acquire/migrations/012_provenance_run_linkage.sql
-- Pipeline-run linkage on the provenance spine (feature `run-linkage`, F3).
--
-- Records WHICH pipeline_run advanced a follow-driven acquisition at each stage, so
-- « quel run a scrapé / dispatché ce média ? » becomes answerable — and, conversely,
-- « quelles acquisitions ce run a-t-il traitées ? ». An acquisition is advanced by
-- DIFFERENT runs at different stages (grab runs as its OWN `kind='maintenance'`
-- pipeline_run, OUTSIDE any full `personalscraper run`; ingest/sort/scrape/dispatch run
-- inside `Pipeline.run()`), so a single run id would be overwritten and lie — hence one
-- nullable column PER STAGE, paralleling the existing `*_at` set.
--
-- Cross-database ADVISORY back-links (pipeline_run lives in library.db, this table in
-- acquire.db): plain TEXT `run_uid` (hex), NOT foreign keys — exactly like 010's
-- `followed_id` and 011's `decision_id`. Every column is NULLable: a grab added straight
-- to qBittorrent (no row at all), a grab with no indexer DB, or any stage that cannot
-- resolve a run degrades to NULL — never an error. The stage writers stamp these inside
-- their existing `_safe_write` (best-effort), so a wiped table / rolled-back column
-- degrades the pipeline to exactly its F0/F1/F2 behaviour.
--
-- Fully additive ALTERs (not a table rewrite): every predating reader/writer ignores the
-- new columns. Wrapped in one transaction (like 008..011) so the four ADD COLUMNs +
-- user_version bump commit together — no half-applied window.

BEGIN TRANSACTION;

ALTER TABLE staging_provenance ADD COLUMN grab_run_uid TEXT;
ALTER TABLE staging_provenance ADD COLUMN ingest_run_uid TEXT;
ALTER TABLE staging_provenance ADD COLUMN scrape_run_uid TEXT;
ALTER TABLE staging_provenance ADD COLUMN dispatch_run_uid TEXT;

-- Record the migration + publish the schema version (mirrors 008..011's markers).
INSERT OR IGNORE INTO schema_version(version) VALUES (12);
PRAGMA user_version = 12;

COMMIT;
