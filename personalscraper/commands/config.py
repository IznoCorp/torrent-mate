"""Configuration-related Typer commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app, config_app
from personalscraper.i18n import t


@config_app.command("migrate-category", help=t("cli_core.config.migrate_category.help"))
def config_migrate_category(
    ctx: typer.Context,
    from_cat: str = typer.Option(..., "--from", help=t("cli_core.config.migrate_category.from_help")),
    to_cat: str = typer.Option(..., "--to", help=t("cli_core.config.migrate_category.to_help")),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help=t("cli_core.config.migrate_category.config_help")
    ),
) -> None:
    """Rewrite media_item.category_id for renamed categories.

    Rewrites every ``media_item`` row whose ``category_id`` equals ``--from``
    to ``--to``.  Run this after renaming a category in ``categories.json5``
    to clear orphan-tagged rows shown by ``library status``.

    The target ``--to`` must already be a declared category id in the current
    config (the rename must be applied first).  The operation is idempotent.

    Examples:
        personalscraper config migrate-category --from old_cat --to new_cat
    """
    from personalscraper import cli_helpers  # noqa: PLC0415
    from personalscraper.app.composition import build_app_context  # noqa: PLC0415
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer.cli import config_migrate_category_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    loaded_config = ctx.obj.config if ctx.obj is not None else None
    if loaded_config is not None:
        settings = cli_helpers.get_settings()
        event_bus = build_app_context(loaded_config, settings).event_bus
    else:
        # init-config boundary: no config loaded. Fresh unobserved bus
        # keeps the required-bus contract local to this CLI entry point.
        event_bus = EventBus()
    rc = config_migrate_category_command(
        from_category=from_cat,
        to_category=to_cat,
        config_path=effective_config,
        event_bus=event_bus,
    )
    if rc != 0:
        raise typer.Exit(rc)


@app.command("init-config", help=t("cli_core.config.init_config.help"))
def init_config_cmd(
    ctx: typer.Context,
    example: Path = typer.Option(
        Path("config.example"),
        help=t("cli_core.config.init_config.example_help"),
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help=t("cli_core.config.init_config.output_help"),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--yes",
        help=t("cli_core.config.init_config.yes_help"),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=t("cli_core.config.init_config.force_help"),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_core.config.init_config.dry_run_help"),
    ),
    sync: bool = typer.Option(
        False,
        "--sync",
        help=t("cli_core.config.init_config.sync_help"),
    ),
) -> None:
    """Create ./config/ from the config.example/ template directory.

    Run without arguments for interactive mode (prompts for key values).
    Use --yes to skip all prompts and accept defaults.
    Use --dry-run to preview what would be created without writing anything.

    Examples:
        personalscraper init-config
        personalscraper init-config --yes
        personalscraper init-config --output /custom/path/config --force
        personalscraper init-config --dry-run
    """
    from personalscraper.commands.init_config import init_config

    # Resolve output path: --sync mode uses the canonical config by default;
    # non-sync mode falls back to ./config/ (backwards-compatible).
    explicit_output: bool = output is not None
    if output is None:
        if sync:
            from personalscraper.conf.loader import resolve_config_path  # noqa: PLC0415

            global_config: Optional[Path] = ctx.obj.config_override if ctx.obj is not None else None
            output = resolve_config_path(global_config)
        else:
            output = Path("./config")

    if sync:
        if force:
            typer.echo(t("cli_core.config.init_config.sync_force_exclusive"), err=True)
            raise typer.Exit(code=2)

        # Guard: in --sync mode, if the resolved target does not exist AND the
        # operator did not explicitly pass --output, fail with a clear message
        # instead of silently creating a fresh directory.
        if not explicit_output and not output.is_dir():
            from personalscraper.conf.loader import ENV_CONFIG_PATH  # noqa: PLC0415

            typer.echo(
                t("cli_core.config.init_config.canonical_not_found", output=str(output), env_var=ENV_CONFIG_PATH),
                err=True,
            )
            raise typer.Exit(code=2)

        from personalscraper.commands.init_config import init_config_sync  # noqa: PLC0415

        typer.echo(t("cli_core.config.init_config.target", output=str(output)))
        init_config_sync(example=example.resolve(), target=output.resolve(), dry_run=dry_run)
        return

    if dry_run:
        typer.echo(t("cli_core.config.init_config.dry_run_copy", example=str(example), output=str(output)))
        if not example.is_dir():
            typer.echo(t("cli_core.config.init_config.dry_run_example_missing", example=str(example)), err=True)
        elif output.exists() and not force:
            typer.echo(t("cli_core.config.init_config.dry_run_exists", output=str(output)), err=True)
        else:
            typer.echo(t("cli_core.config.init_config.dry_run_none"))
        return

    init_config(example, output, interactive=not non_interactive, force=force)
