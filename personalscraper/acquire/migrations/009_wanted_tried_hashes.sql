-- personalscraper/acquire/migrations/009_wanted_tried_hashes.sql
-- Remember which release info-hashes have already been grabbed-and-failed for a
-- wanted item, so the auto-reswitch (reswitch #342) re-searches EXCLUDING them
-- and never loops back to a release whose swarm is dead / whose payload broke.
--
-- One column, no rebuild: unlike migration 008 (which had to rewrite the table
-- to widen a CHECK constraint), this is a pure additive `ADD COLUMN`. SQLite
-- adds it in a single statement with every existing row defaulting to NULL, so
-- there is no half-applied state to guard against and no explicit transaction is
-- needed.
--
-- DEPLOY WINDOW ON THE SHARED acquire.db — SAFE (unlike 008): adding a column is
-- transparent to code that predates it. Old readers SELECT specific columns (or
-- the row mapper decodes the new column defensively via `row.keys()`), so they
-- never see it; old writers INSERT explicit column lists, so they never touch
-- it. No process crashes on a row written by the new code. A rollback is also
-- safe: the extra column is simply ignored by the old code.
--
-- NULL = no release tried yet — the honest default for pre-existing rows. The
-- store encodes the list as a JSON array of lowercase hex info-hashes.
--
-- Wrapped in an explicit transaction (like 008) so the ADD COLUMN and the
-- user_version bump commit together: `executescript` auto-commits each statement
-- on its own outside a BEGIN, so a crash between the ALTER and the PRAGMA would
-- leave the column present with user_version still 8 — the next boot re-runs 009
-- and dies on `duplicate column name`. Inside one transaction there is no such
-- window (review L4).

BEGIN TRANSACTION;

ALTER TABLE wanted ADD COLUMN tried_hashes_json TEXT;

-- Record the migration + publish the schema version (mirrors 008's markers).
INSERT OR IGNORE INTO schema_version(version) VALUES (9);
PRAGMA user_version = 9;

COMMIT;
