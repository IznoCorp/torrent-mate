# Phase 7 — Watch command loop + watch-now + run flags

## Gate

- **Requires Phase 5**: `cross-seed --hash` CLI registered and functional (the loop spawns it per completion).
- **Requires Phase 6**: `WatcherService` + `WatcherState` importable from `acquire/watcher.py`.
- **Requires Phase 3**: `WatchConfig` available in config.
- **Produces for Phase 8**: `personalscraper watch` + `personalscraper watch-now` CLI commands operational, `run --no-console` + `--trigger-reason` flags ready for PM2 ecosystem integration.

## Overview

Three deliverables: the watch daemon loop (`commands/watch.py`), the `watch-now` sentinel command (same module), and two `run` flags (`--no-console`, `--trigger-reason` in `commands/pipeline.py`). The loop builds a listing-only qBit client, reads `IngestTracker` hashes, consults `WatcherService`, executes decisions via subprocess, handles SIGTERM gracefully, and honors the 1 h auth-lockout. The `WatcherRunTriggered` event is emitted by `run` when `--trigger-reason` is set. All CLI commands must be added to `test_app_context_boundary.py` allowlist.

### Sub-phases (6 commits)

| #   | Commit                                                                 | Scope      |
| --- | ---------------------------------------------------------------------- | ---------- |
| 7.1 | `feat(watch-seed): add --no-console and --trigger-reason flags to run` | Run flags  |
| 7.2 | `feat(watch-seed): add WatcherRunTriggered event emission in run`      | Event      |
| 7.3 | `feat(watch-seed): implement watch command loop in commands/watch.py`  | Watch loop |
| 7.4 | `feat(watch-seed): implement watch-now sentinel command`               | Sentinel   |
| 7.5 | `feat(watch-seed): wire watch + watch-now into Typer CLI`              | CLI wiring |
| 7.6 | `test(watch-seed): add integration tests for watch loop + watch-now`   | Tests      |

## Sub-phase 7.1 — --no-console + --trigger-reason flags on run

**Files:**

- Modify: `personalscraper/commands/pipeline.py`

Add two flags to the existing `run` Typer command (`--no-console` is visible
per ACC-11; `--trigger-reason` is hidden):

```python
@app.command(name="run")
def run(
    headless: bool = typer.Option(False, "--headless", help="No Rich console, no Telegram"),
    no_console: bool = typer.Option(False, "--no-console", hidden=False,
        help="Rich console off, Telegram ON (daemon-spawned mode)"),
    trigger_reason: str = typer.Option("", "--trigger-reason", hidden=True,
        help="Set by the Watcher daemon to attribute this run"),
    # ... existing options ...
) -> None:
```

Logic: if `--no-console` is true, disable Rich console output but keep Telegram subscriber enabled (unlike `--headless` which disables both). The `--trigger-reason` value is stored in the Pipeline or AppContext for event emission. When absent (manual CLI), no `WatcherRunTriggered` is emitted.

## Sub-phase 7.2 — WatcherRunTriggered event

**Files:**

- Modify: `personalscraper/acquire/events.py`

```python
@dataclass(frozen=True, kw_only=True)
class WatcherRunTriggered(Event):
    """Emitted when the Watcher daemon triggers a pipeline run.

    Emitted by ``personalscraper run --trigger-reason <reason>`` before
    ``PipelineStarted``.  The reason is set by the watcher loop.

    Attributes:
        reason: Why the run was triggered — "completion", "safety_net",
            or "manual" (watch-now sentinel).
    """

    reason: str
```

Emit in `run()` (in `commands/pipeline.py`) before `PipelineStarted`:

```python
if trigger_reason:
    ctx.bus.emit(WatcherRunTriggered(reason=trigger_reason))
```

The event emission must also be added to the EventBus catalog if there's a central registry. Check `personalscraper/core/event_bus.py` for the event catalog pattern.

## Sub-phase 7.3 — watch command loop

**Files:**

- Create: `personalscraper/commands/watch.py`

**Plan snippet was stale** — this plan was written before the Phase 6 deliverables
(WatcherService, WatcherInput, is_lock_held, _WatchSubStore, **main**.py) were
finalised. The authoritative implementation in `personalscraper/commands/watch.py`
follows the sub-phase 7.3 dispatch brief (not this plan) and differs in these
respects:

- **Typer command**: `@command_with_telemetry("watch")` + `@handle_cli_errors`
  (mirrors `cross_seed.py`), not a bare `run_watch()` function called from
  `cli.py`.
- **AppContext via `_build_app_context(config, settings, build_torrent_client=True)`**
  held for daemon lifetime; `try/finally` closes `provider_registry` + `acquire`.
- **`is_lock_held()`** from `personalscraper.lock` (read-only PID probe, no
  mutate), not `Path.exists()`.
- **Cross-seed is `subprocess.run`** (synchronous, sequential per hash), not
  `Popen`. Log `watcher_cross_seed_failed` on non-zero returncode.
- **Run is `Popen` + polled**: tracked across cycles; skip if still alive
  (`watcher_run_still_active`). On `returncode==0` → persist + reset backoff
  - log `watcher_run_succeeded`; non-zero → `watcher_run_failed`.
- **Sentinel consumed ONLY when reason=="manual"** (operator poke), after spawn.
- **IngestTracker re-read every cycle** via `tracker.load().keys()` — spawned
  runs mutate `ingested_torrents.json`.
- **`t.hash`** not `t.info_hash` (TorrentItem.hash attribute).
- **Structured logs**: all events `watcher_*` snake_case via `get_logger(__name__)`.
- **`store.watch`** property chain: `app_context.acquire.store.watch.get/set`
  on `_WatchSubStore` (commit 2b865bf5).

````

## Sub-phase 7.4 — watch-now sentinel command

**Files:**

- Modify: `personalscraper/commands/watch.py` (add `run_watch_now()`)

```python
def run_watch_now() -> None:
    """Write the sentinel file that the watcher daemon consumes next cycle.

    No IPC, no daemon dependency — if the daemon is down, the sentinel is
    consumed at next boot.  Same channel as the future Web UI (W4).
    """
    from personalscraper.cli_helpers import _build_app_context

    ctx = _build_app_context()
    data_dir = Path(ctx.app_config.paths.data_dir)
    sentinel = data_dir / "watch.trigger"
    sentinel.write_text("")
    logger.info("watch_now_sentinel_written", path=str(sentinel))
    print(f"Sentinel written: {sentinel}")
    print("The watcher daemon will consume it next cycle and fire a pipeline run.")
````

## Sub-phase 7.5 — wire into Typer CLI

**Files:**

- Modify: `personalscraper/cli.py` (add `watch` and `watch-now` commands)

```python
@app.command(name="watch")
def watch_cmd() -> None:
    """Start the watcher daemon (single-process scheduler).

    Spawns run/cross-seed as subprocesses. Runs until SIGTERM.
    """
    from personalscraper.commands.watch import run_watch
    run_watch()


@app.command(name="watch-now")
def watch_now_cmd() -> None:
    """Write a sentinel file to trigger an immediate pipeline run.

    The running ``personalscraper watch`` daemon consumes this file at the
    next poll cycle and fires a run with reason=manual.
    """
    from personalscraper.commands.watch import run_watch_now
    run_watch_now()
```

## Sub-phase 7.6 — integration tests

**Files:**

- Create: `tests/integration/acquire/test_watcher_loop.py`

Tests with fake qBit client + stub subprocess runner:

- `test_sentinel_written_by_watch_now` — `run_watch_now()` creates `watch.trigger`, `sentinel_path.exists()` is True (ACC-9).
- `test_sentinel_consumed_exactly_once` — after one cycle, the sentinel is unlinked.
- `test_new_completion_spawns_cross_seed` — fresh completion → subprocess spawn for `cross-seed --hash`.
- `test_debounce_fires_run` — after debounce expiry → subprocess spawn for `run --no-console`.
- `test_poll_error_skips_cycle` — `get_completed()` raises → cycle logged, loop continues.
- `test_sigterm_graceful_shutdown` — SIGTERM delivered → `_shutdown_requested = True`, loop exits without killing spawned subprocesses.
- `test_disabled_exits_immediately` — `WatchConfig(enabled=False)` → loop exits.

ACC-8: `personalscraper watch --help` and `personalscraper watch-now --help` both exit 0.

ACC-11: `personalscraper run --help | grep -c 'no-console'` ≥ 1.

## Gate check (before advancing to Phase 8)

- [ ] `make lint` — 0 errors.
- [ ] ACC-8: `personalscraper watch --help && personalscraper watch-now --help` → OK.
- [ ] ACC-9: `python -m pytest tests/integration/acquire/test_watcher_loop.py -q -k sentinel` → pass.
- [ ] ACC-11: `personalscraper run --help 2>&1 | grep -c 'no-console'` ≥ 1.
- [ ] `python -m pytest tests/integration/acquire/test_watcher_loop.py -q` — all pass.
- [ ] `commands/watch.py` uses `personalscraper.logger.get_logger` (not `structlog.get_logger`) — verified by `make lint`'s `check_logging.py`.
- [ ] AppContext boundary allowlist updated: `commands/watch.py` functions added to `test_app_context_boundary.py`.
- [ ] `commands/watch.py` ≤ 300 LOC.
