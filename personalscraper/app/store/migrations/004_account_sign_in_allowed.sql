-- ``account.sign_in_allowed``: whether the account may sign in. Every account, existing or new,
-- starts allowed (1); an Admin's ``setAccountAccess`` cuts it (0). Additive: an ADD COLUMN with a
-- constant default rewrites no row.
--
-- ``PRAGMA user_version`` inside the transaction: the column and the version commit together.

BEGIN TRANSACTION;

ALTER TABLE account ADD COLUMN sign_in_allowed INTEGER NOT NULL DEFAULT 1 CHECK (sign_in_allowed IN (0, 1));

PRAGMA user_version = 4;

COMMIT;
