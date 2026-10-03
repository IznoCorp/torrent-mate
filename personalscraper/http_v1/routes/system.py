"""The ``system`` tag's routes: what the running process is."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import services
from personalscraper.http_v1.models.system import Version

router = APIRouter()


@router.get(
    "/version",
    operation_id="readVersion",
    response_model=Version,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_version(app_services: Annotated[AppServices, Depends(services)]) -> Version:
    """The version and the commit the running process serves.

    Args:
        app_services: The application services.

    Returns:
        The build read once at boot, so a stale process never claims a newer stamp.
    """
    build = app_services.build_info
    return Version(version=build.version, commit=build.commit)
