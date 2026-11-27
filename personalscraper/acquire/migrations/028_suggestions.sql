-- 028: the suggestions deck (K3 P11c, DESIGN § 2.11).
--
-- The titles a refresh (``personalscraper acquisition-suggestions-refresh``) found worth
-- following, from the recommendations of the providers over the library's and the follows'
-- ids. The deck is replaced wholesale by each refresh, in one transaction: it is the last
-- refresh's, never an accumulation. Additive: no existing table is touched.
--
-- ``id`` rises with every row written and is never reused (AUTOINCREMENT): it is the order of
-- the deck and the cursor a read continues from, so a cursor of an older deck lands before every
-- row of a newer one and skips none of them. ``(provider, provider_id, kind)`` is a title's
-- identity: TMDB numbers films and shows apart, so the kind is part of it. ``provider_id`` is
-- text because a provider may answer a slug or an IMDb id, not only a number.
--
-- ``kind`` is the follows' (``movie`` / ``show``). ``reason`` is a CODE, never a sentence: the
-- interface words it (``similar_to_owned``: the title resembles one the library holds,
-- ``similar_to_followed``: one the account follows). ``seed_key`` names the title whose
-- recommendation this is (``tvdb:81189``, ``tmdb:603``, ``imdb:tt0133093``). ``rating`` and
-- ``poster`` are NULL when the provider's recommendation gives none. ``refreshed_at`` is the
-- unix time of the refresh that wrote the row (every row of a deck shares it).
--
-- Reads exclude what the reader owns or follows by provider id; the rejection a reader made
-- of a title is a per-account fact that lives in ``app.db`` (O-9), never here.
--
-- Wrapped in one transaction (008/009/024/025/026/027 pattern) so the DDL and the
-- user_version bump commit together.

BEGIN TRANSACTION;

CREATE TABLE suggestion (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    provider     TEXT    NOT NULL,
    provider_id  TEXT    NOT NULL,
    kind         TEXT    NOT NULL CHECK (kind IN ('movie', 'show')),
    title        TEXT    NOT NULL,
    year         INTEGER,
    rating       REAL,
    poster       TEXT,
    reason       TEXT    NOT NULL CHECK (reason IN ('similar_to_owned', 'similar_to_followed')),
    seed_key     TEXT    NOT NULL,
    refreshed_at INTEGER NOT NULL,
    UNIQUE (provider, provider_id, kind)
);

INSERT OR IGNORE INTO schema_version(version) VALUES (28);
PRAGMA user_version = 28;

COMMIT;
