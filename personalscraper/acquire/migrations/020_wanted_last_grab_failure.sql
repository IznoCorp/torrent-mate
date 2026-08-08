-- 020: persist the LAST grab failure on the wanted row (operator report:
-- « Ninja Turtles » sat on « À récupérer » through four identical grab
-- failures with ZERO on-screen explanation — the GrabFailed event reached
-- Telegram only). The web layer serves these columns so the card can say
-- WHY a takeable item is not moving; a successful grab clears them.
--
-- Wrapped in one transaction (008/009 pattern) so the ADD COLUMNs and the
-- user_version bump commit together — a crash between the two would leave
-- the columns present with user_version still 19, and the next boot would
-- re-run this script and die on `duplicate column name`.

BEGIN TRANSACTION;

ALTER TABLE wanted ADD COLUMN last_grab_reason TEXT;
ALTER TABLE wanted ADD COLUMN last_grab_at INTEGER;

INSERT OR IGNORE INTO schema_version(version) VALUES (20);
PRAGMA user_version = 20;

COMMIT;
