"""The acquisition's runs: detect, search, grab, a season taken, and the schedule.

The contract files them under its ``acquisition`` tag. Each route parses the wire key
(``<provider>:<providerId>``) and makes ONE service call: ``AcquisitionRuns`` for the passes and the
schedule, ``SeasonAsk`` for the season. Every pass is queued in the supervisor (202, or the season's
201/200); a pass already running or waiting is never a refusal.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Response

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.acquisition_runs import (
    AcquisitionStatusModel,
    DetectionLaunched,
    GrabLaunched,
    GrabReleaseBody,
    SearchQueued,
    SeasonGrabbed,
)
from personalscraper.http_v1.routes.acquisition import FollowedIdParam

router = APIRouter()

#: The refusals of an act on one acquisition: the contract declares 404 for a key nothing answers to.
_KEYED_RESPONSES = {**PROBLEM_RESPONSES, 404: PROBLEM_RESPONSES[400]}


@router.get(
    "/acquisition/status",
    operation_id="readAcquisitionStatus",
    response_model=AcquisitionStatusModel,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_acquisition_status(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    run_uid: Annotated[
        str | None, Query(alias="runUid", description="an acquisition run to follow, by the uid its ask answered")
    ] = None,
) -> AcquisitionStatusModel:
    """The grab's cadence, when the next search runs, and where an asked run stands.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.
        run_uid: The run to follow, or nothing.

    Returns:
        The schedule.
    """
    return AcquisitionStatusModel.from_schedule(app_services.acquisition.triggers.status(signed_in, run_uid))


@router.post(
    "/acquisition/detect",
    operation_id="runDetection",
    response_model=DetectionLaunched,
    status_code=202,
    responses=PROBLEM_RESPONSES,
)
def run_detection(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> DetectionLaunched:
    """Ask a detection of every follow.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The queued request's uid.
    """
    return DetectionLaunched(run_uid=app_services.acquisition.triggers.detect(signed_in))


@router.post(
    "/acquisition/followed/{followedId}/search",
    operation_id="searchForFollow",
    response_model=SearchQueued,
    status_code=202,
    responses=_KEYED_RESPONSES,
)
def search_for_follow(
    followed_id: FollowedIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> SearchQueued:
    """Ask a search of one acquisition, queued like a grab.

    Args:
        followed_id: The medium's key.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        « En file », with the queued request's uid.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` for a malformed key.
        AppNotFound: ``acquisition.not_found`` when nothing stands under the key.
        AppForbidden: ``acquisition.not_requester`` when the caller did not ask for it.
    """
    uid = app_services.acquisition.triggers.search(signed_in, AcquisitionKey.parse(followed_id))
    return SearchQueued(queued=True, run_uid=uid)


@router.post(
    "/acquisition/followed/{followedId}/grab",
    operation_id="grabForFollow",
    response_model=GrabLaunched,
    status_code=202,
    responses=_KEYED_RESPONSES,
)
def grab_for_follow(
    followed_id: FollowedIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    body: Annotated[GrabReleaseBody | None, Body()] = None,
) -> GrabLaunched:
    """Ask a grab of one acquisition, of a chosen release or of what the last search marked takeable.

    Args:
        followed_id: The medium's key.
        signed_in: The signed-in actor.
        app_services: The application services.
        body: The chosen release's handle, or nothing.

    Returns:
        The queued request's uid.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` or ``releaseId``.
        AppNotFound: ``acquisition.not_found`` when nothing stands under the key.
        AppForbidden: ``acquisition.not_requester`` when the caller did not ask for it.
        AppConflict: ``acquisition.release_unavailable`` when the picked release's row cannot take it.
    """
    release_id = None if body is None else body.release_id
    uid = app_services.acquisition.triggers.grab(signed_in, AcquisitionKey.parse(followed_id), release_id)
    return GrabLaunched(run_uid=uid)


@router.post(
    "/acquisition/follows/{followedId}/seasons/{season}/grab",
    operation_id="grabSeasonForFollow",
    response_model=SeasonGrabbed,
    status_code=201,
    responses={
        **_KEYED_RESPONSES,
        200: {"model": SeasonGrabbed, "description": "the season was already being recovered"},
    },
)
def grab_season_for_follow(
    followed_id: FollowedIdParam,
    season: Annotated[int, Path(description="the season, 1-based")],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    response: Response,
) -> SeasonGrabbed:
    """Take one season of a medium: of its follow, or as a one-off request when nobody follows it.

    Args:
        followed_id: The medium's key.
        season: The season, from 1.
        signed_in: The signed-in actor.
        app_services: The application services.
        response: The response, whose status says whether the season was already being recovered.

    Returns:
        201 the season taken, or 200 ``reused``.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` or ``season``.
        AppNotFound: ``acquisition.not_found`` when no follow, request or owned show answers the key.
        AppForbidden: ``acquisition.not_requester`` on a follow that is not the caller's.
    """
    asked = app_services.acquisition.seasons.ask(signed_in, AcquisitionKey.parse(followed_id), season)
    if asked.reused:
        response.status_code = 200
    return SeasonGrabbed.from_asked(asked)
