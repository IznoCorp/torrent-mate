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

Add two hidden flags to the existing `run` Typer command:

```python
@app.command(name="run")
def run(
    headless: bool = typer.Option(False, "--headless", help="No Rich console, no Telegram"),
    no_console: bool = typer.Option(False, "--no-console", hidden=True,
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

```python
"""Watch daemon loop — personalscraper watch.

Spawns ``personalscraper run --no-console`` and
``personalscraper cross-seed --hash <H>`` as subprocesses per DESIGN W5.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from personalscraper.logger import get_logger

logger = get_logger(__name__)

# Set by SIGTERM handler.
_shutdown_requested = False


def _on_sigterm(signum, frame) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.info("watcher_sigterm_received", signum=signum)


def run_watch() -> None:
    """Main watch loop — runs until SIGTERM or config.enabled becomes False.

    Builds a listing-only qBittorrent client (TorrentLister), reads
    IngestTracker's hash set, consults WatcherService, and executes
    decisions by spawning subprocesses.
    """
    from personalscraper.cli_helpers import _build_app_context

    ctx = _build_app_context()
    config_watch = ctx.app_config.watch
    if not config_watch.enabled:
        logger.info("watcher_disabled", reason="config.watch.enabled=false")
        return

    signal.signal(signal.SIGTERM, _on_sigterm)
    signal.signal(signal.SIGINT, _on_sigterm)

    from personalscraper.acquire.watcher import WatcherService, WatcherState, WatcherInput

    svc = WatcherService(config_watch)
    state = WatcherState()

    # Restore last_successful_run_at from acquire.db
    try:
        store = ctx.acquire_store  # or however the context exposes it
        state.last_successful_run_at = store.get_last_successful_run_at()
    except Exception:
        logger.warning("watcher_state_restore_failed", exc_info=True)

    while not _shutdown_requested:
        try:
            now = time.time()
            completed = ctx.qbit_client.get_completed()
            completed_hashes = {t.info_hash for t in completed}

            # Build input snapshot
            ingested_set = ctx.ingest_tracker.get_all_hashes()  # or equivalent
            seed_pure_set = _get_seed_pure_hashes(completed)

            sentinel_path = Path(ctx.app_config.paths.data_dir) / "watch.trigger"
            sentinel_present = sentinel_path.exists()

            # Check if pipeline.lock is held
            lock_path = Path(ctx.app_config.paths.data_dir) / "pipeline.lock"  # or staging
            lock_held = lock_path.exists()

            inp = WatcherInput(
                completed_hashes=frozenset(completed_hashes),
                ingested_hashes=frozenset(ingested_set),
                seed_pure_hashes=frozenset(seed_pure_set),
                sentinel_present=sentinel_present,
                pipeline_lock_held=lock_held,
                now=now,
            )

            out = svc.evaluate(inp, state)
            state = out.new_state

            # Execute decision
            if out.decision == WatcherDecision.FIRE_RUN:
                _spawn_run(out.run_reason)
                state = _record_success(state, now, store)

            elif out.decision == WatcherDecision.FIRE_CROSS_SEED:
                for h in out.cross_seed_hashes:
                    _spawn_cross_seed(h)

            elif out.decision == WatcherDecision.START_DEBOUNCE:
                logger.debug("watcher_debounce_started", until=state.debounce_until)

            elif out.decision == WatcherDecision.REQUEUE:
                logger.debug("watcher_requeue", reason="pipeline_lock_held")

            # Consume sentinel
            if sentinel_present:
                sentinel_path.unlink(missing_ok=True)

        except TORRENT_LISTING_ERRORS:
            logger.warning("watcher_poll_error", exc_info=True)
            # W1: log, skip cycle, never crash

        time.sleep(config_watch.poll_interval_s)

    logger.info("watcher_shutdown_complete")


def _spawn_run(reason: str) -> None:
    """Spawn ``personalscraper run --no-console --trigger-reason <reason>``."""
    cmd = [sys.executable, "-m", "personalscraper", "run", "--no-console",
           "--trigger-reason", reason]
    logger.info("watcher_spawning_run", reason=reason, cmd=cmd)
    subprocess.Popen(cmd)


def _spawn_cross_seed(info_hash: str) -> None:
    """Spawn ``personalscraper cross-seed --hash <H>``."""
    cmd = [sys.executable, "-m", "personalscraper", "cross-seed", "--hash", info_hash]
    logger.info("watcher_spawning_cross_seed", info_hash=info_hash, cmd=cmd)
    subprocess.Popen(cmd)


def _get_seed_pure_hashes(completed_torrents) -> set[str]:
    """Extract info-hashes of SEED_PURE-tagged completed torrents."""
    # Reuse core/tags.py SEED_PURE constant
    from personalscraper.core.tags import SEED_PURE
    return {t.info_hash for t in completed_torrents if SEED_PURE in (t.tags or set())}


def _record_success(state, now, store) -> WatcherState:
    """Record a successful run fire and reset backoff."""
    try:
        store.set_last_successful_run_at(now)
    except Exception:
        logger.warning("watcher_state_persist_failed", exc_info=True)
    return WatcherState(
        debounce_until=state.debounce_until,
        last_successful_run_at=now,
        backoff_multiplier=0,
    )
```

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
```

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
