"""Exclusion helpers for the scanner directory walk.

Provides:
- :data:`EXCLUDED_NAMES` — frozenset of system/macOS directory names to skip.
- :func:`_should_exclude` — predicate for per-entry exclusion during directory walk.
- :func:`_relpath` — compute relative path from mount point.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Excluded names
# ---------------------------------------------------------------------------

#: Exact-match names that are always skipped during the directory walk.
#: These are well-known macOS / Windows system artefacts that should never
#: be indexed as media content.
EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        ".fseventsd",
        "$Recycle.Bin",
        ".Spotlight-V100",
        ".Trashes",
        "System Volume Information",
        ".DS_Store",
    }
)


# ---------------------------------------------------------------------------
# Exclusion predicate
# ---------------------------------------------------------------------------


def _should_exclude(name: str) -> bool:
    """Return True if a filesystem entry should be skipped during the walk.

    An entry is excluded if its bare name is in :data:`EXCLUDED_NAMES` or if it
    starts with the ``"._"`` prefix used by macOS for resource-fork shadow files.

    Args:
        name: The bare entry name (no directory component).

    Returns:
        ``True`` if the entry must be skipped; ``False`` if it should be walked.
    """
    return name in EXCLUDED_NAMES or name.startswith("._")


# ---------------------------------------------------------------------------
# Relative path helper
# ---------------------------------------------------------------------------


def _relpath(mount_path: str, abs_path: str) -> str:
    """Compute the path relative to *mount_path*, stripping any leading separator.

    Args:
        mount_path: Absolute mount point of the disk (no trailing slash).
        abs_path: Absolute path of the entry on the same disk.

    Returns:
        Relative path string, e.g. ``"001-MOVIES/Inception (2010)"``.
    """
    rel = os.path.relpath(abs_path, mount_path)
    # os.path.relpath never starts with '/' but may start with '.'; keep it clean.
    return rel.lstrip("./") if rel == "." else rel
