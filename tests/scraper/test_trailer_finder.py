"""Unit tests for TrailerFinder — TMDB-first / YouTube-fallback discovery.

All external dependencies (TMDBClient, YoutubeSearch, TrailersCache) are mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.scraper.circuit_breaker import CircuitBreaker, CircuitOpenError
from personalscraper.scraper.tmdb_client import Video
from personalscraper.scraper.trailer_finder import TrailerFinder
from personalscraper.scraper.trailers_cache import TrailersCache

_TRAILER_VIDEO = Video(
    id="abc",
    site="YouTube",
    key="TRAILER_KEY",
    type="Trailer",
    official=True,
    size=1080,
    iso_639_1="en",
)
_TEASER_VIDEO = Video(
    id="def",
    site="YouTube",
    key="TEASER_KEY",
    type="Teaser",
    official=True,
    size=720,
    iso_639_1="en",
)
_YT_URL = "https://www.youtube.com/watch?v=TRAILER_KEY"


@pytest.fixture()
def finder(tmp_path: Path) -> TrailerFinder:
    """Build a TrailerFinder with mocked TMDBClient and YoutubeSearch."""
    client = MagicMock()
    searcher = MagicMock()
    cache = TrailersCache(tmp_path / "tc.json")
    return TrailerFinder(
        tmdb_client=client,
        youtube_search=searcher,
        cache=cache,
        languages=["fr-FR", "en-US"],
    )


class TestTrailerFinder:
    """Tests for TrailerFinder two-tier discovery strategy."""

    def test_returns_tmdb_trailer_url(self, finder: TrailerFinder) -> None:
        """find() returns YouTube URL for first Trailer type from TMDB."""
        finder._tmdb_client._fetch_videos_strict.return_value = [_TRAILER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_tmdb_teaser_used_when_no_trailer(self, finder: TrailerFinder) -> None:
        """find() falls back to Teaser if no Trailer type exists in TMDB results."""
        finder._tmdb_client._fetch_videos_strict.return_value = [_TEASER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == "https://www.youtube.com/watch?v=TEASER_KEY"

    def test_youtube_fallback_on_empty_tmdb(self, finder: TrailerFinder) -> None:
        """find() falls back to YouTube search when TMDB returns no videos."""
        finder._tmdb_client._fetch_videos_strict.return_value = []
        finder._youtube_search.search.return_value = _YT_URL
        finder._youtube_search._breaker = CircuitBreaker(name="yt-test", failure_threshold=5)
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_returns_none_when_both_fail(self, finder: TrailerFinder) -> None:
        """find() returns None when TMDB and YouTube both return nothing."""
        finder._tmdb_client._fetch_videos_strict.return_value = []
        finder._youtube_search.search.return_value = None
        finder._youtube_search._breaker = CircuitBreaker(name="yt-test", failure_threshold=5)
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url is None

    def test_language_priority_fr_before_en(self, finder: TrailerFinder) -> None:
        """find() queries fr-FR before en-US and returns on first hit."""

        def fetch_side_effect(endpoint: str, tmdb_id: int, media_type: str, language: str) -> list[Video]:
            if language == "fr-FR":
                return [_TRAILER_VIDEO]
            return []

        finder._tmdb_client._fetch_videos_strict.side_effect = fetch_side_effect
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        # Only one call (fr-FR) because it already found a result
        assert finder._tmdb_client._fetch_videos_strict.call_count == 1

    def test_tv_show_uses_fetch_tv_videos(self, finder: TrailerFinder) -> None:
        """find() calls _fetch_videos_strict with the tv endpoint for media_type='tv'."""
        finder._tmdb_client._fetch_videos_strict.return_value = [_TRAILER_VIDEO]
        url = finder.find(1399, "tv", title="Game of Thrones", year=2011)
        assert url == _YT_URL
        # Verify it was called with the TV endpoint
        call_args = finder._tmdb_client._fetch_videos_strict.call_args
        assert "/tv/1399/videos" in call_args[0][0]

    def test_cache_hit_skips_network(self, finder: TrailerFinder) -> None:
        """find() returns cached URL without calling TMDBClient or YoutubeSearch."""
        # Prime the cache directly
        finder._cache.set_tmdb_videos(550, "movie", "fr-FR", [_TRAILER_VIDEO])
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        finder._tmdb_client._fetch_videos_strict.assert_not_called()

    def test_non_youtube_videos_filtered_out(self, finder: TrailerFinder) -> None:
        """find() ignores non-YouTube videos even when they are Trailers."""
        vimeo_video = Video(
            id="xyz",
            site="Vimeo",
            key="vimeo-id",
            type="Trailer",
            official=True,
            size=1080,
            iso_639_1="en",
        )
        finder._tmdb_client._fetch_videos_strict.return_value = [vimeo_video]
        finder._youtube_search.search.return_value = _YT_URL
        finder._youtube_search._breaker = CircuitBreaker(name="yt-test", failure_threshold=5)
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        # Vimeo entry must be ignored; YouTube search fallback should be used.
        assert url == _YT_URL
        finder._youtube_search.search.assert_called_once()

    def test_season_uses_fetch_tv_season_videos(self, finder: TrailerFinder) -> None:
        """find() calls _fetch_videos_strict with the season endpoint."""
        finder._tmdb_client._fetch_videos_strict.return_value = [_TRAILER_VIDEO]
        url = finder.find(1399, "tv", title="Game of Thrones", year=2011, season_number=1)
        assert url == _YT_URL
        call_args = finder._tmdb_client._fetch_videos_strict.call_args
        assert "/tv/1399/season/1/videos" in call_args[0][0]


class TestCachePoisoningPrevention:
    """Tests for C5/C6 — outage errors must NOT poison the cache."""

    def test_tmdb_outage_does_not_cache_empty_for_a_week(self, tmp_path: Path) -> None:
        """A TMDB CircuitOpenError must not write an empty entry to TrailersCache.

        Scenario:
          1. TMDB circuit is open → _fetch_videos_strict raises CircuitOpenError.
          2. Assert: no entry written to the cache (the key is absent).
          3. Next call with TMDB returning a real movie → trailer is found
             (not blocked by a cached empty list from step 1).
        """
        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)

        client = MagicMock()
        searcher = MagicMock()
        searcher._breaker = CircuitBreaker(name="yt-test", failure_threshold=5)

        finder = TrailerFinder(
            tmdb_client=client,
            youtube_search=searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # Step 1: TMDB raises CircuitOpenError on every call.
        client._fetch_videos_strict.side_effect = CircuitOpenError("TMDB", 9999.0)
        searcher.search.return_value = None  # YouTube also returns nothing

        result1 = finder.find(550, "movie", title="Fight Club", year=1999)
        assert result1 is None

        # Step 2: The cache must NOT have stored an empty entry for the TMDB key.
        assert trailers_cache.get_tmdb_videos(550, "movie", "en-US") is None, (
            "CircuitOpenError must not cache an empty video list"
        )

        # Step 3: Next call — TMDB is back up and returns a real trailer.
        client._fetch_videos_strict.side_effect = None
        client._fetch_videos_strict.return_value = [_TRAILER_VIDEO]

        result2 = finder.find(550, "movie", title="Fight Club", year=1999)
        assert result2 == _YT_URL, "After TMDB recovery, the trailer should be found (not blocked by cached [])"

    def test_youtube_fallback_transport_error_does_not_cache_no_result(self, tmp_path: Path) -> None:
        """A transport error during YouTube fallback must not write __no_result__ sentinel.

        Scenario:
          1. TMDB returns empty (no videos for this movie).
          2. YouTube breaker is open → _call_youtube_search raises CircuitOpenError.
          3. Assert: no __no_result__ sentinel written to the cache.
          4. Next call — breaker resets and YouTube returns a real URL.
          5. Assert: trailer is found.
        """
        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)

        client = MagicMock()
        searcher = MagicMock()

        # Open breaker: guard() will raise CircuitOpenError.
        yt_breaker = CircuitBreaker(name="youtube-test", failure_threshold=1, cooldown_seconds=9999)
        # Manually trip the breaker open.
        yt_breaker._failure_count = 1
        from personalscraper.scraper.circuit_breaker import CircuitState

        yt_breaker._state = CircuitState.OPEN
        import time

        yt_breaker._opened_at = time.time()
        searcher._breaker = yt_breaker

        finder = TrailerFinder(
            tmdb_client=client,
            youtube_search=searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # TMDB: no videos (genuine empty, but no trailer found).
        client._fetch_videos_strict.return_value = []

        result1 = finder.find(550, "movie", title="Fight Club", year=1999)
        assert result1 is None

        # The __no_result__ sentinel must NOT have been cached.
        assert trailers_cache.contains_search("Fight Club", 1999) is False, (
            "Breaker-open must not cache __no_result__ sentinel"
        )

        # Simulate breaker recovery: reset to CLOSED state.
        yt_breaker._state = CircuitState.CLOSED
        yt_breaker._failure_count = 0
        searcher.search.return_value = _YT_URL

        result2 = finder.find(550, "movie", title="Fight Club", year=1999)
        assert result2 == _YT_URL, "After breaker recovery, YouTube URL should be found"
