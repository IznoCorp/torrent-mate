# Phase 2 — scrape-resolve CLI + Web Runner + Journal Wiring

## Gate

- [ ] Phase 1 complete — migration 013 applied, `DecisionWriter` usable, enqueue wired
- [ ] `ScrapeResult.action = "queued_for_decision"` exercised in unit tests
- [ ] `make lint` + `make test` green

---

### Sub-phase 2.1 — scrape-resolve CLI (fetch-by-ID, self-locking)

**Creates:** `personalscraper/commands/scrape_resolve.py` (or extend existing CLI module)
**Modifies:** CLI command registration in the Typer app, `personalscraper/web/maintenance/runner.py`
(add `"scrape-resolve"` to `_CLI_SELF_LOCKING`)
**Test:** `tests/cli/test_scrape_resolve.py`, `tests/unit/web/maintenance/test_runner.py`

**DESIGN ref:** §5 — `personalscraper scrape-resolve <staging_path> --provider tmdb|tvdb
--id <provider_id>`; exit 0/1/2; self-acquires `pipeline.lock`

CLI command: accepts `staging_path` (Path arg), `--provider` (`tmdb` or `tvdb`), `--id`
(int). Loads config, self-acquires `pipeline.lock` via `cli_compat.acquire_lock()`
(EXACTLY like `library-rescrape` in `analyze.py:305` — not a hand-rolled `is_lock_held`
check + file creation), fetches media by provider ID through existing service fetch/write
paths (TMDB client for movies, TVDB client for TV shows — respecting the multi-provider
separation boundary from `docs/reference/external-ids-flow.md`), writes NFO + artwork into
staging folder. On success: marks decision `resolved` via `DecisionWriter.resolve()` with
`resolution_json = {provider, provider_id, via: 'pick'}`. Exit codes: 0 (success), 1
(scrape error — NFO write failed, API error), 2 (misconfiguration — missing DB, bad
provider). Add `"scrape-resolve"` to `_CLI_SELF_LOCKING` frozenset in
`personalscraper/web/maintenance/runner.py:128`.

Test: golden fixtures for fetch-by-ID (TMDB movie, TVDB TV show — vacuous-test lesson
per `docs/reference/testing.md`), self-locking behavior, exit codes, resolution write.

**Commit:** `feat(scrape-arbiter): add scrape-resolve CLI with self-locking and fetch-by-ID`

---

### Sub-phase 2.2 — Web runner (S3 pattern)

**Creates:** `personalscraper/web/decisions/__init__.py`,
`personalscraper/web/decisions/runner.py`
**Test:** `tests/unit/web/decisions/test_runner.py`

**DESIGN ref:** §5 — detached subprocess, env contract, reserves `pipeline_run` row,
streams output to Redis + 64 KiB ring, route-level lock probe → 409

Runner module mirrors `personalscraper/web/maintenance/runner.py` pattern:

- `_read_mandatory_env()`: reads `PERSONALSCRAPER_RUN_UID`, `PERSONALSCRAPER_DECISION_ID`,
  `PERSONALSCRAPER_DECISION_PROVIDER`, `PERSONALSCRAPER_DECISION_PROVIDER_ID`.
- `main()`: loads config, opens `DecisionWriter`, reads decision row, spawns
  `personalscraper scrape-resolve <staging_path> --provider X --id Y` as subprocess,
  streams stdout/stderr to Redis pubsub (fail-soft, matching `_stream_to_redis`) + 64 KiB
  ring buffer (matching `personalscraper/web/maintenance/runner.py` `_RingBuffer`),
  finalizes `pipeline_run` row on every exit path (success → `"success"`, CLI error →
  `"error"`, SIGTERM → `"killed"`).
- `kind='maintenance'`, `command='scrape-resolve'`, `options_json={decision_id, provider,
provider_id}`.
- Exit codes: 0 (CLI success), 1 (CLI error or lock loss), 2 (misconfiguration), 143
  (SIGTERM).

**Commit:** `feat(scrape-arbiter): add web decisions runner with detached subprocess`

---

### Sub-phase 2.3 — Journal wiring (run reservation + PipelineRunWriter integration)

**Modifies:** `personalscraper/web/decisions/runner.py` (if reservation logic is inline)
or `personalscraper/web/routes/decisions.py` (created in phase 3, but
reservation function is needed now for testability)
**Test:** `tests/unit/web/decisions/test_runner.py`

**DESIGN ref:** §5 — `BEGIN IMMEDIATE` before 202, route-level lock probe → 409 +
pre-spawn re-probe

Extract `_reserve_decision_run(db_path, run_uid, decision_id, provider, provider_id)`
function: opens a `sqlite3` connection, runs `BEGIN IMMEDIATE`, checks no concurrent
decision run is `'running'`, inserts `pipeline_run` row (`kind='maintenance'`,
`command='scrape-resolve'`, `options_json`, `status='running'`), commits. Follows the
`_reserve_run_row` pattern from `personalscraper/web/routes/maintenance.py:854`. Test:
concurrent double-resolve → second gets concurrency error; row finalized on every exit
path of the runner (success, error, SIGTERM, spawn failure).

**Commit:** `feat(scrape-arbiter): add journal wiring for decision run reservation`
