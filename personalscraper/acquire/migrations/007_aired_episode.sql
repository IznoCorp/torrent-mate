-- personalscraper/acquire/migrations/007_aired_episode.sql
-- Aired-episode catalog cache (P0-B.1).
-- The §5 completeness view used to poll the provider catalog LIVE on every
-- request (one get_tv + one get_episodes per season, synchronous) — slow,
-- fragile, and nothing else owned "what has aired". This table caches the
-- aired catalog per followed series; `follow detect` (which already polls the
-- catalog daily + on demand) is its single writer, and the web reads it
-- (fresh read-only connection per request) with a live-poll fallback when a
-- series has no cached rows yet. Rows are replaced wholesale per followed
-- series on each detect pass; ON DELETE CASCADE cleans up with the follow.
PRAGMA user_version = 7;

CREATE TABLE aired_episode (
    followed_id INTEGER NOT NULL REFERENCES followed_series(id) ON DELETE CASCADE,
    season      INTEGER NOT NULL,
    episode     INTEGER NOT NULL,
    title       TEXT,
    air_date    TEXT    NOT NULL,   -- ISO-8601 date (YYYY-MM-DD)
    updated_at  INTEGER NOT NULL,   -- unix epoch s of the detect pass that wrote it
    PRIMARY KEY (followed_id, season, episode)
);

INSERT INTO schema_version(version) VALUES (7);
