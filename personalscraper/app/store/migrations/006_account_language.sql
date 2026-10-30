-- ``account.language``: the language the account is spoken to in — the interface's on every device,
-- and its pushes' (the contract's ``Account.language``). Every existing account speaks French, the
-- language the household always read it in (the operator, 2026-10-05: « Compte existants en fr »);
-- a new account is written with the project's configured language by the services, never by this
-- default. Additive: an ADD COLUMN with a constant default rewrites no row.
--
-- ``PRAGMA user_version`` inside the transaction: the column and the version commit together.

BEGIN TRANSACTION;

ALTER TABLE account ADD COLUMN language TEXT NOT NULL DEFAULT 'fr' CHECK (language IN ('fr', 'en'));

PRAGMA user_version = 6;

COMMIT;
