# Phase 3 — DETECT logic + `follow detect` CLI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add `@follow_app.command("detect")` to `commands/follow.py`. The command calls `list_active` → `poll_aired` → ownership filter → dedup → `store.wanted.add` + emit `WantedEnqueued`. Flags: `--dry-run` (no writes/emits), `--series` (filter active set). Rich table output. Tests: criteria 5-6, 8 (boundary), 9 (layering).

**Architecture:** All logic in one command function; no separate module. Reuses `per_step_boundary(build_torrent_client=False)` exactly like `follow list`. `poll_aired` and `ownership.owns` are fail-soft (log + continue). `now` is injected via `int(time.time())` at the call site for testability (tests stub `time.time`).

**Tech Stack:** Python 3.11+, `typer`, `rich`, `pytest`, `unittest.mock`, `make test`

---

## Gate

Phase 2 must be complete:

- [ ] `personalscraper/acquire/_ports.py` `WantedSubStore` protocol has `find`.
- [ ] `personalscraper/acquire/store.py` `_WantedSubStore` implements `find`.
- [ ] `pytest tests/acquire/test_store_wanted_find.py` passes with 0 failures.

---

## Sub-phase 3.1 — `follow detect` command

**Files:**

- Modify: `personalscraper/commands/follow.py`
- Create: `tests/commands/test_follow_detect.py`

### Task 1: Write failing tests first (TDD)

- [ ] **Step 1: Create `tests/commands/test_follow_detect.py` with golden + dry-run tests**

```python
"""Tests for `follow detect` command (criteria 5-6, 8-9)."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, WantedItem
from personalscraper.core.identity import MediaRef


def _fs(followed_id: int = 1, tvdb_id: int = 99) -> FollowedSeries:
    return FollowedSeries(
        id=followed_id,
        media_ref=MediaRef(tvdb_id=tvdb_id),
        title="Test Show",
        added_at=1_000_000,
        active=True,
    )


def _ep(tvdb_id: int = 99, season: int = 1, ep: int = 1) -> AiredEpisode:
    return AiredEpisode(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        season=season,
        episode=ep,
        air_date=date(2024, 1, 1),
        title="Episode Title",
    )


def _make_ctx(series: list[FollowedSeries], aired: list[AiredEpisode], owned: bool = False,
              existing: WantedItem | None = None):
    """Build a minimal stub AppContext for follow detect tests."""
    store = MagicMock()
    store.follow.list_active.return_value = series
    store.wanted.find.return_value = existing
    store.wanted.add.return_value = 42

    ownership = MagicMock()
    ownership.owns.return_value = owned

    registry = MagicMock()

    acquire = MagicMock()
    acquire.store = store
    acquire.ownership = ownership
    acquire.provider_registry = registry

    bus = MagicMock()
    app_context = MagicMock()
    app_context.acquire = acquire
    app_context.event_bus = bus
    return app_context, store, bus


def _run_detect(app_context, aired_eps: list[AiredEpisode], dry_run: bool = False, series_filter: str | None = None):
    """Drive follow_detect with patched dependencies."""
    from personalscraper.commands.follow import follow_detect

    with (
        patch("personalscraper.commands.follow.per_step_boundary") as mock_boundary,
        patch("personalscraper.commands.follow.poll_aired", return_value=aired_eps),
        patch("personalscraper.commands.follow.int") as mock_int,
    ):
        mock_boundary.return_value.__enter__ = MagicMock(return_value=app_context)
        mock_boundary.return_value.__exit__ = MagicMock(return_value=False)
        mock_int.return_value = 2_000_000  # injected 'now'

        ctx = MagicMock()
        ctx.obj.config = MagicMock()

        follow_detect(ctx, dry_run=dry_run, series=series_filter)


def test_detect_golden_enqueues_uowned_episode():
    """GOLDEN: non-owned, non-dup episode → add() called once, WantedEnqueued emitted once."""
    from personalscraper.acquire.events import WantedEnqueued

    fs = _fs(followed_id=1, tvdb_id=99)
    ep = _ep(tvdb_id=99, season=1, ep=1)
    app_context, store, bus = _make_ctx([fs], [ep], owned=False, existing=None)

    _run_detect(app_context, [ep])

    store.wanted.add.assert_called_once()
    added: WantedItem = store.wanted.add.call_args[0][0]
    assert added.followed_id == 1
    assert added.kind == "episode"
    assert added.status == "pending"
    assert added.season == 1
    assert added.episode == 1

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedEnqueued)
    assert emitted.season == 1
    assert emitted.episode == 1


def test_detect_skips_owned_episode():
    """owned=True → add() NOT called, WantedEnqueued NOT emitted."""
    fs = _fs()
    ep = _ep()
    app_context, store, bus = _make_ctx([fs], [ep], owned=True)

    _run_detect(app_context, [ep])

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_skips_duplicate_episode():
    """existing row found by find() → add() NOT called, WantedEnqueued NOT emitted."""
    fs = _fs()
    ep = _ep()
    existing = WantedItem(
        media_ref=MediaRef(tvdb_id=99), kind="episode", status="pending", enqueued_at=1_000_000,
        followed_id=1, season=1, episode=1,
    )
    app_context, store, bus = _make_ctx([fs], [ep], owned=False, existing=existing)

    _run_detect(app_context, [ep])

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_dry_run_no_writes_no_emits():
    """--dry-run: add() NOT called, bus.emit NOT called regardless of eligibility."""
    fs = _fs()
    ep = _ep()
    app_context, store, bus = _make_ctx([fs], [ep], owned=False, existing=None)

    _run_detect(app_context, [ep], dry_run=True)

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_empty_active_set_no_crash():
    """Empty active followed set → no crash, no adds, no emits."""
    app_context, store, bus = _make_ctx([], [])

    _run_detect(app_context, [])

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_boundary_no_grab_calls():
    """BOUNDARY (criterion 8): detect makes zero grab calls."""
    fs = _fs()
    ep = _ep()
    app_context, store, bus = _make_ctx([fs], [ep])

    _run_detect(app_context, [ep])

    # The grab orchestrator must never be touched
    assert not app_context.acquire.grab.called if hasattr(app_context.acquire, "grab") else True


def test_detect_layering_no_indexer_import():
    """LAYERING (criterion 9): commands/follow.py must not import indexer."""
    import ast
    import pathlib

    src = pathlib.Path("personalscraper/commands/follow.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in getattr(node, "names", [])]
            module = getattr(node, "module", "") or ""
            assert "indexer" not in module, f"Forbidden indexer import: {module}"
            for n in names:
                assert "indexer" not in n, f"Forbidden indexer import: {n}"
```

- [ ] **Step 2: Confirm tests FAIL (command not yet defined)**

```bash
pytest tests/commands/test_follow_detect.py -v 2>&1 | head -20
```

Expected: `ImportError` or `AttributeError` — `follow_detect` does not exist yet.

### Task 2: Implement `follow_detect` in `commands/follow.py`

- [ ] **Step 3: Add required imports to `follow.py`** (after existing imports)

```python
from datetime import date

from personalscraper.acquire.airing import poll_aired
from personalscraper.acquire.desired import cadence_from_config, cadence_from_json, effective_cadence
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import WantedEnqueued
from rich.table import Table
```

Note: `Table` and `Console` are likely already imported. Add only what is missing.

- [ ] **Step 4: Add the `follow_detect` command before `_root_app.add_typer`**

```python
@follow_app.command("detect")
@handle_cli_errors
def follow_detect(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing or emitting."),
    series: Optional[str] = typer.Option(None, "--series", help="Filter active set by title substring or followed_id."),
) -> None:
    """Detect aired episodes for followed series and enqueue them as wanted items.

    For each active followed series, polls aired episodes via the calendar
    provider (RP9), skips owned episodes (RP6) and duplicates already in the
    wanted queue, then enqueues the remainder as WantedItem(kind='episode',
    status='pending') and emits WantedEnqueued per enqueue.

    Use --dry-run to preview without any writes or events.
    Use --series to restrict detection to a single series (title substring or row ID).
    """
    config = ctx.obj.config
    assert config is not None
    console: Console = state["console"]
    settings = cli_compat.get_settings()

    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        acquire = app_context.acquire
        if acquire is None or acquire.store is None:
            console.print("[red]AcquireContext/store not available.[/red]")
            raise typer.Exit(1)

        store = acquire.store
        bus = app_context.event_bus
        registry = acquire.provider_registry
        ownership = acquire.ownership
        today = date.today()
        now = int(time.time())

        active = store.follow.list_active()
        if not active:
            console.print("[yellow]No active followed series.[/yellow]")
            return

        # Optional filter: title substring or integer followed_id.
        if series is not None:
            try:
                filter_id = int(series)
                active = [s for s in active if s.id == filter_id]
            except ValueError:
                active = [s for s in active if series.lower() in s.title.lower()]

        table = Table(title="Follow Detect", show_header=True)
        table.add_column("Series")
        table.add_column("Season", justify="right")
        table.add_column("Episode", justify="right")
        table.add_column("AirDate")
        table.add_column("Title")
        table.add_column("Action")

        enqueued_count = skipped_owned = skipped_dup = 0

        for fs in active:
            try:
                episodes = poll_aired(fs, registry, today=today)
            except Exception as exc:  # noqa: BLE001 — fail-soft per series
                log.warning("cli.follow.detect.poll_failed", series=fs.title, error=str(exc))
                continue

            for ep in episodes:
                # Ownership check (fail-soft: error → treat as not-owned).
                try:
                    owned = ownership.owns(ep.media_ref, kind="episode", season=ep.season, episode=ep.episode)
                except Exception as exc:  # noqa: BLE001
                    log.warning("cli.follow.detect.ownership_error", error=str(exc))
                    owned = False

                if owned:
                    table.add_row(fs.title, str(ep.season), str(ep.episode), str(ep.air_date), ep.title, "[yellow]skipped-owned[/yellow]")
                    skipped_owned += 1
                    continue

                # Dedup check.
                assert fs.id is not None
                dup = store.wanted.find(followed_id=fs.id, kind="episode", season=ep.season, episode=ep.episode)
                if dup is not None:
                    table.add_row(fs.title, str(ep.season), str(ep.episode), str(ep.air_date), ep.title, "[dim]skipped-dup[/dim]")
                    skipped_dup += 1
                    continue

                action = "[dim]dry-run[/dim]" if dry_run else "[green]enqueued[/green]"
                table.add_row(fs.title, str(ep.season), str(ep.episode), str(ep.air_date), ep.title, action)
                enqueued_count += 1

                if not dry_run:
                    item = WantedItem(
                        media_ref=ep.media_ref,
                        kind="episode",
                        status="pending",
                        enqueued_at=now,
                        followed_id=fs.id,
                        season=ep.season,
                        episode=ep.episode,
                    )
                    store.wanted.add(item)
                    bus.emit(WantedEnqueued(
                        media_ref=ep.media_ref,
                        kind="episode",
                        season=ep.season,
                        episode=ep.episode,
                    ))
                    log.info("cli.follow.detect.enqueued", series=fs.title, season=ep.season, episode=ep.episode)

        console.print(table)
        console.print(
            f"{enqueued_count} enqueued, {skipped_owned} skipped-owned, {skipped_dup} skipped-dup"
            + (" [dim](dry-run)[/dim]" if dry_run else "")
        )
```

- [ ] **Step 5: Update `__all__` in `follow.py`**

```python
__all__ = ["follow_add", "follow_app", "follow_detect", "follow_list", "follow_remove"]
```

- [ ] **Step 6: Run detect tests — all must PASS**

```bash
pytest tests/commands/test_follow_detect.py -v
```

Expected: `7 passed`, `0 failed`.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/commands/follow.py tests/commands/test_follow_detect.py
git commit -m "feat(follow-detect): add follow detect CLI command with --dry-run/--series"
```

---

## Phase 3 Gate

- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must exit 0.
- [ ] **CLI registration check:**

```bash
python -c "
from personalscraper.commands.follow import follow_app
cmds = [c.name for c in follow_app.registered_commands]
assert 'detect' in cmds, f'detect missing: {cmds}'
print('OK:', cmds)
"
```

Expected: `OK: [... 'detect' ...]`.
