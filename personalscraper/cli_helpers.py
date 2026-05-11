"""Shared helpers used by Typer command modules."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import typer
from pydantic import ValidationError

from personalscraper.cli_state import AppCtx, state
from personalscraper.conf.staging import ensure_staging_tree as _ensure_staging_tree
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings


def _build_app_context(config: "Config", settings: "Settings") -> AppContext:
    """Build the process-scoped :class:`AppContext` for a CLI invocation.

    Constructed once per CLI command invocation at the boundary (Sub-phase
    2.4 for ``personalscraper run``; Sub-phase 2.5 for the launchd
    ``library-index`` command and the four ``trailers`` subcommands). The
    :class:`EventBus` is a fresh in-process instance with zero
    subscribers — subscriber wiring (RichConsoleSubscriber,
    TelegramSubscriber, etc.) lands in Phase 3.5/3.6.

    Args:
        config: The typed JSON5 configuration loaded by ``cli.main``.
        settings: The Pydantic env-var settings (API keys, paths).

    Returns:
        A frozen :class:`AppContext` ready to drive ``Pipeline.__init__``
        or the orchestrator entrypoints for the launchd / trailers
        commands.
    """
    return AppContext(config=config, settings=settings, event_bus=EventBus())


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
    """Call ensure_staging_tree if config is available on the AppCtx."""
    app_ctx: AppCtx = ctx.obj
    if app_ctx is not None and app_ctx.config is not None:
        _ensure_staging_tree(app_ctx.config)


def _resolve_category(ctx: typer.Context, category: str | None) -> str | None:
    """Resolve a --category CLI value to a canonical category_id."""
    if category is None:
        return None
    app_ctx: AppCtx = ctx.obj
    resolved: str | None = app_ctx.config.resolve_category_alias(category)  # type: ignore[union-attr]
    if resolved is None:
        conf = app_ctx.config
        alias_map = {cid: ccfg.aliases for cid, ccfg in conf.categories.items() if ccfg.aliases}  # type: ignore[union-attr]
        alias_hint = ", ".join(f"{cid}: {aliases}" for cid, aliases in sorted(alias_map.items()))
        valid_ids = ", ".join(sorted(conf.all_category_ids))  # type: ignore[union-attr]
        msg = f"Unknown category '{category}'. Valid IDs: {valid_ids}." + (
            f" Aliases: {alias_hint}." if alias_hint else ""
        )
        typer.echo(f"Error: {msg}", err=True)
        raise typer.Exit(code=2)
    return resolved


__all__ = [
    "_bootstrap_staging",
    "_build_app_context",
    "_format_validation",
    "_resolve_category",
    "handle_cli_errors",
]
