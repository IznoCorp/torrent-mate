# personalscraper/core/identity.py
"""Neutral provider-ID value object for the acquisition lobe.

``MediaRef`` is deliberately NOT named ``ExternalIds`` — that name is taken
by ``indexer/external_ids.py`` (column-bound, series/episode hierarchical) and
``scraper/models.py::ScraperExternalIds`` (flat).  acquire/ may import neither
(layering), so a new neutral name is required.

tvdb_id is the primary identifier per the multi-provider separation rule:
TVDB primary (scrape), TMDB info+fallback, IMDB info only.

Import direction: stdlib + typing only (mirror core/_contracts.py).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaRef:
    """Neutral provider-ID value object keyed on tvdb_id (primary).

    At least one of tvdb_id, tmdb_id, imdb_id must be provided.

    Attributes:
        tvdb_id: TVDB series/movie ID (primary identifier).
        tmdb_id: TMDB series/movie ID (info + fallback).
        imdb_id: IMDB ID string e.g. ``"tt0000001"`` (info only).

    Raises:
        ValueError: If all three identifiers are None.
    """

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None

    def __post_init__(self) -> None:
        """Validate that at least one provider ID is set.

        Raises:
            ValueError: If tvdb_id, tmdb_id, and imdb_id are all None.
        """
        if self.tvdb_id is None and self.tmdb_id is None and self.imdb_id is None:
            raise ValueError("MediaRef requires at least one of tvdb_id, tmdb_id, imdb_id")


__all__ = ["MediaRef"]
