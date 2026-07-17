"""Atomic capability protocols for the metadata family (DESIGN §4).

Decomposes the historical monolithic ``MetadataProvider`` Protocol
(``api/metadata/_base.py``) into 11 single-purpose, ``@runtime_checkable``
protocols. Each concrete provider — TVDB, TMDB, IMDb façade, RT façade —
composes only the capabilities it actually implements (DESIGN §4
"Composition par client").

The protocols are deliberately structural: a class satisfies a capability
by exposing the right method name and signature, without inheriting.
This unlocks ``isinstance(provider, RatingProvider)`` checks in helpers
(``gather_ratings``) that operate on heterogeneous provider collections.

One capability is **new** — it does not derive from a method on the
legacy ``MetadataProvider`` — and exists to support the multi-provider IDs
work (DESIGN §3 "Hiérarchie scrape canonique") :

- :class:`IDValidator` — re-validate a provider-side ID against an
  expected title / year tuple (Q5=B revalidation rule).

Cross-provider ID resolution (TVDB ↔ TMDB ↔ IMDb) is owned by the
external-ids flow (``scraper._xref`` + the indexer backfill), not by a
capability Protocol.

The remaining 9 capabilities derive from the 8 public methods of the
existing ``MetadataProvider`` Protocol (``get_details()`` splits into
``MovieDetailsProvider`` + ``TvDetailsProvider``).

Phase 1.2 ships only these contracts. Client classes (``TMDbClient``,
``TVDbClient``, …) are not modified here; they continue to expose the
legacy method names (``get_details``, ``get_season``, ``get_notations``)
until later phases refactor them. ``isinstance`` checks against current
clients will therefore return ``False`` until those phases land — by
design, since these capabilities describe the *target* shape.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    Notations,
    Recommendation,
    SearchResult,
    Video,
)


@runtime_checkable
class Searchable(Protocol):
    """Capability — search by title + optional year + media type.

    Concrete signatures follow the legacy ``MetadataProvider.search``
    method so that any future refactor of clients to declare this
    Protocol explicitly composes without touching call sites.
    """

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]: ...


@runtime_checkable
class MovieDetailsProvider(Protocol):
    """Capability — fetch full details for a movie by provider-side ID.

    Counterpart to :class:`TvDetailsProvider`. Returns the shared
    :class:`MediaDetails` dataclass; the split into provider-side
    ``MovieDetails`` / ``TvDetails`` types (DESIGN §4.2) is deferred to
    a later refinement and does not gate the capability shape.

    The ``provider_id`` parameter accepts ``int | str`` because some
    callers parse the ID from an NFO (returns ``int``) while others
    receive it as a string from the registry or search results. Concrete
    clients coerce internally — see ``TMDBClient.get_movie`` /
    ``TVDBClient.get_movie``.
    """

    def get_movie(self, provider_id: int | str) -> MediaDetails: ...


@runtime_checkable
class TvDetailsProvider(Protocol):
    """Capability — fetch full details for a TV show by provider-side ID.

    The ``provider_id`` parameter accepts ``int | str`` for the same
    reason as :class:`MovieDetailsProvider.get_movie` — NFO-parsed IDs
    arrive as ``int``, other call sites pass ``str``.
    """

    def get_tv(self, provider_id: int | str) -> MediaDetails: ...


@runtime_checkable
class EpisodeFetcher(Protocol):
    """Capability — fetch the episode list of a season for a TV show.

    Returns ``list[EpisodeInfo]`` rather than the legacy
    :class:`SeasonDetails` wrapper so each capability composes
    independently and consumers may iterate without unwrapping a
    nominal container.
    """

    def get_episodes(self, series_id: str, season: int) -> list[EpisodeInfo]: ...


@runtime_checkable
class RatingProvider(Protocol):
    """Capability — fetch provider-side rating(s) for a media item.

    Returns ``list[Notations] | None``: ``None`` when the provider has
    no rating for this ID, an empty list when querying succeeded but
    the provider reports no notation, and a non-empty list otherwise.
    Multiple :class:`Notations` per provider are allowed (e.g. IMDb +
    Rotten Tomatoes both surface through the OMDb backend).
    """

    def get_rating(self, provider_id: str) -> list[Notations] | None: ...


@runtime_checkable
class IDValidator(Protocol):
    """Capability — re-validate a provider-side ID against expected title / year.

    Used at scrape time to reject hallucinated or stale IDs (DESIGN §3,
    rule Q5=B). Returns ``True`` when the provider confirms the ID
    points at a media item whose title and year match within the
    provider-defined tolerance.
    """

    def validate_id(
        self,
        provider_id: str,
        expected_title: str,
        expected_year: int | None,
    ) -> bool: ...


@runtime_checkable
class ArtworkProvider(Protocol):
    """Capability — fetch artwork URLs (poster, landscape, season poster, backdrop)."""

    def get_artwork_urls(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[ArtworkItem]: ...


@runtime_checkable
class KeywordProvider(Protocol):
    """Capability — fetch the keyword / tag list for a media item."""

    def get_keywords(
        self,
        media_id: str,
        media_type: MediaType,
    ) -> list[str]: ...


@runtime_checkable
class VideoProvider(Protocol):
    """Capability — fetch trailers / featurettes for a media item in a target language."""

    def get_videos(
        self,
        media_id: str,
        media_type: MediaType,
        language: str,
    ) -> list[Video]: ...


@runtime_checkable
class RecommendationProvider(Protocol):
    """Capability — fetch provider-side related-content recommendations."""

    def get_recommendations(
        self,
        media_id: str,
        media_type: MediaType,
    ) -> list[Recommendation]: ...


__all__ = [
    "Searchable",
    "MovieDetailsProvider",
    "TvDetailsProvider",
    "EpisodeFetcher",
    "RatingProvider",
    "IDValidator",
    "ArtworkProvider",
    "KeywordProvider",
    "VideoProvider",
    "RecommendationProvider",
]
