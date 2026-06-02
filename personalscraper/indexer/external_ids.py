"""Pydantic models for the ``external_ids_json`` and ``ratings_json`` columns.

Migration 005 (``provider-ids`` feature) stores per-media-item provider
identifiers and per-source ratings as JSON strings on ``media_item``.
These two columns share the schema definitions captured here :

- :class:`ExternalIds` — hierarchical map ``{provider: {series_id,
  episode_id}}`` covering TVDB, TMDb and IMDb. Provider entries are
  optional ; missing keys mean the scraper never resolved that family.
- :class:`RatingEntry` — one ``Notations``-shaped rating row,
  normalised for NFO serialisation (``score`` stored as a string so
  ``"87%"`` / ``"8.5/10"`` survive round-trips).
- :class:`Ratings` — wrapper carrying the rating list.

The models exist primarily for :func:`personalscraper.indexer.scanner`
write paths and :func:`personalscraper.indexer.query` read paths.
Direct ``json.dumps`` is still acceptable on the write side ; the
models give the ``library`` / ``recommender`` / ``verify`` consumers a
typed handle on the JSON payloads.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Provider family literal. Matches the keys used by migration 005 +
# downstream JSON-path indices.
ProviderFamily = Literal["tvdb", "tmdb", "imdb"]

# Rating source literal. Mirrors :class:`Notations.source` from the
# metadata family for round-trip compatibility.
RatingSource = Literal["imdb", "tmdb", "rotten_tomatoes", "metacritic", "trakt"]


class ProviderIds(BaseModel):
    """Per-provider series + episode identifier pair.

    Both fields are optional — the scraper populates ``series_id`` once
    the canonical scrape resolves the ID, and ``episode_id`` once the
    xref enrichment pass surfaces an episode-level identifier.
    """

    series_id: str | None = None
    episode_id: str | None = None


class ExternalIds(BaseModel):
    """Hierarchical container for cross-provider IDs.

    Stored as the JSON payload of ``media_item.external_ids_json``.
    Missing provider entries are encoded as absent keys rather than
    ``None`` to keep the JSON compact and the json_extract indexes
    sparse.
    """

    tvdb: ProviderIds = Field(default_factory=ProviderIds)
    tmdb: ProviderIds = Field(default_factory=ProviderIds)
    imdb: ProviderIds = Field(default_factory=ProviderIds)


class RatingEntry(BaseModel):
    """A single rating row, mirroring ``api.metadata.Notations``.

    ``score`` is stored as a string so NFO-formatted values
    (``"8.5/10"``, ``"87%"``, ``"74/100"``) survive round-trips.
    Numeric clients convert on the fly. ``votes`` is optional —
    Rotten Tomatoes does not expose a vote count.
    """

    source: RatingSource
    score: str
    votes: int | None = None


class Ratings(BaseModel):
    """Collection of per-source rating rows for a media item.

    Stored as the JSON payload of ``media_item.ratings_json``. An
    empty list is valid and means "scraped, no rating available".
    """

    entries: list[RatingEntry] = Field(default_factory=list)


__all__ = [
    "ExternalIds",
    "ProviderIds",
    "RatingEntry",
    "Ratings",
    "RatingSource",
    "ProviderFamily",
]
