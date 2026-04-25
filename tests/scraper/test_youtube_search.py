"""Unit tests for YoutubeSearch — direct YouTube search fallback layer.

HTTP transport is fully mocked via unittest.mock.patch on requests.get.
yt-dlp is also mocked to prevent real network calls from the fallback path.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.scraper.youtube_search import YoutubeSearch

FIXTURES = Path(__file__).parent.parent / "fixtures" / "youtube"


def _fixture_response(name: str) -> MagicMock:
    """Build a mock requests.Response from a fixture file.

    Args:
        name: Filename inside the ``tests/fixtures/youtube/`` directory.

    Returns:
        MagicMock configured to look like a successful requests.Response.
    """
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = data
    return mock_resp


def _no_result_ydl() -> MagicMock:
    """Build a MagicMock yt_dlp module whose YoutubeDL returns no entries.

    Returns:
        MagicMock that mimics ``yt_dlp`` with ``YoutubeDL`` returning
        ``{"entries": []}`` so the fallback path yields ``None``.
    """
    fake_ydl = MagicMock()
    fake_ydl.__enter__ = MagicMock(return_value=fake_ydl)
    fake_ydl.__exit__ = MagicMock(return_value=False)
    fake_ydl.extract_info.return_value = {"entries": []}
    fake_yt_dlp = MagicMock()
    fake_yt_dlp.YoutubeDL.return_value = fake_ydl
    return fake_yt_dlp


def _patch_yt_dlp_no_result():
    """Context manager that patches the yt-dlp import to return no results.

    Returns:
        A context manager returned by ``unittest.mock.patch``.
    """
    import builtins

    real_import = builtins.__import__
    fake_yt_dlp = _no_result_ydl()

    def _mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yt_dlp":
            return fake_yt_dlp
        return real_import(name, *args, **kwargs)

    return patch("builtins.__import__", side_effect=_mock_import)


class TestYoutubeSearch:
    """Tests for YoutubeSearch — primary API path and yt-dlp fallback."""

    @pytest.fixture()
    def searcher(self, tmp_path: Path) -> YoutubeSearch:
        """YoutubeSearch instance backed by a tmp quota cache."""
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        return YoutubeSearch(
            query_format="{title} {year} bande annonce",
            api_key="test-key",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=CircuitBreaker(name="youtube-test", failure_threshold=5, cooldown_seconds=60),
        )

    def test_returns_first_video_url(self, searcher: YoutubeSearch) -> None:
        """search() returns a YouTube URL for the first result."""
        with patch("requests.get", return_value=_fixture_response("search_fight_club.json")):
            url = searcher.search("Fight Club", 1999)
        assert url == "https://www.youtube.com/watch?v=6JnN1DmbqoU"

    def test_returns_none_on_empty_results(self, searcher: YoutubeSearch) -> None:
        """search() returns None when YouTube returns no items and fallback finds nothing."""
        empty = MagicMock()
        empty.ok = True
        empty.status_code = 200
        empty.json.return_value = {"items": []}
        with _patch_yt_dlp_no_result(), patch("requests.get", return_value=empty):
            url = searcher.search("Unknown Movie", 2099)
        assert url is None

    def test_returns_none_on_http_error(self, searcher: YoutubeSearch) -> None:
        """search() returns None on HTTP 5xx and fallback finds nothing."""
        error_resp = MagicMock()
        error_resp.ok = False
        error_resp.status_code = 500
        with _patch_yt_dlp_no_result(), patch("requests.get", return_value=error_resp):
            url = searcher.search("Fight Club", 1999)
        assert url is None

    def test_returns_none_on_403(self, searcher: YoutubeSearch) -> None:
        """search() returns None on HTTP 403 (quota exhausted or bad key)."""
        error_resp = MagicMock()
        error_resp.ok = False
        error_resp.status_code = 403
        with _patch_yt_dlp_no_result(), patch("requests.get", return_value=error_resp):
            url = searcher.search("Fight Club", 1999)
        assert url is None

    def test_query_format_substitution(self, searcher: YoutubeSearch) -> None:
        """search() sends a query with title and year substituted."""
        with patch("requests.get", return_value=_fixture_response("search_fight_club.json")) as mock_get:
            searcher.search("Fight Club", 1999)
        call_url: str = mock_get.call_args[0][0]
        assert "Fight+Club" in call_url or "Fight Club" in call_url
        assert "1999" in call_url

    def test_returns_none_on_connection_error(self, searcher: YoutubeSearch) -> None:
        """search() returns None on connection failure and fallback finds nothing."""
        import requests as _requests

        with (
            _patch_yt_dlp_no_result(),
            patch(
                "requests.get",
                side_effect=_requests.exceptions.ConnectionError("no network"),
            ),
        ):
            url = searcher.search("Fight Club", 1999)
        assert url is None

    def test_custom_query_format(self, tmp_path: Path) -> None:
        """YoutubeSearch respects a custom query format string."""
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        s = YoutubeSearch(
            query_format="{title} {year} trailer",
            api_key="test-key",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=CircuitBreaker(name="youtube-test", failure_threshold=5, cooldown_seconds=60),
        )
        with patch("requests.get", return_value=_fixture_response("search_fight_club.json")) as mock_get:
            s.search("Fight Club", 1999)
        call_url: str = mock_get.call_args[0][0]
        assert "trailer" in call_url

    def test_skips_primary_when_no_api_key(self, tmp_path: Path) -> None:
        """search() skips primary entirely when api_key is empty."""
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        s = YoutubeSearch(
            query_format="{title} {year} trailer",
            api_key="",  # empty → force fallback path
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=CircuitBreaker(name="youtube-test", failure_threshold=5, cooldown_seconds=60),
        )
        with _patch_yt_dlp_no_result(), patch("requests.get") as mock_get:
            s.search("Fight Club", 1999)
        mock_get.assert_not_called()

    def test_skips_primary_when_circuit_open(self, tmp_path: Path) -> None:
        """search() skips primary when the circuit breaker is open."""
        import requests as _requests

        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        breaker = CircuitBreaker(name="youtube-test", failure_threshold=1, cooldown_seconds=9999)
        # Trip the circuit — record_failure only trips on circuit-eligible errors.
        # Use requests.exceptions.ConnectionError to ensure it counts.
        breaker.record_failure(_requests.exceptions.ConnectionError("down"))
        assert not breaker.can_proceed()

        s = YoutubeSearch(
            query_format="{title} {year} trailer",
            api_key="test-key",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=breaker,
        )
        with _patch_yt_dlp_no_result(), patch("requests.get") as mock_get:
            s.search("Fight Club", 1999)
        mock_get.assert_not_called()

    def test_quota_exhaustion_skips_primary(self, tmp_path: Path) -> None:
        """search() skips primary when quota is exhausted for the day."""
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        quota = JsonTTLCache(tmp_path / "quota.json")
        s = YoutubeSearch(
            query_format="{title} {year} trailer",
            api_key="test-key",
            quota_cache=quota,
            breaker=CircuitBreaker(name="youtube-test", failure_threshold=5, cooldown_seconds=60),
            daily_quota_units=100,
            search_list_cost_units=100,
        )
        # Pre-fill quota to the daily limit so _has_quota_left() returns False.
        s._mark_quota_exhausted()
        assert not s._has_quota_left()

        with _patch_yt_dlp_no_result(), patch("requests.get") as mock_get:
            s.search("Fight Club", 1999)
        mock_get.assert_not_called()

    def test_yt_dlp_fallback_returns_url(self, tmp_path: Path) -> None:
        """search() uses yt-dlp fallback when api_key is empty and yt_dlp is available."""
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        s = YoutubeSearch(
            query_format="{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=CircuitBreaker(name="youtube-test", failure_threshold=5, cooldown_seconds=60),
        )

        fake_ydl = MagicMock()
        fake_ydl.__enter__ = MagicMock(return_value=fake_ydl)
        fake_ydl.__exit__ = MagicMock(return_value=False)
        fake_ydl.extract_info.return_value = {"entries": [{"id": "YTDLP_ID"}]}
        fake_yt_dlp = MagicMock()
        fake_yt_dlp.YoutubeDL.return_value = fake_ydl

        import builtins

        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "yt_dlp":
                return fake_yt_dlp
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            url = s.search("Fight Club", 1999)

        assert url == "https://www.youtube.com/watch?v=YTDLP_ID"

    def test_yt_dlp_fallback_returns_none_on_empty_entries(self, tmp_path: Path) -> None:
        """search() returns None when yt-dlp finds no entries."""
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        s = YoutubeSearch(
            query_format="{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=CircuitBreaker(name="youtube-test", failure_threshold=5, cooldown_seconds=60),
        )

        import builtins

        real_import = builtins.__import__
        fake_yt_dlp = _no_result_ydl()

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "yt_dlp":
                return fake_yt_dlp
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            url = s.search("Unknown Title", 2099)

        assert url is None
