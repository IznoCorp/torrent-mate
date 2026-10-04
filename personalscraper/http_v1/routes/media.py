"""The media routes: one medium's sheet, its seasons and its rescrape, by provider identity.

The contract files them under its ``media`` tag. Each route parses the wire identity
with :func:`~personalscraper.app.library.identity.parse_media_ref` and makes ONE
``LibraryService`` call; the sheet answers any identity the provider knows, held or not.
The poster route answers the library folder's own poster file, the one a sheet points
at when no provider names a poster.
"""

from __future__ import annotations

from typing import Annotated, Final
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Response

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.library.identity import Provider, parse_media_ref
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES, V1_PREFIX
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.media import MediaSeasons, MediaSheet, RescrapeQueued

router = APIRouter()

#: The reads' refusals: the contract declares 404 for an id the provider does not know.
_READ_RESPONSES = {**PROBLEM_RESPONSES, 404: PROBLEM_RESPONSES[400]}

#: ``rescrapeMedia``'s refusals: 404 for an id no row holds, and no 409 — a rescrape
#: already running is an accepted ask.
_RESCRAPE_RESPONSES = {status: answer for status, answer in _READ_RESPONSES.items() if status != 409}

#: ``readMediaPoster``'s refusals: it reads no provider (no 503) and changes nothing (no 409).
_POSTER_RESPONSES = {status: answer for status, answer in _READ_RESPONSES.items() if status not in (409, 503)}

#: ``readMediaPoster``'s answer: the file's bytes, under the media type its extension names.
_POSTER_IMAGE: Final = {"schema": {"type": "string", "format": "binary"}}

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
    return MediaSheet.from_facts(
        app_services.library.read_sheet(signed_in, ref), local_poster_url=_poster_url(provider, provider_id)
    )


def _poster_url(provider: Provider, provider_id: str) -> str:
    """``readMediaPoster``'s URL for one identity, prefix included, usable as an image source.

    Args:
        provider: The provider the id belongs to.
        provider_id: The id at that provider, percent-encoded as one path segment.

    Returns:
        ``/api/v1/media/{provider}/{providerId}/poster``.
    """
    return f"{V1_PREFIX}/media/{provider.value}/{quote(provider_id, safe='')}/poster"


@router.get(
    "/media/{provider}/{providerId}/poster",
    operation_id="readMediaPoster",
    response_class=Response,
    status_code=200,
    responses={
        **_POSTER_RESPONSES,
        200: {"description": "the poster image", "content": {"image/jpeg": _POSTER_IMAGE, "image/png": _POSTER_IMAGE}},
    },
)
def read_media_poster(
    provider: ProviderParam,
    provider_id: ProviderIdParam,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> Response:
    """The poster file the medium's library folder holds, resolved on its disk now.

    Args:
        provider: The provider the id belongs to.
        provider_id: The id at that provider.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The image, under its media type.
    """
    ref = parse_media_ref(provider.value, provider_id)
    poster = app_services.library.read_local_poster(signed_in, ref)
    return Response(content=poster.content, media_type=poster.media_type)


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
