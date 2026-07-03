-- personalscraper/acquire/migrations/002_cross_seed.sql
-- Cross-seed history + daily quota tables (watch-seed Phase 4.1).
PRAGMA user_version = 2;

CREATE TABLE IF NOT EXISTS cross_seed_history (
    source_hash TEXT NOT NULL,
    tracker     TEXT NOT NULL,
    searched_at REAL NOT NULL,  -- Unix timestamp (float) from time.time()
    PRIMARY KEY (source_hash, tracker)
);

CREATE TABLE IF NOT EXISTS cross_seed_quota (
    date  TEXT    NOT NULL,  -- 'YYYY-MM-DD' (local date)
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date)
);

INSERT INTO schema_version(version) VALUES (2);
