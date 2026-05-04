"""Unit tests for TrailersCache — TMDB video and YouTube search result caching."""

import json
import threading
from datetime import timezone
from pathlib import Path

import pytest

from personalscraper.api.metadata._base import Video
from personalscraper.scraper.trailers_cache import TrailersCache

UTC = timezone.utc


@pytest.fixture()
def cache(tmp_path: Path) -> TrailersCache:
    """A fresh TrailersCache backed by a temp directory."""
    return TrailersCache(tmp_path / "trailers_cache.json")


_VIDEO = Video(
    id="abc",
    site="YouTube",
    key="XYZ123",
    type="Trailer",
    official=True,
    size=1080,
    iso_639_1="en",
)


class TestTmdbVideosCache:
    """Tests for TMDB video list caching behaviour."""

    def test_miss_returns_none(self, cache: TrailersCache) -> None:
        """get_tmdb_videos() returns None when the key is absent."""
        assert cache.get_tmdb_videos(550, "movie", "en-US") is None

    def test_set_then_get_returns_list(self, cache: TrailersCache) -> None:
        """get_tmdb_videos() returns the stored list after set_tmdb_videos()."""
        cache.set_tmdb_videos(550, "movie", "en-US", [_VIDEO])
        result = cache.get_tmdb_videos(550, "movie", "en-US")
        assert result is not None
        assert len(result) == 1
        assert result[0].key == "XYZ123"

    def test_different_languages_are_independent(self, cache: TrailersCache) -> None:
        """Entries for different languages do not collide."""
        cache.set_tmdb_videos(550, "movie", "en-US", [_VIDEO])
        assert cache.get_tmdb_videos(550, "movie", "fr-FR") is None

    def test_different_media_types_are_independent(self, cache: TrailersCache) -> None:
        """Entries for 'movie' and 'tv' do not collide."""
        cache.set_tmdb_videos(550, "movie", "en-US", [_VIDEO])
        assert cache.get_tmdb_videos(550, "tv", "en-US") is None


class TestYoutubeSearchCache:
    """Tests for YouTube search result caching behaviour."""

    def test_miss_returns_none(self, cache: TrailersCache) -> None:
        """get_youtube_search() returns None when the key is absent."""
        assert cache.get_youtube_search("Fight Club", 1999) is None

    def test_set_then_get_returns_url(self, cache: TrailersCache) -> None:
        """get_youtube_search() returns the stored URL after set_youtube_search()."""
        url = "https://www.youtube.com/watch?v=test123"
        cache.set_youtube_search("Fight Club", 1999, url)
        assert cache.get_youtube_search("Fight Club", 1999) == url

    def test_none_url_is_stored(self, cache: TrailersCache) -> None:
        """A None result (no trailer found) should also be cacheable.

        Uses the public ``has_cached_search()`` API to distinguish a true
        cache miss from a stored "no trailer found" sentinel — no
        implementation-private helpers (`_make_yt_key`, `_has_key`) are
        imported from the test.
        """
        # Miss before set
        assert cache.has_cached_search("Obscure Movie", 2020) is False
        # Store a None result (the implementation records a sentinel internally)
        cache.set_youtube_search("Obscure Movie", 2020, None)
        # Hit after set, even though the cached "value" is None
        assert cache.has_cached_search("Obscure Movie", 2020) is True
        # get_youtube_search returns the sentinel marker (implementation-defined;
        # see TrailersCache docstring for the exact sentinel value).
        result = cache.get_youtube_search("Obscure Movie", 2020)
        assert result is not None  # sentinel, not a miss


class TestContainsSearch:
    """Tests for TrailersCache.contains_search — TTL-aware hit detection."""

    def test_contains_search_returns_false_on_miss(self, cache: TrailersCache) -> None:
        """contains_search() returns False when no entry has been written."""
        assert cache.contains_search("Unknown Movie", 2020) is False

    def test_contains_search_returns_true_when_fresh(self, cache: TrailersCache) -> None:
        """contains_search() returns True for a freshly written entry."""
        cache.set_youtube_search("Fight Club", 1999, "https://www.youtube.com/watch?v=abc")
        assert cache.contains_search("Fight Club", 1999) is True

    def test_contains_search_returns_false_after_ttl_expiry(self, tmp_path: Path) -> None:
        """contains_search() returns False for an entry whose TTL has elapsed.

        Writes a raw JSON entry with a ``cached_at`` timestamp far in the past
        (older than the 7-day YouTube TTL) and asserts that ``contains_search``
        treats it as a miss even though the key is present on disk.
        """
        cache_path = tmp_path / "trailers_cache.json"
        trailers_cache = TrailersCache(cache_path)

        # Import the internal key builder to inject the expired entry directly.
        from personalscraper.scraper.trailers_cache import _yt_key

        key = _yt_key("Stale Movie", 2010)
        # Write an entry dated 8 days ago (past the 7-day TTL).
        eight_days_ago = "2020-01-01T00:00:00+00:00"
        raw = {
            key: {
                "value": "https://www.youtube.com/watch?v=stale",
                "cached_at": eight_days_ago,
                "ttl_seconds": 7 * 24 * 3600,
            }
        }
        cache_path.write_text(json.dumps(raw), encoding="utf-8")

        # TTL-aware check: the key is present but expired → False.
        assert trailers_cache.contains_search("Stale Movie", 2010) is False
        # The underlying get() also returns None for an expired entry.
        assert trailers_cache.get_youtube_search("Stale Movie", 2010) is None

    def test_set_does_not_drop_concurrent_writes(self, tmp_path: Path) -> None:
        """Two threads setting distinct keys concurrently both survive.

        Exercises the fcntl advisory lock in JsonTTLCache: two threads race to
        call ``set_youtube_search`` for different titles.  After both threads
        finish, both keys must be readable from the same backing file.
        """
        cache_path = tmp_path / "concurrent.json"
        # Create separate TrailersCache instances backed by the same file so
        # both threads go through the same locking path.
        cache_a = TrailersCache(cache_path)
        cache_b = TrailersCache(cache_path)

        url_a = "https://www.youtube.com/watch?v=AAA"
        url_b = "https://www.youtube.com/watch?v=BBB"

        errors: list[Exception] = []

        def write_a() -> None:
            try:
                cache_a.set_youtube_search("Movie A", 2001, url_a)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def write_b() -> None:
            try:
                cache_b.set_youtube_search("Movie B", 2002, url_b)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=write_a)
        t2 = threading.Thread(target=write_b)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"

        # Both entries must survive — no concurrent write dropped an entry.
        reader = TrailersCache(cache_path)
        assert reader.get_youtube_search("Movie A", 2001) == url_a, "Entry A was dropped by concurrent write"
        assert reader.get_youtube_search("Movie B", 2002) == url_b, "Entry B was dropped by concurrent write"
