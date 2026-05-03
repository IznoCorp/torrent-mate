"""Staging directory helper functions.

Provides pure functions for computing staging paths from StagingDirConfig
entries, plus ``ensure_staging_tree`` for idempotent filesystem bootstrap.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.conf.models.staging import StagingDirConfig
    from personalscraper.sorter.file_type import FileType

_log = get_logger("staging")


def folder_name(entry: "StagingDirConfig") -> str:
    """Compute the on-disk folder name for a staging entry.

    Format: ``f"{entry.id:03d}-{entry.name.upper()}"``.
    The actual folder names are determined by config.staging_dirs entries.

    Args:
        entry: A StagingDirConfig entry from config.staging_dirs.

    Returns:
        The folder name string derived as ``f"{entry.id:03d}-{entry.name.upper()}"``.

    """
    return f"{entry.id:03d}-{entry.name.upper()}"


def staging_path(config: "Config", entry: "StagingDirConfig") -> Path:
    """Compute the absolute path for a staging subdirectory.

    Args:
        config: The loaded Config instance.
        entry: A StagingDirConfig entry from config.staging_dirs.

    Returns:
        Absolute Path to the staging subdirectory.
    """
    return config.paths.staging_dir / folder_name(entry)


def find_by_file_type(config: "Config", file_type: "FileType") -> "StagingDirConfig":
    """Find the staging entry matching a FileType.

    Args:
        config: The loaded Config instance.
        file_type: The FileType enum member to look up.

    Returns:
        The first StagingDirConfig whose file_type matches.

    Raises:
        KeyError: If no staging entry matches the given file_type.
    """
    for entry in config.staging_dirs:
        if entry.file_type == file_type.value:
            return entry
    raise KeyError(
        f"No staging_dirs entry found for file_type={file_type.value!r}. Check your config.json5 staging_dirs section."
    )


def find_ingest_dir(config: "Config") -> "StagingDirConfig":
    """Return the staging entry designated as the ingest directory.

    The Phase 1 validator guarantees exactly one entry has role='ingest'.

    Args:
        config: The loaded Config instance.

    Returns:
        The StagingDirConfig entry with role='ingest'.

    Raises:
        KeyError: If no entry has role='ingest' (should not happen post-validation).
    """
    for entry in config.staging_dirs:
        if entry.role == "ingest":
            return entry
    raise KeyError(
        "No staging_dirs entry with role='ingest' found. "
        "Config validation should have caught this -- check config.json5."
    )


def ensure_staging_tree(config: "Config") -> list[Path]:
    """Create staging_dir root and per-entry subdirectories if absent.

    Idempotent: directories that already exist are silently skipped.
    Emits a single structlog warning listing the paths that were created,
    so the operator is aware of the auto-bootstrap on first run.

    Args:
        config: The loaded Config instance. Uses config.paths.staging_dir
            and config.staging_dirs to determine which paths to create.

    Returns:
        List of Path objects that were actually created (empty if all existed).
    """
    staging_root = config.paths.staging_dir
    created: list[Path] = []

    # Create staging root if missing
    if not staging_root.exists():
        staging_root.mkdir(parents=True, exist_ok=True)
        created.append(staging_root)

    # Create each configured subdirectory if missing
    for entry in config.staging_dirs:
        subdir = staging_root / folder_name(entry)
        if not subdir.exists():
            subdir.mkdir(parents=True, exist_ok=True)
            created.append(subdir)

    if created:
        _log.warning(
            "staging_tree_created",
            paths=[str(p) for p in created],
            count=len(created),
            message=(
                f"Auto-created {len(created)} staging path(s) under {staging_root}. "
                "This is normal on first run. See config.json5 staging_dirs section."
            ),
        )

    return created
