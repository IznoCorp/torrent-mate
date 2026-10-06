-- The read mark of an account's notices: ``account_notice.read_at``, the epoch ``time.time()`` at
-- which the account marked the notice read; NULL while it is unread. Additive: one nullable
-- column, every existing notice stays unread.
--
-- ``PRAGMA user_version`` inside the transaction: the column and the version commit together.

BEGIN TRANSACTION;

ALTER TABLE account_notice ADD COLUMN read_at REAL;

PRAGMA user_version = 10;

COMMIT;
