"""Configuration-related Typer commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app, config_app
from personalscraper.cli_state import state


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
        Path("config.example.json5"),
        help="Path to the example template to read from.",
    ),
    output: Path = typer.Option(
        Path("config.json5"),
        help="Destination path for the generated config.json5.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--yes",
        help="Skip interactive prompts and accept all defaults.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite output file if it already exists.",
    ),
) -> None:
    """Create config.json5 from the example template.

    Run without arguments for interactive mode (prompts for each value).
    Use --yes to skip all prompts and accept defaults.

    Examples:
        personalscraper init-config
        personalscraper init-config --yes
        personalscraper init-config --output /custom/path/config.json5 --force
    """
    from personalscraper.commands.init_config import init_config

    init_config(example, output, interactive=not non_interactive, force=force)


@config_app.command("migrate-to-v2")
def config_migrate_to_v2(
    ctx: typer.Context,
    legacy: Path = typer.Argument(
        ...,
        help="Path to the legacy monolithic config.json5 to migrate.",
    ),
    target_dir: Path = typer.Argument(
        ...,
        help="Destination directory for the split v2 config files.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would be written without touching disk."),
) -> None:
    """Migrate a v1 monolithic config.json5 to the v2 split layout.

    Reads the legacy single-file config.json5, splits its top-level keys
    across per-concern JSON5 files, and writes them atomically to TARGET_DIR.

    The legacy file is renamed to <legacy>.v1.bak on success.  Unknown v1 keys
    are placed in TARGET_DIR/local.json5 and listed in migration-warnings.txt.

    Use --dry-run to preview the plan without writing anything.

    Examples:
        personalscraper config migrate-to-v2 ~/.personalscraper/config.json5 ~/.personalscraper/config/
        personalscraper config migrate-to-v2 --dry-run ~/.personalscraper/config.json5 ~/.personalscraper/config/

    Args:
        ctx: Typer context (unused here — config sub-app runs without the
            main callback's eager config load).
        legacy: Path to the legacy monolithic config.json5.
        target_dir: Destination directory for the split v2 files.
        dry_run: When True, print planned writes and exit 0 without touching disk.
    """
    from personalscraper.conf.migration import (  # noqa: PLC0415
        MigrationAlreadyDoneError,
        MigrationError,
        MigrationMalformedError,
        migrate_v1_to_v2,
        plan_migration,
    )

    console = state["console"]
    legacy_resolved = legacy.expanduser().resolve()
    target_resolved = target_dir.expanduser().resolve()

    if dry_run:
        try:
            plan = plan_migration(legacy_resolved)
        except MigrationMalformedError as exc:
            typer.echo(f"Migration error: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        console.print(f"[yellow]DRY-RUN:[/yellow] Would write the following files to {target_resolved}:")
        for fname, content in plan.items():
            if fname == "migration-warnings.txt":
                console.print(f"  [dim]{fname}[/dim]  (warnings text file)")
            else:
                key_list = ", ".join(content.keys()) if isinstance(content, dict) else "<text>"
                console.print(f"  [cyan]{fname}[/cyan]  keys: {key_list}")
        console.print(f"[dim]Legacy file would be renamed to {legacy_resolved}.v1.bak[/dim]")
        return

    try:
        migrate_v1_to_v2(legacy_resolved, target_resolved)
    except MigrationAlreadyDoneError as exc:
        console.print(f"[yellow]Already migrated:[/yellow] {exc}")
        raise typer.Exit(code=0) from exc
    except MigrationMalformedError as exc:
        typer.echo(f"Migration error (malformed input): {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except MigrationError as exc:
        typer.echo(f"Migration failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Migration complete.[/green] Split config written to {target_resolved}")
    console.print(f"[dim]Legacy file backed up as {legacy_resolved}.v1.bak[/dim]")
