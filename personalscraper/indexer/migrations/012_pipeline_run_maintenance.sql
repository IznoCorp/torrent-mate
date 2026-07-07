-- Schema migration 012 — extend pipeline_run for maintenance action tracking.
--
-- Background:
--
-- The maintenance dashboard feature (S3, #182) needs to record which maintenance
-- actions (library-* CLI commands) were run, with their serialised options and
-- truncated output.  Rather than a separate table, the existing ``pipeline_run``
-- table is extended with four additive columns:
--
--   kind          — discriminates 'pipeline' runs from 'maintenance' actions
--   command       — CLI command name (NULL for pipeline rows)
--   options_json  — canonical JSON of the action options (NULL for pipeline rows)
--   output_tail   — last N bytes of the command output for the web-UI log widget
--
-- All existing rows get ``kind='pipeline'`` (the default), making this a purely
-- additive, backwards-compatible change.  The new index on ``kind`` accelerates
-- the maintenance-history filter query.

-- ---------------------------------------------------------------------------
-- Step 1 — add the four new columns (additive, all existing rows get defaults).
-- ---------------------------------------------------------------------------

ALTER TABLE pipeline_run ADD COLUMN kind         TEXT NOT NULL DEFAULT 'pipeline';
ALTER TABLE pipeline_run ADD COLUMN command      TEXT NULL;
ALTER TABLE pipeline_run ADD COLUMN options_json TEXT NULL;
ALTER TABLE pipeline_run ADD COLUMN output_tail  TEXT NULL;

-- ---------------------------------------------------------------------------
-- Step 2 — index on kind for the maintenance-history list query.
-- ---------------------------------------------------------------------------

CREATE INDEX idx_pipeline_run_kind ON pipeline_run(kind);

-- ---------------------------------------------------------------------------
-- Step 3 — version bump.
-- ---------------------------------------------------------------------------

INSERT INTO schema_version (version) VALUES (12);
PRAGMA user_version = 12;
