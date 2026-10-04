"""The media routes: one medium's sheet, its seasons and its rescrape, by provider identity.

The contract files them under its ``media`` tag. Each route parses the wire identity
with :func:`~personalscraper.app.library.identity.parse_media_ref` and makes ONE
``LibraryService`` call; the sheet answers any identity the provider knows, held or not.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.library.identity import Provider, parse_media_ref
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.media import MediaSeasons, MediaSheet, RescrapeQueued

router = APIRouter()

#: The reads' refusals: the contract declares 404 for an id the provider does not know.
_READ_RESPONSES = {**PROBLEM_RESPONSES, 404: PROBLEM_RESPONSES[400]}

#: ``rescrapeMedia``'s refusals: 404 for an id no row holds, and no 409 — a rescrape
#: already running is an accepted ask.
_RESCRAPE_RESPONSES = {status: answer for status, answer in _READ_RESPONSES.items() if status != 409}

ProviderParam = Annotated[Provider, Path(description="the provider the identifier belongs to")]
ProviderIdParam = Annotated[str, Path(alias="providerId", description="the identifier at that provider")]


@router.get(
    "/media/{provider}/{providerId}",
    operation_id="readMediaSheet",
    response_model=MediaSheet,
    response_model_exclude_unset=True,
    status_code=200,
    responses=_READ_RESPONSES,
)
def read_media_sheet(
    provider: ProviderParam,
    provider_id: ProviderIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> MediaSheet:
    """One medium's sheet: the provider's facts crossed with the library's.

    Args:
        provider: The provider the id belongs to.
        provider_id: The id at that provider.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The sheet; a film's carries no episodes, seasons or TMDB television id.
    """
    ref = parse_media_ref(provider.value, provider_id)
    return MediaSheet.from_facts(app_services.library.read_sheet(signed_in, ref))


@router.get(
    "/media/{provider}/{providerId}/seasons",
    operation_id="readMediaSeasons",
    response_model=MediaSeasons,
    status_code=200,
    responses=_READ_RESPONSES,
)
def read_media_seasons(
    provider: ProviderParam,
    provider_id: ProviderIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> MediaSeasons:
    """A show's seasons and what the library holds of each.

    Args:
        provider: The provider the id belongs to.
        provider_id: The id at that provider.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The seasons, the held episodes and the aired counts.
    """
    ref = parse_media_ref(provider.value, provider_id)
    return MediaSeasons.from_facts(app_services.library.read_seasons(signed_in, ref))


@router.post(
    "/media/{provider}/{providerId}/rescrape",
    operation_id="rescrapeMedia",
    response_model=RescrapeQueued,
    status_code=202,
    responses=_RESCRAPE_RESPONSES,
)
def rescrape_media(
    provider: ProviderParam,
    provider_id: ProviderIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> RescrapeQueued:
    """Ask the providers for one medium's metadata again.

    Args:
        provider: The provider the id belongs to.
        provider_id: The id at that provider.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The acceptance: running now, or visibly in file.
    """
    ref = parse_media_ref(provider.value, provider_id)
    return RescrapeQueued.from_acceptance(app_services.library.request_rescrape(signed_in, ref))
