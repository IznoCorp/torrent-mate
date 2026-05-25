"""Pydantic models for the scraper service boundary.

These models type the data flowing into the scraper layer from the API
clients and out toward the NFO generator. They are distinct from the
indexer-layer :mod:`personalscraper.indexer.external_ids` models which
reflect the *DB column* shape.

Two models are exported:

- :class:`ScraperExternalIds` — flat series-level cross-provider IDs as
  they exist at the scraper boundary: ``tvdb_id`` (int), ``tmdb_id``
  (int), ``imdb_id`` (string). Optional fields; ``None`` means the
  scraper did not resolve that provider family.
- :class:`ScraperRatings` — typed container for a list of
  :class:`~personalscraper.api.metadata._base.Notations` rating rows,
  used as the typed counterpart of the legacy ``list[dict]`` that was
  threaded through service methods.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScraperExternalIds(BaseModel):
    """Series-level cross-provider IDs at the scraper boundary.

    Flat shape: one optional field per provider family. ``None`` means
    the scraper has not resolved that provider. Numeric IDs use ``int``
    because TVDB and TMDB return integers from their API; the IMDb ID
    is always a ``tt``-prefixed string.

    Attributes:
        tvdb_id: TVDB series identifier (integer), or None.
        tmdb_id: TMDB series identifier (integer), or None.
        imdb_id: IMDb identifier (e.g. ``"tt0000000"``), or empty string.
    """

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str = ""

    def to_external_ids_dict(self) -> dict[str, int | str]:
        """Return the legacy ``external_ids``-shaped dict for NFO consumers.

        The NFO generator and legacy code paths read provider IDs from
        a ``{"tvdb_id": ..., "tmdb_id": ..., "imdb_id": ...}`` dict keyed
        with the ``_id``-suffixed names. This helper produces that dict
        omitting ``None`` entries so the NFO generator can safely call
        ``external_ids.get("tvdb_id")`` and get ``None`` back for absent
        providers rather than a stale ``0``.

        Returns:
            Dict with only the non-None, non-empty fields.
        """
        result: dict[str, int | str] = {}
        if self.tvdb_id is not None:
            result["tvdb_id"] = self.tvdb_id
        if self.tmdb_id is not None:
            result["tmdb_id"] = self.tmdb_id
        if self.imdb_id:
            result["imdb_id"] = self.imdb_id
        return result


class ScraperRatings(BaseModel):
    """Typed container for per-source rating rows at the scraper boundary.

    Replaces the legacy ``list[dict]`` / ``list[Notations]`` patterns
    that were passed between service methods. The inner list type is
    :class:`~personalscraper.api.metadata._base.Notations` (a frozen
    dataclass from the API layer) — kept as ``Any`` here to avoid a
    hard import cycle; callers should import ``Notations`` directly when
    they need the full type.

    Attributes:
        entries: Ordered list of rating rows; empty means "no ratings
            resolved". Insertion order is the rendering order in the NFO.
    """

    entries: list[Any] = Field(default_factory=list)

    @classmethod
    def from_notations(cls, notations: list[Any]) -> "ScraperRatings":
        """Wrap a list of :class:`Notations` into a :class:`ScraperRatings`.

        Args:
            notations: List of ``Notations`` objects from the API layer.

        Returns:
            ScraperRatings wrapping the same list (no copy).
        """
        return cls(entries=list(notations))

    def is_empty(self) -> bool:
        """Return True when no ratings are available.

        Returns:
            True if the entries list is empty.
        """
        return len(self.entries) == 0


__all__ = [
    "ScraperExternalIds",
    "ScraperRatings",
]
