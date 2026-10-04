-- ``account.demoted_from``: the role an account held before a Plex link dropped it to its Plex
-- kind's starting role (the contract's ``AccountSummary.demotedFrom``); NULL when not demoted, and
-- cleared once an Admin gives it a role. A foreign key: deleting that role clears it. Additive: an
-- ADD COLUMN with no default rewrites no row.
--
-- ``PRAGMA user_version`` inside the transaction: the column and the version commit together.

BEGIN TRANSACTION;

ALTER TABLE account ADD COLUMN demoted_from TEXT REFERENCES role(id) ON DELETE SET NULL;

PRAGMA user_version = 5;

COMMIT;
