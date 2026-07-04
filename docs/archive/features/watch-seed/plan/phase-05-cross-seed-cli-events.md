# Phase 5 — Cross-seed CLI + events

## Gate

- **Requires Phase 4**: `CrossSeedService` is built inside `_build_app_context` and exposed on the acquire context. The service's `check()` and `sweep()` methods are functional and tested.
- **Produces for Phase 7**: The `cross-seed --sweep` and `cross-seed --hash` CLI commands that the Watcher daemon's watch loop spawns as subprocesses (W5). Also the `CrossSeedInjected` / `CrossSeedRejected` events that subscribers can consume.

## Overview

Register the `cross-seed` Typer command group on the top-level CLI. Two subcommands: `--sweep` (throttled back-catalog) and `--hash <H>` (single-torrent). The commands build an `AppContext`, extract the `CrossSeedService`, and call its methods. Add `CrossSeedInjected` and `CrossSeedRejected` event dataclasses to `acquire/events.py` (frozen kw_only dataclasses over `Event`).

### Sub-phases (4 commits)

| #   | Commit                                                                 | Scope     |
| --- | ---------------------------------------------------------------------- | --------- |
| 5.1 | `feat(watch-seed): add CrossSeedInjected and CrossSeedRejected events` | Events    |
| 5.2 | `feat(watch-seed): register cross-seed --sweep CLI command`            | CLI sweep |
| 5.3 | `feat(watch-seed): register cross-seed --hash CLI command`             | CLI hash  |
| 5.4 | `test(watch-seed): add CLI tests for cross-seed commands`              | CLI tests |

## Sub-phase 5.1 — cross-seed events

**Files:**

- Modify: `personalscraper/acquire/events.py` (two new frozen kw_only dataclasses over `Event`)
- Modify: `personalscraper/acquire/cross_seed.py` (ctor extension + emission)
- Modify: `personalscraper/acquire/_factory.py` (bus wiring)
- Modify: `personalscraper/events/__init__.py` (hub re-exports)
- Modify: `tests/fixtures/event_samples.py` (sample factories)
- Modify: `tests/acquire/test_acquire_events.py` (parametrized entries)

Follow the existing pattern of frozen kw_only dataclasses over `core.event_bus.Event`:

```python
@dataclass(frozen=True, kw_only=True)
class CrossSeedInjected(Event):
    """Emitted when a cross-seed torrent is successfully injected + verified.

    Attributes:
        info_hash: The info-hash of the injected torrent.
        source_tracker: The tracker the .torrent was fetched from (target).
        source_hash: The info-hash of the original (source) torrent.
        save_path: Absolute path to the data directory used as savepath.
    """

    info_hash: str
    source_tracker: str
    source_hash: str
    save_path: str


@dataclass(frozen=True, kw_only=True)
class CrossSeedRejected(Event):
    """Emitted when a candidate is rejected before injection.

    Attributes:
        info_hash: The info-hash of the CANDIDATE .torrent (not the source).
        tracker: The tracker the candidate was fetched from.
        reason: Human-readable rejection reason
            (e.g. "structural_mismatch: root_name", "fetch_failed: 401").
        source_hash: The info-hash of the source torrent.
    """

    info_hash: str
    tracker: str
    reason: str
    source_hash: str
```

**Ctor extension (PLAN CLARIFICATION):** The Phase 4 service has no event bus.
`CrossSeedService.__init__` is extended with `event_bus: EventBus | None = None`
(keyword-only, default `None` → no emission). The bus is wired in
`_factory.py` where `event_bus` is already available. Emission follows the
`AcquisitionService` emit-after-persist convention:

- `CrossSeedInjected` is emitted AFTER the obligation write.
- `CrossSeedRejected` is emitted at each rejection point (fetch_failed,
  magnet_not_supported, parse_failed, structural mismatch, recheck_failed).

## Sub-phase 5.2 — cross-seed --sweep CLI command

**Files:**

- Create: `personalscraper/commands/cross_seed.py`
- Modify: `personalscraper/cli.py` (import list)

**IMPLEMENTATION NOTE (2026-07-02):** The snippets below were STALE and have been
replaced by the actual implementation. Key corrections vs the original plan:

- `_build_app_context()` takes `(config, settings, *, build_torrent_client=...)`
  — it is NOT a zero-arg factory. Use `per_step_boundary(config, settings,
build_torrent_client=True)` for the context-manager pattern that sibling
  acquire commands (`grab`, `seed`) follow.
- The cross-seed service handle lives at `app_context.acquire.cross_seed`
  (`AcquireContext` field), not `ctx.cross_seed_service`.
- The command is a `@command_with_telemetry("cross-seed")` top-level entry,
  registered via import side-effect in `cli.py`, matching the `grab` command
  pattern (single command with options, NOT a sub-group like `seed`/`follow`).
- `--hash` is deferred to sub-phase 5.3 for minimal diff.
- No `pipeline.lock` — cross-seed touches only qBittorrent + acquire.db.

See the actual file `personalscraper/commands/cross_seed.py` for the
authoritative implementation.

## Sub-phase 5.3 — cross-seed --hash CLI command

**Files:**

- Modify: `personalscraper/commands/cross_seed.py` (add `run_hash()`)

```python
def run_hash(info_hash: str) -> None:
    """Cross-seed a single torrent by info-hash (X1 per-completion path).

    This is the form the Watcher daemon spawns per completion (W5) and
    the operator's manual entry point.  Idempotent — re-running the same
    hash is a no-op (recently-searched guard).
    """
    ctx = _build_app_context()
    cs = ctx.cross_seed_service
    result = cs.check(info_hash)
    for inj_hash in result.injected:
        logger.info("cross_seed_injected", info_hash=inj_hash)
    for rej_hash, tracker, reason in result.rejected:
        logger.info("cross_seed_rejected", info_hash=rej_hash, tracker=tracker, reason=reason)
    if result.skipped:
        logger.info("cross_seed_skipped", info_hash=info_hash)
```

Events (`CrossSeedInjected`, `CrossSeedRejected`) are emitted by `CrossSeedService.check()` internally — the CLI layer just logs the structured result.

## Sub-phase 5.4 — CLI tests

**Files:**

- Create: `tests/commands/test_cross_seed_cli.py`

CLI tests must patch `load_config` (project memory: CI has no `config/`):

```python
"""CLI tests for personalscraper cross-seed commands."""

from unittest.mock import patch

from personalscraper.cli import app as cli_app
from typer.testing import CliRunner


runner = CliRunner()


@patch("personalscraper.conf.loader.load_config")
@patch("personalscraper.acquire.cross_seed.CrossSeedService.sweep")
def test_cross_seed_sweep_exits_zero(mock_sweep, mock_config, test_config):
    mock_config.return_value = test_config
    mock_sweep.return_value = type("SweepResult", (), {"checked": 0, "injected": 0, "quota_exhausted": False})()
    result = runner.invoke(cli_app, ["cross-seed", "--sweep"])
    assert result.exit_code == 0


@patch("personalscraper.conf.loader.load_config")
@patch("personalscraper.acquire.cross_seed.CrossSeedService.check")
def test_cross_seed_hash_exits_zero(mock_check, mock_config, test_config):
    mock_config.return_value = test_config
    mock_check.return_value = type("CrossSeedResult", (), {"injected": [], "rejected": [], "skipped": False})()
    result = runner.invoke(cli_app, ["cross-seed", "--hash", "abc123"])
    assert result.exit_code == 0


@patch("personalscraper.conf.loader.load_config")
def test_cross_seed_no_args_exits_two(mock_config, test_config):
    mock_config.return_value = test_config
    result = runner.invoke(cli_app, ["cross-seed"])
    assert result.exit_code == 2  # Typer missing-option exit


def test_cross_seed_help_shows_options():
    """ACC-5: --sweep and --hash are documented."""
    result = runner.invoke(cli_app, ["cross-seed", "--help"])
    assert result.exit_code == 0
    assert "--sweep" in result.stdout
    assert "--hash" in result.stdout
```

## Gate check (before advancing to Phase 6)

- [ ] `make lint` — 0 errors.
- [ ] `personalscraper cross-seed --help >/dev/null 2>&1 && echo OK` (ACC-5).
- [ ] `python -m pytest tests/unit/commands/test_cross_seed_cli.py -q` — all pass.
- [ ] `python -c "from personalscraper.acquire.events import CrossSeedInjected, CrossSeedRejected"` — both importable.
- [ ] `tests/architecture/test_layering.py` stays green (CLI module in `commands/` may import `acquire/` — that's downward per architecture).
- [ ] AppContext boundary: `commands/cross_seed.py` must be added to `test_app_context_boundary.py` allowlist — its `run_sweep`/`run_hash` functions receive `AppContext` via `_build_app_context()`.
