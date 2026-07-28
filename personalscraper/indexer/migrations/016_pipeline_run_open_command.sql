-- Schema migration 016 — partial index over the OPEN pipeline_run rows.
--
-- The GET /followed render answers « is a priming run in flight for this
-- series? » by selecting the pipeline_run rows whose command matches and whose
-- ended_at IS NULL. No index covered (command, ended_at), so SQLite walked the
-- whole table on every page load. pipeline_run is append-only and nothing
-- prunes it, so that scan grows forever while the answer never does.
--
-- Partial index: only the rows that are still open are indexed, and there are a
-- handful of those at any instant — the index stays tiny however large the
-- table gets, which is also why the write cost on this hot-write table is
-- negligible (a row leaves the index as soon as ended_at is stamped).
--
-- Additive and idempotent (IF NOT EXISTS): applied at web boot by the lifespan
-- migration pass as well as by the CLI.

CREATE INDEX IF NOT EXISTS idx_pipeline_run_open_command
    ON pipeline_run (command)
    WHERE ended_at IS NULL;

INSERT INTO schema_version (version) VALUES (16);
PRAGMA user_version = 16;
