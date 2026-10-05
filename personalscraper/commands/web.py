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

import secrets
from pathlib import Path
from typing import TYPE_CHECKING

import typer
import uvicorn

from personalscraper.app.accounts.passwords import hash_password
from personalscraper.app.composition import ONE_ATTEMPT, build_app_context
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_telemetry import cli_telemetry
from personalscraper.conf.envfile import write_env_keys
from personalscraper.conf.environment import Environment, current_environment
from personalscraper.config import get_settings
from personalscraper.http_v1.standalone import build_standalone_v1_app
from personalscraper.i18n import t
from personalscraper.logger import get_logger
from personalscraper.web.app import create_app

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger(__name__)

# Repo-root ``.env`` — the LOCAL layer of the credential overlay pydantic-settings
# reads (see ``personalscraper.config._resolve_env_files`` / ``_ENV_FILES``: a
# canonical `.env` may be layered UNDER this one, but the local file wins, so
# ``web.py set-keys`` correctly writes the authoritative layer). web.py lives two
# package levels deep (personalscraper/commands/web.py), so the repo root is
# three parents up.
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

web_app = typer.Typer(
    name="web",
    invoke_without_command=True,
    help=t("cli_web.app_help"),
)


@web_app.callback(invoke_without_command=True, help=t("cli_web.app_help"))
@cli_telemetry("web")
@handle_cli_errors
def web(
    ctx: typer.Context,
    host: str | None = typer.Option(
        None,
        "--host",
        help=t("cli_web.host_help"),
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help=t("cli_web.port_help"),
    ),
) -> None:
    """Start the TorrentMate web UI daemon (FastAPI + uvicorn).

    Serves the built SPA from ``personalscraper/web/static/``, the REST API
    (health, version, auth), and the WebSocket event relay.  Refuses to boot
    if the SPA has not been built and ``config.web.dev_mode`` is False.

    The optional ``--host`` / ``--port`` overrides let a second clone serve on a
    different address without editing the shared config dir: the staging clone
    (``~/staging/torrentmate``) runs ``web --port 8711`` under PM2 while
    ``config.web.port`` stays ``8710`` for prod.  When an override is omitted the
    corresponding ``config.web`` value is used.

    When a sub-command is invoked (e.g. ``web set-password``) the callback
    returns immediately without booting the daemon.

    Uvicorn installs its own SIGINT/SIGTERM handlers for graceful shutdown
    of the async event loop and open WebSocket connections.  The app context
    (provider registry, acquire context) is closed in a finally block after
    uvicorn exits.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        host: Optional bind-address override for ``config.web.host``. ``None``
            falls back to the configured host.
        port: Optional port override for ``config.web.port`` (e.g. ``8711`` on
            the staging clone). ``None`` falls back to the configured port.
    """
    # Sub-commands (e.g. ``web set-password``) must not boot the daemon.
    if ctx.invoked_subcommand is not None:
        return

    config: Config = ctx.obj.config
    assert config is not None

    if not config.web.enabled:
        typer.echo(t("cli_web.disabled"))
        log.info("web_disabled")
        raise typer.Exit(code=1)

    # Resolve the static dir the same way web/app.py does — module-relative,
    # no hardcoded absolute path.
    static_dir = Path(__file__).resolve().parent.parent / "web" / "static"
    index_html = static_dir / "index.html"

    if not index_html.exists() and not config.web.dev_mode:
        typer.echo(t("cli_web.spa_missing"), err=True)
        log.error("web_boot_refused", reason="spa_missing", static_dir=str(static_dir))
        raise typer.Exit(code=1)

    settings = get_settings()

    # CLI overrides win over config; None → the configured value. Lets the
    # staging clone bind 8711 (PM2 args "web --port 8711") while sharing the
    # single config dir where web.port stays 8710 for prod.
    bind_host = config.web.host if host is None else host
    bind_port = config.web.port if port is None else port

    # Build the AppContext once for process lifetime — no torrent client
    # (the web process never contacts a torrent daemon). Its bus and its
    # registry are the process's: v1 is handed them, so its provider calls
    # make one attempt (D1).
    app_context = build_app_context(config, settings, build_torrent_client=False, provider_retry=ONE_ATTEMPT)

    try:
        log.info("web_starting", host=bind_host, port=bind_port)
        uvicorn.run(
            create_app(config, settings, app_context=app_context),
            host=bind_host,
            port=bind_port,
            # ``log_config=None`` keeps uvicorn from installing its OWN logging
            # config: its default sets ``propagate=False`` on ``uvicorn.access``
            # / ``uvicorn.error``, which would route those records around our
            # handlers — and therefore around the secret redaction.
            log_config=None,
        )
    finally:
        app_context.provider_registry.close()
        acquire = app_context.acquire
        if acquire is not None:
            acquire.close()
        log.info("web_shutdown_complete")


@web_app.command("serve-v1", help=t("cli_web.serve_v1.help"))
@handle_cli_errors
def serve_v1(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", "--host", help=t("cli_web.serve_v1.host_help")),
    port: int = typer.Option(8713, "--port", help=t("cli_web.serve_v1.port_help")),
) -> None:
    """Serve the v1 application alone, at ``/api/v1``, for a reverse proxy on this machine.

    Refused under production: a development server never opens production stores, so the
    process must run under a named environment (``PERSONALSCRAPER_ENV``) whose marked
    ``data_dir`` holds its own ``app`` store.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        host: The bind address; loopback by default, the reverse proxy being local.
        port: The bind port.

    Raises:
        typer.Exit: Code 1 under production.
    """
    config: Config = ctx.obj.config
    assert config is not None

    environment = current_environment()
    if environment is Environment.PROD:
        typer.echo(t("cli_web.serve_v1.refused_prod"), err=True)
        log.error("web_serve_v1_refused", reason="prod_environment")
        raise typer.Exit(code=1)

    log.info("web_serve_v1_starting", host=host, port=port, environment=environment.value)
    uvicorn.run(
        build_standalone_v1_app(config, get_settings()),
        host=host,
        port=port,
        # Same reason as the daemon's: uvicorn's own logging config would route its
        # records around our handlers, and therefore around the secret redaction.
        log_config=None,
        # The app trusts its proxy's headers itself (``build_standalone_v1_app``); uvicorn's
        # own middleware, widened by ``FORWARDED_ALLOW_IPS``, must not be a second decision.
        proxy_headers=False,
    )


@web_app.command("set-password", help=t("cli_web.set_password.help"))
@handle_cli_errors
def set_password(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help=t("cli_web.set_password.write_help"),
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
    username = typer.prompt(t("cli_web.set_password.username_prompt"), default=default_username)
    password = typer.prompt(t("cli_web.set_password.password_prompt"), hide_input=True, confirmation_prompt=True)

    password_hash = hash_password(password)

    settings = get_settings()
    keys = {"WEB_PASSWORD_HASH": password_hash}
    jwt_secret_generated = not settings.web_jwt_secret
    if jwt_secret_generated:
        keys["WEB_JWT_SECRET"] = secrets.token_urlsafe(32)

    username_matches_config = username == default_username

    if write:
        confirmed = typer.confirm(t("cli_web.set_password.confirm_write", path=str(_ENV_PATH)))
        if not confirmed:
            typer.echo(t("cli_web.set_password.aborted"))
            raise typer.Exit(code=0)
        write_env_keys(keys, _ENV_PATH)
        typer.echo(t("cli_web.set_password.updated", path=str(_ENV_PATH)))
        if not username_matches_config:
            typer.echo(t("cli_web.set_password.reminder", username=username, configured=default_username))
        # Never log secret values — only booleans about what changed.
        log.info(
            "web_set_password_written",
            username_matches_config=username_matches_config,
            jwt_secret_generated=jwt_secret_generated,
        )
        return

    typer.echo(t("cli_web.set_password.add_lines"))
    for key, value in keys.items():
        typer.echo(f"{key}={value}")  # french-ok: layout only, a .env line
    if not username_matches_config:
        typer.echo(t("cli_web.set_password.note", username=username, configured=default_username))
    log.info("web_set_password_printed", jwt_secret_generated=jwt_secret_generated)
