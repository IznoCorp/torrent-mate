-- Schema migration 011 — pipeline_run table for pipe-control run history.
--
-- Background:
--
-- The pipe-control feature (§phase-01) needs a persistent record of every
-- pipeline execution to support pause/resume, the web-UI run-history widget,
-- and cross-run analytics.  Each row captures the run identity (``run_uid``),
-- how it was triggered (CLI, web UI, launchd cron), whether it was a dry run,
-- the outcome (success/error/killed), and an opaque ``steps_json`` blob for
-- per-step timing data written by the ``PipelineRunWriter``.
--
-- ``started_at`` and ``ended_at`` are REAL Unix-epoch seconds (``time.time()``,
-- both the run-level columns and the per-step entries inside ``steps_json``)
-- rather than the migration convention's ``*_at`` INTEGER, to keep sub-second
-- precision.  The convention is waived here per explicit design choice in the
-- plan.

-- ---------------------------------------------------------------------------
-- Step 1 — create the pipeline_run table.
-- ---------------------------------------------------------------------------

CREATE TABLE pipeline_run (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_uid    TEXT    UNIQUE NOT NULL,
    trigger    TEXT    NOT NULL,
    dry_run    INTEGER NOT NULL DEFAULT 0,
    started_at REAL    NOT NULL,
    ended_at   REAL,
    outcome    TEXT,
    steps_json TEXT,
    error      TEXT,
    pid        INTEGER
);

-- ---------------------------------------------------------------------------
-- Step 2 — index on started_at for the run-history list query.
-- ---------------------------------------------------------------------------

CREATE INDEX idx_pipeline_run_started ON pipeline_run(started_at);

-- ---------------------------------------------------------------------------
-- Step 3 — version bump.
-- ---------------------------------------------------------------------------

INSERT INTO schema_version (version) VALUES (11);
PRAGMA user_version = 11;
