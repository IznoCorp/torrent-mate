"""Shared dispatch types — data structures and exceptions.

Extracted from ``dispatcher.py`` during the module split so that
``_movie.py``, ``_tv.py``, and ``dispatcher.py`` can import these
without circular-dependency issues.
"""

from dataclasses import dataclass
from pathlib import Path


class DispatchError(Exception):
    """Error during dispatch operation."""


@dataclass
class DispatchResult:
    """Result of dispatching a single media item.

    Attributes:
        source: Source directory path.
        destination: Destination path (None if skipped).
        disk: Target disk name (None if skipped).
        action: Operation performed.
        reason: Reason for skip or error.
        files_copied: Number of files transferred.
        size_mb: Total size transferred in MB.
    """

    source: Path
    destination: Path | None = None
    disk: str | None = None
    action: str = "error"
    reason: str | None = None
    files_copied: int = 0
    size_mb: float = 0
