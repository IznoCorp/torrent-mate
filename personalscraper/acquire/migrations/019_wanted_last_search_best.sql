-- 019: persist the LAST search's best-candidate summary (web addition A).
-- JSON snapshot of SearchVerdict.chosen (title/resolution/source/codec/
-- language/seeders) written by record_search_outcome on EVERY concluded
-- search — cleared when the last search chose nothing, so the column always
-- describes the LATEST pass, never a stale one. The « À récupérer » card
-- reads it (« S02E05 · 1080p WEB-DL · 42 sources »).
--
-- Wrapped in one transaction (008/009 pattern) so the ADD COLUMN and the
-- user_version bump commit together — a crash between the two would leave
-- the column present with user_version still 18, and the next boot would
-- re-run this script and die on `duplicate column name`.

BEGIN TRANSACTION;

ALTER TABLE wanted ADD COLUMN last_search_best_json TEXT;

INSERT OR IGNORE INTO schema_version(version) VALUES (19);
PRAGMA user_version = 19;

COMMIT;
