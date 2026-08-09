-- 021: persist the grabbed RELEASE NAME on the provenance row (operator
-- report: « Nom de release non enregistré » on a freshly-grabbed journey).
-- Between grab and ingest — hours for a BluRay — neither ingest_path nor
-- current_path exists, yet the name IS known at grab time: it is the chosen
-- candidate's title. journey_release_name() falls back to this column.
--
-- Wrapped in one transaction (008/009 pattern) so the ADD COLUMN and the
-- user_version bump commit together — a crash between the two would leave
-- the column present with user_version still 20, and the next boot would
-- re-run this script and die on `duplicate column name`.

BEGIN TRANSACTION;

ALTER TABLE staging_provenance ADD COLUMN release_name TEXT;

INSERT OR IGNORE INTO schema_version(version) VALUES (21);
PRAGMA user_version = 21;

COMMIT;
