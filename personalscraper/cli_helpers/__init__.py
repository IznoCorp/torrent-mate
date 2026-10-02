"""Shared helpers used by Typer command modules."""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import typer
from pydantic import ValidationError

from personalscraper.cli_state import AppCtx, state
from personalscraper.conf.staging import ensure_staging_tree as _ensure_staging_tree
from personalscraper.config import get_settings
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import current_correlation_id
from personalscraper.ingest.ingest import run_ingest
from personalscraper.lock import (
    acquire_lock,
    acquire_pipeline_lock,
    release_lock,
    scrape_locks_dir_for,
)
from personalscraper.logger import get_logger
from personalscraper.subscribers.redis_stream import build_redis_publisher

log = get_logger("cli_helpers")

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings


@contextmanager
def per_step_boundary(
    config: "Config",
    settings: "Settings",
    *,
    build_torrent_client: bool = False,
    stream_events: bool = False,
) -> Iterator[AppContext]:
    """Context manager wrapping the per-step CLI boundary.

    Builds an :class:`AppContext`, binds ``current_correlation_id`` for the
    duration of the block, and yields the context. On exit the ContextVar
    is reset whether the body succeeded or raised. Used by the per-step
    Typer subcommands (``ingest``, ``sort``, ``scrape``, ``verify``,
    ``enforce``, ``dispatch``, ``process``) so every event emitted during
    a standalone subcommand carries a correlation_id and lands on a bus
    consistent with ``personalscraper run``.

    Args:
        config: Loaded JSON5 configuration.
        settings: Loaded env-var settings.
        build_torrent_client: Forwarded to :func:`~personalscraper.app.composition.build_app_context`. Only
            the torrent-consuming subcommands (``ingest``, ``torrents_list``)
            pass True; the rest leave it False so they never contact the
            torrent daemon at boot (review #1/#2/#5).
        stream_events: When ``True``, wire the fail-soft Redis event
            publisher on the step bus so the run feeds the web UI live log
            feed (universal run journal). Only the pipeline step commands
            opt in; other consumers keep a publisher-free boundary.

    Yields:
        The fresh :class:`AppContext` bound for this invocation.
    """
    # Imported at call time so a patch of ``personalscraper.app.composition.build_app_context``
    # intercepts it (and so the CLI seam keeps no eager edge into the application layer).
    from personalscraper.app.composition import build_app_context  # noqa: PLC0415

    app_context = build_app_context(config, settings, build_torrent_client=build_torrent_client)
    token = current_correlation_id.set(str(uuid4()))
    # Stream step events to the web UI live feed exactly like a full
    # ``personalscraper run`` (universal run journal, 2026-07-08). Opt-in:
    # only the pipeline step commands pass ``stream_events=True`` — the many
    # other boundary consumers (library-*, grab, seed, …) keep a clean stdout
    # (several of their tests parse strict JSON output, and the publisher's
    # fail-soft warnings would pollute it when Redis is absent). The builder
    # is gated on ``web.enabled`` and fail-soft — Redis down never blocks a
    # step command.
    redis_publisher = build_redis_publisher(app_context.event_bus, config.web) if stream_events else None
    try:
        yield app_context
    finally:
        if redis_publisher is not None:
            try:
                redis_publisher.close()
            except Exception:  # noqa: BLE001 — teardown must never mask the step outcome
                log.warning("per_step_boundary_publisher_close_failed", exc_info=True)
        current_correlation_id.reset(token)
        app_context.provider_registry.close()
        if app_context.acquire is not None:
            app_context.acquire.close()


def _format_validation(exc: ValidationError) -> str:
    """Format pydantic ValidationError as a user-friendly one-liner."""
    parts: list[str] = []
    for err in exc.errors():
        field = " → ".join(str(loc) for loc in err["loc"])
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)


def handle_cli_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Catch configuration errors and display user-friendly messages."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            msg = _format_validation(exc)
            get_logger("cli").error("config_error", message=msg)
            state["console"].print(f"[red]Configuration error:[/red] {msg}")
            raise typer.Exit(1)

    return wrapper


def _bootstrap_staging(ctx: typer.Context) -> None:
    """Call ensure_staging_tree if config is available on the legacy ``AppCtx``."""
    legacy: AppCtx = ctx.obj
    if legacy is not None and legacy.config is not None:
        _ensure_staging_tree(legacy.config)


def _resolve_category(ctx: typer.Context, category: str | None) -> str | None:
    """Resolve a --category CLI value to a canonical category_id."""
    if category is None:
        return None
    legacy: AppCtx = ctx.obj
    resolved: str | None = legacy.config.resolve_category_alias(category)  # type: ignore[union-attr]
    if resolved is None:
        conf = legacy.config
        alias_map = {cid: ccfg.aliases for cid, ccfg in conf.categories.items() if ccfg.aliases}  # type: ignore[union-attr]
        alias_hint = ", ".join(f"{cid}: {aliases}" for cid, aliases in sorted(alias_map.items()))
        valid_ids = ", ".join(sorted(conf.all_category_ids))  # type: ignore[union-attr]
        msg = f"Unknown category '{category}'. Valid IDs: {valid_ids}." + (
            f" Aliases: {alias_hint}." if alias_hint else ""
        )
        typer.echo(f"Error: {msg}", err=True)
        raise typer.Exit(code=2)
    return resolved


# Re-export the generalised boundary() decorator + its bundle. Imported LAST so
# the helpers it depends on (``per_step_boundary``,
# ``_bootstrap_staging``) are already bound in this module's namespace when
# ``boundary`` imports them back from the package (no circular-import gap).
from personalscraper.cli_helpers.boundary import CommandContext, boundary  # noqa: E402

# ``get_settings`` / ``run_ingest`` / the four ``lock`` helpers above are
# re-exported here as the single shared seam for the Typer command modules
# (COMMANDS-CLI-03). Commands access them as ``cli_helpers.<helper>`` module
# attributes rather than importing ``personalscraper.cli`` — that dissolves the
# cli⇄commands facade import cycle (cli.py imports the command modules; the
# command modules must not import cli.py back). Keeping them as module
# attributes (not per-command ``from`` imports) preserves the single-target test
# seam: patching ``personalscraper.cli_helpers.<helper>`` intercepts every
# command at once (the ``importlib`` gotcha documented in boundary.py).
__all__ = [
    "CommandContext",
    "_bootstrap_staging",
    "_format_validation",
    "_resolve_category",
    "acquire_lock",
    "acquire_pipeline_lock",
    "boundary",
    "get_settings",
    "handle_cli_errors",
    "per_step_boundary",
    "release_lock",
    "run_ingest",
    "scrape_locks_dir_for",
]
