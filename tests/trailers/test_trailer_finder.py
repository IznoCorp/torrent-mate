"""Unit tests for TrailerFinder — provider-agnostic / YouTube-fallback discovery.

All external dependencies (ProviderRegistry, YoutubeSearch, TrailersCache) are mocked.
"""

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import Video
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.circuit import CircuitBreaker, CircuitOpenError
from personalscraper.core.event_bus import EventBus
from personalscraper.trailers.discovery.trailer_finder import TrailerFinder
from personalscraper.trailers.discovery.trailers_cache import TrailersCache


def _mock_registry(finder: TrailerFinder) -> MagicMock:
    """Type-narrow ``finder._registry`` to its real MagicMock at runtime.

    The fixture installs a MagicMock under the typed ``ProviderRegistry`` slot so
    individual tests can reach into ``return_value`` / ``side_effect`` /
    ``call_count`` without Pyright complaining about attributes that don't
    exist on the real class.
    """
    return cast(MagicMock, finder._registry)


def _mock_provider(finder: TrailerFinder) -> MagicMock:
    """Type-narrow the mock provider inside ``finder._registry.locked().provider``."""
    reg = _mock_registry(finder)
    return cast(MagicMock, reg.locked.return_value.provider)


def _mock_yt(finder: TrailerFinder) -> MagicMock:
    """Type-narrow ``finder._youtube_search`` to its real MagicMock at runtime."""
    return cast(MagicMock, finder._youtube_search)


_TRAILER_VIDEO = Video(
    id="abc",
    site="youtube",
    key="TRAILER_KEY",
    type="trailer",
    official=True,
    size=1080,
    iso_639_1="en",
)
_TEASER_VIDEO = Video(
    id="def",
    site="youtube",
    key="TEASER_KEY",
    type="teaser",
    official=True,
    size=720,
    iso_639_1="en",
)
_YT_URL = "https://www.youtube.com/watch?v=TRAILER_KEY"


@pytest.fixture()
def finder(tmp_path: Path) -> TrailerFinder:
    """Build a TrailerFinder with mocked ProviderRegistry and YoutubeSearch."""
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_locked = MagicMock()
    mock_locked.provider = MagicMock()
    mock_locked.bound_id = "12345"
    mock_registry.locked.return_value = mock_locked

    searcher = MagicMock()
    cache = TrailersCache(tmp_path / "tc.json")
    return TrailerFinder(
        registry=mock_registry,
        youtube_search=searcher,
        cache=cache,
        languages=["fr-FR", "en-US"],
    )


class TestTrailerFinder:
    """Tests for TrailerFinder two-tier discovery strategy."""

    def test_returns_tmdb_trailer_url(self, finder: TrailerFinder) -> None:
        """find() returns YouTube URL for first Trailer type from provider."""
        _mock_provider(finder).get_videos.return_value = [_TRAILER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_tmdb_teaser_used_when_no_trailer(self, finder: TrailerFinder) -> None:
        """find() falls back to Teaser if no Trailer type exists in provider results."""
        _mock_provider(finder).get_videos.return_value = [_TEASER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == "https://www.youtube.com/watch?v=TEASER_KEY"

    def test_youtube_fallback_on_empty_provider(self, finder: TrailerFinder) -> None:
        """find() falls back to YouTube search when provider returns no videos."""
        _mock_provider(finder).get_videos.return_value = []
        _mock_yt(finder).search.return_value = _YT_URL
        _mock_yt(finder)._breaker = CircuitBreaker(name="yt-test", failure_threshold=5, event_bus=EventBus())
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_returns_none_when_both_fail(self, finder: TrailerFinder) -> None:
        """find() returns None when provider and YouTube both return nothing."""
        _mock_provider(finder).get_videos.return_value = []
        _mock_yt(finder).search.return_value = None
        _mock_yt(finder)._breaker = CircuitBreaker(name="yt-test", failure_threshold=5, event_bus=EventBus())
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url is None

    def test_language_priority_fr_before_en(self, finder: TrailerFinder) -> None:
        """find() queries fr-FR before en-US and returns on first hit."""

        def fetch_side_effect(media_id: str, media_type: MediaType, language: str) -> list[Video]:
            if language == "fr-FR":
                return [_TRAILER_VIDEO]
            return []

        _mock_provider(finder).get_videos.side_effect = fetch_side_effect
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        # Only one call (fr-FR) because it already found a result
        assert _mock_provider(finder).get_videos.call_count == 1

    def test_tv_show_uses_get_videos(self, finder: TrailerFinder) -> None:
        """find() calls get_videos() with MediaType.TV for media_type='tv'."""
        _mock_provider(finder).get_videos.return_value = [_TRAILER_VIDEO]
        url = finder.find(1399, "tv", title="Game of Thrones", year=2011)
        assert url == _YT_URL
        call_args = _mock_provider(finder).get_videos.call_args
        assert call_args[0][1] == MediaType.TV

    def test_cache_hit_skips_network(self, finder: TrailerFinder) -> None:
        """find() returns cached URL without calling provider or YoutubeSearch."""
        # Prime the cache directly
        finder._cache.set_tmdb_videos(550, "movie", "fr-FR", [_TRAILER_VIDEO])
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        _mock_provider(finder).get_videos.assert_not_called()

    def test_non_youtube_videos_filtered_out(self, finder: TrailerFinder) -> None:
        """find() ignores non-YouTube videos even when they are Trailers."""
        vimeo_video = Video(
            id="xyz",
            site="vimeo",
            key="vimeo-id",
            type="trailer",
            official=True,
            size=1080,
            iso_639_1="en",
        )
        _mock_provider(finder).get_videos.return_value = [vimeo_video]
        _mock_yt(finder).search.return_value = _YT_URL
        _mock_yt(finder)._breaker = CircuitBreaker(name="yt-test", failure_threshold=5, event_bus=EventBus())
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        # Vimeo entry must be ignored; YouTube search fallback should be used.
        assert url == _YT_URL
        _mock_yt(finder).search.assert_called_once()

    def test_season_uses_fetch_videos_strict(self, finder: TrailerFinder) -> None:
        """find() calls _fetch_videos_strict with the season endpoint."""
        _mock_provider(finder)._fetch_videos_strict.return_value = [_TRAILER_VIDEO]
        url = finder.find(1399, "tv", title="Game of Thrones", year=2011, season_number=1)
        assert url == _YT_URL
        call_args = _mock_provider(finder)._fetch_videos_strict.call_args
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
        from personalscraper.core.circuit import CircuitBreaker
        from personalscraper.core.json_ttl_cache import JsonTTLCache
        from personalscraper.trailers.discovery.youtube_search import YoutubeSearch

        # Build a YoutubeSearch with non-default quota values.
        custom_daily = 5000
        custom_cost = 200
        yt_breaker = CircuitBreaker(name="yt-test", failure_threshold=5, event_bus=EventBus())
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

        # Mock registry with a provider that returns empty videos (forces YouTube fallback).
        mock_registry = MagicMock(spec=ProviderRegistry)
        mock_locked = MagicMock()
        mock_provider = MagicMock()
        mock_provider._fetch_videos_strict.return_value = []  # force YouTube fallback
        mock_locked.provider = mock_provider
        mock_registry.locked.return_value = mock_locked

        constructed_searchers: list[YoutubeSearch] = []
        _original_init = YoutubeSearch.__init__

        def capturing_init(self_inner: YoutubeSearch, *args: Any, **kwargs: Any) -> None:
            _original_init(self_inner, *args, **kwargs)
            constructed_searchers.append(self_inner)

        finder = TrailerFinder(
            registry=mock_registry,
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

    def test_provider_outage_does_not_cache_empty_for_a_week(self, tmp_path: Path) -> None:
        """A provider CircuitOpenError must not write an empty entry to TrailersCache.

        Scenario:
          1. Provider raises CircuitOpenError via get_videos() side_effect.
          2. find() re-raises CircuitOpenError (propagates to orchestrator counter).
          3. Assert: no entry written to the cache (the key is absent).
          4. Next call with provider returning a real movie → trailer is found
             (not blocked by a cached empty list from step 1).
        """
        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)

        mock_registry = MagicMock(spec=ProviderRegistry)
        mock_locked = MagicMock()
        mock_provider = MagicMock()
        mock_locked.provider = mock_provider
        mock_registry.locked.return_value = mock_locked

        searcher = MagicMock()
        searcher._breaker = CircuitBreaker(name="yt-test", failure_threshold=5, event_bus=EventBus())

        finder = TrailerFinder(
            registry=mock_registry,
            youtube_search=searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # Step 1: Provider raises CircuitOpenError on every call.
        mock_provider.get_videos.side_effect = CircuitOpenError("TMDB", 9999.0)

        # After the fix find() re-raises CircuitOpenError so the orchestrator can
        # tally counts["circuit_open"]; it must NOT return None and swallow it.
        with pytest.raises(CircuitOpenError):
            finder.find(550, "movie", title="Fight Club", year=1999)

        # Step 2: The cache must NOT have stored an empty entry for the provider key.
        # (The exception unwinds the stack before the cache write site.)
        assert trailers_cache.get_tmdb_videos(550, "movie", "en-US") is None, (
            "CircuitOpenError must not cache an empty video list"
        )

        # Step 3: Next call — provider is back up and returns a real trailer.
        mock_provider.get_videos.side_effect = None
        mock_provider.get_videos.return_value = [_TRAILER_VIDEO]

        result2 = finder.find(550, "movie", title="Fight Club", year=1999)
        assert result2 == _YT_URL, "After provider recovery, the trailer should be found (not blocked by cached [])"

    def test_youtube_fallback_transport_error_does_not_cache_no_result(self, tmp_path: Path) -> None:
        """A YouTube CircuitOpenError must not write __no_result__ sentinel.

        Scenario:
          1. Provider returns empty (no videos for this movie).
          2. YouTube breaker is open → _call_youtube_search raises CircuitOpenError.
          3. find() re-raises CircuitOpenError (propagates to orchestrator counter).
          4. Assert: no __no_result__ sentinel written to the cache.
          5. Next call — breaker resets and YouTube returns a real URL.
          6. Assert: trailer is found.
        """
        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)

        mock_registry = MagicMock(spec=ProviderRegistry)
        mock_locked = MagicMock()
        mock_provider = MagicMock()
        mock_locked.provider = mock_provider
        mock_registry.locked.return_value = mock_locked

        searcher = MagicMock()

        # Open breaker: guard() will raise CircuitOpenError. Single-line to
        # satisfy the Phase 5.1 audit grep (every breaker construction must
        # carry ``event_bus=`` on the same opening-paren line).
        yt_breaker = CircuitBreaker(name="youtube-test", failure_threshold=1, cooldown_seconds=9999, event_bus=EventBus())  # noqa: E501  # fmt: skip
        # Manually trip the breaker open.
        yt_breaker._failure_count = 1
        from personalscraper.core.circuit import CircuitState

        yt_breaker._state = CircuitState.OPEN
        import time

        yt_breaker._opened_at = time.time()
        searcher._breaker = yt_breaker

        finder = TrailerFinder(
            registry=mock_registry,
            youtube_search=searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # Provider: no videos (genuine empty, but no trailer found).
        mock_provider.get_videos.return_value = []

        # After the fix find() re-raises CircuitOpenError so the orchestrator can
        # tally counts["circuit_open"]; it must NOT return None and swallow it.
        with pytest.raises(CircuitOpenError):
            finder.find(550, "movie", title="Fight Club", year=1999)

        # The __no_result__ sentinel must NOT have been cached.
        # (The exception unwinds the stack before the cache write site.)
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
          1. Provider returns empty for all languages.
          2. _fallback_search raises TypeError (yt-dlp parser drift).
          3. find() catches it and returns None WITHOUT caching __no_result__.
          4. On the next call (yt-dlp fixed), YouTube returns a real URL.
          5. Assert: trailer is found (not blocked by a poisoned sentinel).

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch

        from personalscraper.trailers.discovery.youtube_search import YoutubeSearch

        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)

        mock_registry = MagicMock(spec=ProviderRegistry)
        mock_locked = MagicMock()
        mock_provider = MagicMock()
        mock_locked.provider = mock_provider
        mock_registry.locked.return_value = mock_locked

        yt_breaker = CircuitBreaker(name="yt-test", failure_threshold=5, cooldown_seconds=60, event_bus=EventBus())

        from personalscraper.core.json_ttl_cache import JsonTTLCache

        real_searcher = YoutubeSearch(
            "{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=yt_breaker,
        )

        finder = TrailerFinder(
            registry=mock_registry,
            youtube_search=real_searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # Provider: no videos (genuine empty for the language).
        mock_provider.get_videos.return_value = []

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
          1. Provider returns empty.
          2. The breaker is CLOSED before the YouTube call, but transitions OPEN
             during it (a fresh transport failure trips the threshold).
          3. _call_youtube_search detects the transition and raises CircuitOpenError.
          4. find() re-raises CircuitOpenError (propagates to orchestrator counter).
          5. Cache write is skipped inherently because the exception unwinds first.
          6. After breaker recovery, YouTube returns a real URL.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch

        import requests as _requests

        from personalscraper.core.circuit import CircuitState
        from personalscraper.core.json_ttl_cache import JsonTTLCache
        from personalscraper.trailers.discovery.youtube_search import YoutubeSearch

        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)

        mock_registry = MagicMock(spec=ProviderRegistry)
        mock_locked = MagicMock()
        mock_provider = MagicMock()
        mock_locked.provider = mock_provider
        mock_registry.locked.return_value = mock_locked

        # Use a low threshold so one failure trips the breaker.
        yt_breaker = CircuitBreaker(name="yt-test", failure_threshold=1, cooldown_seconds=9999, event_bus=EventBus())
        real_searcher = YoutubeSearch(
            "{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=yt_breaker,
        )

        finder = TrailerFinder(
            registry=mock_registry,
            youtube_search=real_searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # Provider: no videos.
        mock_provider.get_videos.return_value = []

        # _fallback_search trips the breaker via record_failure and returns None.
        # We simulate this by patching search() to record a failure and return None.
        def _search_tripping_breaker(title: str, year: int | None) -> None:
            yt_breaker.record_failure(_requests.exceptions.ConnectionError("transport failure"))
            return None

        # After the fix find() re-raises CircuitOpenError so the orchestrator can
        # tally counts["circuit_open"]; it must NOT return None and swallow it.
        with patch.object(real_searcher, "search", side_effect=_search_tripping_breaker):
            with pytest.raises(CircuitOpenError):
                finder.find(550, "movie", title="Fight Club", year=1999)

        # __no_result__ sentinel must NOT have been cached.
        # (The exception unwinds the stack before the cache write site.)
        assert trailers_cache.contains_search("Fight Club", 1999) is False, (
            "Breaker opened during call must not cache __no_result__ sentinel"
        )

        # After recovery: reset breaker and return a real URL.
        yt_breaker._state = CircuitState.CLOSED
        yt_breaker._failure_count = 0

        with patch.object(real_searcher, "_fallback_search", return_value=_YT_URL):
            result2 = finder.find(550, "movie", title="Fight Club", year=1999)

        assert result2 == _YT_URL, "After breaker recovery, trailer should be found"


class TestDownloadErrorRegression:
    """Regression tests for sub-phase 11.2 — yt_dlp.utils.DownloadError must not escape find()."""

    def test_find_handles_yt_dlp_download_error_from_fallback(self, tmp_path: Path) -> None:
        """find() returns None and skips __no_result__ cache when _fallback_search raises DownloadError.

        Scenario:
          1. Provider returns empty for all languages (forces YouTube fallback).
          2. _fallback_search raises yt_dlp.utils.DownloadError (re-raised by
             _youtube_fallback_strict, regression from sub-phase 11.2).
          3. find() must catch it, return None, and NOT write __no_result__ to
             the cache so the item is retried on the next run.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch

        from yt_dlp.utils import DownloadError as _YtDlpDownloadError

        from personalscraper.core.json_ttl_cache import JsonTTLCache
        from personalscraper.trailers.discovery.youtube_search import YoutubeSearch

        cache_path = tmp_path / "tc.json"
        trailers_cache = TrailersCache(cache_path)

        mock_registry = MagicMock(spec=ProviderRegistry)
        mock_locked = MagicMock()
        mock_provider = MagicMock()
        mock_locked.provider = mock_provider
        mock_registry.locked.return_value = mock_locked

        yt_breaker = CircuitBreaker(name="yt-test", failure_threshold=5, cooldown_seconds=60, event_bus=EventBus())

        real_searcher = YoutubeSearch(
            "{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=yt_breaker,
        )

        finder = TrailerFinder(
            registry=mock_registry,
            youtube_search=real_searcher,
            cache=trailers_cache,
            languages=["en-US"],
        )

        # Provider returns empty — forces YouTube fallback path.
        mock_provider.get_videos.return_value = []

        # _fallback_search raises DownloadError (the regression scenario).
        with patch.object(
            real_searcher,
            "_fallback_search",
            side_effect=_YtDlpDownloadError("simulated yt-dlp download error"),
        ):
            result = finder.find(550, "movie", title="Fight Club", year=1999)

        # find() must return None — not propagate the exception to the caller.
        assert result is None, "DownloadError must be caught; find() must return None"

        # The __no_result__ sentinel must NOT have been written — the error is
        # transient, so the next run should retry rather than read a stale sentinel.
        assert trailers_cache.contains_search("Fight Club", 1999) is False, (
            "DownloadError must not poison the cache with a __no_result__ sentinel"
        )
