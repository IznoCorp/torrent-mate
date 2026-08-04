"""Pydantic models for the media sheet endpoint (media-sheet feature D1-D9).

``GET /api/media/{provider}/{provider_id}`` returns a :class:`MediaSheetResponse`
with identity, metadata from a live provider call, library ownership crossing,
and an optional ``degraded_reason`` when the provider is unreachable.
"""

from __future__ import annotations

from pydantic import BaseModel


class SeasonEntry(BaseModel):
    """One season entry in the media sheet season catalog.

    Attributes:
        season_number: Season number (1-based; 0 for specials).
        episode_count: Number of episodes in this season per the provider catalog.
    """

    season_number: int
    episode_count: int


class SeasonOwnership(BaseModel):
    """Ownership breakdown for one season of a TV show.

    Attributes:
        season_number: Season number (1-based; 0 for specials).
        episode_count: Total episodes in this season per the provider catalog.
        owned_count: How many episodes of this season are locally owned.
        aired_count: How many episodes have aired/released (provider catalog count).
    """

    season_number: int
    episode_count: int
    owned_count: int
    aired_count: int


class OwnershipBlock(BaseModel):
    """Library ownership status for a media item.

    Attributes:
        owned: ``True`` when at least one file for this media is locally owned.
        seasons: Per-season breakdown for TV shows; empty for movies.
    """

    owned: bool
    seasons: list[SeasonOwnership] = []


class MediaSheetResponse(BaseModel):
    """Full media sheet returned by ``GET /api/media/{provider}/{provider_id}``.

    Identity fields (provider, provider_id, title) are always present — even
    under degradation they survive because they come from the call parameters or
    a partial provider response.  Metadata fields are ``None`` when the provider
    does not supply them (DESIGN D4/D9 — never an empty string).

    Attributes:
        provider: Provider name (``"tmdb"`` / ``"tvdb"``).
        provider_id: Provider-specific media identifier.
        title: Display title.
        year: Release year, or ``None``.
        poster_url: Full URL to the poster image.
        overview: Full plot summary.
        director: Director name, or ``None`` when unknown.
        genres: List of genre names.
        trailer_url: YouTube trailer URL, or ``None``.
        series_status: TV series production status, or ``None`` for movies.
        episode_count: Total episode count for a TV series, or ``None``
            for movies (from the provider's series-level metadata).
        seasons: Season catalog (season number → episode count per season).
        ownership: Library ownership block, or ``None`` when the library
            database is unavailable (fail-soft).
        degraded_reason: French human-readable reason when the provider was
            unreachable and the response is partial. ``None`` on a full response.
    """

    provider: str
    provider_id: str
    title: str
    year: int | None
    poster_url: str
    overview: str
    director: str | None
    genres: list[str]
    trailer_url: str | None
    series_status: str | None
    episode_count: int | None = None
    seasons: list[SeasonEntry]
    ownership: OwnershipBlock | None
    degraded_reason: str | None
