"""Unit tests for TrailersCache — TMDB video and YouTube search result caching."""

from pathlib import Path

import pytest

from personalscraper.scraper.tmdb_client import Video
from personalscraper.scraper.trailers_cache import TrailersCache


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
