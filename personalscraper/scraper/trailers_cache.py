"""Cache for TMDB video responses and YouTube search results.

Uses ``JsonTTLCache`` for storage. TMDB video lists are cached for 7 days
(trailers don't change often). YouTube search results are cached for 7 days.

Key scheme:
    TMDB videos:    ``tmdb_videos:{media_type}:{tmdb_id}:{language}``
    YouTube search: ``yt_search:{title_hash}:{year}``
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from personalscraper.logger import get_logger
from personalscraper.scraper.json_ttl_cache import JsonTTLCache
from personalscraper.scraper.tmdb_client import Video

logger = get_logger(__name__)

_TMDB_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_YOUTUBE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# Sentinel stored when a YouTube search returned no results, to distinguish
# a "searched and found nothing" hit from a cache miss.
_NO_RESULT_SENTINEL: dict[str, bool] = {"__no_result__": True}


def _tmdb_key(tmdb_id: int, media_type: str, language: str) -> str:
    """Build the cache key for a TMDB video list entry.

    Args:
        tmdb_id: TMDB numeric ID.
        media_type: "movie" or "tv".
        language: BCP-47 language tag.

    Returns:
        Cache key string.
    """
    return f"tmdb_videos:{media_type}:{tmdb_id}:{language}"


def _yt_key(title: str, year: int | None) -> str:
    """Build the cache key for a YouTube search result.

    Uses a short SHA-1 digest of the title to avoid key length issues with
    long or unicode titles.

    Args:
        title: Media title.
        year: Release year, or None.

    Returns:
        Cache key string.
    """
    digest = hashlib.sha1(title.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"yt_search:{digest}:{year or 0}"


class TrailersCache:
    """File-backed cache for TMDB video lists and YouTube search results.

    Thin typed wrapper over ``JsonTTLCache``.

    Attributes:
        _cache: Underlying ``JsonTTLCache`` instance.
    """

    def __init__(self, path: Path) -> None:
        """Initialize the cache backed by ``path``.

        Args:
            path: Absolute path to the backing JSON file.
        """
        self._cache = JsonTTLCache(path)

    # ------------------------------------------------------------------
    # TMDB video lists
    # ------------------------------------------------------------------

    def get_tmdb_videos(self, tmdb_id: int, media_type: str, language: str) -> list[Video] | None:
        """Return cached TMDB video list or None on miss.

        Args:
            tmdb_id: TMDB numeric ID.
            media_type: "movie" or "tv".
            language: BCP-47 language tag.

        Returns:
            List of Video instances, or None on cache miss / expiry.
        """
        key = _tmdb_key(tmdb_id, media_type, language)
        raw = self._cache.get(key)
        if raw is None:
            return None
        try:
            return [Video(**v) for v in raw]
        except (TypeError, KeyError) as exc:
            logger.warning("trailers_cache_deserialize_failed", key=key, error=str(exc), exc_info=True)
            return None

    def set_tmdb_videos(self, tmdb_id: int, media_type: str, language: str, videos: list[Video]) -> None:
        """Cache a TMDB video list for 7 days.

        Args:
            tmdb_id: TMDB numeric ID.
            media_type: "movie" or "tv".
            language: BCP-47 language tag.
            videos: List of Video instances to cache.
        """
        key = _tmdb_key(tmdb_id, media_type, language)
        serialized: list[dict[str, Any]] = [
            {
                "id": v.id,
                "site": v.site,
                "key": v.key,
                "type": v.type,
                "official": v.official,
                "size": v.size,
                "iso_639_1": v.iso_639_1,
            }
            for v in videos
        ]
        self._cache.set(key, serialized, ttl_seconds=_TMDB_TTL_SECONDS)

    # ------------------------------------------------------------------
    # YouTube search results
    # ------------------------------------------------------------------

    def get_youtube_search(self, title: str, year: int | None) -> str | None:
        """Return cached YouTube URL, or None on cache miss.

        Note: a stored ``None`` (no result found) is returned as the sentinel
        string ``"__no_result__"`` — callers should treat any non-None return
        as a cache hit and check whether the value equals ``"__no_result__"``
        to distinguish a stored-nothing hit from a real URL.

        Args:
            title: Media title.
            year: Release year, or None.

        Returns:
            YouTube URL string, ``"__no_result__"`` sentinel, or None on miss.
        """
        key = _yt_key(title, year)
        raw = self._cache.get(key)
        if raw is None:
            return None
        if isinstance(raw, dict) and raw.get("__no_result__"):
            return "__no_result__"
        return str(raw)

    def set_youtube_search(self, title: str, year: int | None, url: str | None) -> None:
        """Cache a YouTube search result (URL or no-result) for 7 days.

        Args:
            title: Media title.
            year: Release year, or None.
            url: YouTube URL string, or None if no trailer was found.
        """
        key = _yt_key(title, year)
        value: Any = url if url is not None else _NO_RESULT_SENTINEL
        self._cache.set(key, value, ttl_seconds=_YOUTUBE_TTL_SECONDS)

    def contains_search(self, title: str, year: int | None) -> bool:
        """Return True if a fresh (non-expired) YouTube search result is cached.

        Uses ``JsonTTLCache.get`` which honours the per-entry TTL, so an entry
        that has passed its expiry is treated as a miss and returns False.
        This is the correct check to use in ``TrailerFinder.find()`` before
        calling the YouTube API.

        Args:
            title: Media title.
            year: Release year, or None.

        Returns:
            True when the key is present and the entry has not yet expired.
        """
        key = _yt_key(title, year)
        return self._cache.get(key) is not None

    def has_cached_search(self, title: str, year: int | None) -> bool:
        """Deprecated alias for ``contains_search``.

        Originally TTL-unaware, now delegates to the TTL-aware variant; new
        code should use ``contains_search``.  The legacy TTL-bypassing behavior
        is gone.

        Args:
            title: Media title.
            year: Release year, or None.

        Returns:
            True when the key is present and the entry has not yet expired.
        """
        return self.contains_search(title, year)
