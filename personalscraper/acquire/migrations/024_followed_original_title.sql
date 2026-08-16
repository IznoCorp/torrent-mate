-- 024: the movie's original-language title, for cross-language identity (#435).
--
-- A movie followed under its localized display title (« Avant d'aller dormir »)
-- is commonly released under its ORIGINAL title (`Before.I.Go.To.Sleep.2014...`)
-- on the trackers: MULTI releases on French trackers are named in the original
-- language. The movie identity filter compares the parsed release title to the
-- followed title, so with only the localized title it rejects the correct film
-- (rapidfuzz 25 < 60 on the pair above) before the year — the real
-- discriminator — is even consulted. Storing the provider's original title
-- lets the filter accept a match against ANY known title.
--
-- The value is stored VERBATIM, even when it equals the display title:
-- non-NULL means « healed », which is what stops the detect-pass backfill from
-- refetching the same row forever. NULL means « not resolved yet » — never
-- « same as title ».
--
-- Wrapped in one transaction (008/009 pattern) so the ADD COLUMN and the
-- user_version bump commit together — a crash between the two would leave the
-- column present with user_version still 23, and the next boot would re-run
-- this script and die on `duplicate column name`.

BEGIN TRANSACTION;

ALTER TABLE followed_series ADD COLUMN original_title TEXT;

INSERT OR IGNORE INTO schema_version(version) VALUES (24);
PRAGMA user_version = 24;

COMMIT;
