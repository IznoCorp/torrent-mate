"""Configuration-related Typer commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app, config_app


@config_app.command("migrate-category")
def config_migrate_category(
    ctx: typer.Context,
    from_cat: str = typer.Option(..., "--from", help="Old category_id to replace"),
    to_cat: str = typer.Option(..., "--to", help="New category_id to write (must be declared in config)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
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
    from personalscraper import cli as cli_compat  # noqa: PLC0415
    from personalscraper.cli_helpers import _build_app_context  # noqa: PLC0415
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer.cli import config_migrate_category_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    loaded_config = ctx.obj.config if ctx.obj is not None else None
    if loaded_config is not None:
        settings = cli_compat.get_settings()
        event_bus = _build_app_context(loaded_config, settings).event_bus
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


@app.command("init-config")
def init_config_cmd(
    example: Path = typer.Option(
        Path("config.example"),
        help="Path to the example template directory to copy from.",
    ),
    output: Path = typer.Option(
        Path("./config"),
        help="Destination path for the new config directory.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--yes",
        help="Skip interactive prompts and accept all defaults.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite output directory if it already exists.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Preview mode: show what would be created without writing any files. "
            "Checks that config.example/ exists and reports the target path."
        ),
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

    if dry_run:
        typer.echo(f"[DRY-RUN] Would copy {example} → {output}")
        if not example.is_dir():
            typer.echo(f"[DRY-RUN] WARNING: example directory not found: {example}", err=True)
        elif output.exists() and not force:
            typer.echo(f"[DRY-RUN] WARNING: {output} already exists; use --force to overwrite.", err=True)
        else:
            typer.echo("[DRY-RUN] No files written.")
        return

    init_config(example, output, interactive=not non_interactive, force=force)
