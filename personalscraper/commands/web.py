"""Web daemon command — ``personalscraper web``.

Serves the TorrentMate web UI (FastAPI + SPA) on the configured host and
port, alongside the REST API (health, version, auth) and WebSocket event
relay.  Designed to be managed by PM2 via ``ecosystem.config.js``.

Uvicorn installs its own SIGINT/SIGTERM handlers for graceful shutdown
of the async event loop and open WebSocket connections.  The app context
(provider registry, acquire context) is closed in a finally block after
uvicorn exits.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
import uvicorn

from personalscraper import cli as cli_compat
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import _build_app_context, handle_cli_errors
from personalscraper.logger import get_logger
from personalscraper.web.app import create_app

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger(__name__)


@command_with_telemetry("web")
@handle_cli_errors
def web(ctx: typer.Context) -> None:
    """Start the TorrentMate web UI daemon (FastAPI + uvicorn).

    Serves the built SPA from ``personalscraper/web/static/``, the REST API
    (health, version, auth), and the WebSocket event relay.  Refuses to boot
    if the SPA has not been built and ``config.web.dev_mode`` is False.

    Uvicorn installs its own SIGINT/SIGTERM handlers for graceful shutdown
    of the async event loop and open WebSocket connections.  The app context
    (provider registry, acquire context) is closed in a finally block after
    uvicorn exits.
    """
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

    settings = cli_compat.get_settings()

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
