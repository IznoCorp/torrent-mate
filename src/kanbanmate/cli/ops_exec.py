"""Hidden detached-job runner entry point (bosun §11.3 — NOT operator-facing).

Spawned only by :func:`kanbanmate.app.ops.create_job` as a detached process via
``python -m kanbanmate.cli.ops_exec <job_id> --root <root>``. It lives in its OWN module (not as a
command on the main ``kanban`` Typer app) for two reasons: it keeps ``cli/app.py`` under the 1000-LOC
hard ceiling (the same "sibling module" remedy ``http`` uses for ``config_api``), and running a
standalone module under ``python -m`` avoids the double-import trap that would arise if the spawn
re-imported the ``kanban`` app module while it was already executing as ``__main__``.
"""

from __future__ import annotations

from pathlib import Path

import typer

from kanbanmate.app.ops import run_job

app = typer.Typer(add_completion=False, help="Internal detached-job runner (not operator-facing).")


@app.command()
def main(job_id: str, root: str = typer.Option(..., "--root")) -> None:
    """Run one detached job to completion, exiting with the job's exit code.

    Args:
        job_id: The id of the queued job record under ``<root>/ops/``.
        root: The kanban runtime root holding the ``ops/`` job records.
    """
    raise SystemExit(run_job(Path(root), job_id))


if __name__ == "__main__":
    app()
