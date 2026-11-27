-- ``suggestion_rejection``: the titles an account rejected from the suggestions deck (K3-G7). A
-- rejection is the REJECTING ACCOUNT's (operator ruling O-9 A, 2026-11-27): it hides the title
-- from that account's deck and from no other's. It belongs to the account and goes with it
-- (``ON DELETE CASCADE``).
--
-- ``(provider, provider_id, kind)`` is a title's identity in the deck (``acquire.db``'s
-- ``suggestion``), which a refresh replaces wholesale: the identity, never the deck row's key,
-- is what a rejection holds, so a title a later deck brings back stays rejected. No key into
-- ``acquire.db``: the two stores are separate files. ``rejected_at`` is epoch ``time.time()``.
-- Additive: one new table, no row of an existing table is touched.
--
-- ``PRAGMA user_version`` inside the transaction: the table and the version commit together.

BEGIN TRANSACTION;

CREATE TABLE suggestion_rejection (
    account_id  TEXT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    provider    TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('movie', 'show')),
    rejected_at REAL NOT NULL,
    PRIMARY KEY (account_id, provider, provider_id, kind)
);

PRAGMA user_version = 12;

COMMIT;
