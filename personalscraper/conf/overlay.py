"""Multi-file overlay merge logic for the v2 split-config loader.

Provides a shallow-per-key merge strategy where each overlay file is expected
to own a distinct top-level key.  The only exception is ``local.json5``, which
is allowed to override any key without raising a conflict error.
"""

from pathlib import Path
from typing import Any

_LOCAL_FILENAME = "local.json5"


class ConfigConflictError(ValueError):
    """Raised when two non-local overlays claim the same top-level key.

    Two non-``local.json5`` overlay files must not both define the same
    top-level key.  If they do the merge is ambiguous and we raise this error
    rather than silently picking a winner.
    """


class ConfigLoadError(OSError):
    """Raised when a required overlay file cannot be read.

    Covers both missing files and I/O errors encountered while opening overlay
    files declared in the master ``config.json5``.
    """


def merge_overlays(base: dict[str, Any], *overlays: dict[str, Any], allow_conflict: bool = False) -> dict[str, Any]:
    """Merge overlay dicts into *base* using shallow-per-key semantics.

    Each overlay dict may carry an optional ``"__source__"`` entry (a
    ``pathlib.Path``) inserted by the loader to identify ``local.json5`` files.
    That sentinel key is consumed here and never written to the merged result.

    Merge rules:
    - Every top-level key in an overlay is assigned to the result.
    - If two *non-local* overlays define the same key, ``ConfigConflictError``
      is raised.
    - A ``local.json5``-sourced overlay always wins and never raises a conflict
      error (last-wins overrides).

    Args:
        base: Starting dictionary, typically parsed from the master
            ``config.json5``.  The ``overlays`` list key itself is kept in the
            result so callers can inspect it; consumers ignore it after loading.
        *overlays: Additional dicts to merge in order.  Each may contain the
            ``"__source__"`` sentinel key to indicate its origin path.
        allow_conflict: When ``True``, skip conflict detection entirely (useful
            for unit tests that exercise the happy path without caring about
            ownership).  Default: ``False``.

    Returns:
        A new ``dict`` containing the merged result.  Neither ``base`` nor any
        overlay is mutated.

    Raises:
        ConfigConflictError: When two non-local overlays own the same top-level
            key (only when ``allow_conflict=False``).
    """
    result: dict[str, Any] = dict(base)
    # Track which non-local overlay first claimed each key.
    # key -> source path (or None if source is unknown / base)
    claimed_by: dict[str, Path | None] = {}

    for overlay in overlays:
        # Pop the internal source sentinel — do not leak it into the result.
        source: Path | None = overlay.get("__source__")
        is_local = source is not None and source.name == _LOCAL_FILENAME

        for key, value in overlay.items():
            if key == "__source__":
                continue  # sentinel — skip

            if not allow_conflict and not is_local and key in claimed_by:
                prior = claimed_by[key]
                prior_name = prior.name if prior is not None else "<base>"
                src_name = source.name if source is not None else "<unknown>"
                raise ConfigConflictError(
                    f"Overlay conflict: key '{key}' is defined by both "
                    f"'{prior_name}' and '{src_name}'. "
                    f"Each overlay must own a distinct top-level key."
                )

            result[key] = value

            # Only track ownership for non-local overlays so that a second
            # non-local overlay claiming the same key still raises.
            if not is_local:
                claimed_by.setdefault(key, source)

    return result
