-- 023: the provider's production status of a followed series.
--
-- Operator, 2026-08-09: « À jour » must split in two — a series whose aired
-- episodes are all in the library but which still has episodes ahead, and one
-- that is FINISHED. The operator's rule was « plus d'épisodes annoncés avec une
-- diffusion à venir », and on its own that rule lies: on 2026-08-09 « House of
-- the Dragon » had ZERO future episodes cached while airing that very day, so
-- an absence of announcements would have declared a running series terminée.
-- Absence of an announcement is not the end of a series — it is, most often,
-- simply a provider that has not published the next dates yet.
--
-- So « Terminé » needs a POSITIVE fact, and the provider already carries it
-- (TVDB « Ended », TMDB « Ended » / « Canceled »). It costs no extra API call:
-- the detect pass ALREADY fetches the series details to build the air-date
-- catalogue (acquire.airing.poll_known) and simply threw this field away.
--
-- NULL means « never polled / provider silent » — never « still running » and
-- never « ended ». A follow with NULL therefore keeps « À jour » (§14: no
-- verdict without knowledge).
--
-- Wrapped in one transaction (008/009 pattern) so the ADD COLUMN and the
-- user_version bump commit together — a crash between the two would leave the
-- column present with user_version still 22, and the next boot would re-run
-- this script and die on `duplicate column name`.

BEGIN TRANSACTION;

ALTER TABLE followed_series ADD COLUMN series_status TEXT;

INSERT OR IGNORE INTO schema_version(version) VALUES (23);
PRAGMA user_version = 23;

COMMIT;
