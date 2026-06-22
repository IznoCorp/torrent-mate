"""Detached board-provisioning runner (bosun §10 step 3 — NOT operator-facing).

Spawned by the install-wizard ``POST /api/admin/wizard/provision`` route's
``wizard_provision`` job as a standalone module via
``python -m kanbanmate.cli.provision_exec --root <root> --project <project_id>``. It performs the
actual (network-touching) board provisioning: it diffs the GitHub Status options against the desired
column set and applies the difference via the production GitHub seeder.

It runs the SAME audited app-level path the ``POST /api/board/provision`` endpoint uses
(:func:`kanbanmate.app.board_provision.provision_board`) — it does NOT re-implement provisioning.
The endpoint resolves the desired columns from a posted/saved draft; this wizard runner resolves them
from the clone's ``columns.yml`` template (the install-time source of truth, before any editor draft
exists), keeping the wizard self-contained on a fresh install.

It lives in its OWN module (not a command on the main ``kanban`` Typer app) for the SAME two reasons
:mod:`kanbanmate.cli.ops_exec` / :mod:`kanbanmate.cli.onboard_exec` do: it keeps ``cli/app.py`` under
the 1000-LOC hard ceiling, and a standalone ``python -m`` entry avoids the double-import trap of
re-importing the ``kanban`` app module while it is already executing as ``__main__``.

As a ``cli``-layer module it MAY import ``cli.init`` + ``app`` + ``core`` (downward-only layering).
It runs detached, so network/clock I/O is fine here. It exits non-zero on failure so the spawning job
records ``failed`` (the only operator-visible outcome).
"""

from __future__ import annotations

from pathlib import Path

import typer

from kanbanmate.app.board_provision import provision_board
from kanbanmate.cli.init import (
    CLONE_COLUMNS_RELPATH,
    _load_registry,
    _projects_path,
)
from kanbanmate.core.columns import load_columns

app = typer.Typer(
    add_completion=False, help="Internal detached board-provisioning runner (not operator-facing)."
)


def _desired_columns(clone: Path) -> list[str]:
    """Resolve the desired Status option names from the clone's ``columns.yml`` (board order).

    The wizard provisions BEFORE any editor draft exists, so the desired column set is read from the
    per-repo template at ``<clone>/.claude/kanban/columns.yml`` (the install-time source of truth).
    Names — not keys — are used because the GitHub Status options are the human-readable labels (the
    same contract the ``POST /api/board/provision`` endpoint uses: ``[c.name for c in columns]``).

    Args:
        clone: The absolute path to the project's local clone.

    Returns:
        The desired column NAMES, in board order.

    Raises:
        FileNotFoundError: When the clone has no ``columns.yml``.
        ValueError: When the document is malformed (propagated from :func:`load_columns`).
    """
    columns_path = clone / CLONE_COLUMNS_RELPATH
    text = columns_path.read_text(encoding="utf-8")
    return [col.name for col in load_columns(text).values()]


@app.command()
def main(
    root: str = typer.Option(..., "--root"),
    project: str = typer.Option(..., "--project", help="Project v2 node id to provision"),
) -> None:
    """Provision the target board's Status options against its ``columns.yml`` (apply).

    Resolves the registry entry for ``project`` (so a stale/unknown id fails loud rather than
    touching the wrong board), reads the desired columns from the clone, then applies the diff via
    the shared :func:`kanbanmate.app.board_provision.provision_board` path with the production GitHub
    seeder. Options only — never cards/PRs/merges (CLAUDE.md autonomy floor).

    Args:
        root: The kanban runtime root holding ``projects.json``.
        project: The Project v2 node id to provision.

    Raises:
        SystemExit: With a non-zero code when the project is unknown to the registry.
    """
    registry = _load_registry(_projects_path(Path(root)))
    entry = registry.get(project)
    if entry is None:
        typer.echo(f"refused: unknown project {project!r} (not in registry)", err=True)
        raise SystemExit(2)

    desired = _desired_columns(Path(entry.clone))
    result = provision_board(
        project_id=entry.project_id,
        desired_columns=desired,
        fallback_options=list(entry.option_map.keys()),
        dry_run=False,
    )
    typer.echo(
        f"provisioned {project} — applied={result.applied} "
        f"columns={len(desired)} options={len(result.option_map)}"
    )


if __name__ == "__main__":
    app()
