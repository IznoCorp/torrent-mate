"""Pure path-confinement check for onboarding (bosun §5.3, decision D2).

The CALLER (app layer) does the I/O: ``expanduser`` + ``Path.resolve()`` (follows symlinks) on both
the candidate and each ``ONBOARD_BASE_DIRS`` entry, then passes the resolved paths here. This module
does NO I/O — it only decides containment, so it lives in ``core``.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Sequence


def is_within_base_dirs(resolved: PurePosixPath, resolved_bases: Sequence[PurePosixPath]) -> bool:
    """Return ``True`` iff ``resolved`` equals or is under one of ``resolved_bases`` (DESIGN §5.3).

    Args:
        resolved: The already-resolved (symlink-followed) candidate path.
        resolved_bases: The already-resolved ``ONBOARD_BASE_DIRS`` entries.

    Returns:
        ``True`` when the candidate is contained in (or equals) a base dir, else ``False``.
    """
    for base in resolved_bases:
        if resolved == base or base in resolved.parents:
            return True
    return False
