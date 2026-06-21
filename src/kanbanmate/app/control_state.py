"""Per-ticket "human attached" sentinel for reaper coordination (tiller §4.4).

The WS handler writes ``control/ticket-<n>.attached`` under the project's resolved
store root when a human takes control; the reaper skips ``end_session`` while the
sentinel is present (or deletes it as stale after ``stale_minutes``). Pure path
helpers + thin filesystem ops — no I/O inside ``core/``.
"""

from __future__ import annotations

import time
from pathlib import Path

_DEFAULT_STALE_MINUTES = 5


def sentinel_path(store_root: Path, ticket: int) -> Path:
    """Return the per-ticket sentinel path ``control/ticket-<n>.attached``.

    Args:
        store_root: The project's runtime store root (e.g. ``~/.kanban-km/projects/<id>``).
        ticket: The issue number.

    Returns:
        The sentinel file path (not necessarily existing).
    """
    return store_root / "control" / f"ticket-{ticket}.attached"


def write_sentinel(path: Path) -> None:
    """Create (or touch) the sentinel file, creating parent dirs as needed.

    Args:
        path: The sentinel path returned by :func:`sentinel_path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def remove_sentinel(path: Path) -> None:
    """Remove the sentinel file if it exists (best-effort, no raise).

    Args:
        path: The sentinel path to remove.
    """
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def is_attached(path: Path, *, stale_minutes: int = _DEFAULT_STALE_MINUTES) -> bool:
    """Return whether the sentinel is present and not stale.

    A sentinel older than ``stale_minutes`` is treated as stale (client crashed
    without releasing control) and removed so the reaper is not pinned forever.

    Args:
        path: The sentinel path.
        stale_minutes: Age in minutes after which the sentinel is treated as stale.

    Returns:
        ``True`` if the sentinel exists and is fresh; ``False`` otherwise.
    """
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > stale_minutes * 60:
        remove_sentinel(path)
        return False
    return True
