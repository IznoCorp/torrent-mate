# Phase 04 — Import migration + CLI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

## Gate

Phase 03 must be complete and `make check` green:
- `WiringConfig` has `board_backend` + `board_mirror` fields.
- `ProjectEntry` has `board_backend` field.
- `wiring_for_entry` threads `board_backend`.

## Goal

Implement `app/board_import.py` (the snapshot→seed logic) and the `kanban board` CLI sub-app (`cli/board.py`) with `import` and `status` commands. Register the sub-app in `cli/app.py`.

## Files

- **Create:** `src/kanbanmate/app/board_import.py` — `import_board` function (snapshot → seed; idempotent)
- **Create:** `src/kanbanmate/cli/board.py` — `board_app` Typer sub-app (`kanban board import`, `kanban board status`)
- **Modify:** `src/kanbanmate/cli/app.py` — `app.add_typer(board_app, name="board")`
- **Create:** `tests/app/test_board_import.py` — import seeding, idempotent re-run, dry-run tests

## Key design facts (grounded)

- `GithubClient.snapshot()` returns `BoardSnapshot(tickets=tuple[Ticket,...], fetched_at=float)`. Each `Ticket` has `item_id`, `issue_number`, `title`, `column_key`, `body`.
- `seed_board(store, columns, placement, order, version=1)` in `adapters/store/fs_board.py` writes atomically under the lock.
- Idempotent re-run: a re-run increments the existing version (reads current `doc["version"]` first), preserves existing `order` for cards still in the same column, reconciles `placement` from the live snapshot.
- `--dry-run`: runs all logic but calls `seed_board` with `dry_run=True` suppression (or simply skips the write and returns the computed data).
- `cli/app.py` uses `app.add_typer(config_app, name="config")` pattern (line 73); `board_app` follows identically.
- The `kanban board import` command needs `--root` and `--project` options (same pattern as other CLI commands).
- CLI output assertions must NOT depend on ANSI/terminal width. Use `--no-color` or assert on structured data.
- `load_columns(columns_yaml)` returns an `OrderedDict[str, Column]`; iterate `.values()` for the ordered column key list.

---

### Task 1: `app/board_import.py` — the import logic

**Files:**
- Create: `src/kanbanmate/app/board_import.py`

**Interfaces:**
- Consumes: `FsBoardStateStore`, `seed_board` from `adapters.store.fs_board`
- Consumes: forge client (`BoardReader`) for `snapshot()`
- Produces: `import_board(forge, store, columns, dry_run=False) -> dict` returning `{"version": int, "summary": {...}}`

- [ ] **Step 1: Write the file**

```python
"""One-shot board import: seed the native store from a live GitHub snapshot (anchor §8).

Idempotent: a re-run reconciles ``placement`` against the live GitHub Status and
preserves any existing native ``order`` for cards still in the same column (only
newly-seen cards are appended to their column tail). ``--dry-run`` computes the
result without writing.

Layering: ``app`` — may import ``adapters`` and ``core``.
"""

from __future__ import annotations

from typing import Any

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board


def import_board(
    forge: Any,
    store: FsBoardStateStore,
    columns: list[str],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Seed the native board store from the live GitHub Projects v2 snapshot (anchor §8).

    1. Fetch the live snapshot from ``forge``.
    2. Build ``placement`` from each ticket's current GitHub Status ``column_key``.
    3. Build ``order``: for each column, append items in GitHub ``updatedAt`` order
       (the snapshot returns items in the GraphQL page order — a deterministic initial order).
       For a re-run, preserve existing native order for items still in the same column;
       append newly-seen items to the column tail.
    4. Write atomically with the new ``version = existing_version + 1`` (or ``1`` on first run).
    5. On ``dry_run=True``, skip the write and return the computed data.

    Args:
        forge: A ``BoardReader`` (``GithubClient`` or a fake for tests) for ``snapshot()``.
        store: The native board store to seed.
        columns: Ordered column key list (from ``columns.yml`` order).
        dry_run: When ``True``, compute but do not write; return the data.

    Returns:
        ``{"version": int, "summary": {"total": int, "per_column": {col: count}}}``.
    """
    snap = forge.snapshot()
    existing = store.load()
    existing_version: int = existing.get("version", 0)
    existing_order: dict[str, list[str]] = existing.get("order", {})
    existing_placement: dict[str, str] = existing.get("placement", {})

    # Build placement map from the live GitHub snapshot.
    placement: dict[str, str] = {}
    for ticket in snap.tickets:
        col = ticket.column_key if ticket.column_key in columns else (columns[0] if columns else "")
        placement[ticket.item_id] = col

    # Build order: for each column, preserve existing native order for items still there,
    # then append newly-seen items (items in the live snapshot that are newly assigned to
    # this column or didn't exist in the native store before).
    order: dict[str, list[str]] = {col: [] for col in columns}
    for col in columns:
        # Existing order entries that are still in this column (stable order preserved).
        still_here = [
            iid for iid in existing_order.get(col, [])
            if placement.get(iid) == col
        ]
        # Newly-seen items assigned to this column (in snapshot page order = updatedAt order).
        existing_set = set(existing_placement.keys())
        newly_seen = [
            ticket.item_id
            for ticket in snap.tickets
            if ticket.item_id not in existing_set and placement.get(ticket.item_id) == col
        ]
        # Re-run: items that moved INTO this column from another.
        moved_in = [
            iid for iid, assigned_col in placement.items()
            if assigned_col == col
            and iid not in still_here
            and iid not in newly_seen
        ]
        order[col] = still_here + newly_seen + moved_in

    new_version = existing_version + 1 if existing_version > 0 else 1

    if not dry_run:
        seed_board(store, columns=columns, placement=placement, order=order, version=new_version)

    per_column = {col: len(order[col]) for col in columns}
    return {
        "version": new_version,
        "dry_run": dry_run,
        "summary": {
            "total": len(placement),
            "per_column": per_column,
        },
    }
```

- [ ] **Step 2: Smoke check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -c "from kanbanmate.app.board_import import import_board; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/kanbanmate/app/board_import.py
git commit -m "feat(anchor): board_import — snapshot-to-store seed, idempotent reconcile"
```

---

### Task 2: Import tests (`tests/app/test_board_import.py`)

**Files:**
- Create: `tests/app/test_board_import.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for board_import: seeding, idempotent re-run, dry-run (anchor §12.8)."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

import pytest

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board
from kanbanmate.app.board_import import import_board
from kanbanmate.core.domain import BoardSnapshot, Ticket

COLUMNS = [
    "Backlog", "Brainstorming", "Spec", "Plan", "Planned",
    "ReadyToDev", "PrepareFeature", "InProgress", "PRCI",
    "Review", "Merge", "Done", "Cancel", "Blocked",
]


def _forge_with_tickets(*tickets: Ticket) -> MagicMock:
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)
    return forge


def _ticket(item_id: str, col: str) -> Ticket:
    return Ticket(item_id=item_id, issue_number=1, title="T", column_key=col, body="")


def test_import_seeds_board_from_snapshot(tmp_path: pathlib.Path) -> None:
    """import_board seeds board.json from the live GitHub snapshot."""
    forge = _forge_with_tickets(
        _ticket("a", "Backlog"),
        _ticket("b", "InProgress"),
    )
    store = FsBoardStateStore(tmp_path)
    result = import_board(forge, store, COLUMNS)

    assert result["version"] == 1
    assert result["dry_run"] is False
    doc = store.load()
    assert doc["placement"]["a"] == "Backlog"
    assert doc["placement"]["b"] == "InProgress"
    assert "a" in doc["order"]["Backlog"]
    assert "b" in doc["order"]["InProgress"]


def test_import_idempotent_rerun_preserves_native_order(tmp_path: pathlib.Path) -> None:
    """A re-run increments version, preserves existing native order for unchanged items."""
    store = FsBoardStateStore(tmp_path)
    # First import.
    forge = _forge_with_tickets(_ticket("a", "Backlog"), _ticket("b", "Backlog"))
    import_board(forge, store, COLUMNS)
    # Manually set a custom native order.
    store.reorder_column("Backlog", ["b", "a"])

    # Second import (same snapshot).
    result = import_board(forge, store, COLUMNS)
    assert result["version"] == 2

    doc = store.load()
    # Native order ["b", "a"] must be preserved since both items are still in Backlog.
    assert doc["order"]["Backlog"] == ["b", "a"]


def test_import_dryrun_does_not_write(tmp_path: pathlib.Path) -> None:
    """--dry-run computes the result but does not write board.json."""
    forge = _forge_with_tickets(_ticket("a", "Backlog"))
    store = FsBoardStateStore(tmp_path)
    result = import_board(forge, store, COLUMNS, dry_run=True)

    assert result["dry_run"] is True
    assert result["version"] == 1
    # board.json must NOT exist (no write).
    assert not (tmp_path / "board.json").exists()


def test_import_unknown_column_lands_in_entry(tmp_path: pathlib.Path) -> None:
    """A ticket with an unknown GitHub Status column falls back to the entry column."""
    forge = _forge_with_tickets(_ticket("x", "UnknownGitHubStatus"))
    store = FsBoardStateStore(tmp_path)
    import_board(forge, store, COLUMNS)
    doc = store.load()
    assert doc["placement"]["x"] == "Backlog", "entry column is COLUMNS[0] = Backlog"


def test_import_summary_counts_per_column(tmp_path: pathlib.Path) -> None:
    forge = _forge_with_tickets(
        _ticket("a", "Backlog"),
        _ticket("b", "Backlog"),
        _ticket("c", "InProgress"),
    )
    store = FsBoardStateStore(tmp_path)
    result = import_board(forge, store, COLUMNS)
    assert result["summary"]["total"] == 3
    assert result["summary"]["per_column"]["Backlog"] == 2
    assert result["summary"]["per_column"]["InProgress"] == 1
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/app/test_board_import.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/app/test_board_import.py
git commit -m "test(anchor): board_import — seed, idempotent re-run, dry-run, entry-col fallback"
```

---

### Task 3: `cli/board.py` + register in `cli/app.py`

**Files:**
- Create: `src/kanbanmate/cli/board.py`
- Modify: `src/kanbanmate/cli/app.py`

**Interfaces:**
- Produces: `board_app` Typer sub-app (the `kanban board` commands)
- Consumes: `import_board`, `FsBoardStateStore`, `wiring_for_selection`, `_load_registry`

- [ ] **Step 1: Write `cli/board.py`**

```python
"""``kanban board`` sub-app: import and status commands (anchor §8).

``kanban board import`` seeds the native store from the live GitHub snapshot.
``kanban board status`` shows the native store summary.

Layering: ``cli`` is a top-level entrypoint — it may import ``app``, ``adapters``,
``core``, and ``daemon``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from kanbanmate.cli.init import DEFAULT_KANBAN_ROOT

board_app = typer.Typer(help="Native board state management (anchor §8).")


@board_app.command("import")
def board_import(
    root: Path = typer.Option(DEFAULT_KANBAN_ROOT, help="KanbanMate runtime root."),
    project: str | None = typer.Option(None, help="Project v2 node id (required for N>1)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without writing."),
) -> None:
    """Seed the native board store from the live GitHub Projects v2 snapshot."""
    from kanbanmate.adapters.github.client import GithubClient
    from kanbanmate.adapters.store.fs_board import FsBoardStateStore
    from kanbanmate.app.board_import import import_board
    from kanbanmate.core.columns import load_columns
    from kanbanmate.daemon.registry_wiring import wiring_for_selection

    try:
        wc = wiring_for_selection(root, project=project)
    except (FileNotFoundError, Exception) as exc:
        typer.echo(f"kanban board import: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    store_path = Path(wc.state_root) if wc.state_root else (
        Path(wc.kanban_root) if wc.kanban_root else DEFAULT_KANBAN_ROOT
    )
    store = FsBoardStateStore(store_path)
    forge = GithubClient(wc.token, project_id=wc.project_id, repo=wc.repo)
    col_map = load_columns(wc.columns_yaml)
    columns = [col.key for col in col_map.values()]

    result = import_board(forge, store, columns, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    typer.echo(f"{prefix}Board import: version={result['version']}, "
               f"total={result['summary']['total']} cards")
    for col, count in result["summary"]["per_column"].items():
        if count > 0:
            typer.echo(f"  {col}: {count}")


@board_app.command("status")
def board_status(
    root: Path = typer.Option(DEFAULT_KANBAN_ROOT, help="KanbanMate runtime root."),
    project: str | None = typer.Option(None, help="Project v2 node id (required for N>1)."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show the native board store summary (placement + version)."""
    from kanbanmate.adapters.store.fs_board import FsBoardStateStore
    from kanbanmate.daemon.registry_wiring import wiring_for_selection

    try:
        wc = wiring_for_selection(root, project=project)
    except (FileNotFoundError, Exception) as exc:
        typer.echo(f"kanban board status: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    store_path = Path(wc.state_root) if wc.state_root else (
        Path(wc.kanban_root) if wc.kanban_root else DEFAULT_KANBAN_ROOT
    )
    store = FsBoardStateStore(store_path)
    doc = store.load()

    if json_output:
        typer.echo(json.dumps(doc, indent=2))
        return

    if doc.get("version", 0) == 0:
        typer.echo("No native board store found. Run `kanban board import` first.")
        return

    typer.echo(f"Native board store: version={doc['version']}")
    placement = doc.get("placement", {})
    per_col: dict[str, int] = {}
    for col in doc.get("columns", []):
        per_col[col] = sum(1 for v in placement.values() if v == col)
        if per_col[col] > 0:
            typer.echo(f"  {col}: {per_col[col]}")
```

- [ ] **Step 2: Register `board_app` in `cli/app.py`**

In `src/kanbanmate/cli/app.py`, after the `from kanbanmate.cli.config import config_app` import, add:

```python
from kanbanmate.cli.board import board_app
```

After `app.add_typer(config_app, name="config")` (line 73), add:

```python
# anchor §8: ``kanban board import`` / ``kanban board status`` sub-app.
app.add_typer(board_app, name="board")
```

- [ ] **Step 3: Smoke-test the CLI**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m kanbanmate.cli.app board --help
```

Expected: shows `import` and `status` commands.

- [ ] **Step 4: Run make check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make check
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/cli/board.py src/kanbanmate/cli/app.py
git commit -m "feat(anchor): kanban board import/status CLI sub-app"
```
