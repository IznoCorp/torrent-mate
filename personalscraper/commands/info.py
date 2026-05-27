"""Informational and setup Typer commands."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import typer

from personalscraper.cli_state import state

info_app = typer.Typer(name="info", invoke_without_command=True)


@info_app.callback(invoke_without_command=True)
def info(ctx: typer.Context) -> None:
    """Display version, config paths, and disk status.

    Output format respects the global ``--format`` flag
    (e.g. ``personalscraper --format json info``).

    Examples:
        personalscraper info
        personalscraper --format json info
    """
    if ctx.invoked_subcommand is not None:
        return

    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415
    from personalscraper.info.run import collect_info, format_info

    config = ctx.obj.config
    assert config is not None  # guaranteed non-None by callback
    console = state["console"]
    report = collect_info(config)
    emit(
        dataclasses.asdict(report),
        rich_renderer=lambda: console.print(format_info(report)),
    )


@info_app.command("providers")
def info_providers(
    ctx: typer.Context,
    config_override: Path | None = typer.Option(
        None,
        "--config",
        help="Override default config/providers.json5 for boot validation.",
    ),
) -> None:
    """Print per-provider circuit state snapshot from the ProviderRegistry.

    Output: one line per configured provider, format:
        <name>  circuit=<state>  failures=<count>

    Exits non-zero if RegistryConfigError is raised during boot validation
    (missing credentials or broken config).
    """
    from personalscraper.api.metadata.registry import ProviderRegistry  # noqa: PLC0415
    from personalscraper.api.metadata.registry._errors import RegistryConfigError  # noqa: PLC0415
    from personalscraper.api.transport._policy import CircuitPolicy  # noqa: PLC0415
    from personalscraper.conf.models.providers import ProvidersConfig  # noqa: PLC0415
    from personalscraper.config import get_settings  # noqa: PLC0415
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

    if config_override is not None:
        import json5  # noqa: PLC0415

        with open(config_override) as fh:
            raw = json5.load(fh)
        providers_config = ProvidersConfig.model_validate(raw.get("providers", raw))
    else:
        providers_config = ctx.obj.config.providers

    settings = get_settings()
    event_bus = EventBus()
    cb_policy = CircuitPolicy(
        failure_threshold=ctx.obj.config.thresholds.circuit_breaker_threshold,
        cooldown_seconds=ctx.obj.config.thresholds.circuit_breaker_cooldown,
    )

    try:
        registry = ProviderRegistry(
            settings=settings,
            event_bus=event_bus,
            cb_policy=cb_policy,
            providers_config=providers_config,
        )
    except RegistryConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    try:
        status = registry.status()
        for name, s in status.items():
            typer.echo(f"{name:<20} circuit={s.circuit_state}  failures={s.failure_count_recent}")
    finally:
        registry.close()
