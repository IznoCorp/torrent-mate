# Phase 8 — CLI (`personalscraper trailers …`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §3 Key Decision §3 (standalone CLI). Create
`personalscraper/trailers/cli.py` with subcommands `scan`, `download`, `verify`, `purge`
and wire as `personalscraper trailers` typer sub-app in `personalscraper/cli.py`.
Implement the full filter set (`--disk DISK_N` matching the existing `Disk1-4` convention
from `cli.py:545+`, `--category`, `--since`, `--limit`, `--dry-run`, `--no-refresh`,
`--include-state`, `--verbose`). Tests use `typer.testing.CliRunner`.

**Architecture:** `trailers_app = typer.Typer()` in `cli.py` (trailers module), mounted
as a typer sub-app in the main `personalscraper/cli.py`. Each subcommand loads
`TrailersConfig` from `personalscraper.conf.models.Config.trailers` (the schema frozen in
Phase 7), then calls `TrailersOrchestrator` or a dedicated helper (for `verify` / `purge`).
Progress reporting uses `rich.progress.Progress` + `rich.table.Table`, matching existing
CLI conventions. Logging goes through `personalscraper.logger.get_logger` (structlog), not
stdlib `logging`.

**Tech Stack:** Python, `typer`, `typer.testing.CliRunner`, `rich`, `structlog`, `pytest`,
`ruff`, `mypy`.

---

## Gate (entry condition)

Phases 6 and 7 must both be complete. Phase 7 locks in `cfg.trailers.*`; this phase consumes
it directly at runtime (no `MagicMock` masking).

```bash
python -c "from personalscraper.trailers.orchestrator import TrailersOrchestrator; print('OK')"
python -c "from personalscraper.conf.models import TrailersConfig; print('OK')"
```

---

## Dependencies

- Phase 6 (`TrailersOrchestrator`, `Scanner` — CLI delegates to these).
- Phase 7 (`TrailersConfig` — CLI reads `cfg.trailers.enabled`, `cfg.trailers.state_file`,
  `cfg.trailers.library_scan_max_age_hours`, etc. at runtime).

---

## Invariants for this phase

- `scan` is always a dry-run (never downloads).
- Re-running `download` on a clean library is a no-op (idempotent via `trailer_exists`).
- All subcommands call `state_store.auto_gc()` at the start (via orchestrator init).
- Existing CLI tests in `tests/test_cli.py` remain green.
- `--disk` values match the existing convention (`Disk1`, `Disk2`, `Disk3`, `Disk4`) —
  tests MUST use these, not `disk_a` / `disk_b` placeholders.
- Non-zero exit codes on `error > 0` (propagated from orchestrator counts). `0` on success,
  `1` on any error count, `2` on argument / config errors. Tests assert these codes
  explicitly, not only "exit_code == 0".

---

## Sub-phase 8.1 — `trailers/cli.py` skeleton + `scan` subcommand

### Files

| Action | Path                              | Responsibility                     |
| ------ | --------------------------------- | ---------------------------------- |
| Create | `personalscraper/trailers/cli.py` | Typer sub-app with all subcommands |
| Modify | `personalscraper/cli.py`          | Mount `trailers` sub-app           |
| Create | `tests/trailers/test_cli.py`      | CLI tests using CliRunner          |

### Step 1: Write failing tests

Create `tests/trailers/test_cli.py`:

```python
"""CLI tests for 'personalscraper trailers *' subcommands.

Uses typer.testing.CliRunner. All orchestrator/scanner calls are mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

# Patch targets
_PATCH_LOAD_CONFIG = "personalscraper.cli.load_config"
_PATCH_ORCH = "personalscraper.trailers.cli.TrailersOrchestrator"
_PATCH_SCANNER = "personalscraper.trailers.cli.Scanner"


def _fake_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.library_scan_max_age_hours = 24
    cfg.paths.staging_dir = tmp_path
    cfg.disks = []
    return cfg


class TestTrailersScanCommand:
    def test_scan_exits_zero(self, tmp_path):
        """trailers scan exits 0."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "scan"])
        assert result.exit_code == 0, result.output

    def test_scan_shows_no_items_message(self, tmp_path):
        """trailers scan shows 'No media without trailers found' when clean."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "scan"])
        assert "No media without trailers" in result.output or "0" in result.output

    def test_scan_limit_flag(self, tmp_path):
        """trailers scan --limit 5 is accepted without error."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "scan", "--limit", "5"])
        assert result.exit_code == 0


class TestTrailersDownloadCommand:
    def test_download_exits_zero(self, tmp_path):
        """trailers download exits 0 when orchestrator runs successfully."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_ORCH) as MockOrch,
        ):
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 0, "already_present": 0, "no_trailer": 0,
                "bot_detected": 0, "error": 0, "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = runner.invoke(app, ["trailers", "download"])
        assert result.exit_code == 0, result.output

    def test_download_dry_run_does_not_call_orchestrator(self, tmp_path):
        """trailers download --dry-run shows what would be done without downloading."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_ORCH) as MockOrch,
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "download", "--dry-run"])
        assert result.exit_code == 0
        MockOrch.return_value.run.assert_not_called()

    def test_download_disk_filter_passed_through(self, tmp_path):
        """trailers download --disk Disk1 passes the filter to the scanner (project convention)."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_ORCH) as MockOrch,
        ):
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 0, "already_present": 0, "no_trailer": 0,
                "bot_detected": 0, "error": 0, "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = runner.invoke(app, ["trailers", "download", "--disk", "Disk1"])
        assert result.exit_code == 0


class TestTrailersVerifyCommand:
    def test_verify_exits_zero(self, tmp_path):
        """trailers verify exits 0."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_library.return_value = []
            result = runner.invoke(app, ["trailers", "verify"])
        assert result.exit_code == 0


class TestTrailersPurgeCommand:
    def test_purge_dry_run_exits_zero(self, tmp_path):
        """trailers purge --dry-run exits 0."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch("personalscraper.trailers.cli.TrailerStateStore") as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {}
            result = runner.invoke(app, ["trailers", "purge", "--dry-run"])
        assert result.exit_code == 0

    def test_purge_include_state_flag_accepted(self, tmp_path):
        """trailers purge --include-state is accepted without error."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch("personalscraper.trailers.cli.TrailerStateStore") as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {}
            result = runner.invoke(app, ["trailers", "purge", "--dry-run", "--include-state"])
        assert result.exit_code == 0
```

### Step 2: Implement `personalscraper/trailers/cli.py`

```python
"""CLI commands for the trailers feature.

Sub-app mounted at ``personalscraper trailers`` via typer.

Subcommands:
    scan      — Dry-run: list media missing trailers
    download  — Discover and download missing trailers
    verify    — Audit existing trailers (size, extension)
    purge     — Remove orphan trailers (media parent absent)

Common filters (all subcommands):
    --disk DISK_ID
    --category CATEGORY_ID
    --since YYYY-MM-DD
    --limit N
    --dry-run
    --no-refresh   (skip library cache refresh)
"""

import typer

from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.scanner import Scanner
from personalscraper.trailers.state import TrailerStateStore

app = typer.Typer(name="trailers", help="Trailer acquisition and management commands.")


@app.command()
def scan(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", help="Restrict to one disk by ID."),
    category: str | None = typer.Option(None, "--category", help="Restrict to one category ID."),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    limit: int | None = typer.Option(None, "--limit", help="Max items to scan."),
    no_refresh: bool = typer.Option(False, "--no-refresh", help="Use cached library scan even if stale."),
) -> None:
    """Dry-run: list media items missing trailers."""
    ...  # implementation: scan then print table

@app.command()
def download(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk"),
    category: str | None = typer.Option(None, "--category"),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    limit: int | None = typer.Option(None, "--limit"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_refresh: bool = typer.Option(False, "--no-refresh"),
) -> None:
    """Discover and download missing trailers."""
    ...

@app.command()
def verify(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk"),
    category: str | None = typer.Option(None, "--category"),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    deep: bool = typer.Option(False, "--deep", help="Run ffprobe playability probe (expensive)."),
    no_refresh: bool = typer.Option(False, "--no-refresh"),
) -> None:
    """Audit existing trailers.

    Runs four checks per trailer:

    1. **Existence** — trailer file present at the expected placement path.
    2. **Size** — file size ≥ ``config.trailers.filters.min_file_size_bytes``.
    3. **Extension** — file suffix in ``config.trailers.filters.allowed_extensions``
       (default ``{"mp4", "mkv", "webm"}``).
    4. **Playable** (opt-in, ``--deep``) — ffprobe returns non-zero duration.

    Failures report a category: ``missing``, ``undersized``, ``wrong_extension``,
    ``unplayable``. Exit codes: ``0`` if all pass, ``2`` if any functional check
    fails, ``4`` if a ``--deep`` ffprobe call errors out (probe itself broken).
    """
    ...

@app.command()
def purge(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk"),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    include_state: bool = typer.Option(False, "--include-state",
                                       help="Also wipe orphan state entries."),
) -> None:
    """Remove orphan trailers whose media parent is absent.

    When ``--include-state`` is set, after the filesystem purge completes call
    ``state_store.purge_orphans()`` and log the count in the CLI output.
    """
    ...
```

Fill in each command body with: load config from `ctx.obj.config`, instantiate the right
scanner/orchestrator/state_store, apply filters, call the relevant operation, print a Rich
summary table or plain count to stdout.

**Shared `--since` filter helper:** parse `YYYY-MM-DD` into a `datetime` at UTC midnight,
then drop items whose "added date" is earlier. The added date comes from
`LibraryScanItem` if the field is exposed (check `personalscraper/library/models.py`); if
no such field exists, fall back to `Path(nfo_path).stat().st_mtime` converted to a UTC
datetime. The helper lives in `personalscraper/trailers/cli.py` (module-level) so all four
subcommands share a single implementation, and its unit tests go into
`tests/trailers/test_cli.py` (fake library items with varied mtimes).

**Verify subcommand test scaffold.** Add one test per check category to
`tests/trailers/test_cli.py::TestTrailersVerifyCommand` (mock `Scanner.scan_library` /
filesystem):

- `test_verify_flags_missing_trailer` — trailer path does not exist → exit 2.
- `test_verify_flags_undersized_trailer` — file size below `min_file_size_bytes` → exit 2.
- `test_verify_flags_wrong_extension` — file suffix not in allowed list → exit 2.
- `test_verify_deep_flag_invokes_ffprobe` — `--deep` calls a mocked ffprobe helper;
  non-zero duration returned → exit 0. Exception from ffprobe → exit 4.

### Step 3: Mount sub-app in `personalscraper/cli.py`

Find the main `app = typer.Typer(...)` declaration and add:

```python
from personalscraper.trailers.cli import app as trailers_app
app.add_typer(trailers_app, name="trailers")
```

### Step 4: Run tests

```bash
pytest tests/trailers/test_cli.py -v
```

### Step 5: Commit sub-phase 8.1

```bash
git add \
  personalscraper/trailers/cli.py \
  personalscraper/cli.py \
  tests/trailers/test_cli.py
git commit -m "feat(trailer): add trailers CLI sub-app with scan, download, verify, purge"
```

---

## Sub-phase 8.2 — Wire top-level `run` flags

Extend `personalscraper run` (in `personalscraper/cli.py`) to accept:

- `--skip-trailers` (bool flag) — passed to `Pipeline(..., skip_trailers=True)`; causes
  `run_trailers()` to return a skipped `StepReport`.
- `--continue-on-trailer-error` (bool flag) — passed to
  `Pipeline(..., continue_on_trailer_error=True)`; when True, a trailers step error does not
  abort dispatch.

Both flags default to their `config.trailers.pipeline.{skip,continue_on_error}` values if
set, falling back to `False`. The default values flow through the config layer so the
operator can flip them permanently via `config.json5` without re-invoking cron scripts.

### Files

| Action | Path                     | Responsibility                                      |
| ------ | ------------------------ | --------------------------------------------------- |
| Modify | `personalscraper/cli.py` | Add two flags to the top-level `run` command        |
| Modify | `tests/test_cli.py`      | Cover both flags (accept + passthrough to Pipeline) |

### Step 1: Add the two flags to the `run` command

In the existing `run()` function (or equivalent) of `personalscraper/cli.py`, add:

```python
skip_trailers: bool = typer.Option(
    False,
    "--skip-trailers",
    help="Skip the trailers pipeline step for this invocation.",
),
continue_on_trailer_error: bool = typer.Option(
    False,
    "--continue-on-trailer-error",
    help="Do not abort dispatch when the trailers step crashes.",
),
```

Forward both values into the `Pipeline(...)` constructor call (the corresponding kwargs
were added in Phase 5 sub-phase 5.2). Read defaults from
`config.trailers.pipeline.skip` / `config.trailers.pipeline.continue_on_error` when the CLI
flag was not provided — if these sub-keys are absent in the Pydantic model at this point,
treat the default as `False` and note the follow-up for Phase 7 (add a
`TrailersPipelineConfig` nested model with `skip: bool = False` and
`continue_on_error: bool = False`).

### Step 2: CLI tests

Add to `tests/test_cli.py` (or wherever `personalscraper run` is tested):

- `test_run_accepts_skip_trailers` — `runner.invoke(app, ["run", "--skip-trailers", …])`
  exits 0 and the patched `Pipeline` was called with `skip_trailers=True`.
- `test_run_accepts_continue_on_trailer_error` — same shape for the other flag.

### Step 3: Commit sub-phase 8.2

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "feat(trailer): add --skip-trailers and --continue-on-trailer-error run flags"
```

---

## Phase 8 quality gate

- [ ] `pytest tests/trailers/test_cli.py -q` — all green
- [ ] `pytest tests/test_cli.py -q` — no regressions in main CLI tests
- [ ] `python -m ruff check personalscraper/trailers/cli.py personalscraper/cli.py` — no errors
- [ ] `python -m mypy personalscraper/trailers/cli.py` — no type errors
- [ ] `python -m personalscraper trailers --help` — prints help without error

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/trailers/test_cli.py -q
pytest tests/test_cli.py -q
python -m ruff check personalscraper/trailers/cli.py personalscraper/cli.py
python -m mypy personalscraper/trailers/cli.py
python -m personalscraper trailers --help
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 08 gate — trailers CLI wired with full filter set"
```

## Exit condition for Phase 9

Phase 9 may start only when:

- `personalscraper trailers --help` prints the subcommand list
- All CLI tests pass (no regressions in `tests/test_cli.py`)
- The milestone commit is on the branch
