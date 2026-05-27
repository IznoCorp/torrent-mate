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
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus, current_correlation_id
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings


def _build_app_context(config: "Config", settings: "Settings") -> AppContext:
    """Build the process-scoped :class:`AppContext` for a CLI invocation.

    Constructed once per CLI command invocation at the boundary
    (``personalscraper run``, the launchd ``library-index`` command, the
    four ``trailers`` subcommands). The :class:`EventBus` is a fresh
    in-process instance; subscriber wiring (``RichConsoleSubscriber``,
    ``TelegramSubscriber``, …) is the caller's responsibility.

    The :class:`ProviderRegistry` is instantiated here from ``settings`` +
    ``config.providers`` so the whole process shares ONE registry (DESIGN
    §6.1 boot sequence). A misconfigured providers section raises
    :class:`RegistryConfigError` at this boundary — fail loud at boot
    rather than discover the problem mid-pipeline.

    Args:
        config: The typed JSON5 configuration loaded by ``cli.main``.
        settings: The Pydantic env-var settings (API keys, paths).

    Returns:
        A frozen :class:`AppContext` ready to drive ``Pipeline.__init__``
        or the orchestrator entrypoints for the launchd / trailers
        commands.
    """
    # Lazy imports: ProviderRegistry pulls the full provider tree, so we
    # defer it to keep CLI import time minimal for commands that never
    # build an AppContext (``--help``, ``init-config``).
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.api.transport._policy import CircuitPolicy

    event_bus = EventBus()
    cb_policy = CircuitPolicy(
        failure_threshold=config.thresholds.circuit_breaker_threshold,
        cooldown_seconds=config.thresholds.circuit_breaker_cooldown,
    )
    provider_registry = ProviderRegistry(
        settings=settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
        providers_config=config.providers,
    )
    return AppContext(
        config=config,
        settings=settings,
        event_bus=event_bus,
        provider_registry=provider_registry,
    )


@contextmanager
def per_step_boundary(config: "Config", settings: "Settings") -> Iterator[AppContext]:
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

    Yields:
        The fresh :class:`AppContext` bound for this invocation.
    """
    app_context = _build_app_context(config, settings)
    token = current_correlation_id.set(str(uuid4()))
    try:
        yield app_context
    finally:
        current_correlation_id.reset(token)


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


__all__ = [
    "_bootstrap_staging",
    "_build_app_context",
    "_format_validation",
    "_resolve_category",
    "handle_cli_errors",
    "per_step_boundary",
]
