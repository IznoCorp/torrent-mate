"""Detached onboarding runner (bosun §9 — NOT operator-facing).

Spawned by the ``POST /api/projects`` route's ``project_add`` job as a standalone module via
``python -m kanbanmate.cli.onboard_exec --mode <local|clone> --root <root> --repo <owner/name>
[--path <p> | --git-url <u>]``. It performs the actual (network-touching, long-running) onboarding —
register an existing clone (``--mode local``) or git-clone a URL then register it (``--mode clone``).

It lives in its OWN module (not a command on the main ``kanban`` Typer app) for the SAME two reasons
:mod:`kanbanmate.cli.ops_exec` does: it keeps ``cli/app.py`` under the 1000-LOC hard ceiling, and a
standalone ``python -m`` entry avoids the double-import trap of re-importing the ``kanban`` app module
while it is already executing as ``__main__``.

As a ``cli``-layer module it MAY import ``cli.init`` + ``app`` + ``core`` (downward-only layering).
It runs detached, so network/clock I/O is fine here. It exits non-zero on failure so the spawning
job records ``failed``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from kanbanmate.app.onboard import ONBOARD_BASE_DIRS, path_is_confined
from kanbanmate.cli.init import init
from kanbanmate.core.git_url import validate_git_url

app = typer.Typer(
    add_completion=False, help="Internal detached onboarding runner (not operator-facing)."
)


def _clone_target(git_url: str) -> Path:
    """Derive the on-disk clone destination for ``git_url`` under the first base dir.

    The repo name (last path segment, ``.git`` stripped) becomes a sub-directory under the first
    ``ONBOARD_BASE_DIRS`` root (expanded). Server-controlled — never a client-supplied path — and the
    result is re-checked by :func:`path_is_confined` before any I/O.

    Args:
        git_url: The validated ``https://<host>/<owner>/<repo>(.git)`` clone URL.

    Returns:
        The absolute clone destination path under the first base dir.
    """
    name = git_url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]
    base = Path(ONBOARD_BASE_DIRS[0]).expanduser()
    return base / name


@app.command()
def main(
    mode: str = typer.Option(..., "--mode", help="local | clone"),
    root: str = typer.Option(..., "--root"),
    repo: str = typer.Option(..., "--repo", help="owner/name for the registry entry"),
    path: str = typer.Option("", "--path", help="existing clone path (mode=local)"),
    git_url: str = typer.Option("", "--git-url", help="https clone URL (mode=clone)"),
) -> None:
    """Onboard one project (register-local or clone-then-register), exiting non-zero on failure.

    Args:
        mode: ``"local"`` (register an existing clone) or ``"clone"`` (git-clone then register).
        root: The kanban runtime root holding ``projects.json``.
        repo: The ``owner/name`` slug recorded in the registry.
        path: The existing clone path (required + revalidated for ``mode=local``).
        git_url: The clone URL (required + revalidated for ``mode=clone``).

    Raises:
        SystemExit: With a non-zero code on any validation or onboarding failure.
    """
    if mode == "local":
        if not path_is_confined(path):
            typer.echo(f"refused: path {path!r} outside allowed roots", err=True)
            raise SystemExit(2)
        init(repo, root=Path(root), clone=Path(path))
    elif mode == "clone":
        reason = validate_git_url(git_url)
        if reason is not None:
            typer.echo(f"refused: {reason}", err=True)
            raise SystemExit(2)
        target = _clone_target(git_url)
        # Defense-in-depth: the server-derived target must ITSELF land inside the allowed roots
        # (validating ``target.parent`` would pass a traversal name like ``..`` whose parent is the
        # base dir while the target resolves above it — see the git_url traversal guard).
        if not path_is_confined(str(target)):
            typer.echo(f"refused: clone target {target!s} outside allowed roots", err=True)
            raise SystemExit(2)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", git_url, str(target)],
                check=True,
            )
        init(repo, root=Path(root), clone=target)
    else:
        typer.echo(f"refused: mode must be 'local' or 'clone', got {mode!r}", err=True)
        raise SystemExit(2)
    typer.echo(f"onboarded {repo} (mode={mode})")


if __name__ == "__main__":
    app()
