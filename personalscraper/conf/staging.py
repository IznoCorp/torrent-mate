"""Staging directory helper functions.

Provides pure functions for computing staging paths from StagingDirConfig
entries. No I/O — filesystem operations live in ensure_staging_tree (Phase 3).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.conf.models import Config, StagingDirConfig
    from personalscraper.sorter.file_type import FileType


def folder_name(entry: "StagingDirConfig") -> str:
    """Compute the on-disk folder name for a staging entry.

    Format: ``f"{entry.id:03d}-{entry.name.upper()}"``.
    E.g. ``{id: 1, name: "movies"}`` → ``"001-MOVIES"``.

    Args:
        entry: A StagingDirConfig entry from config.staging_dirs.

    Returns:
        The folder name string (e.g. "001-MOVIES").
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
        "Config validation should have caught this — check config.json5."
    )
