"""Metadata provider protocol for TMDB and TVDB clients.

Defines the MetadataProvider Protocol — the common interface that both
TMDBClient and TVDBClient implement. Enables polymorphic usage in the
matching and orchestration phases (V3 phases 5-6, 11-12).

Each client adds type-specific methods (search_movie, get_tv_season, etc.)
beyond this minimal shared contract.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class MetadataProvider(Protocol):
    """Common interface for metadata providers (TMDB, TVDB).

    Inspired by tinyMediaManager. Enables testing with FakeProvider
    and future extensibility. Each client dispatches these methods
    to their type-specific implementations internally.
    """

    def search(self, title: str, year: int | None = None, media_type: str = "movie") -> list[dict]:
        """Search for a media item by title.

        Args:
            title: Media title to search for.
            year: Optional release year to boost relevance.
            media_type: Type of media ("movie" or "tv").

        Returns:
            List of raw API result dicts.
        """
        ...

    def get_details(self, media_id: int, media_type: str = "movie") -> dict:
        """Get full details for a media item (metadata + images + cross IDs).

        Args:
            media_id: Provider-specific media ID.
            media_type: Type of media ("movie" or "tv").

        Returns:
            Dict with full metadata, images, and external IDs.
        """
        ...

    def get_artwork_urls(self, media_id: int, media_type: str = "movie") -> list[dict]:
        """Get available artwork URLs for a media item.

        Args:
            media_id: Provider-specific media ID.
            media_type: Type of media ("movie" or "tv").

        Returns:
            List of artwork dicts with keys: "type" (poster|landscape|season_poster),
            "url", "language" (fr|en|None), "season" (int|None).
        """
        ...
