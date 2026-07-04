"""Version route for the TorrentMate web UI (tm-shell feature)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

import personalscraper

router = APIRouter(prefix="/api", tags=["version"])


def _read_build_commit() -> str:
    """Read the build commit hash from the static BUILD_COMMIT file.

    Returns:
        The commit hash string, or ``"dev"`` if the file is absent or unreadable.
    """
    build_commit_path = Path(__file__).resolve().parent.parent / "static" / "BUILD_COMMIT"
    try:
        return build_commit_path.read_text().strip()
    except (FileNotFoundError, OSError):
        return "dev"


@router.get("/version")
def version() -> dict[str, str]:
    """Application version endpoint.

    Returns:
        A dict with ``version`` (the Python package version) and
        ``build_commit`` (the deployed git SHA, or ``"dev"``).
    """
    return {
        "version": personalscraper.__version__,
        "build_commit": _read_build_commit(),
    }
