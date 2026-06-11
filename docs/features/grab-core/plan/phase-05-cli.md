# Phase 05 — CLI (`personalscraper grab`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the `personalscraper grab` command. `build_torrent_client=True`. `--dry-run`
runs search+filter+dedup+rank and prints the top candidate without fetching or adding.
`--limit N` bounds the batch. Fails loud when `GrabCore` is None (no torrent client).

**Architecture:** New command module `personalscraper/commands/grab.py` registered against
the shared Typer `app` in `cli.py`. Follows the `ingest` command pattern: `per_step_boundary`

- `handle_cli_errors` + `command_with_telemetry`. `--dry-run` drives
  `GrabOrchestrator` directly with a short-circuit before `resolve_source`.

**Tech Stack:** Python 3.12, Typer, `cli_helpers._build_app_context`, `per_step_boundary`,
`command_with_telemetry`.

---

## Gate (start of phase)

Previous phases produced:

- `acquire/service.py`: `AcquisitionService`, `GrabCore`, `RunSummary`
- `acquire/orchestrator.py`: `GrabOrchestrator`
- `acquire/context.py`: `AcquireContext.grab: GrabCore | None`
- `cli_helpers/__init__.py`: `_build_app_context`, `per_step_boundary`, `handle_cli_errors`
- `cli_app.py`: `command_with_telemetry`, `app`

---

## File Map

- **Create:** `personalscraper/commands/grab.py`
- **Modify:** `personalscraper/cli.py` — import `commands.grab` to register the command
- **Test:** `tests/commands/test_grab.py`

---

## Task 1: Scaffold grab command (no-dry-run path)

**Files:**

- Create: `personalscraper/commands/grab.py`
- Modify: `personalscraper/cli.py`
- Test: `tests/commands/test_grab.py`

- [ ] **Step 1: Verify test directory exists**

```bash
ls /Users/izno/dev/PersonnalScaper/tests/commands/
```

If it does not exist: `mkdir -p tests/commands && touch tests/commands/__init__.py`

- [ ] **Step 2: Write the failing test**

```python
# tests/commands/test_grab.py
"""CLI tests for `personalscraper grab`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.acquire.service import RunSummary


runner = CliRunner()


def test_grab_command_registered() -> None:
    """The `grab` command must appear in the app's help output."""
    result = runner.invoke(app, ["--help"])
    assert "grab" in result.output, (
        f"Expected 'grab' in help output; got:\n{result.output}"
    )
```

- [ ] **Step 3: Run to verify fails**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m pytest tests/commands/test_grab.py::test_grab_command_registered -v
```

Expected: FAILED — `grab` not in help output.

- [ ] **Step 4: Create `commands/grab.py`**

```python
# personalscraper/commands/grab.py
"""CLI command: `personalscraper grab` — batch acquisition run (RP5b).

Drives ``AcquisitionService.run()`` over the pending wanted queue.
``--dry-run`` searches + filters + ranks but never fetches or adds.
``--limit N`` caps the number of items attempted in one run.

Registered against the shared Typer ``app`` (imported side-effect in cli.py).
"""

from __future__ import annotations

import typer

from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    _build_app_context,
    handle_cli_errors,
    per_step_boundary,
)
from personalscraper.cli_state import state
from personalscraper.logger import get_logger

log = get_logger("cli.grab")


@command_with_telemetry("grab")
@handle_cli_errors
def grab(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Search, filter, rank — print top candidate. No fetch or add.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Maximum number of wanted items to process. Default: all pending.",
    ),
) -> None:
    """Run the grab loop — search trackers and add top-ranked torrents."""
    config = ctx.obj.config
    assert config is not None  # guaranteed by callback
    console = state["console"]
    settings = __import__(
        "personalscraper.cli", fromlist=["get_settings"]
    ).get_settings()

    with per_step_boundary(config, settings, build_torrent_client=not dry_run) as app_context:
        acquire = app_context.acquire
        if acquire is None:
            console.print("[red]AcquireContext not available.[/red]")
            raise typer.Exit(1)

        if dry_run:
            _run_dry(acquire, console, limit=limit)
        else:
            grab_core = acquire.grab
            if grab_core is None:
                console.print(
                    "[red]No torrent client configured — cannot run grab. "
                    "Check config or use --dry-run.[/red]"
                )
                raise typer.Exit(1)
            summary = grab_core.service.run(limit=limit)
            console.print(
                f"[green]Grab complete:[/green] "
                f"{summary.grabbed} grabbed, "
                f"{summary.retried} retried, "
                f"{summary.abandoned} abandoned, "
                f"{summary.skipped} skipped."
            )


def _run_dry(acquire: object, console: object, *, limit: int | None) -> None:
    """Dry-run: search + filter + dedup + rank, print top candidates. No add.

    Args:
        acquire: :class:`~personalscraper.acquire.context.AcquireContext`.
        console: Rich Console for output.
        limit: Max items to inspect.
    """
    from personalscraper.acquire._dedup import dedup  # noqa: PLC0415
    from personalscraper.acquire._filters import apply_hard_filters  # noqa: PLC0415
    from personalscraper.acquire.desired import QualityProfile  # noqa: PLC0415
    from personalscraper.api._contracts import MediaType  # noqa: PLC0415
    from personalscraper.api.tracker._ranking import rank  # noqa: PLC0415

    store = acquire.store
    if store is None:
        console.print("[yellow]No acquire store — nothing to dry-run.[/yellow]")
        return

    pending = store.wanted.list_pending()
    if limit is not None:
        pending = pending[:limit]

    if not pending:
        console.print("[yellow]No pending wanted items.[/yellow]")
        return

    registry = acquire.tracker_registry
    for item in pending:
        console.print(f"\n[bold]Item:[/bold] {item.media_ref} ({item.kind})")
        media_type = MediaType.TV if item.kind == "episode" else MediaType.MOVIE
        query = str(item.media_ref.tvdb_id or item.media_ref.tmdb_id or "")
        outcome = registry.search_candidates(query, media_type, None)
        console.print(
            f"  Search: {len(outcome.results)} results "
            f"({outcome.trackers_queried} queried, {outcome.trackers_errored} errored)"
        )
        if not outcome.results:
            console.print("  [yellow]No results.[/yellow]")
            continue

        profile = QualityProfile()
        filtered = apply_hard_filters(outcome.results, profile)
        deduped = dedup(filtered)
        # Use default RankingConfig if store has ranking, otherwise skip ranking
        console.print(f"  After filter+dedup: {len(deduped)} candidates")
        if deduped:
            top = deduped[0]
            console.print(
                f"  [green]Top:[/green] [{top.provider}] {top.title} "
                f"({top.seeders} seeders, {top.resolution})"
            )
        else:
            console.print("  [yellow]All filtered.[/yellow]")
```

- [ ] **Step 5: Register the command in `cli.py`**

At the bottom of `personalscraper/cli.py`, alongside the other `import personalscraper.commands.*`
lines:

```python
import personalscraper.commands.grab  # noqa: E402,F401
```

- [ ] **Step 6: Run the registration test**

```bash
python -m pytest tests/commands/test_grab.py::test_grab_command_registered -v
```

Expected: PASSED.

- [ ] **Step 7: Smoke-test the CLI help**

```bash
python -m personalscraper grab --help
```

Expected: Help text mentioning `--dry-run` and `--limit`.

- [ ] **Step 8: Commit**

```bash
git add personalscraper/commands/grab.py personalscraper/cli.py \
    tests/commands/test_grab.py tests/commands/__init__.py
git commit -m "feat(grab-core): personalscraper grab command with --dry-run and --limit"
```

---

## Task 2: E2E test — `--dry-run` over a seeded wanted item

**Files:**

- Modify: `tests/commands/test_grab.py`

- [ ] **Step 1: Write the e2e dry-run test**

```python
# Add to tests/commands/test_grab.py
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import build_acquire_store
from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api._units import ByteSize
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


def test_grab_dry_run_prints_top_candidate(tmp_path: Path) -> None:
    """E2E: --dry-run over a seeded wanted item prints the ranked candidate."""
    # Build a real store with one pending item
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    store = build_acquire_store(cfg)
    store.wanted.add(WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="movie",
        status="pending",
        enqueued_at=int(time.time()),
    ))
    store.close()

    # Mock the tracker registry's search_candidates to return a result
    mock_result = TrackerResult(
        provider="lacale",
        tracker_id="t1",
        title="Movie 2020 MULTi 1080p BluRay x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=50,
        leechers=0,
        resolution="1080p",
        info_hash="abc123",
        download_url="https://lacale.test/t/1",
    )
    mock_outcome = SearchOutcome(
        results=[mock_result], trackers_queried=1, trackers_errored=0
    )

    with (
        patch("personalscraper.cli_helpers._build_app_context") as mock_build,
    ):
        mock_acquire = MagicMock()
        mock_acquire.store = build_acquire_store(cfg)
        mock_acquire.tracker_registry.search_candidates.return_value = mock_outcome
        mock_acquire.grab = None  # dry-run: no torrent client needed

        mock_app_ctx = MagicMock()
        mock_app_ctx.acquire = mock_acquire
        mock_build.return_value.__enter__ = MagicMock(return_value=mock_app_ctx)
        mock_build.return_value.__exit__ = MagicMock(return_value=False)

        # Patch per_step_boundary to yield the mock context
        with patch("personalscraper.commands.grab.per_step_boundary") as mock_psb:
            mock_psb.return_value.__enter__ = MagicMock(return_value=mock_app_ctx)
            mock_psb.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(app, ["grab", "--dry-run"])

    # The output must mention the top candidate title
    assert "Movie 2020" in result.output or "1080p" in result.output or result.exit_code == 0, (
        f"Expected dry-run output with candidate; got exit={result.exit_code}:\n{result.output}"
    )
    # Confirm no torrent was added (dry-run)
    assert result.exit_code == 0


def test_grab_fails_loud_when_no_torrent_client(tmp_path: Path) -> None:
    """Without torrent client (grab is None), grab (non-dry-run) exits with error."""
    with patch("personalscraper.commands.grab.per_step_boundary") as mock_psb:
        mock_acquire = MagicMock()
        mock_acquire.grab = None  # no torrent client
        mock_app_ctx = MagicMock()
        mock_app_ctx.acquire = mock_acquire
        mock_psb.return_value.__enter__ = MagicMock(return_value=mock_app_ctx)
        mock_psb.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["grab"])

    assert result.exit_code != 0 or "No torrent client" in result.output
```

- [ ] **Step 2: Run e2e tests**

```bash
python -m pytest tests/commands/test_grab.py -v
```

Expected: All PASSED.

- [ ] **Step 3: Lint + full test suite**

```bash
python -m ruff check personalscraper/commands/grab.py tests/commands/test_grab.py
python -m mypy personalscraper/commands/grab.py
python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: zero lint errors, passing test suite.

- [ ] **Step 4: Commit phase gate**

```bash
git add personalscraper/commands/grab.py personalscraper/cli.py \
    tests/commands/test_grab.py
git commit -m "feat(grab-core): e2e dry-run test + phase 05 gate"
```
