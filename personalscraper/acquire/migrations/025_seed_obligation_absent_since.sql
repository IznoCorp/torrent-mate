-- 025: when a seed obligation's torrent was first seen missing from the client.
--
-- The obligation sweep releases an obligation only once its torrent has stayed
-- absent for a confirmation delay (a client restarting and answering before its
-- torrents are loaded must not release anything). ``absent_since`` holds the
-- unix time of the first pass that did not see the torrent; NULL means « seen
-- at the last pass » or « never swept ». Nullable, no backfill: existing rows
-- keep NULL, which is exactly « not yet observed absent ».
--
-- Wrapped in one transaction (008/009/024 pattern) so the ADD COLUMN and the
-- user_version bump commit together.

BEGIN TRANSACTION;

ALTER TABLE seed_obligation ADD COLUMN absent_since INTEGER;

INSERT OR IGNORE INTO schema_version(version) VALUES (25);
PRAGMA user_version = 25;

COMMIT;
