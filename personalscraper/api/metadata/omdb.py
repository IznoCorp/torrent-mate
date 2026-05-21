"""OMDb metadata HTTP backend (internal — use IMDbClient / RottenTomatoesClient).

Implements MetadataClient + MetadataProvider Protocol. Single-endpoint API
with query-param auth (apikey=). Returns typed models from _base.py.

OMDb particularities:
- Always returns HTTP 200; errors signaled via Response: "False" in body.
- Ratings[] values are unparsed strings ("8.8/10", "87%", "74/100").
- Year can be "YYYY", "YYYY–", or "YYYY–YYYY".
- Runtime is "NNN min" string.
- "N/A" sentinel used for missing optional fields.

**Scope (provider-ids feature)** — :class:`OMDbAdapter` is the canonical
name for this client. It is an *internal HTTP backend* shared by the
:class:`~personalscraper.api.metadata.imdb.IMDbClient` and
:class:`~personalscraper.api.metadata.rotten_tomatoes.RottenTomatoesClient`
façades. The scraper layer must not call OMDb directly — it goes
through the IMDb / RT façades, which expose the business semantics
(``get_rating``, ``validate_id``, ``get_cross_refs``) while sharing a
single underlying HTTP client (one rate-limit budget, one circuit
breaker). ``OMDBClient`` is preserved as a backward-compatible alias
for existing import sites; new code should import ``OMDbAdapter``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from personalscraper.api._contracts import ApiError, MediaType, ProviderName
from personalscraper.api.metadata._base import (
    ArtworkItem,
    MediaDetails,
    MetadataClient,
    Notations,
    Recommendation,
    SearchResult,
)
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport

log = get_logger("api.omdb")

_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0)
_DEFAULT_RETRY = RetryPolicy(max_attempts=3)

# OMDB source label to Notations.source literal
_SOURCE_MAP: dict[str, Literal["imdb", "rotten_tomatoes", "metacritic"]] = {
    "Internet Movie Database": "imdb",
    "Rotten Tomatoes": "rotten_tomatoes",
    "Metacritic": "metacritic",
}

# OMDB type string → MediaType
_OMDB_TYPE_MAP: dict[str, MediaType] = {
    "movie": MediaType.MOVIE,
    "series": MediaType.TV,
}


class OMDbAdapter(MetadataClient):
    """Internal OMDb HTTP backend shared by the IMDb and Rotten Tomatoes façades.

    Authentication via API key as query parameter (apikey=).
    Free tier: 1000 req/day.

    Direct use is discouraged — call sites in the scraper layer
    must compose
    :class:`~personalscraper.api.metadata.imdb.IMDbClient` and
    :class:`~personalscraper.api.metadata.rotten_tomatoes.RottenTomatoesClient`
    instead (DESIGN §4). A single ``OMDbAdapter`` instance backs both
    façades so the rate-limit and circuit-breaker budgets stay
    consolidated.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["OMDB_API_KEY"]
    provider_name: ClassVar[str] = ProviderName.OMDB.value

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        """Build a TransportPolicy for OMDB.

        Args:
            api_key: OMDB API key from .env.

        Returns:
            TransportPolicy configured for the OMDB single endpoint.
        """
        return TransportPolicy(
            provider_name=ProviderName.OMDB,
            base_url="http://www.omdbapi.com",
            auth=ApiKeyAuth(api_key, param="apikey", location="query"),
            timeout_seconds=10,
            retry=_DEFAULT_RETRY,
            circuit=_DEFAULT_CIRCUIT,
        )

    def __init__(self, transport: HttpTransport, *, language: str = "fr-FR") -> None:
        """Initialize OMDB client.

        Args:
            transport: HttpTransport pre-configured with OMDB policy.
            language: Language code (unused by OMDB, accepted for Protocol compat).
        """
        super().__init__(transport, language=language)

    # -- MetadataProvider Protocol ------------------------------------------

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        """Search OMDB by title.

        Args:
            title: Title string to search for.
            year: Optional release year filter.
            media_type: "movie" or "tv" (OMDB uses "series").

        Returns:
            List of SearchResult objects.
        """
        omdb_type = "series" if media_type == "tv" else "movie"
        params: dict[str, Any] = {"s": title, "type": omdb_type}
        if year is not None:
            params["y"] = str(year)

        data = _assert_dict(self._transport.get(params=params))
        return _parse_search_results(data, provider=self.provider_name)

    def get_details(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> MediaDetails:
        """Fetch full details by IMDb ID.

        Args:
            media_id: IMDb ID (e.g. "tt1375666").
            media_type: "movie" or "tv".

        Returns:
            MediaDetails with parsed fields.

        Raises:
            ApiError: OMDB returned Response: "False".
        """
        data = _assert_dict(self._transport.get(params={"i": media_id}))
        return _parse_media_details(data, provider=self.provider_name, media_type=media_type)

    def get_notations(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[Notations] | None:
        """Fetch ratings from OMDB's Ratings[] array.

        Args:
            media_id: IMDb ID.
            media_type: "movie" or "tv".

        Returns:
            List of Notations (one per source), or None if no ratings.
        """
        data = _assert_dict(self._transport.get(params={"i": media_id}))
        return _parse_notations(data, provider=self.provider_name)

    def get_recommendations(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[Recommendation]:
        """OMDB has no recommendations endpoint — returns empty list."""
        return []


# -- Response parsers -------------------------------------------------------


# Backward-compatible alias — existing import sites keep working. The
# canonical name is :class:`OMDbAdapter` (DESIGN §4). New code must
# import :class:`OMDbAdapter` so the role (internal HTTP backend) is
# explicit at the call site.
OMDBClient = OMDbAdapter


def _assert_dict(data: dict[str, Any] | str) -> dict[str, Any]:
    """Cast HttpTransport response to dict; transport guarantees JSON parse."""
    if isinstance(data, str):
        raise ApiError(
            provider="omdb",
            http_status=0,
            message=f"Unexpected string response from OMDB: {data[:200]}",
        )
    return data


def _check_response(data: dict[str, Any]) -> None:
    """Raise ApiError if OMDB Response is "False"."""
    if data.get("Response") == "False":
        raise ApiError(
            provider="omdb",
            http_status=200,
            message=data.get("Error", "Unknown OMDB error"),
        )


def _sentinel(value: str) -> str | None:
    """Convert "N/A" sentinel to None."""
    if value == "N/A":
        return None
    return value


def _parse_year(raw: str | None) -> int | None:
    """Parse first 4-digit integer from Year field.

    Handles "2010", "2008–2013", "1989–".
    """
    if not raw:
        return None
    m = re.search(r"(\d{4})", raw)
    if m:
        return int(m.group(1))
    return None


def _parse_runtime(raw: str | None) -> int | None:
    """Parse int from "148 min" string."""
    if not raw or raw == "N/A":
        return None
    m = re.search(r"(\d+)", raw)
    if m:
        return int(m.group(1))
    return None


def _parse_rating_value(raw: str) -> float:
    """Normalize a rating value string to 0-10 float.

    Args:
        raw: Rating value, e.g. "8.8/10", "87%", "74/100".

    Returns:
        Float in 0-10 range.
    """
    raw = raw.strip()
    if "/" in raw:
        score_str, _, scale_str = raw.partition("/")
        score = float(score_str.strip())
        scale = float(scale_str.strip()) if scale_str.strip() else 10.0
        return score * 10.0 / scale if scale != 10.0 else score
    if raw.endswith("%"):
        return float(raw[:-1]) / 10.0
    return float(raw)


def _parse_search_results(data: dict[str, Any], *, provider: str) -> list[SearchResult]:
    """Parse OMDB search response into SearchResult list.

    Args:
        data: Raw JSON response from OMDB ?s= query.
        provider: Provider name for model labels.

    Returns:
        List of SearchResult.
    """
    _check_response(data)
    results: list[SearchResult] = []
    for item in data.get("Search", []):
        year = _parse_year(item.get("Year"))
        omdb_type = item.get("Type", "movie")
        media_type = _OMDB_TYPE_MAP.get(omdb_type, MediaType.MOVIE)
        results.append(
            SearchResult(
                provider=provider,
                provider_id=item.get("imdbID", ""),
                title=item.get("Title", ""),
                year=year,
                media_type=media_type,
                poster_url=item.get("Poster", ""),
            )
        )
    return results


def _parse_media_details(data: dict[str, Any], *, provider: str, media_type: MediaType) -> MediaDetails:
    """Parse OMDB title/ID detail response into MediaDetails.

    Args:
        data: Raw JSON response from OMDB ?t= or ?i= query.
        provider: Provider name for model labels.
        media_type: "movie" or "tv".

    Returns:
        MediaDetails with parsed fields.
    """
    _check_response(data)

    genre_str = _sentinel(data.get("Genre", "")) or ""
    genres = [g.strip() for g in genre_str.split(",") if g.strip()]

    poster = _sentinel(data.get("Poster", ""))
    images: list[ArtworkItem] = []
    if poster:
        images.append(ArtworkItem(type="poster", url=poster))

    imdb_id = data.get("imdbID", "")
    external_ids: dict[str, str] = {"imdb": imdb_id} if imdb_id else {}

    imdb_rating = None
    raw_imdb = data.get("imdbRating", "N/A")
    if raw_imdb != "N/A":
        try:
            imdb_rating = float(raw_imdb)
        except (ValueError, TypeError):
            pass

    return MediaDetails(
        provider=provider,
        provider_id=imdb_id,
        title=data.get("Title", ""),
        year=_parse_year(data.get("Year")),
        overview=data.get("Plot", ""),
        genres=genres,
        runtime_minutes=_parse_runtime(data.get("Runtime")),
        rating=imdb_rating,
        images=images,
        external_ids=external_ids,
    )


def _parse_notations(data: dict[str, Any], *, provider: str) -> list[Notations] | None:
    """Parse OMDB Ratings[] array into list of Notations.

    Args:
        data: Raw JSON response from OMDB ?i= query.
        provider: Provider name for model labels.

    Returns:
        List of Notations (one per source), or None if no ratings available.
    """
    _check_response(data)
    ratings: list[dict[str, str]] = data.get("Ratings", [])
    if not ratings:
        return None

    notations: list[Notations] = []
    for r in ratings:
        source_label = r.get("Source", "")
        source = _SOURCE_MAP.get(source_label)
        if source is None:
            log.debug("omdb_unknown_rating_source", source=source_label)
            continue

        raw_value = r.get("Value", "")
        try:
            score = _parse_rating_value(raw_value)
        except (ValueError, TypeError):
            log.warning("omdb_unparseable_rating", source=source_label, value=raw_value)
            continue

        notations.append(
            Notations(
                provider=provider,
                source=source,
                score=score,
            )
        )

    return notations if notations else None
