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
-- ``suggestion_seed`` is the refresh's memory of the seeds it asked: ``seed_key`` is the key a
-- seed carries in the deck (``suggestion.seed_key``), ``asked_at`` the unix time of the last refresh
-- in which a provider answered for it. The refresh asks the seeds least recently asked first, so a
-- run bounded by ``--max`` reaches the whole library and the whole set of follows over the weeks
-- instead of the same head every time. It survives the deck's replacement (a seed whose
-- recommendations were all duplicates leaves no row in the deck, and was asked all the same).
--
-- ``external_ids`` is a JSON object, ``{"imdb": "tt0903747", "tmdb": "1396", "tvdb": "81189"}``:
-- the other ids the provider gave the title beside ``provider_id`` (a provider such as Trakt
-- names a title by a slug, which the library and the follows do not know). Only the keys the
-- provider gave are present; ``{}`` when it gave none.
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
    external_ids TEXT    NOT NULL DEFAULT '{}',
    UNIQUE (provider, provider_id, kind)
);

CREATE TABLE suggestion_seed (
    seed_key TEXT    PRIMARY KEY,
    asked_at INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version(version) VALUES (28);
PRAGMA user_version = 28;

COMMIT;
