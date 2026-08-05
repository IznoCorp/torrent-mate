-- personalscraper/acquire/migrations/016_provenance_reconstructed.sql
-- Mark a REBUILT journey as rebuilt (feature `workflow-jonction`, product-intent §14.3).
--
-- The §13 repair of 2026-08-05 rebuilt 57 lost journeys from the databases that still
-- held the facts. Three fields were NOT reconstructable and were deliberately left NULL —
-- `ingest_path`, `current_path`, `scraped_at` — because the staging folders had been
-- deleted and inventing a plausible path is exactly the lie §méthode forbids.
--
-- But the journey stepper lights a stage IFF its timestamp is non-NULL, so those honest
-- NULLs render as « étape pas faite »: a media shown as « Rangé » sitting on top of an
-- unlit « Ingéré » and « Scrapé ». That describes a path that cannot exist — §14.2 says a
-- dispatched media went through ingest, sort, identification and scraping, by definition.
--
-- §14.3 draws the distinction this column makes possible: « Si une étape n'est pas connue,
-- l'interface dit INCONNUE, jamais PAS FAITE ». A NULL timestamp on a row bearing
-- `reconstructed_at` means « unknown »; on any other row it still means « not reached ».
--
-- Fully additive ALTER (not a table rewrite): every predating reader/writer ignores the
-- new column, and NULL — the default — is the correct value for every journey the
-- pipeline itself wrote. Wrapped in one transaction so the column and the version bump
-- commit together.

BEGIN TRANSACTION;

ALTER TABLE staging_provenance ADD COLUMN reconstructed_at INTEGER;

-- Record the migration + publish the schema version.
INSERT OR IGNORE INTO schema_version(version) VALUES (16);
PRAGMA user_version = 16;

COMMIT;
