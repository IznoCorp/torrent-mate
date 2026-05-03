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
    from personalscraper.indexer.cli import config_migrate_category_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = config_migrate_category_command(
        from_category=from_cat,
        to_category=to_cat,
        config_path=effective_config,
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
) -> None:
    """Create ./config/ from the config.example/ template directory.

    Run without arguments for interactive mode (prompts for key values).
    Use --yes to skip all prompts and accept defaults.

    Examples:
        personalscraper init-config
        personalscraper init-config --yes
        personalscraper init-config --output /custom/path/config --force
    """
    from personalscraper.commands.init_config import init_config

    init_config(example, output, interactive=not non_interactive, force=force)
