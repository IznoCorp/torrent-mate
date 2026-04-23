"""Interactive init-config command implementation.

Creates ``config.json5`` by cloning and prompting through
``config.example.json5``. The legacy ``.env`` migration path (V14) has
been removed along with the rest of the V14 compatibility layer.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import json5
import typer

logger = logging.getLogger(__name__)


def _backup_output(output: Path) -> None:
    """Move *output* to ``output.bak``, overwriting existing backup.

    Args:
        output: Path to the file to back up.
    """
    backup = output.with_suffix(output.suffix + ".bak")
    if backup.exists():
        backup.unlink()
    output.rename(backup)
    logger.info("Backed up existing config to %s", backup)


def init_config(
    example: Path,
    output: Path,
    *,
    interactive: bool,
    force: bool,
) -> None:
    """Create ``config.json5`` from the example template.

    Behaviour when *output* already exists:

    - Without ``force``: prints an error and exits with code 2.
    - With ``force``: backs up the existing file to ``<output>.bak``
      (overwriting any previous backup — idempotent) and writes the new one.

    Args:
        example: Path to ``config.example.json5``.
        output: Destination path for the new ``config.json5``.
        interactive: Whether to prompt the user for values (``True``) or
            use defaults silently (``False``).
        force: If ``True``, overwrite an existing *output* (with auto-backup).

    Raises:
        SystemExit: With code 2 if *output* exists without ``--force``.
    """
    if output.exists():
        if not force:
            typer.echo(
                f"config.json5 already exists at {output}. Use --force to overwrite.",
                err=True,
            )
            sys.exit(2)
        _backup_output(output)

    config_dict = _build_from_example(example, interactive=interactive)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json5.dumps(config_dict, indent=2), encoding="utf-8")
    typer.echo(f"Config written to {output}")


def _build_from_example(example: Path, *, interactive: bool) -> dict[str, Any]:
    """Build config dict from the example file, optionally prompting for values.

    Parses the example file via ``example_parser.parse_example`` to extract
    comments and defaults, then either uses defaults silently (non-interactive)
    or prompts the user for each value via ``typer.prompt``.

    Args:
        example: Path to ``config.example.json5``.
        interactive: Whether to prompt the user.

    Returns:
        Config dict built from prompts or defaults.
    """
    from personalscraper.conf.example_parser import parse_example  # noqa: PLC0415

    if not example.is_file():
        typer.echo(f"Example file not found: {example}", err=True)
        sys.exit(2)

    with example.open(encoding="utf-8") as fh:
        try:
            base: dict[str, Any] = json5.load(fh)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Could not parse example file: {exc}", err=True)
            sys.exit(2)

    if not interactive:
        return base

    prompts = parse_example(example)
    overrides: dict[str, str] = {}

    typer.echo("\nPersonalScraper init-config — press ENTER to accept defaults.\n")

    for prompt in prompts:
        if prompt.comment:
            typer.echo(f"  # {prompt.comment}")
        value = typer.prompt(
            f"  {prompt.key_path}",
            default=prompt.default_value.strip('"').strip("'"),
            show_default=True,
        )
        if value != prompt.default_value.strip('"').strip("'"):
            overrides[prompt.key_path] = value

    _apply_overrides(base, overrides)
    return base


def _apply_overrides(data: dict[str, Any], overrides: dict[str, str]) -> None:
    """Apply dot-path overrides to a nested dict in place.

    Supports simple dotted paths (e.g. ``"paths.torrent_complete_dir"``).
    Array index paths (e.g. ``"disks[0].id"``) are skipped with a warning
    since their structure depends on array length which was already set.

    Args:
        data: Mutable config dict to update.
        overrides: Mapping of dot-path key → new string value.
    """
    for path, value in overrides.items():
        if "[" in path:
            logger.debug("Skipping array path override: %s", path)
            continue
        parts = path.split(".")
        node: Any = data
        for part in parts[:-1]:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                node = None
                break
        if isinstance(node, dict):
            node[parts[-1]] = value
