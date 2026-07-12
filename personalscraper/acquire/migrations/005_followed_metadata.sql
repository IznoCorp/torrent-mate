-- personalscraper/acquire/migrations/005_followed_metadata.sql
-- Watch-list card enrichment (webui-overhaul OBJ3).
-- Cache lightweight display metadata on the followed series so the Suivis
-- cards can show a poster / description / year / season count without a
-- per-card provider call. Populated at follow time from the add-by-search
-- candidate (poster_url is the remote TMDB/TVDB image URL); year + season_count
-- are additionally backfilled at read time from the indexer when absent.
-- All columns are nullable — an existing follow simply has NULLs until it is
-- re-followed or matched in the library.
PRAGMA user_version = 5;

ALTER TABLE followed_series ADD COLUMN poster_url TEXT;
ALTER TABLE followed_series ADD COLUMN overview TEXT;
ALTER TABLE followed_series ADD COLUMN year INTEGER;
ALTER TABLE followed_series ADD COLUMN season_count INTEGER;

INSERT INTO schema_version(version) VALUES (5);
