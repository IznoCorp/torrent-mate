"""``kanban board`` sub-app: import and status commands (anchor §8).

``kanban board import`` seeds the native store from the live GitHub snapshot.
``kanban board status`` shows the native store summary.

Layering: ``cli`` is a top-level entrypoint — it may import ``app``, ``adapters``,
``core``, and ``daemon``.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from kanbanmate.cli.init import DEFAULT_KANBAN_ROOT

board_app = typer.Typer(help="Native board state management (anchor §8).")


@board_app.command("import")
def board_import(
    root: Path = typer.Option(DEFAULT_KANBAN_ROOT, help="KanbanMate runtime root."),
    project: str | None = typer.Option(None, help="Project v2 node id (required for N>1)."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change without writing."
    ),
) -> None:
    """Seed the native board store from the live GitHub Projects v2 snapshot."""
    from kanbanmate.adapters.github.client import GithubClient
    from kanbanmate.adapters.store.fs_board import FsBoardStateStore
    from kanbanmate.app.board_import import import_board
    from kanbanmate.core.columns import load_columns
    from kanbanmate.daemon.registry_wiring import wiring_for_selection

    try:
        wc = wiring_for_selection(root, project=project)
    except Exception as exc:
        typer.echo(f"kanban board import: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    store_path = (
        Path(wc.state_root)
        if wc.state_root
        else (Path(wc.kanban_root) if wc.kanban_root else DEFAULT_KANBAN_ROOT)
    )
    store = FsBoardStateStore(store_path)
    forge = GithubClient(wc.token, project_id=wc.project_id, repo=wc.repo)
    col_map = load_columns(wc.columns_yaml)
    columns = [col.key for col in col_map.values()]

    result = import_board(forge, store, columns, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    typer.echo(
        f"{prefix}Board import: version={result['version']}, "
        f"total={result['summary']['total']} cards"
    )
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
    except Exception as exc:
        typer.echo(f"kanban board status: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    store_path = (
        Path(wc.state_root)
        if wc.state_root
        else (Path(wc.kanban_root) if wc.kanban_root else DEFAULT_KANBAN_ROOT)
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
