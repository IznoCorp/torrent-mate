"""``kanban config`` sub-app — CLI entry point for the config HTTP server (DESIGN §14).

Sub-commands:
  ``kanban config serve``   — start the FastAPI config API server.

The FastAPI import is LAZY (deferred to the ``serve`` function body) so the
bare ``kanban`` CLI never fails when ``[ui]`` is not installed.  An
:exc:`ImportError` there prints an actionable "install kanbanmate[ui]" message.

The optional UI login (bridge — protect internet exposure) is configured from the operator's
gitignored ``.env`` (``KANBAN_MATE_UI_LOGIN`` / ``KANBAN_MATE_UI_PASSWORD`` / optional
``KANBAN_MATE_UI_SESSION_SECRET`` / ``KANBAN_MATE_UI_PORT``). An empty password disables the login.

Layering: ``cli`` may import anything except ``daemon`` (no explicit guard in
``test_layering.py`` for cli, but cli is a top entrypoint — it imports typer
and the cli.init registry helpers).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import secrets
from pathlib import Path

import typer

logger = logging.getLogger(__name__)


def _is_loopback_host(host: str) -> bool:
    """Return ``True`` if ``host`` binds only to the loopback interface (127.0.0.0/8 or ::1).

    A bare hostname that does not parse as an IP (e.g. ``localhost``) is treated as loopback
    (the conservative reading: a literal ``0.0.0.0`` / ``::`` / a routable IP is what we warn
    about). Used to gate the non-loopback + auth-disabled exposure warning in :func:`serve`.

    Args:
        host: The bind address string passed to ``--host``.

    Returns:
        ``True`` when the address is a loopback IP or a non-IP hostname; ``False`` for any
        non-loopback IP literal (e.g. ``0.0.0.0``, ``::``, a LAN/public address).
    """
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # Not an IP literal (e.g. "localhost"): conservatively treat as loopback.
        return True


config_app = typer.Typer(
    name="config",
    help="Pipeline config management: start the headless HTTP API server.",
    no_args_is_help=True,
    add_completion=False,
)

_DEFAULT_ROOT = Path("~/.kanban/").expanduser()
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8766  # distinct from the webhook receiver port (8765)
_ENV_PORT = "KANBAN_MATE_UI_PORT"
_ENV_LOGIN = "KANBAN_MATE_UI_LOGIN"
_ENV_PASSWORD = "KANBAN_MATE_UI_PASSWORD"
_ENV_SECRET = "KANBAN_MATE_UI_SESSION_SECRET"


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple ``KEY=VALUE`` ``.env`` file (no shell expansion, ``#`` comments).

    Args:
        path: The ``.env`` path. A missing file yields an empty mapping.

    Returns:
        The parsed ``{KEY: VALUE}`` pairs (surrounding quotes stripped).
    """
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _resolve_ui_env(env_file: Path) -> dict[str, str]:
    """Merge process env over the ``.env`` file for the ``KANBAN_MATE_UI_*`` keys.

    Real environment variables WIN over the file (so a systemd/PM2 override is honoured); the
    file fills the gaps.

    Args:
        env_file: The ``.env`` file to read.

    Returns:
        A mapping of the four ``KANBAN_MATE_UI_*`` keys (absent keys omitted).
    """
    from_file = _load_env_file(env_file)
    merged: dict[str, str] = {}
    for key in (_ENV_PORT, _ENV_LOGIN, _ENV_PASSWORD, _ENV_SECRET):
        value = os.environ.get(key, from_file.get(key, ""))
        if value != "":
            merged[key] = value
    return merged


@config_app.command()
def serve(
    host: str = typer.Option(_DEFAULT_HOST, "--host", help="Bind address (loopback by default)."),
    port: int | None = typer.Option(
        None, "--port", help=f"TCP port (default {_DEFAULT_PORT} or {_ENV_PORT})."
    ),
    root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Kanban runtime root."),
    env_file: Path = typer.Option(
        Path(".env"), "--env-file", help="Path to the .env with KANBAN_MATE_UI_* credentials."
    ),
) -> None:
    """Start the KanbanMate config HTTP API server.

    Requires the ``[ui]`` optional extra (``pip install 'kanbanmate[ui]'``). Binds to loopback by
    default. The login is enabled iff ``KANBAN_MATE_UI_PASSWORD`` is set (non-empty) in the
    environment or the ``--env-file`` — otherwise the UI is open (loopback/dev only).

    Args:
        host: The bind address.
        port: The TCP port (CLI override; else ``KANBAN_MATE_UI_PORT``; else 8766).
        root: The kanban runtime root (used to resolve the registry).
        env_file: The ``.env`` path carrying the ``KANBAN_MATE_UI_*`` credentials.
    """
    # Lazy import: FastAPI and uvicorn are NOT base dependencies.
    # This guard means `kanban` CLI works even without [ui] installed.
    try:
        import uvicorn  # noqa: PLC0415

        from kanbanmate.http.auth import AuthConfig  # noqa: PLC0415
        from kanbanmate.http.config_api import app as fastapi_app  # noqa: PLC0415
    except ImportError as exc:
        typer.echo(
            f"Error: {exc}\n\n"
            "The config server requires the [ui] optional extra.\n"
            "Install it with: pip install 'kanbanmate[ui]'",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    ui_env = _resolve_ui_env(env_file)
    resolved_port = port if port is not None else int(ui_env.get(_ENV_PORT, _DEFAULT_PORT))

    # Build the auth config.
    password = ui_env.get(_ENV_PASSWORD, "")
    # bosun §12: a random per-start secret logs the operator out on every restart/redeploy, defeating
    # in-UI redeploy. Warn loudly when auth is on but the secret is unpinned; surface it in the dashboard.
    _pinned = bool(ui_env.get(_ENV_SECRET, ""))
    secret = ui_env.get(_ENV_SECRET, "") or secrets.token_hex(32)
    if password and not _pinned:  # auth enabled (non-empty password) + no pinned secret
        logger.warning(
            "KANBAN_MATE_UI_SESSION_SECRET is not set — the session secret is random per start, "
            "so a restart/redeploy will log the operator out. "
            "Set it in the UI .env to persist sessions."
        )
    # bosun review-c2: the whole privileged surface (POST /api/admin/redeploy, daemon stop/restart,
    # PAT overwrite via /api/admin/wizard/token, project delete, PAUSE toggle) is unauthenticated AND
    # CSRF-unprotected when the password is empty (auth disabled). A non-loopback bind with no password
    # therefore exposes daemon control + PAT overwrite + prod redeploy world-open. Warn LOUDLY (do NOT
    # refuse — that would break a valid --host 0.0.0.0 + password-set deploy fronted by Caddy).
    if not password and not _is_loopback_host(host):
        logger.warning(
            "INSECURE: binding to non-loopback host %r with NO password (auth disabled) — the "
            "privileged /api/admin/* surface (daemon stop/restart, prod redeploy, GitHub PAT "
            "overwrite, project delete, PAUSE toggle) is WORLD-OPEN with no auth and no CSRF. "
            "Set KANBAN_MATE_UI_PASSWORD or bind to 127.0.0.1.",
            host,
        )
    # Export a pinned secret from the .env file to the process environment so the dashboard
    # can detect it (os.environ wins over .env in _resolve_ui_env, so this is idempotent).
    if _pinned and not os.environ.get(_ENV_SECRET):
        os.environ[_ENV_SECRET] = ui_env[_ENV_SECRET]
    fastapi_app.state.auth = AuthConfig(
        login=ui_env.get(_ENV_LOGIN, "admin"),
        password=password,
        secret=secret,
    )

    # Thread the runtime root into the app so every endpoint's _get_service()
    # resolves the registry under the operator's --root rather than the default ~/.kanban/.
    fastapi_app.state.kanban_root = root

    login_state = "ENABLED (login required)" if password else "DISABLED (open — set a password)"
    typer.echo(
        f"Starting KanbanMate config API on http://{host}:{resolved_port} "
        f"(root: {root}) — auth: {login_state}"
    )
    uvicorn.run(fastapi_app, host=host, port=resolved_port, log_level="info")
