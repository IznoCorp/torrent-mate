-- 026: the library-wide aired catalogue.
--
-- A provider-id-keyed store of the episodes a show has announced, with their
-- air dates, so « x of y aired episodes » can be answered for every show of the
-- library and not only for the followed ones (``aired_episode`` is per follow).
-- Written only by ``personalscraper library-catalogue-refresh``; a show's rows
-- are replaced in one transaction. Additive: no existing table is touched.
--
-- ``air_date`` is an ISO ``YYYY-MM-DD`` string or NULL (announced, no date yet).
-- ``status`` is the provider's raw production status (« Ended », « Continuing »,
-- « Returning Series »…), NULL when the provider names none. ``fetched_at`` is
-- the unix time of the last successful refresh of that show, NULL while the show
-- has only ever failed (a row then records the failed attempts and nothing else:
-- it reads as « never fetched »). ``last_attempt_at`` is the unix time of the last
-- attempt, successful or not, and ``failures`` counts the failed attempts since the
-- last success: a failing show is retried no sooner than the politeness period.
--
-- Wrapped in one transaction (008/009/024/025 pattern) so the DDL and the
-- user_version bump commit together.

BEGIN TRANSACTION;

CREATE TABLE catalogue_show (
    provider    TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    status      TEXT,
    fetched_at  REAL,
    last_attempt_at REAL NOT NULL,
    failures    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, provider_id)
);

CREATE TABLE catalogue_episode (
    provider    TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    season      INTEGER NOT NULL,
    episode     INTEGER NOT NULL,
    air_date    TEXT,
    title       TEXT,
    PRIMARY KEY (provider, provider_id, season, episode)
);

INSERT OR IGNORE INTO schema_version(version) VALUES (26);
PRAGMA user_version = 26;

COMMIT;
