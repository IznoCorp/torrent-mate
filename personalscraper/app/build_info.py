"""The build the running process serves: its package version and the commit it booted with.

v1's own reader of the deploy's ``BUILD_COMMIT`` stamp. The application layer may not
import ``personalscraper.web``, so the stamp is read by its path; v0's reader
(``web/routes/version.py``) stays as it is until v0 is deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from personalscraper import __version__

#: Where the deploy stamps ``BUILD_COMMIT`` (the web application's static directory).
_STATIC_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "web" / "static"


@dataclass(frozen=True)
class BuildInfo:
    """The build one process serves.

    Attributes:
        version: The package version.
        commit: The git commit the process booted with, or ``"dev"``.
    """

    version: str
    commit: str


def read_build_commit(static_dir: Path) -> str:
    """Read the commit the deploy stamped in ``BUILD_COMMIT``.

    Args:
        static_dir: The directory holding the stamp.

    Returns:
        The stamp without its surrounding whitespace, or ``"dev"`` when it is absent
        or unreadable (a development checkout).
    """
    try:
        return (static_dir / "BUILD_COMMIT").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


#: Read ONCE, at import. Re-reading per request would let a stale process that a
#: failed restart left running serve the freshly stamped commit, and the deploy's
#: post-check could no longer tell which build is running (R27).
BUILD_INFO: Final[BuildInfo] = BuildInfo(version=__version__, commit=read_build_commit(_STATIC_DIR))
