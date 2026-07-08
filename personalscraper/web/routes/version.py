"""Version route for the TorrentMate web UI (tm-shell feature)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

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


#: Build commit captured ONCE at process boot (module import). Re-reading the
#: file per request would let a stale (pre-deploy) process serve the freshly
#: stamped file from disk, making ``GET /api/version`` useless for verifying
#: WHICH build is actually running (R27). The cached value identifies THIS
#: process's build — deploy.sh asserts it equals the deployed sha.
_BUILD_COMMIT: str = _read_build_commit()


class VersionResponse(BaseModel):
    """Response model for the version endpoint.

    Attributes:
        version: The Python package version string.
        build_commit: The deployed git SHA, or ``"dev"``.
    """

    version: str
    build_commit: str


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    """Application version endpoint.

    Returns:
        A dict with ``version`` (the Python package version) and
        ``build_commit`` (the git SHA the RUNNING process booted with, or
        ``"dev"`` — cached at import, see :data:`_BUILD_COMMIT`).
    """
    return VersionResponse(
        version=personalscraper.__version__,
        build_commit=_BUILD_COMMIT,
    )
