"""The acquisition's reads: the release picker, the provider search, the deck, and the ranking preview.

The contract files the first four under its ``acquisition`` tag and the preview under ``trackers``. Each
route makes ONE service call and maps its facts to the contract's bodies; the right each operation asks is
the perimeter's (``OPERATION_RIGHTS``), and what a reader may see of the follows is the service's
(own-scoped, DESIGN § 2.4).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Query

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.acquisition.search import SearchKind
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.acquisition_reads import (
    RankingConfigBody,
    RankingPreviewModel,
    RankingPreviewReleaseModel,
    ReleaseModel,
    SearchResults,
    SuggestionModel,
)

router = APIRouter()

#: ``previewRanking``'s refusals: it reads no provider, so no 503 (its 409 is the idempotency guard's).
_PREVIEW_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: PROBLEM_RESPONSES[status] for status in (400, 401, 403, 500)
}

#: The wire's ``kind`` restriction on a search, and the service's name for each.
_SEARCH_KINDS: dict[str, SearchKind] = {"movie": "movie", "show": "tv"}


def _season_or_episode(name: str, value: int | None) -> int | None:
    """Refuse a season or an episode that is not 1-based.

    Args:
        name: The parameter's name, for the refusal.
        value: What was asked.

    Returns:
        The value.

    Raises:
        AppBadRequest: ``request.invalid`` naming the parameter, when it is below 1.
    """
    if value is not None and value < 1:
        raise AppBadRequest(
            "A season and an episode count from 1.", code=RefusalCode.REQUEST_INVALID, params={"fields": [name]}
        )
    return value


@router.get(
    "/acquisition/releases",
    operation_id="readReleases",
    response_model=list[ReleaseModel],
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_releases(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    followed_id: Annotated[
        str | None,
        Query(
            alias="followedId",
            pattern="^(tvdb|tmdb|imdb):.+$",
            description=(
                "the wanted item's medium: the medium's key, `<provider>:<providerId>` — TVDB first for a show, "
                "TMDB first for a film (the operator's ruling O-1 A): it names a medium followed or not, and a "
                "removed follow, never its title. Absent, the candidates of every item (what the quality profile "
                "counts against)"
            ),
        ),
    ] = None,
    season: Annotated[int | None, Query(description="the season, 1-based — absent for a film")] = None,
    episode: Annotated[
        int | None, Query(description="the episode, 1-based — absent for a whole season and for a film")
    ] = None,
) -> list[ReleaseModel]:
    """The release candidates of one wanted item, or of every item the reader may see.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.
        followed_id: The medium's key; absent, every item's candidates.
        season: The season, 1-based.
        episode: The episode, 1-based.

    Returns:
        The candidates, the best rank first, each with its handle and the season and episode it numbers; empty
        for an item the reader may not read, a closed item, or one no search concluded for.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``season`` or ``episode`` when below 1, or ``episode`` when
            asked with no season, or ``followedId`` when it is not a key.
        FollowAmbiguous: ``follow.ambiguous`` when two follow rows hold the key's id.
    """
    key = None if followed_id is None else AcquisitionKey.parse(followed_id)
    offers = app_services.acquisition.releases.offers(
        signed_in, key, _season_or_episode("season", season), _season_or_episode("episode", episode)
    )
    return [ReleaseModel.from_offer(offer) for offer in offers]


@router.get(
    "/acquisition/search",
    operation_id="searchProviders",
    response_model=SearchResults,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def search_providers(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    query: Annotated[str | None, Query(description="what was typed")] = None,
    kind: Annotated[str | None, Query(description="restrict to films or to shows")] = None,
) -> SearchResults:
    """Search the metadata providers for a title to follow.

    Nothing typed is nothing to search for: an answer with no result, not a refusal (the add screen asks
    on opening, before a letter is typed).

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.
        query: What was typed.
        kind: ``movie`` or ``show`` to restrict the search; absent, both.

    Returns:
        The best-ranked page, with the total the providers hold.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``kind`` when it is neither ``movie`` nor ``show``.
        AppUnavailable: ``provider.unavailable`` when no provider could answer.
    """
    wanted = None
    if kind:
        wanted = _SEARCH_KINDS.get(kind)
        if wanted is None:
            raise AppBadRequest(
                "A search is restricted to films (movie) or shows (show).",
                code=RefusalCode.REQUEST_INVALID,
                params={"fields": ["kind"]},
            )
    typed = (query or "").strip()
    if not typed:
        return SearchResults.empty()
    return SearchResults.from_page(app_services.acquisition.search.search(signed_in, typed, wanted))


@router.get(
    "/acquisition/search/by-id",
    operation_id="searchProviderById",
    response_model=SearchResults,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def search_provider_by_id(
    provider: Annotated[Literal["tmdb", "tvdb", "imdb"], Query(description="the source the identifier belongs to")],
    id: Annotated[
        str,
        Query(
            description=(
                "the identifier, in that source's format: digits for TMDB and TVDB, « tt » and digits for IMDB"
            )
        ),
    ],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> SearchResults:
    """Find the one medium a source knows under an identifier.

    Args:
        provider: The source.
        id: The identifier.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The medium, or no result when the source knows none under the identifier.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``id`` when it is not in the source's format.
        AppUnavailable: ``provider.unavailable`` when the source could not answer: a failure is never no result.
    """
    return SearchResults.from_media(app_services.acquisition.search.lookup(signed_in, provider, id.strip()))


@router.get(
    "/acquisition/suggestions",
    operation_id="readSuggestions",
    response_model=list[SuggestionModel],
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_suggestions(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    after: Annotated[str | None, Query(description="continue a deck already started")] = None,
) -> list[SuggestionModel]:
    """The titles worth following, minus what the reader owns, follows or rejected.

    LIMIT OF THE CONTRACT: ``after`` is a title, and a title is not unique in the deck (a film and a show can
    bear the same one). The deck continues past the FIRST card of that title, so a reader whose last card is a
    second one of the same title is served again the cards between the two. An opaque cursor would lift it.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.
        after: The title of the last card the reader holds, to continue the deck past it.

    Returns:
        One page of the deck; empty when the deck has no more.
    """
    page = app_services.acquisition.suggestions.read(signed_in, None, after_title=after or None)
    return [SuggestionModel.from_card(card) for card in page.items]


@router.post(
    "/acquisition/ranking/preview",
    operation_id="previewRanking",
    response_model=RankingPreviewModel,
    status_code=200,
    responses=_PREVIEW_RESPONSES,
)
def preview_ranking(
    body: Annotated[RankingConfigBody, Body()],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> RankingPreviewModel:
    """Score the preview's fixed sample set under a candidate ranking.

    Read-only and pure: every sample stays visible, the ones under ``minSeeders`` flagged ``excluded`` and
    sunk last.

    Args:
        body: The candidate ranking.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The samples, scored and ordered, and the trackers a criterion may name.
    """
    ranking = app_services.acquisition.ranking
    scored = ranking.preview(signed_in, body.to_engine())
    return RankingPreviewModel(
        ranked=[RankingPreviewReleaseModel.from_preview(release) for release in scored],
        known_trackers=list(ranking.known_trackers),
    )
