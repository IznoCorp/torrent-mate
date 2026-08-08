-- 022: an explicit intent to REPLACE a film already in the library.
--
-- Operator report 2026-08-08: « un film déjà en médiathèque doit être
-- re-téléchargé et remplacé ». The web UI already confirms the replacement
-- (§5 dialog, « Le suivre relancera une acquisition dont le résultat
-- REMPLACERA la version en place »), but detect closed the follow the moment
-- it saw the film owned — so the acquisition the operator had just authorised
-- never ran, and the promise in the dialog was false.
--
-- The flag carries that authorisation into the pipeline. It is cleared as soon
-- as the wanted row exists: the intent is spent, and when the NEW file lands
-- the ordinary owned-closure applies again.
--
-- Wrapped in one transaction (008/009 pattern) so the ADD COLUMN and the
-- user_version bump commit together — a crash between the two would leave the
-- column present with user_version still 21, and the next boot would re-run
-- this script and die on `duplicate column name`.

BEGIN TRANSACTION;

ALTER TABLE followed_series ADD COLUMN replace_owned INTEGER NOT NULL DEFAULT 0;

INSERT OR IGNORE INTO schema_version(version) VALUES (22);
PRAGMA user_version = 22;

COMMIT;
