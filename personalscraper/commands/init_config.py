"""Interactive init-config command implementation.

Creates ``config.json5`` from the example template (interactive) or from a
legacy ``.env`` migration (``--from-current``).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import json5
import typer

from personalscraper.conf.migration import (
    generate_config_from_env,
    migrate_category_files,
    migrate_data_dir,
    migrate_library_json,
)

logger = logging.getLogger(__name__)

# Required env variables for --from-current --yes (non-interactive).
_REQUIRED_DISK_VARS = ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR"]
_REQUIRED_PATH_VARS = ["STAGING_DIR", "TORRENT_COMPLETE_DIR"]

# Library JSON files migrated by migrate_library_json (preferences excluded).
_LIBRARY_JSON_FILES = [
    "library_index.json",
    "library_analysis.json",
    "library_rescrape.json",
    "library_recommendations.json",
    "library_validation.json",
]


def _load_dotenv(env_path: Path) -> dict[str, str]:
    """Parse a ``.env`` file into a plain dict.

    Ignores blank lines and ``#`` comments. Does not expand variables.

    Args:
        env_path: Path to the ``.env`` file.

    Returns:
        Dict mapping variable names to their string values.
    """
    env: dict[str, str] = {}
    if not env_path.is_file():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def _backup_output(output: Path) -> None:
    """Move *output* to ``output.v15.bak``, overwriting existing backup.

    Args:
        output: Path to the file to back up.
    """
    backup = output.with_suffix(output.suffix + ".v15.bak")
    # Overwrite existing backup (idempotent — second --force run).
    if backup.exists():
        backup.unlink()
    output.rename(backup)
    logger.info("Backed up existing config to %s", backup)


def _run_from_current(
    output: Path,
    *,
    interactive: bool,
    staging_dir: Path,
    env_path: Path,
) -> dict[str, Any]:
    """Build config dict by migrating a legacy environment + data.

    Performs the full migration from the legacy layout:
    1. Parse ``.env`` for DISK*_DIR, STAGING_DIR, TORRENT_COMPLETE_DIR.
    2. Generate config dict via ``generate_config_from_env``.
    3. Migrate ``.personalscraper/`` → ``.data/`` (if source exists).
    4. Rewrite ``library_*.json`` files with current category IDs.
    5. Merge ``library_preferences.json`` into config["library"].
    6. Migrate ``.category`` files → NFO ``<category>`` elements.

    Args:
        output: Intended output path (for log context only).
        interactive: Whether the session is interactive (allows prompting).
        staging_dir: Staging root directory (used for data_dir discovery).
        env_path: Path to the ``.env`` file.

    Returns:
        Config dict ready for JSON5 serialization.

    Raises:
        SystemExit: With code 2 on fatal validation errors when non-interactive.
    """
    env_values = _load_dotenv(env_path)

    # Supplement with process environment so CI/test environments work.
    for key in (*_REQUIRED_DISK_VARS, *_REQUIRED_PATH_VARS):
        if key not in env_values and key in os.environ:
            env_values[key] = os.environ[key]

    # Validate required fields in non-interactive mode.
    if not interactive:
        # Allow partial disk configs (only DISK1_DIR is truly required).
        missing_required = [v for v in ["DISK1_DIR", *_REQUIRED_PATH_VARS] if not env_values.get(v)]
        if missing_required:
            typer.echo(
                f"--from-current --yes requires all DISK*_DIR in .env. Missing: {', '.join(missing_required)}",
                err=True,
            )
            sys.exit(2)

    # Step 1: Discover legacy data_dir.
    v14_data_dir = staging_dir / ".personalscraper"
    prefs_path: Path | None = None
    if v14_data_dir.is_dir():
        prefs_path = v14_data_dir / "library_preferences.json"
        if not prefs_path.is_file():
            prefs_path = None

    # Step 2: Generate config dict (with library prefs merged if available).
    config_dict = generate_config_from_env(env_values, library_prefs_path=prefs_path)

    # Step 3: Migrate data directory.
    if v14_data_dir.is_dir():
        try:
            new_data_dir = migrate_data_dir(staging_dir)
            config_dict["paths"]["data_dir"] = str(new_data_dir)
            logger.info("Migrated data dir: %s → %s", v14_data_dir, new_data_dir)
        except (FileExistsError, RuntimeError) as exc:
            logger.warning("Could not migrate data dir: %s — continuing", exc)
            new_data_dir = v14_data_dir
    else:
        new_data_dir = staging_dir / ".data"

    # Step 4: Rewrite library_*.json files in new data dir.
    for fname in _LIBRARY_JSON_FILES:
        fpath = new_data_dir / fname
        if fpath.is_file():
            try:
                migrate_library_json(fpath)
            except FileExistsError as exc:
                logger.warning("Skipped %s: %s", fname, exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error migrating %s: %s — skipping", fname, exc)

    # Step 5: Back up and remove library_preferences.json after merging.
    if prefs_path and prefs_path.is_file():
        bak = prefs_path.with_suffix(".json.v14.bak")
        if not bak.exists():
            prefs_path.rename(bak)
            logger.info("Backed up %s → %s", prefs_path.name, bak.name)
        else:
            logger.warning("Preferences backup already exists at %s — not removing original", bak)

    # Step 6: Migrate .category files.
    try:
        count = migrate_category_files(staging_dir, data_dir=new_data_dir)
        logger.info("Migrated %d .category file(s) to NFO <category> elements", count)
    except RuntimeError as exc:
        logger.warning("Skipped .category migration: %s", exc)

    return config_dict


def init_config(
    example: Path,
    output: Path,
    *,
    interactive: bool,
    from_current: bool,
    force: bool,
) -> None:
    """Create ``config.json5`` from the example template or a legacy migration.

    Behaviour when *output* already exists:

    - Without ``force``: prints an error and exits with code 2.
    - With ``force``: backs up the existing file to ``<output>.v15.bak``
      (overwriting any previous backup — idempotent) and writes the new one.

    When ``from_current`` is ``True`` and ``interactive`` is ``False``:
    validates that all required ``DISK*_DIR`` variables are present in
    ``.env``.  Exits with code 2 and an explicit message if any are missing.

    Args:
        example: Path to ``config.example.json5``.
        output: Destination path for the new ``config.json5``.
        interactive: Whether to prompt the user for values (``True``) or
            use defaults silently (``False``).
        from_current: If ``True``, read the legacy ``.env`` and run all migrations.
        force: If ``True``, overwrite an existing *output* (with auto-backup).

    Raises:
        SystemExit: With code 2 on error (output exists without --force,
            or --from-current --yes with missing required .env vars).
    """
    # --- Guard: output already exists ---
    if output.exists():
        if not force:
            typer.echo(
                f"config.json5 already exists at {output}. Use --force to overwrite.",
                err=True,
            )
            sys.exit(2)
        _backup_output(output)

    # --- Build config dict ---
    if from_current:
        # Discover staging_dir and env_path relative to output's parent or CWD.
        cwd = output.parent if output.parent.exists() else Path.cwd()
        env_path = cwd / ".env"

        # Use STAGING_DIR from env if set; fall back to output.parent.
        env_values_peek = _load_dotenv(env_path)
        staging_str = env_values_peek.get("STAGING_DIR") or os.environ.get("STAGING_DIR", "")
        staging_dir = Path(staging_str).expanduser().resolve() if staging_str else cwd

        config_dict = _run_from_current(
            output,
            interactive=interactive,
            staging_dir=staging_dir,
            env_path=env_path,
        )
    else:
        # Simple path: parse example and prompt interactively for each value.
        config_dict = _build_from_example(example, interactive=interactive)

    # --- Serialize and write ---
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

    # Load the example as a raw JSON5 dict (base for defaults).
    with example.open(encoding="utf-8") as fh:
        try:
            base: dict[str, Any] = json5.load(fh)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Could not parse example file: {exc}", err=True)
            sys.exit(2)

    if not interactive:
        # Non-interactive: return example defaults as-is.
        return base

    # Interactive: prompt for each leaf value using extracted comments.
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

    # Merge overrides back into base dict (simple dot-path assignment).
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
