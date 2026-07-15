"""Exclusion helpers for the scanner directory walk.

Provides:
- :data:`EXCLUDED_NAMES` — frozenset of system/macOS directory names to skip.
- :func:`_should_exclude` — predicate for per-entry exclusion during directory walk.
- :func:`_relpath` — compute relative path from mount point.
"""

from __future__ import annotations

import os

from personalscraper._fs_utils import is_apple_double

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
        # Indexer-owned sentinel placed at every disk root by the drift
        # detector; it is not media content and must never be inserted as
        # a ``media_file`` row (otherwise it shows up forever as an
        # orphan with ``release_id IS NULL`` because no media_item owns
        # the disk root).
        ".personalscraper-disk-id",
    }
)


# ---------------------------------------------------------------------------
# Config-driven category exclusions (non-video roots)
# ---------------------------------------------------------------------------

#: Folder names of non-video categories (e.g. the audiobooks folder) that the
#: current scan must skip. Set by ``scan()`` from the loaded config for the
#: duration of one scan (try/finally reset) — the walkers are config-blind,
#: so the set lives here next to the static exclusions. Files under these
#: roots are structurally unlinkable (the item stage never creates a
#: ``media_item`` for non-video categories), so indexing them only produces
#: eternal ``release_id IS NULL`` orphans (744 rows live, 2026-07-15).
#:
#: Matching is by BARE NAME at any depth (same mechanism as
#: :data:`EXCLUDED_NAMES`): a media folder containing a subdirectory named
#: exactly like the operator's audiobook category folder would be skipped
#: too — accepted, the names are operator-chosen and distinctive.
_category_excluded: frozenset[str] = frozenset()


def set_category_exclusions(names: frozenset[str]) -> None:
    """Install the per-scan set of non-video category folder names.

    Args:
        names: Bare folder names to exclude for the current scan; pass an
            empty frozenset to reset (``scan()`` does so in its finally).
    """
    global _category_excluded
    _category_excluded = names


# ---------------------------------------------------------------------------
# Exclusion predicate
# ---------------------------------------------------------------------------


def _should_exclude(name: str) -> bool:
    """Return True if a filesystem entry should be skipped during the walk.

    An entry is excluded if its bare name is in :data:`EXCLUDED_NAMES`, in the
    per-scan :data:`_category_excluded` set (non-video category roots), or if
    it is a macOS AppleDouble metadata file (delegates to
    :func:`personalscraper._fs_utils.is_apple_double` — single source of truth).

    Args:
        name: The bare entry name (no directory component).

    Returns:
        ``True`` if the entry must be skipped; ``False`` if it should be walked.
    """
    return name in EXCLUDED_NAMES or name in _category_excluded or is_apple_double(name)


# ---------------------------------------------------------------------------
# Relative path helper
# ---------------------------------------------------------------------------


def _relpath(mount_path: str, abs_path: str) -> str:
    """Compute the path relative to *mount_path*, stripping any leading separator.

    Args:
        mount_path: Absolute mount point of the disk (no trailing slash).
        abs_path: Absolute path of the entry on the same disk.

    Returns:
        Relative path string, e.g. ``"{movies_dir}/Inception (2010)"``.
    """
    rel = os.path.relpath(abs_path, mount_path)
    # os.path.relpath never starts with '/' but may start with '.'; keep it clean.
    return rel.lstrip("./") if rel == "." else rel
