"""Shared helpers used by Typer command modules."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import typer
from pydantic import ValidationError

from personalscraper.cli_state import AppCtx, state
from personalscraper.conf.staging import ensure_staging_tree as _ensure_staging_tree
from personalscraper.logger import get_logger


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


__all__ = ["_bootstrap_staging", "_format_validation", "_resolve_category", "handle_cli_errors"]
