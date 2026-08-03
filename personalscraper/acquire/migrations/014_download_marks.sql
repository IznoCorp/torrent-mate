-- Migration 014: download_marks table for exactly-once download event emission (O4/D7).
--
-- One advisory row per grabbed torrent hash. The reconcile pass reads the mark,
-- emits only the transitions not yet recorded (started / 25-50-75 thresholds /
-- completed), and persists the mark BEFORE emitting (emit-after-persist: a crash
-- between persist and emit loses that emit rather than duplicating it — download
-- events are advisory). Marks are pruned when the hash no longer belongs to any
-- OPEN wanted row.

CREATE TABLE IF NOT EXISTS download_marks (
    info_hash           TEXT PRIMARY KEY,
    started_emitted     INTEGER NOT NULL DEFAULT 0,
    last_threshold      INTEGER NOT NULL DEFAULT 0,   -- 0 | 25 | 50 | 75
    completed_emitted   INTEGER NOT NULL DEFAULT 0,
    updated_at          REAL NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

-- Repo convention: the script itself bumps user_version so the DDL and the
-- version commit land in the same executescript transaction (see 012/013).
PRAGMA user_version = 14;
