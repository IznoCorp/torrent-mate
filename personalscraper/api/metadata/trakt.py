"""Trakt metadata provider.

Implements MetadataClient + MetadataProvider Protocol. Trakt API v2 with
header-based auth (trakt-api-key + trakt-api-version).

Trakt particularities:
- Dual-header auth (key + fixed version string).
- Response wrapper varies by endpoint (search, trending, details, related).
- Rating is native 0-10 float — no parsing needed.
- Image URLs are relative to media.trakt.tv.
- extended=full required for rich detail fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from personalscraper.api._contracts import ApiError, MediaType, ProviderName
from personalscraper.api.metadata._base import (
    ArtworkItem,
    MediaDetails,
    MetadataClient,
    Notations,
    Recommendation,
    SearchResult,
)
from personalscraper.api.metadata._contracts import (
    MovieDetailsProvider,
    RecommendationProvider,
    Searchable,
    TvDetailsProvider,
)
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport

log = get_logger("api.trakt")

_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0)
_DEFAULT_RETRY = RetryPolicy(max_attempts=3)
_DEFAULT_RATE = RateLimitPolicy(requests_per_second=5.0)

# Image base URL — Trakt returns relative paths like "media.trakt.tv/images/..."
_IMAGE_BASE = "https://"

# Image key → ArtworkItem.type mapping
_IMAGE_TYPE_MAP = {
    "poster": "poster",
    "fanart": "backdrop",
    "banner": "backdrop",
}


class TraktClient(
    MetadataClient,
    Searchable,
    MovieDetailsProvider,
    TvDetailsProvider,
    RecommendationProvider,
):
    """Trakt API v2 metadata provider.

    App-only auth via two headers (trakt-api-key + trakt-api-version: 2).
    Supports search, details, ratings, related movies, and trending.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["TRAKT_CLIENT_ID"]
    provider_name: ClassVar[str] = ProviderName.TRAKT.value

    @classmethod
    def policy(cls, client_id: str) -> TransportPolicy:
        """Build a TransportPolicy for Trakt.

        Args:
            client_id: Trakt Client ID from .env.

        Returns:
            TransportPolicy with dual-header auth and rate limiting.
        """
        return TransportPolicy(
            provider_name=ProviderName.TRAKT,
            base_url="https://api.trakt.tv",
            auth=ApiKeyAuth(client_id, param="trakt-api-key", location="header"),
            extra_headers={"trakt-api-version": "2"},
            timeout_seconds=10,
            retry=_DEFAULT_RETRY,
            circuit=_DEFAULT_CIRCUIT,
            rate_limit=_DEFAULT_RATE,
        )

    def __init__(self, transport: HttpTransport, *, language: str = "fr-FR") -> None:
        """Initialize Trakt client.

        Args:
            transport: HttpTransport pre-configured with Trakt policy.
            language: Language code (unused by Trakt, accepted for Protocol compat).
        """
        super().__init__(transport, language=language)

    # -- MetadataProvider Protocol ------------------------------------------

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        """Search Trakt by title.

        Args:
            title: Title string to search for.
            year: Optional release year filter.
            media_type: "movie" or "tv".

        Returns:
            List of SearchResult objects.
        """
        endpoint = "show" if media_type == "tv" else media_type
        params: dict[str, Any] = {"query": title}
        if year is not None:
            params["year"] = str(year)

        raw = self._transport.get(f"/search/{endpoint}", params=params)
        data = _assert_list(raw)
        key = "show" if media_type == "tv" else "movie"
        return _parse_search_results(data, provider=self.provider_name, key=key)

    def get_details(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> MediaDetails:
        """Fetch full details by Trakt ID, slug, or IMDb ID.

        Args:
            media_id: Trakt numeric ID, slug, or IMDb ID.
            media_type: "movie" or "tv".

        Returns:
            MediaDetails with parsed fields.

        Raises:
            ApiError: 404 or other HTTP error.
        """
        endpoint = "shows" if media_type == "tv" else "movies"
        data = _assert_dict(
            self._transport.get(
                f"/{endpoint}/{media_id}",
                params={"extended": "full"},
            )
        )
        return _parse_media_details(data, provider=self.provider_name, media_type=media_type)

    def get_movie(self, provider_id: str) -> MediaDetails:
        """MovieDetailsProvider Protocol alias for :meth:`get_details`.

        Adapter only — no caching. Callers picking the Protocol-style
        ``get_movie(id)`` and the legacy ``get_details(id,
        MediaType.MOVIE)`` for the same row issue two HTTP calls. Pick
        one style per call site.

        Args:
            provider_id: Trakt numeric ID, slug, or IMDb ID.

        Returns:
            Populated MediaDetails.
        """
        return self.get_details(provider_id, MediaType.MOVIE)

    def get_tv(self, provider_id: str) -> MediaDetails:
        """TvDetailsProvider Protocol alias for :meth:`get_details`.

        Adapter only — see :meth:`get_movie` for the no-cache caveat.

        Args:
            provider_id: Trakt numeric ID, slug, or IMDb ID.

        Returns:
            Populated MediaDetails.
        """
        return self.get_details(provider_id, MediaType.TV)

    def get_notations(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[Notations] | None:
        """Fetch Trakt community rating.

        Args:
            media_id: Trakt ID, slug, or IMDb ID.
            media_type: "movie" or "tv".

        Returns:
            List with a single Notations(source="trakt"), or None.
        """
        endpoint = "shows" if media_type == "tv" else "movies"
        data = _assert_dict(self._transport.get(f"/{endpoint}/{media_id}/ratings"))
        return _parse_notations(data, provider=self.provider_name)

    def get_recommendations(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[Recommendation]:
        """Fetch related movies/shows.

        Args:
            media_id: Trakt ID, slug, or IMDb ID.
            media_type: "movie" or "tv".

        Returns:
            List of Recommendation objects.
        """
        endpoint = "shows" if media_type == "tv" else "movies"
        raw = self._transport.get(f"/{endpoint}/{media_id}/related")
        data = _assert_list(raw)
        return _parse_related(data, provider=self.provider_name, media_type=media_type)


# -- Response type guards --------------------------------------------------


def _assert_dict(data: dict[str, Any] | list[Any] | str) -> dict[str, Any]:
    """Cast HttpTransport response to dict.

    HttpTransport.get() declares ``dict[str, Any] | str`` but its ``response_format='json'``
    branch returns whatever ``response.json()`` parses, which can include lists for
    array-shaped JSON. We widen the input union so callers don't need ``type: ignore``.
    """
    if not isinstance(data, dict):
        snippet = data if isinstance(data, str) else type(data).__name__
        raise ApiError(provider="trakt", http_status=0, message=f"Expected JSON object, got: {snippet!s:.200}")
    return data


def _assert_list(data: dict[str, Any] | list[Any] | str) -> list[dict[str, Any]]:
    """Cast HttpTransport response to list of dicts.

    HttpTransport.get() declares ``dict[str, Any] | str`` but its ``response_format='json'``
    branch returns whatever ``response.json()`` parses — Trakt search/related endpoints
    return JSON arrays. The widened union here matches the real transport return shape
    and removes the prior ``type: ignore[arg-type]`` at call sites.
    """
    if not isinstance(data, list):
        snippet = data if isinstance(data, str) else type(data).__name__
        raise ApiError(provider="trakt", http_status=0, message=f"Expected JSON array, got: {snippet!s:.200}")
    return data


# -- Response parsers ------------------------------------------------------


def _parse_search_results(data: list[dict[str, Any]], *, provider: str, key: str) -> list[SearchResult]:
    """Parse Trakt search response into SearchResult list.

    Search wraps items in {score, type, movie/show: {...}}.

    Args:
        data: Raw JSON array from /search/{type}.
        provider: Provider name for model labels.
        key: Sub-object key ("movie" or "show").

    Returns:
        List of SearchResult.
    """
    results: list[SearchResult] = []
    for item in data:
        inner = item.get(key, {})
        if not inner:
            continue
        ids = inner.get("ids", {})
        results.append(
            SearchResult(
                provider=provider,
                provider_id=_resolve_id(ids),
                title=inner.get("title", ""),
                year=inner.get("year"),
                media_type=MediaType.TV if key == "show" else MediaType.MOVIE,
                overview=inner.get("overview", ""),
            )
        )
    return results


def _parse_media_details(data: dict[str, Any], *, provider: str, media_type: MediaType) -> MediaDetails:
    """Parse Trakt detail response into MediaDetails.

    Args:
        data: Raw JSON object from /movies/{id}?extended=full.
        provider: Provider name for model labels.
        media_type: "movie" or "tv".

    Returns:
        MediaDetails with parsed fields.
    """
    ids = data.get("ids", {})
    imdb_id = ids.get("imdb", "")
    external_ids: dict[str, str] = {"imdb": imdb_id} if imdb_id else {}
    if ids.get("tmdb"):
        external_ids["tmdb"] = str(ids["tmdb"])
    if ids.get("tvdb"):
        external_ids["tvdb"] = str(ids["tvdb"])

    genres: list[str] = data.get("genres", [])

    images = _parse_images(data.get("images", {}))

    return MediaDetails(
        provider=provider,
        provider_id=_resolve_id(ids),
        title=data.get("title", ""),
        original_title=data.get("original_title", ""),
        year=data.get("year"),
        overview=data.get("overview", ""),
        genres=genres,
        runtime_minutes=data.get("runtime"),
        rating=data.get("rating"),
        images=images,
        external_ids=external_ids,
    )


def _parse_notations(data: dict[str, Any], *, provider: str) -> list[Notations] | None:
    """Parse Trakt ratings response.

    Args:
        data: Raw JSON from /movies/{id}/ratings.
        provider: Provider name for model labels.

    Returns:
        List with a single Notations(source="trakt"), or None if no rating.
    """
    rating = data.get("rating")
    if rating is None:
        return None
    votes = data.get("votes")
    return [
        Notations(
            provider=provider,
            source="trakt",
            score=float(rating),
            votes_count=int(votes) if votes else None,
        )
    ]


def _parse_related(data: list[dict[str, Any]], *, provider: str, media_type: MediaType) -> list[Recommendation]:
    """Parse Trakt related response into Recommendation list.

    Args:
        data: Raw JSON array from /movies/{id}/related.
        provider: Provider name for model labels.
        media_type: "movie" or "tv".

    Returns:
        List of Recommendation.
    """
    results: list[Recommendation] = []
    for item in data:
        ids = item.get("ids", {})
        results.append(
            Recommendation(
                provider=provider,
                provider_id=_resolve_id(ids),
                title=item.get("title", ""),
                year=item.get("year"),
                media_type=MediaType.TV if media_type == MediaType.TV else MediaType.MOVIE,
            )
        )
    return results


# -- Helpers ---------------------------------------------------------------


def _resolve_id(ids: dict[str, Any]) -> str:
    """Resolve the best ID from a Trakt ids block.

    Priority: slug > imdb > trakt (numeric).
    """
    slug = ids.get("slug")
    if slug:
        return str(slug)
    imdb = ids.get("imdb")
    if imdb:
        return str(imdb)
    trakt_id = ids.get("trakt")
    if trakt_id:
        return str(trakt_id)
    return ""


def _parse_images(images: dict[str, Any]) -> list[ArtworkItem]:
    """Parse Trakt images block into ArtworkItem list.

    Args:
        images: Raw images dict from Trakt detail response.

    Returns:
        List of ArtworkItem with full URLs.
    """
    results: list[ArtworkItem] = []
    for key, atype in _IMAGE_TYPE_MAP.items():
        urls = images.get(key, [])
        for url in urls:
            if url:
                results.append(
                    ArtworkItem(
                        type=cast(Literal["poster", "backdrop"], atype),
                        url=f"{_IMAGE_BASE}{url}",
                    )
                )
    return results
