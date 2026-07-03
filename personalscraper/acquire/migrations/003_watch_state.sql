-- personalscraper/acquire/migrations/003_watch_state.sql
-- Watcher daemon KV state table (watch-seed Phase 7.3).
PRAGMA user_version = 3;

CREATE TABLE IF NOT EXISTS watch_state (
    key   TEXT PRIMARY KEY,
    value REAL NOT NULL
);

INSERT INTO schema_version(version) VALUES (3);
