# Phase 1 — Critical bug fixes

**Goal** : Close Pattern A findings from the audit — the items where provider-ids' ACCEPTANCE.md ticked ✅ but the code does not deliver.

## Gate (in)

- `fix/tech-debt` branch checked out at `8da517f` (archive + bump commit) or descendant
- `IMPLEMENTATION.md` at root carries the tech-debt header
- `make check` green (carries over from provider-ids merge)

## Gate (out)

- All 4 sub-phase commits landed on the branch
- `make check` green after each sub-phase
- `personalscraper indexer backfill-ids --help` succeeds
- `personalscraper library-index` succeeds on a 4-disk config (no race)
- `.env.example` contains every key referenced by `os.environ.get` / `Settings` in `personalscraper/`

## Sub-phases

### 1.1 — `library/rescraper` DEV #2 regression vector

**File** : `personalscraper/library/rescraper.py:_rescrape_episodes`

**Problem** : after `match_episode_files` + `rename_episodes`, sibling NFOs are never regenerated. The episode payload built at line 419-425 only carries `{title, still_path}` — the same shape that originally caused DEV #2.

**Fix** :

- Build the full payload with `external_ids` from the TVDB/TMDB season response (mirror `tv_service._build_episode_map`)
- Call `_generate_episode_nfos` (or its library-side equivalent) after `rename_episodes`
- Add regression test mirroring `tests/scraper/test_regression_dev2_episode_ids.py` invoking `library.rescraper.run_rescrape` on a fixture with stripped episode NFOs

**Commit** : `fix(tech-debt): library/rescraper regenerates episode NFOs with canonical uniqueid`

### 1.2 — `personalscraper indexer backfill-ids` CLI

**Files** : new `personalscraper/commands/library/backfill.py`, registered in `cli_app.py`

**Wiring** : `run_backfill_ids` already exists in `personalscraper/indexer/scanner/_modes/backfill_ids.py`. Add Typer command :

```
personalscraper indexer backfill-ids [--show TITLE] [--ids-only|--ratings-only] [--dry-run]
```

- Load config + DB connection + clients via `cli_compat`
- Build EventBus
- Call `run_backfill_ids` with CLI flags mapped 1:1
- Render `BackfillStats` summary on the console

**Tests** :

- Unit test for the command with mocked `run_backfill_ids`
- Integration test verifying the help text + exit codes

**Commit** : `feat(tech-debt): wire indexer backfill-ids Typer subcommand`

### 1.3 — `library-index` concurrent migration race (C5)

**File** : `personalscraper/indexer/scanner/__init__.py` + `personalscraper/indexer/migrations/004_extend_media_stream.sql`

**Problem** : 3 parallel disk workers all try to apply migration 004's `CREATE INDEX idx_stream_kind_codec` simultaneously, race, fail.

**Fix combination** :

- Make every `CREATE INDEX` / `CREATE TABLE` in `personalscraper/indexer/migrations/*.sql` use `IF NOT EXISTS` (idempotent re-apply)
- Apply migrations once on the writer connection BEFORE forking workers in `scan()`

**Regression test** : multi-disk fixture that exercises the parallel-worker fan-out and asserts no `RuntimeError` is raised. Use `pyfakefs` or `tmp_path`-based real disks.

**Commit** : `fix(tech-debt): library-index applies migrations once before forking workers`

### 1.4 — `.env.example` missing keys

**File** : `.env.example`

**Missing keys to add** (with explanatory comments) :

- `OMDB_API_KEY` (used by `omdb.py`, `imdb.py`, `rotten_tomatoes.py`)
- `LACALE_API_KEY` (used by `api/_activation.py`)
- `TRAKT_CLIENT_ID` + `TRAKT_CLIENT_SECRET`
- `TRANSMISSION_USERNAME` + `TRANSMISSION_PASSWORD`
- `LIBRARY_ANALYZER_MAX_WORKERS` (or migrate to `preferences.json5` — decided in Phase 4.4)

**Validation** : `grep -rn "os.environ.get\|os.getenv" personalscraper/` — every key referenced must have a matching line in `.env.example`.

**Commit** : `docs(tech-debt): add missing env vars to .env.example`

## Definition of done

- 4 commits on `fix/tech-debt` matching the sub-phase descriptions
- `make check` green
- New regression tests : `tests/library/test_rescraper_dev2.py` (1.1), `tests/test_cli.py::test_backfill_ids_*` (1.2), `tests/indexer/test_concurrent_migration.py` (1.3)
- Smoke : `personalscraper indexer backfill-ids --dry-run` runs without error on the live `.data/library.db`
