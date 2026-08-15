"""Tracker query construction for the acquire lobe (Follow D3 seam).

Extracted from ``orchestrator.py`` verbatim (module-size ceiling): the query
builder is consumed by the orchestrator's search chain, the ``grab --dry-run``
preview and the search-pass boundary, and it carries no orchestrator state.
``orchestrator`` re-exports it, so callers keep their historical import path.

Import direction: ``acquire/`` imports ``core/`` + stdlib only here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.acquire.domain import WantedItem


def build_search_query(item: "WantedItem", title: str | None, year: int | None = None) -> str:
    """Build a tracker search query from a wanted item + resolved series title.

    This is the Follow D3 title-resolution seam. When the series ``title`` is
    known (resolved from the followed-series row), an episode query becomes
    ``"{title} SxxEyy"`` and a movie query becomes ``"{title} {year}"`` when the
    year is known (« Wicker 2026 » — narrows an ambiguous title so the trackers
    do not return every « Wicker* » film, #28) or ``"{title}"`` otherwise — the
    form the title-based trackers (c411, tr4ker) actually match. When ``title``
    is ``None`` (standalone item with no followed row, or a resolver miss), it
    falls back to the primary provider ID string — the legacy behavior, which
    finds nothing on title-based trackers but keeps the query non-empty.

    The search chain calls it TWICE for a cross-language follow (#435): once
    with the display title, once — on a fruitless first attempt — with the
    original-language title.

    Args:
        item: The claimed wanted item (carries ``kind`` + ``season`` +
            ``episode`` + ``media_ref``).
        title: The resolved series/movie title, or ``None``.
        year: The movie's release year, or ``None`` — appended to a movie query
            to disambiguate the title (#28). Ignored for episodes.

    Returns:
        A non-empty query string.
    """
    if title:
        if item.kind == "episode" and item.season is not None and item.episode is not None:
            return f"{title} S{item.season:02d}E{item.episode:02d}"
        if item.kind == "season" and item.season is not None:
            return f"{title} S{item.season:02d}"
        if year is not None:
            return f"{title} {year}"
        return title
    media_ref = item.media_ref
    if media_ref.tvdb_id is not None:
        return str(media_ref.tvdb_id)
    if media_ref.tmdb_id is not None:
        return str(media_ref.tmdb_id)
    return str(media_ref.imdb_id)


__all__ = ["build_search_query"]
