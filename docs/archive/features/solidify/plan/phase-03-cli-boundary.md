# Phase 3 — CLI boundary + composition root (T7)

## Gate

```bash
make lint && make test && make check

# cli_compat facade cycle dissolved: no module imports `cli` as a helper facade
rg -n "from personalscraper import cli as cli_compat" -g '*.py' personalscraper/   # 0 after migration
rg -n "cli_compat\." -g '*.py' personalscraper/                                    # 0 — helpers moved to cli_helpers/

# atomic-write single owner (CROSS-CUTTING-02) — bulk sites converted this phase
rg -l "os\.replace" -t py personalscraper/ -g '!io_utils.py' -g '!core/**' -g '!scraper/keywords_cache.py' -g '!scraper/json_ttl_cache.py' -g '!trailers/placement.py'  # only P6-owned/moved files remain

python -c "import personalscraper" && echo IMPORT-OK

# Partial ACC-09 (final assertion in P13); confirm the non-moving sites are converted
rg -n "os\.replace" -t py personalscraper/conf/envfile.py personalscraper/ingest/tracker.py personalscraper/web/routes/config.py  # 0
# _omdb_quota.py: plan correction (P3.8) — its remaining os.replace :292 is a corrupt-state
# QUARANTINE RENAME (a move, not an atomic write); its write path already uses atomic_write_json.
# It stays. P13's ACC-09 allowlist must include this site.
```

## Objective

Introduce ONE `cli_helpers.boundary()` decorator (lock / journal / staging / context, with
config+db resolution and a `needs=` parameter for read-only commands) owning the ~30-line
scaffold repeated across the pipeline + library commands (DESIGN §5 T7). Route
dependency-hand-wiring commands through `_build_app_context` (composition-root
re-enforcement), dissolve the `import personalscraper.cli as cli_compat` facade cycle by
moving helpers into `cli_helpers/`, decompose `commands/watch.py::watch`, hook telemetry
into the boundary decorator (covering the uninstrumented sub-app commands for free), and
land the cross-cutting utils cleanup: ONE durable atomic-write in `io_utils` (bulk sites)
and `lock.py` path injection via the boundary decorator (CROSS-CUTTING-02/03).

## Findings addressed

COMMANDS-CLI-01/04/05/06 (boundary scaffold duplicated; read-only commands over-build
AppContext; telemetry gaps), COMMANDS-CLI-08, INDEXER-08 (indexer CLI open_db+migrations
ceremony), MECHANICAL-DUP-01 (cli_compat facade), MEMTRACE-GRAPH-01 (`watch()`
decomposition), CROSS-CUTTING-02 (atomic-write, bulk sites), CROSS-CUTTING-03 (`lock.py`
config-at-default-time).

## Code anchors (verified)

- `personalscraper/cli_helpers/__init__.py`: `_build_app_context` :29 (the shared composition root — MEMORY: a lifetime lock here serializes unrelated commands; use lazy-open + BEGIN IMMEDIATE + lock-free reads), `per_step_boundary` :220 (existing seed-CLI boundary the new `boundary()` generalises), `__all__` includes `per_step_boundary` :335. Directory currently holds only `__init__.py` + `output.py` — helpers land here.
- Facade cycle: `personalscraper/commands/pipeline.py:10` `from personalscraper import cli as cli_compat`; usages e.g. `cli_compat.acquire_pipeline_lock` :90, `cli_compat.get_settings` :368, `cli_compat.release_lock` :405. `cli.py` (146 LOC) re-exports `acquire_lock`, `acquire_pipeline_lock`, `release_lock`, `scrape_locks_dir_for`, `get_settings`. Other `cli_compat` importers: `trailers/cli.py`, `commands/grab.py`, `commands/cross_seed.py`, `commands/scrape_resolve.py`, `commands/config.py`, `commands/follow.py`, `commands/library/{audit,query,maintenance,scan}.py`.
- Pipeline commands using the boundary today: `personalscraper/commands/pipeline.py` — `ingest` :82, `sort` :127, `scrape` :167, `verify` :214, `enforce` :285, `dispatch` :345, `clean` :410, `cleanup` :462, `process` :513, `run` :587; each wraps `cli_step_journal(...)` + `_bootstrap_staging` + `per_step_boundary(...)`.
- `personalscraper/commands/watch.py`: `watch` :91 (module 494 LOC; audit cc 131), `watch_now` :474 — decompose into poll/decide/trigger units.
- `personalscraper/lock.py`: `_default_lock_file` :39 lazily calls `load_config(resolve_config_path())` :47 (CROSS-CUTTING-03 — not literally import-time, but a config re-load fallback that the boundary decorator should render unnecessary by injecting the resolved lock path). `acquire_lock(lock_file=None)` :51.
- `personalscraper/io_utils.py`: `_atomic_write_bytes` :22 (`os.replace` :42), `atomic_write_json` :56, `atomic_write_text` :71 — the durable writer all sites import.
- `os.replace` sites (CROSS-CUTTING-02 / ACC-09): `scraper/keywords_cache.py`, `scraper/json_ttl_cache.py` (both MOVE in P6 → owned there), `web/routes/config.py`, `trailers/placement.py` (owned in P6), `ingest/tracker.py`, `api/metadata/_omdb_quota.py`, `conf/envfile.py`, plus `io_utils.py` itself. This phase converts the four NON-moving, non-core sites (`web/routes/config.py`, `ingest/tracker.py`, `api/metadata/_omdb_quota.py`, `conf/envfile.py`); P6 handles `trailers/placement.py` and the two moved caches.

Discrepancy note: DESIGN §5 (cross-cutting) says lock.py "stops loading config at
import-default time"; verified the current code loads config **lazily** inside
`_default_lock_file()`, not at import. The real fix is the same in effect: the boundary
decorator injects the resolved path so `_default_lock_file`'s `load_config` fallback is
never hit on the primary paths — keep the fallback for direct callers.

## Tasks

1. **P3.1 — `boundary()` decorator.** Add `boundary(*, needs=..., lock=True, journal=True, staging=True)` to `cli_helpers/` generalising `per_step_boundary`: resolves config + db, acquires `pipeline.lock` (injecting the path into `lock.py`, not re-loading config), opens `cli_step_journal`, bootstraps staging, and yields the right context bundle. `needs=` selects a narrower bundle (read-only commands stop paying full AppContext construction — COMMANDS-CLI-06). Verify: `pytest tests -k "cli_boundary or boundary_decorator" -q`; a read-only command builds the narrow bundle (assert no torrent client / no writer opened).
2. **P3.2 — Telemetry into the boundary.** Fold the `command_with_telemetry` hook into the boundary decorator so the ~30 uninstrumented sub-app commands get telemetry for free. Verify: `pytest tests -k "telemetry" -q`; a previously-uninstrumented sub-app command now records a telemetry event.
3. **P3.3 — Migrate pipeline commands.** Convert the 9 pipeline commands + `run` in `commands/pipeline.py` to the new `boundary()` decorator (replacing the manual `cli_step_journal`/`_bootstrap_staging`/`per_step_boundary`/`release_lock` scaffold). Behaviour byte-identical. Verify: `pytest tests -k "commands_pipeline or cli_pipeline" -q`; the P0/P1 pipeline behaviour unchanged.
4. **P3.4 — Migrate library commands + indexer open_db ceremony (INDEXER-08).** Convert `commands/library/{scan,query,audit,maintenance}.py` to `boundary(needs=...)`; collapse the indexer `open_db` + pending-migrations ceremony into one context manager reused by all library commands. Verify: `pytest tests -k "library_cli or indexer_cli or open_db" -q`; migrations still applied exactly once per command.
5. **P3.5 — Dissolve the cli_compat cycle.** Move the helper functions re-exported by `cli.py` (`acquire_pipeline_lock`, `release_lock`, `scrape_locks_dir_for`, `get_settings` wrappers, `scrape_locks_dir_for`) into `cli_helpers/`; update every `from personalscraper import cli as cli_compat` importer to import from `cli_helpers`. `cli.py` keeps only the Typer app wiring. Verify: `rg -n "from personalscraper import cli as cli_compat" -g '*.py' personalscraper/` == 0 and `rg -n "cli_compat\." -g '*.py' personalscraper/` == 0; `python -c "import personalscraper.cli"` OK.
6. **P3.6 — Composition-root re-enforcement.** Route commands that hand-wire dependencies through `_build_app_context` (or its narrower `needs=` bundle). Preserve the lazy-open + BEGIN IMMEDIATE + lock-free-reads discipline (single-writer DBs; do not add a shared lifetime lock). Verify: `pytest tests -k "app_context or composition_root" -q`; the app_context boundary AST test still passes.
7. **P3.7 — `watch()` decomposition (MEMTRACE-GRAPH-01).** Split `commands/watch.py::watch` into `_poll`, `_decide`, `_trigger` units, each with a Google-style docstring; the top-level `watch` orchestrates. Behaviour identical (poll interval, last-successful-run persistence at :439-453). Verify: `pytest tests -k "watch" -q`; complexity of the top-level function drops (spot-check).
8. **P3.8 — CROSS-CUTTING-02 (bulk) + CROSS-CUTTING-03.** Route the four non-moving `os.replace` sites (`web/routes/config.py`, `ingest/tracker.py`, `api/metadata/_omdb_quota.py`, `conf/envfile.py`) through `io_utils.atomic_write_text`/`atomic_write_json`/`_atomic_write_bytes`; delete any weaker local atomic writer. Wire `boundary()` to inject the resolved lock path so `lock.py` never re-loads config on the primary path. Verify: `rg -n "os\.replace" -t py <those four files>` == 0; lock tests green.
9. **P3.9 — Green + module-size relief.** Full gate; confirm `commands/pipeline.py` (826 non-blank LOC today) drops below 800 after the boundary extraction. Verify: `python3 scripts/check-module-size.py` shows `commands/pipeline.py` resolved (or note remaining relief owed to P13).

## Non-goals

- Do not move `trailers/placement.py`, `scraper/keywords_cache.py`, or `scraper/json_ttl_cache.py` os.replace sites — P6 owns those (module moves).
- Do not change pipeline step policy/permit/journal semantics (P1/P2 own those); P3 only
  wraps the commands in the shared boundary.
- Do not introduce a shared lifetime lock in `_build_app_context` (would serialize unrelated
  commands — MEMORY).
- Do not touch the web auth perimeter or `guarded_api` (single web auth dependency stays).

## Commit

```
refactor(solidify): cli_helpers.boundary() decorator (lock/journal/staging/context, needs=)
refactor(solidify): dissolve cli_compat facade cycle; helpers move to cli_helpers/
refactor(solidify): decompose watch() into poll/decide/trigger; atomic-write single owner (bulk)
```

Phase-gate commit:

```
chore(solidify): phase 3 gate — CLI boundary decorator + composition-root re-enforcement
```
