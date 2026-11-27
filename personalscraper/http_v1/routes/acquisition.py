"""The acquisition routes of the follows: list, follow, pause, leave, restore, quality, pause, reassign, completeness.

The contract files them under its ``acquisition`` tag. Each route parses the wire key
(``<provider>:<providerId>``, a medium followed or not, removed or not — never its title) with
:meth:`~personalscraper.app.acquisition.model.AcquisitionKey.parse` and makes ONE call on the follow
service; the rules (requesters, what is in force, soft removal, the prime) are the service's.
"""

from __future__ import annotations

import time
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Path, Query

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.library.identity import parse_media_ref
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.acquisition import (
    Acknowledgement,
    CreateFollowBody,
    FollowCompletenessModel,
    FollowModel,
    ReassignBody,
    Requesters,
    SetPauseBody,
    SetQualityBody,
    UpdateFollowBody,
    floor_of,
)

router = APIRouter()

#: The refusals of an act on one follow: the contract declares 404 for a key no follow answers to.
_FOLLOW_RESPONSES = {**PROBLEM_RESPONSES, 404: PROBLEM_RESPONSES[400]}

_KEY_PARAM_DESCRIPTION = (
    "the medium's key, `<provider>:<providerId>` — TVDB first for a show, TMDB first for a film "
    "(the operator's ruling O-1 A): it names a medium followed or not, and a removed follow, never its title"
)
FollowedIdParam = Annotated[str, Path(alias="followedId", description=_KEY_PARAM_DESCRIPTION)]

#: The kinds a follow is of (the engine's ``FollowKind``, which http_v1 never imports).
FollowKind = Literal["movie", "show"]
_KINDS: tuple[FollowKind, ...] = ("movie", "show")


def _now() -> float:
    """The epoch the answer is made at.

    Returns:
        Seconds since the epoch.
    """
    return time.time()


def _identity(body: CreateFollowBody) -> tuple[AcquisitionKey, FollowKind]:
    """The key and the kind a create names, refused when it names no medium.

    A follow with no identity has no sheet to open: the body's provider pair is optional in the
    contract and required in fact.

    Args:
        body: The create body.

    Returns:
        The medium's key and its kind.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``kind``, ``provider`` or ``providerId``.
    """
    kind = next((one for one in _KINDS if one == body.kind), None)
    if kind is None:
        raise AppBadRequest("Unknown kind.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["kind"]})
    if body.provider is None or body.provider_id is None:
        named = (("provider", body.provider), ("providerId", body.provider_id))
        missing = [name for name, value in named if value is None]
        raise AppBadRequest(
            "A follow names the medium it follows.", code=RefusalCode.REQUEST_INVALID, params={"fields": missing}
        )
    return AcquisitionKey.of(parse_media_ref(body.provider, str(body.provider_id)), kind), kind


@router.get(
    "/acquisition/followed",
    operation_id="readFollows",
    response_model=list[FollowModel],
    response_model_exclude_unset=True,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_follows(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    scenario: Annotated[
        Literal["real", "loaded"] | None,
        Query(
            description=(
                "THE MAQUETTE'S DATA DIAL, not a parameter of the operation: v1 ignores it and answers the one "
                "body of data it holds."
            )
        ),
    ] = None,
) -> list[FollowModel]:
    """Everything the signed-in account may read of what is followed.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.
        scenario: The maquette's data dial; ignored.

    Returns:
        The standing follows the account asked for, or every one with ``acquisition.see.others``.
    """
    del scenario  # the maquette's dial: v1 has one world
    now = _now()
    return [FollowModel.from_view(view, now) for view in app_services.acquisition.follows.read_follows(signed_in)]


@router.post(
    "/acquisition/followed",
    operation_id="createFollow",
    response_model=FollowModel,
    response_model_exclude_unset=True,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def create_follow(
    body: Annotated[CreateFollowBody, Body()],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> FollowModel:
    """Follow a medium: a new follow, or the signed-in account joining the one that exists.

    Args:
        body: The medium: its title, kind, year and one provider pair.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The follow as it now stands.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``kind``, ``provider`` or ``providerId``.
        AppConflict: ``follow.ambiguous`` when two rows hold the key.
    """
    key, kind = _identity(body)
    view = app_services.acquisition.follows.create(signed_in, key, title=body.title, kind=kind, year=body.year)
    return FollowModel.from_view(view, _now())


@router.patch(
    "/acquisition/followed/{followedId}",
    operation_id="updateFollow",
    response_model=FollowModel,
    response_model_exclude_unset=True,
    status_code=200,
    responses=_FOLLOW_RESPONSES,
)
def update_follow(
    followed_id: FollowedIdParam,
    body: Annotated[UpdateFollowBody, Body()],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> FollowModel:
    """Pause or resume a follow.

    Args:
        followed_id: The medium's key.
        body: The status: ``disabled`` pauses, any other resumes.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The follow as it now stands.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` for a malformed key.
        AppNotFound: ``acquisition.not_found`` when no follow holds the key.
        AppForbidden: ``acquisition.follow_shared`` on a follow others asked for too,
            ``acquisition.not_requester`` on one the caller did not ask for.
    """
    view = app_services.acquisition.follows.set_status(signed_in, AcquisitionKey.parse(followed_id), body.status)
    return FollowModel.from_view(view, _now())


@router.delete(
    "/acquisition/followed/{followedId}",
    operation_id="deleteFollow",
    response_model=Acknowledgement,
    status_code=200,
    responses=_FOLLOW_RESPONSES,
)
def delete_follow(
    followed_id: FollowedIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> Acknowledgement:
    """Stop following: the caller leaves the follow, which ends with its last requester.

    Args:
        followed_id: The medium's key.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The acknowledgement.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` for a malformed key.
        AppNotFound: ``acquisition.not_found`` when no follow holds the key.
        AppForbidden: ``acquisition.not_requester`` when the caller did not ask for it.
    """
    app_services.acquisition.follows.remove(signed_in, AcquisitionKey.parse(followed_id))
    return Acknowledgement(ok=True)


@router.post(
    "/acquisition/followed/{followedId}/restore",
    operation_id="restoreFollow",
    response_model=FollowModel,
    response_model_exclude_unset=True,
    status_code=200,
    responses=_FOLLOW_RESPONSES,
)
def restore_follow(
    followed_id: FollowedIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> FollowModel:
    """Put a removed follow back as it was.

    Args:
        followed_id: The medium's key.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The follow, with its year, its date and its searches as they were.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` for a malformed key.
        AppNotFound: ``follow.not_restorable`` when nothing removed under the key can be put back.
    """
    view = app_services.acquisition.follows.restore(signed_in, AcquisitionKey.parse(followed_id))
    return FollowModel.from_view(view, _now())


@router.put(
    "/acquisition/followed/{followedId}/quality",
    operation_id="setAcquisitionQuality",
    response_model=FollowModel,
    response_model_exclude_unset=True,
    status_code=200,
    responses=_FOLLOW_RESPONSES,
)
def set_acquisition_quality(
    followed_id: FollowedIdParam,
    body: Annotated[SetQualityBody, Body()],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> FollowModel:
    """Set the caller's quality floor on one acquisition.

    Args:
        followed_id: The medium's key.
        body: The floor, ``null`` to follow the default.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The follow, its profile in force recomputed.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` for a malformed key.
        AppNotFound: ``acquisition.not_found`` when no follow holds the key.
        AppForbidden: ``acquisition.not_requester`` when the caller did not ask for it.
    """
    view = app_services.acquisition.follows.set_quality(
        signed_in, AcquisitionKey.parse(followed_id), floor_of(body.profile)
    )
    return FollowModel.from_view(view, _now())


@router.put(
    "/acquisition/followed/{followedId}/pause",
    operation_id="setAcquisitionPause",
    response_model=FollowModel,
    response_model_exclude_unset=True,
    status_code=200,
    responses=_FOLLOW_RESPONSES,
)
def set_acquisition_pause(
    followed_id: FollowedIdParam,
    body: Annotated[SetPauseBody, Body()],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> FollowModel:
    """Set the caller's pause on one acquisition.

    Args:
        followed_id: The medium's key.
        body: Whether the caller pauses its own ask.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The follow, its pause recomputed.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` for a malformed key.
        AppNotFound: ``acquisition.not_found`` when no follow holds the key.
        AppForbidden: ``acquisition.not_requester`` when the caller did not ask for it.
    """
    view = app_services.acquisition.follows.set_pause(signed_in, AcquisitionKey.parse(followed_id), body.paused)
    return FollowModel.from_view(view, _now())


@router.post(
    "/acquisition/requesters/reassign",
    operation_id="reassignRequester",
    response_model=Requesters,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def reassign_requester(
    body: Annotated[ReassignBody, Body()],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> Requesters:
    """Move one requester of an acquisition to another account.

    Args:
        body: What the key names, the key, the requester moved off and the account moved on.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The acquisition's requesters after the move.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``acquisition`` for a malformed key.
        AppNotFound: ``account.unknown`` when the target is no account of the roster (a 404 the
            contract does not declare on this operation), ``acquisition.not_found`` when no such
            subject holds the key.
        AppForbidden: ``acquisition.not_requester`` when the source did not ask for it.
    """
    try:
        key = AcquisitionKey.parse(body.acquisition)
    except AppBadRequest:
        raise AppBadRequest(
            "Malformed acquisition key.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["acquisition"]}
        ) from None
    refs = app_services.acquisition.follows.reassign(
        signed_in, body.kind, key, AccountId(body.source), AccountId(body.target)
    )
    return Requesters.from_refs(refs)


@router.get(
    "/acquisition/followed/{followedId}/completeness",
    operation_id="readFollowCompleteness",
    response_model=FollowCompletenessModel,
    status_code=200,
    responses=_FOLLOW_RESPONSES,
)
def read_follow_completeness(
    followed_id: FollowedIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> FollowCompletenessModel:
    """What has aired against what the library holds, season by season, for one follow.

    Args:
        followed_id: The medium's key.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The follow's completeness.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``followedId`` for a malformed key.
        AppNotFound: ``acquisition.not_found`` when no follow the caller may read holds the key.
    """
    return FollowCompletenessModel.from_completeness(
        app_services.acquisition.completeness.read(signed_in, AcquisitionKey.parse(followed_id))
    )
