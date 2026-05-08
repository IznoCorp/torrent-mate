"""Interactive init-config command implementation.

Creates ``./config/`` by copying the ``config.example/`` template directory,
then optionally prompting the user to fill in key path values.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import json5
import typer

from personalscraper.logger import get_logger

log = get_logger("init_config")


def _backup_dir(output: Path) -> None:
    """Rename *output* to ``output.bak``, removing any existing backup.

    Args:
        output: Path to the directory to back up.
    """
    backup = output.with_name(output.name + ".bak")
    if backup.exists():
        shutil.rmtree(backup)
    output.rename(backup)
    log.info("config_backed_up", backup=str(backup))


def init_config(
    example: Path,
    output: Path,
    *,
    interactive: bool,
    force: bool,
) -> None:
    """Create ``./config/`` from the ``config.example/`` template directory.

    Behaviour when *output* already exists:

    - Without ``force``: prints an error and exits with code 2.
    - With ``force``: backs up the existing directory to ``<output>.bak``
      and writes the new one.

    Args:
        example: Path to ``config.example/`` directory.
        output: Destination path for the new ``./config/`` directory.
        interactive: Whether to prompt the user for values (``True``) or
            use defaults silently (``False``).
        force: If ``True``, overwrite an existing *output* (with auto-backup).

    Raises:
        SystemExit: With code 2 if *output* exists without ``--force``.
    """
    if not example.is_dir():
        typer.echo(f"Example directory not found: {example}", err=True)
        sys.exit(2)

    if output.exists():
        if not force:
            typer.echo(
                f"Config directory already exists at {output}. Use --force to overwrite.",
                err=True,
            )
            sys.exit(2)
        _backup_dir(output)

    shutil.copytree(example, output)
    typer.echo(f"Config directory created at {output}")

    if interactive:
        _prompt_for_values(output)

    typer.echo(
        "Next steps:\n"
        f"  1. Edit {output}/paths.json5 to set your paths\n"
        f"  2. Edit {output}/disks.json5 to configure your storage disks\n"
        f"  3. Review {output}/metadata.json5 and {output}/torrent.json5 for API config\n"
        f"  4. Edit .env to set your API keys (see .env.example)\n"
        f"  5. Run `personalscraper run` to start the pipeline"
    )


def _prompt_for_values(config_dir: Path) -> None:
    """Prompt user for key path values and write them into the config files.

    Args:
        config_dir: Path to the config directory containing overlay files.
    """
    paths_file = config_dir / "paths.json5"
    if paths_file.is_file():
        try:
            with paths_file.open("r", encoding="utf-8") as fh:
                paths_data = json5.load(fh)
        except Exception:
            paths_data = {}

        paths = paths_data.get("paths", {})
        torrent_dir = typer.prompt(
            "qBittorrent completed torrents directory",
            default=str(paths.get("torrent_complete_dir", "/path/to/torrents/complete")),
        )
        staging_dir = typer.prompt(
            "Staging directory",
            default=str(paths.get("staging_dir", "./staging/")),
        )
        data_dir = typer.prompt(
            "Data directory (pipeline state, DB, locks)",
            default=str(paths.get("data_dir", "./.data")),
        )
        paths_data["paths"] = {
            "torrent_complete_dir": torrent_dir,
            "staging_dir": staging_dir,
            "data_dir": data_dir,
        }
        paths_file.write_text(json5.dumps(paths_data, indent=2), encoding="utf-8")
        typer.echo(f"Paths written to {paths_file}")

    disks_file = config_dir / "disks.json5"
    if disks_file.is_file():
        try:
            with disks_file.open("r", encoding="utf-8") as fh:
                disks_data = json5.load(fh)
        except Exception:
            disks_data = {}

        current_disks = disks_data.get("disks", [])
        if current_disks:
            typer.echo(f"Found {len(current_disks)} disk(s) in template. Skipping disk prompts.")
            typer.echo(f"Edit {disks_file} directly to configure storage disks.")
        else:
            typer.echo("No disks configured. Add them in disks.json5 before running the pipeline.")
