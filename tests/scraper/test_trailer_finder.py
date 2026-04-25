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


class TestSeasonFallbackQuotaConfig:
    """Tests for season YouTube fallback quota parameter forwarding (I4)."""

    def test_season_fallback_respects_configured_quota(self, tmp_path: Path) -> None:
        """_youtube_fallback_strict() constructs the passthrough searcher with explicit quota params.

        The one-shot ``YoutubeSearch`` built for the pre-formatted season query
        must receive the same ``daily_quota_units`` and ``search_list_cost_units``
        as the primary searcher — not the module-level defaults.  This test also
        asserts that the attributes are accessed as public attributes, not via
        private ``_daily_quota_units`` / ``_search_list_cost_units`` names.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache
        from personalscraper.scraper.youtube_search import YoutubeSearch

        # Build a YoutubeSearch with non-default quota values.
        custom_daily = 5000
        custom_cost = 200
        yt_breaker = CircuitBreaker(name="yt-test", failure_threshold=5)
        quota_cache = JsonTTLCache(tmp_path / "quota.json")
        searcher = YoutubeSearch(
            "{title} {year} trailer",
            api_key="FAKE_KEY",
            quota_cache=quota_cache,
            breaker=yt_breaker,
            daily_quota_units=custom_daily,
            search_list_cost_units=custom_cost,
        )

        # Verify public attributes are exposed correctly.
        assert searcher.daily_quota_units == custom_daily
        assert searcher.search_list_cost_units == custom_cost

        # Build a finder using this searcher and assert the passthrough searcher
        # for a season query inherits the quota parameters.
        cache = TrailersCache(tmp_path / "tc.json")
        client = MagicMock()
        client._fetch_videos_strict.return_value = []  # Force YouTube fallback

        constructed_searchers: list[YoutubeSearch] = []
        _original_init = YoutubeSearch.__init__

        def capturing_init(self_inner: YoutubeSearch, *args: object, **kwargs: object) -> None:
            _original_init(self_inner, *args, **kwargs)
            constructed_searchers.append(self_inner)

        finder = TrailerFinder(
            tmdb_client=client,
            youtube_search=searcher,
            cache=cache,
            languages=["en-US"],
        )

        # Patch YoutubeSearch.__init__ to capture construction of the passthrough searcher.
        from unittest.mock import patch

        with patch.object(YoutubeSearch, "__init__", capturing_init):
            # season_number != None triggers the passthrough-searcher construction path.
            finder.find(1399, "tv", title="Game of Thrones", year=2011, season_number=2)

        # The passthrough searcher constructed for the season query must carry
        # the same quota parameters as the primary searcher.
        passthrough = next(
            (s for s in constructed_searchers if s._query_format == "{title}"),
            None,
        )
        assert passthrough is not None, "A passthrough YoutubeSearch must have been constructed for the season query"
        assert passthrough.daily_quota_units == custom_daily, (
            "passthrough searcher must inherit daily_quota_units from primary"
        )
        assert passthrough.search_list_cost_units == custom_cost, (
            "passthrough searcher must inherit search_list_cost_units from primary"
        )


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


class TestCachePoisoningClosure:
    """Sub-phase 11.2 — parser-drift and breaker-just-opened must not poison cache."""

    def test_youtube_fallback_typeerror_does_not_cache_no_result(self, tmp_path: Path) -> None:
        """A TypeError from _fallback_search must not write __no_result__ to the cache.

        Scenario:
          1. TMDB returns empty for all languages.
          2. _fallback_search raises TypeError (yt-dlp parser drift).
          3. find() catches it and returns None WITHOUT caching __no_result__.
          4. On the next call (yt-dlp fixed), YouTube returns a real URL.
          5. Assert: trailer is found (not blocked by a poisoned sentinel).

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch

        from personalscraper.scraper.youtube_search import YoutubeSearch

        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)
        client = MagicMock()
        yt_breaker = CircuitBreaker(name="yt-test", failure_threshold=5, cooldown_seconds=60)

        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        real_searcher = YoutubeSearch(
            "{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=yt_breaker,
        )

        finder = TrailerFinder(
            tmdb_client=client,
            youtube_search=real_searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # TMDB: no videos (genuine empty for the language).
        client._fetch_videos_strict.return_value = []

        # Step 1: _fallback_search raises TypeError (yt-dlp parser drift).
        with patch.object(real_searcher, "_fallback_search", side_effect=TypeError("unexpected type")):
            result1 = finder.find(550, "movie", title="Fight Club", year=1999)

        assert result1 is None

        # Step 2: __no_result__ must NOT have been cached.
        assert trailers_cache.contains_search("Fight Club", 1999) is False, (
            "TypeError from _fallback_search must not cache __no_result__ sentinel"
        )

        # Step 3: After the yt-dlp bug is fixed, a real URL is returned.
        with patch.object(real_searcher, "_fallback_search", return_value=_YT_URL):
            result2 = finder.find(550, "movie", title="Fight Club", year=1999)

        assert result2 == _YT_URL, "After parser fix, trailer should be found (not blocked by poisoned cache)"

    def test_breaker_just_opened_during_call_does_not_cache(self, tmp_path: Path) -> None:
        """When the breaker transitions closed→open during a call, __no_result__ is NOT cached.

        Scenario:
          1. TMDB returns empty.
          2. The breaker is CLOSED before the YouTube call, but transitions OPEN
             during it (a fresh transport failure trips the threshold).
          3. _call_youtube_search detects the transition and raises CircuitOpenError.
          4. find() catches it and returns None WITHOUT caching __no_result__.
          5. After breaker recovery, YouTube returns a real URL.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch

        import requests as _requests

        from personalscraper.scraper.circuit_breaker import CircuitState
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache
        from personalscraper.scraper.youtube_search import YoutubeSearch

        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)
        client = MagicMock()

        # Use a low threshold so one failure trips the breaker.
        yt_breaker = CircuitBreaker(name="yt-test", failure_threshold=1, cooldown_seconds=9999)
        real_searcher = YoutubeSearch(
            "{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=yt_breaker,
        )

        finder = TrailerFinder(
            tmdb_client=client,
            youtube_search=real_searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # TMDB: no videos.
        client._fetch_videos_strict.return_value = []

        # _fallback_search trips the breaker via record_failure and returns None.
        # We simulate this by patching search() to record a failure and return None.
        def _search_tripping_breaker(title: str, year: int | None) -> None:
            yt_breaker.record_failure(_requests.exceptions.ConnectionError("transport failure"))
            return None

        with patch.object(real_searcher, "search", side_effect=_search_tripping_breaker):
            result1 = finder.find(550, "movie", title="Fight Club", year=1999)

        assert result1 is None

        # __no_result__ sentinel must NOT have been cached.
        assert trailers_cache.contains_search("Fight Club", 1999) is False, (
            "Breaker opened during call must not cache __no_result__ sentinel"
        )

        # After recovery: reset breaker and return a real URL.
        yt_breaker._state = CircuitState.CLOSED
        yt_breaker._failure_count = 0

        with patch.object(real_searcher, "_fallback_search", return_value=_YT_URL):
            result2 = finder.find(550, "movie", title="Fight Club", year=1999)

        assert result2 == _YT_URL, "After breaker recovery, trailer should be found"
