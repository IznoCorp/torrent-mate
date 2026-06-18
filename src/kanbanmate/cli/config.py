"""``kanban config`` sub-app — CLI entry point for the config HTTP server (DESIGN §14).

Sub-commands:
  ``kanban config serve``   — start the FastAPI config API server.

The FastAPI import is LAZY (deferred to the ``serve`` function body) so the
bare ``kanban`` CLI never fails when ``[ui]`` is not installed.  An
:exc:`ImportError` there prints an actionable "install kanbanmate[ui]" message.

Layering: ``cli`` may import anything except ``daemon`` (no explicit guard in
``test_layering.py`` for cli, but cli is a top entrypoint — it imports typer
and the cli.init registry helpers).
"""

from __future__ import annotations

from pathlib import Path

import typer

config_app = typer.Typer(
    name="config",
    help="Pipeline config management: start the headless HTTP API server.",
    no_args_is_help=True,
    add_completion=False,
)

_DEFAULT_ROOT = Path("~/.kanban/").expanduser()
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8766  # distinct from the webhook receiver port (8765)


@config_app.command()
def serve(
    host: str = typer.Option(_DEFAULT_HOST, "--host", help="Bind address (loopback by default)."),
    port: int = typer.Option(_DEFAULT_PORT, "--port", help="TCP port to listen on."),
    root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Kanban runtime root."),
) -> None:
    """Start the KanbanMate config HTTP API server.

    Requires the ``[ui]`` optional extra (``pip install 'kanbanmate[ui]'``).
    The server binds to loopback by default (single-operator, no auth).

    Args:
        host: The bind address.
        port: The TCP port.
        root: The kanban runtime root (used to resolve the registry).
    """
    # Lazy import: FastAPI and uvicorn are NOT base dependencies.
    # This guard means `kanban` CLI works even without [ui] installed.
    try:
        import uvicorn  # noqa: PLC0415
        from kanbanmate.http.config_api import app as fastapi_app  # noqa: PLC0415
    except ImportError as exc:
        typer.echo(
            f"Error: {exc}\n\n"
            "The config server requires the [ui] optional extra.\n"
            "Install it with: pip install 'kanbanmate[ui]'",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    # Thread the runtime root into the app so every endpoint's _get_service()
    # (called with no argument) resolves the registry under the operator's --root
    # rather than the default ~/.kanban/. Without this the --root flag is a no-op.
    fastapi_app.state.kanban_root = root

    typer.echo(f"Starting KanbanMate config API on http://{host}:{port} (root: {root})")
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
