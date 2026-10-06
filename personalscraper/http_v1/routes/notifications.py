"""The ``notifications`` tag's routes: the signed-in account's in-app notices."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.notifications import NoticeModel, NoticesModel

router = APIRouter()


@router.get(
    "/notices",
    operation_id="readNotices",
    response_model=NoticesModel,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_notices(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> NoticesModel:
    """The signed-in account's in-app notices, the newest first.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        Its notices.
    """
    views = app_services.notices.read_notices(signed_in)
    return NoticesModel(notices=[NoticeModel.from_view(view) for view in views])
