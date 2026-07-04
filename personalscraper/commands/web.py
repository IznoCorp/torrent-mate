"""Web daemon command group — ``personalscraper web``.

Hosts the TorrentMate web UI (FastAPI + SPA) on the configured host and
port, alongside the REST API (health, version, auth) and WebSocket event
relay.  Designed to be managed by PM2 via ``ecosystem.config.js``.

This module exposes a Typer sub-app (``web_app``) so that ``personalscraper
web`` (bare) boots the daemon via the group callback, while nested commands
such as ``personalscraper web set-password`` hang off the same group.

Uvicorn installs its own SIGINT/SIGTERM handlers for graceful shutdown
of the async event loop and open WebSocket connections.  The app context
(provider registry, acquire context) is closed in a finally block after
uvicorn exits.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import typer
import uvicorn

from personalscraper.cli_helpers import _build_app_context, handle_cli_errors
from personalscraper.cli_telemetry import cli_telemetry
from personalscraper.config import get_settings
from personalscraper.logger import get_logger
from personalscraper.web.app import create_app
from personalscraper.web.auth.passwords import hash_password

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger(__name__)

# Repo-root ``.env`` — the same file pydantic-settings reads for credentials
# (see ``personalscraper.config._ENV_PATH``). web.py lives two package levels
# deep (personalscraper/commands/web.py), so the repo root is three parents up.
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

web_app = typer.Typer(
    name="web",
    invoke_without_command=True,
    help="TorrentMate web UI daemon and admin commands.",
)


@web_app.callback(invoke_without_command=True)
@cli_telemetry("web")
@handle_cli_errors
def web(ctx: typer.Context) -> None:
    """Start the TorrentMate web UI daemon (FastAPI + uvicorn).

    Serves the built SPA from ``personalscraper/web/static/``, the REST API
    (health, version, auth), and the WebSocket event relay.  Refuses to boot
    if the SPA has not been built and ``config.web.dev_mode`` is False.

    When a sub-command is invoked (e.g. ``web set-password``) the callback
    returns immediately without booting the daemon.

    Uvicorn installs its own SIGINT/SIGTERM handlers for graceful shutdown
    of the async event loop and open WebSocket connections.  The app context
    (provider registry, acquire context) is closed in a finally block after
    uvicorn exits.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
    """
    # Sub-commands (e.g. ``web set-password``) must not boot the daemon.
    if ctx.invoked_subcommand is not None:
        return

    config: Config = ctx.obj.config
    assert config is not None

    if not config.web.enabled:
        typer.echo("Web daemon is disabled (config.web.enabled=false).")
        log.info("web_disabled")
        raise typer.Exit(code=1)

    # Resolve the static dir the same way web/app.py does — module-relative,
    # no hardcoded absolute path.
    static_dir = Path(__file__).resolve().parent.parent / "web" / "static"
    index_html = static_dir / "index.html"

    if not index_html.exists() and not config.web.dev_mode:
        msg = (
            "SPA not built — static/index.html is missing. "
            "Run the deploy script or set web.dev_mode=true in config/web.json5."
        )
        typer.echo(msg, err=True)
        log.error("web_boot_refused", reason="spa_missing", static_dir=str(static_dir))
        raise typer.Exit(code=1)

    settings = get_settings()

    # Build the AppContext once for process lifetime — no torrent client
    # (the web process never contacts a torrent daemon).
    app_context = _build_app_context(config, settings, build_torrent_client=False)

    try:
        log.info("web_starting", host=config.web.host, port=config.web.port)
        uvicorn.run(
            create_app(config, settings),
            host=config.web.host,
            port=config.web.port,
        )
    finally:
        app_context.provider_registry.close()
        acquire = app_context.acquire
        if acquire is not None:
            acquire.close()
        log.info("web_shutdown_complete")


@web_app.command("set-password")
@handle_cli_errors
def set_password(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Atomically write the generated keys into the repo-root .env (after confirmation).",
    ),
) -> None:
    """Generate the web UI password hash (and a JWT secret) for ``.env``.

    Prompts for a username (default: ``config.web.username``) and a password
    (entered twice, hidden), then produces the ``WEB_PASSWORD_HASH`` line the
    login route expects.  When ``WEB_JWT_SECRET`` is absent/empty in the
    current environment, a fresh ``secrets.token_urlsafe(32)`` value is
    generated and included.

    By default the ``.env`` lines are printed for the operator to paste; the
    file is never touched.  With ``--write`` the keys are upserted into the
    repo-root ``.env`` in place (existing lines replaced, everything else
    preserved) after an interactive confirmation.  Secret values are never
    logged.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        write: When True, atomically update the repo-root ``.env`` after
            confirmation instead of printing the lines.
    """
    config: Config = ctx.obj.config
    assert config is not None

    default_username = config.web.username
    username = typer.prompt("Web UI username", default=default_username)
    password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)

    password_hash = hash_password(password)

    settings = get_settings()
    env_lines = [f"WEB_PASSWORD_HASH={password_hash}"]
    jwt_secret_generated = not settings.web_jwt_secret
    if jwt_secret_generated:
        env_lines.append(f"WEB_JWT_SECRET={secrets.token_urlsafe(32)}")

    username_matches_config = username == default_username

    if write:
        confirmed = typer.confirm(f"Write these keys into {_ENV_PATH}?")
        if not confirmed:
            typer.echo("Aborted; .env left unchanged.")
            raise typer.Exit(code=0)
        _write_env_keys(env_lines, _ENV_PATH)
        typer.echo(f"Updated {_ENV_PATH} (restart the web daemon to apply).")
        if not username_matches_config:
            typer.echo(
                f"Reminder: username '{username}' differs from config.web.username "
                f"('{default_username}') — update config/web.json5 to match."
            )
        # Never log secret values — only booleans about what changed.
        log.info(
            "web_set_password_written",
            username_matches_config=username_matches_config,
            jwt_secret_generated=jwt_secret_generated,
        )
        return

    typer.echo("# Add these lines to your .env file:")
    for line in env_lines:
        typer.echo(line)
    if not username_matches_config:
        typer.echo(
            f"# Note: username '{username}' differs from config.web.username "
            f"('{default_username}') — update config/web.json5 to match."
        )
    log.info("web_set_password_printed", jwt_secret_generated=jwt_secret_generated)


def _write_env_keys(new_lines: list[str], env_path: Path) -> None:
    """Atomically upsert ``KEY=value`` lines into an ``.env`` file.

    Existing lines whose key matches one in *new_lines* are replaced in
    place; every other line (comments, blanks, unrelated keys) is preserved.
    Keys not already present are appended.  The write is atomic via a
    same-directory temp file plus ``os.replace``.  Secret values are never
    logged by this helper.

    Args:
        new_lines: Fully-formed ``KEY=value`` strings to upsert.
        env_path: Path to the ``.env`` file to update (created if absent).
    """
    new_by_key = {line.split("=", 1)[0]: line for line in new_lines}

    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    out_lines: list[str] = []
    for line in existing_lines:
        stripped = line.lstrip()
        key = stripped.split("=", 1)[0] if ("=" in stripped and not stripped.startswith("#")) else None
        if key is not None and key in new_by_key:
            out_lines.append(new_by_key[key])
            seen.add(key)
        else:
            out_lines.append(line)
    for key, line in new_by_key.items():
        if key not in seen:
            out_lines.append(line)

    content = "\n".join(out_lines) + "\n"

    fd, tmp_name = tempfile.mkstemp(dir=str(env_path.parent), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, env_path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
