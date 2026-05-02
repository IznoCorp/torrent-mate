"""Unit tests for YoutubeSearch — direct YouTube search fallback layer.

HTTP transport is fully mocked via unittest.mock.patch on requests.get.
yt-dlp is also mocked to prevent real network calls from the fallback path.
"""

import json
from pathlib import Path
from typing import Any
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

    def _mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
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
        with patch("requests.Session.get", return_value=_fixture_response("search_fight_club.json")):
            url = searcher.search("Fight Club", 1999)
        assert url == "https://www.youtube.com/watch?v=6JnN1DmbqoU"

    def test_returns_none_on_empty_results(self, searcher: YoutubeSearch) -> None:
        """search() returns None when YouTube returns no items and fallback finds nothing."""
        empty = MagicMock()
        empty.ok = True
        empty.status_code = 200
        empty.json.return_value = {"items": []}
        with _patch_yt_dlp_no_result(), patch("requests.Session.get", return_value=empty):
            url = searcher.search("Unknown Movie", 2099)
        assert url is None

    def test_returns_none_on_http_error(self, searcher: YoutubeSearch) -> None:
        """search() returns None on HTTP 5xx and fallback finds nothing."""
        error_resp = MagicMock()
        error_resp.ok = False
        error_resp.status_code = 500
        with _patch_yt_dlp_no_result(), patch("requests.Session.get", return_value=error_resp):
            url = searcher.search("Fight Club", 1999)
        assert url is None

    def test_returns_none_on_403(self, searcher: YoutubeSearch) -> None:
        """search() returns None on HTTP 403 (quota exhausted or bad key) AND marks the quota."""
        error_resp = MagicMock()
        error_resp.ok = False
        error_resp.status_code = 403
        with _patch_yt_dlp_no_result(), patch("requests.Session.get", return_value=error_resp):
            url = searcher.search("Fight Club", 1999)
        assert url is None
        # The 403 path must mark the quota exhausted so subsequent calls bypass HTTP entirely.
        # Without this, a quota-exceeded YouTube account keeps wasting HTTP calls all day.
        assert not searcher._has_quota_left()

    def test_non_json_response_records_breaker_failure(self, searcher: YoutubeSearch) -> None:
        """A 200 OK with HTML body (proxy error page) must hit the breaker."""
        bad = MagicMock()
        bad.ok = True
        bad.status_code = 200
        bad.json.side_effect = ValueError("not json")
        with _patch_yt_dlp_no_result(), patch("requests.Session.get", return_value=bad):
            url = searcher.search("Fight Club", 1999)
        assert url is None
        # Schema drift / HTML-from-proxy must register against the breaker so a
        # sustained outage opens the circuit instead of retrying forever.
        assert searcher._breaker._failure_count >= 1

    def test_missing_video_id_records_breaker_failure(self, searcher: YoutubeSearch) -> None:
        """A response missing items[0]['id']['videoId'] is treated as schema drift."""
        weird = MagicMock()
        weird.ok = True
        weird.status_code = 200
        weird.json.return_value = {"items": [{"id": "scalar_not_dict"}]}  # malformed
        with _patch_yt_dlp_no_result(), patch("requests.Session.get", return_value=weird):
            url = searcher.search("Fight Club", 1999)
        assert url is None
        assert searcher._breaker._failure_count >= 1

    def test_query_format_substitution(self, searcher: YoutubeSearch) -> None:
        """search() sends a query with title and year substituted."""
        with patch("requests.Session.get", return_value=_fixture_response("search_fight_club.json")) as mock_get:
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
                "requests.Session.get",
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
        with patch("requests.Session.get", return_value=_fixture_response("search_fight_club.json")) as mock_get:
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

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
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

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "yt_dlp":
                return fake_yt_dlp
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            url = s.search("Unknown Title", 2099)

        assert url is None


# ── Sub-phase 10.4 new tests ──────────────────────────────────────────────────


class TestFallbackExceptionSplit:
    """I4 — _fallback_search splits parser-drift from network errors."""

    @pytest.fixture()
    def searcher_no_key(self, tmp_path: Path) -> YoutubeSearch:
        """YoutubeSearch with empty api_key so the fallback path is always taken.

        Args:
            tmp_path: Pytest tmp_path fixture.

        Returns:
            A YoutubeSearch with no API key configured.
        """
        from personalscraper.scraper.circuit_breaker import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache

        return YoutubeSearch(
            query_format="{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota.json"),
            breaker=CircuitBreaker(name="youtube-test", failure_threshold=5, cooldown_seconds=60),
        )

    def test_fallback_keyerror_does_not_push_breaker(
        self, searcher_no_key: YoutubeSearch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """KeyError in _fallback_search is logged at ERROR, does NOT push the breaker, and re-raises.

        Parser drift (yt-dlp returns an unexpected dict shape) must not open the
        circuit — that would block all subsequent fallback attempts for the entire
        cooldown period, which is far too disruptive for a parser bug.

        Post sub-phase 11.2: _fallback_search re-raises so the strict layer can
        decide caching policy.  ``search()`` still returns ``None`` (it is the
        fail-soft public entry point) because the re-raised exception propagates
        up through ``search()`` which does not catch it, but this unit test calls
        ``_fallback_search`` directly so we assert the raise contract.

        Args:
            searcher_no_key: YoutubeSearch with empty api_key.
            caplog: Pytest log-capture fixture.
        """
        import builtins
        import logging

        real_import = builtins.__import__

        # DownloadError must be a distinct class that KeyError does NOT inherit
        # from — otherwise the ``except yt_dlp.utils.DownloadError`` clause
        # catches the KeyError before our new ``except (KeyError, ...)`` branch.
        class _FakeDownloadError(Exception):
            pass

        def _make_ydl_raising_keyerror() -> object:
            ydl = MagicMock()
            ydl.__enter__ = MagicMock(return_value=ydl)
            ydl.__exit__ = MagicMock(return_value=False)
            ydl.extract_info.side_effect = KeyError("missing_field")

            fake = MagicMock()
            fake.YoutubeDL.return_value = ydl
            # Provide a distinct exception type so ``except DownloadError`` is NOT
            # triggered by a KeyError — the two must be unrelated in the MRO.
            fake.utils.DownloadError = _FakeDownloadError
            return fake

        fake_yt_dlp = _make_ydl_raising_keyerror()

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "yt_dlp":
                return fake_yt_dlp
            return real_import(name, *args, **kwargs)

        initial_failure_count = searcher_no_key._breaker._failure_count

        # _fallback_search now re-raises KeyError — verify the raise contract.
        with caplog.at_level(logging.DEBUG), patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(KeyError, match="missing_field"):
                searcher_no_key._fallback_search("Fight Club 1999 trailer")

        # Breaker counter must be unchanged — a KeyError is not a network error.
        assert searcher_no_key._breaker._failure_count == initial_failure_count

        # The log must be at ERROR level (parser drift, not WARNING).
        # structlog records arrive with event name in rec.message or rec.msg dict.
        def _has_event(rec: object) -> bool:
            msg = getattr(rec, "msg", None)
            message = getattr(rec, "message", "")
            return (isinstance(msg, dict) and msg.get("event") == "youtube_fallback_unexpected_error") or (
                "youtube_fallback_unexpected_error" in str(message)
            )

        error_records = [r for r in caplog.records if _has_event(r)]
        assert error_records, "expected youtube_fallback_unexpected_error log"
        assert error_records[0].levelno == logging.ERROR


class TestPrimarySearchRetry:
    """I6 — _primary_search retries transient transport errors."""

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

    def test_session_is_configured_with_retry_adapter(self, searcher: YoutubeSearch) -> None:
        """YoutubeSearch builds its session with an HTTPAdapter carrying a Retry policy.

        This verifies I6: the session's https adapter must be an HTTPAdapter
        whose ``max_retries`` is a ``Retry`` instance (not the default ``False``).

        Args:
            searcher: YoutubeSearch fixture.
        """
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry as Urllib3Retry

        adapter = searcher._session.get_adapter("https://www.googleapis.com/")
        assert isinstance(adapter, HTTPAdapter), "expected HTTPAdapter on https://"
        assert isinstance(adapter.max_retries, Urllib3Retry), (
            "expected Retry instance as max_retries, got: %r" % adapter.max_retries
        )
        # total must equal _PRIMARY_MAX_ATTEMPTS - 1 (= 2 retries).
        assert adapter.max_retries.total == 2, (  # type: ignore[union-attr]
            f"expected 2 retries, got {adapter.max_retries.total}"
        )

    def test_session_includes_429_in_status_forcelist(self, searcher: YoutubeSearch) -> None:
        """The session adapter's status_forcelist includes 429 (YouTube rate-limit).

        YouTube returns 429 when quota is temporarily exhausted; the retry layer
        must back off and retry rather than propagating the error to application
        code.

        Args:
            searcher: YoutubeSearch fixture.
        """
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry as Urllib3Retry

        adapter = searcher._session.get_adapter("https://www.googleapis.com/")
        assert isinstance(adapter, HTTPAdapter)
        retry: Urllib3Retry = adapter.max_retries  # type: ignore[assignment]
        assert isinstance(retry, Urllib3Retry)
        assert 429 in retry.status_forcelist, (
            f"429 must be in status_forcelist to retry on YouTube rate-limit; got {retry.status_forcelist}"
        )

    def test_primary_search_retries_on_429(self, searcher: YoutubeSearch) -> None:
        """A 429 response is absorbed by the retry layer; application sees one success.

        The test is split into two complementary assertions:

        1. **Configuration** — 429 is in ``status_forcelist``, so urllib3 will
           schedule a retry instead of surfacing the status to application code.
        2. **Application outcome** — given that urllib3 retries and eventually
           returns a 200, ``search()`` returns the expected YouTube URL (i.e. the
           application layer only processes one successful response, never the
           429 itself).

        We simulate the application-layer outcome by patching ``Session.get`` to
        return the 200 response directly.  The urllib3-level retry mechanics are
        covered by the ``status_forcelist`` configuration test above.

        Args:
            searcher: YoutubeSearch fixture.
        """
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry as Urllib3Retry

        # Part 1 — configuration: 429 must be in the retry forcelist.
        adapter = searcher._session.get_adapter("https://www.googleapis.com/")
        assert isinstance(adapter, HTTPAdapter)
        retry: Urllib3Retry = adapter.max_retries  # type: ignore[assignment]
        assert 429 in retry.status_forcelist

        # Part 2 — application outcome: after the retry delivers a 200, search()
        # returns the URL.  We patch Session.get directly to simulate the post-retry
        # response the application would receive.
        with patch("requests.Session.get", return_value=_fixture_response("search_fight_club.json")):
            url = searcher.search("Fight Club", 1999)

        assert url == "https://www.youtube.com/watch?v=6JnN1DmbqoU"

    def test_primary_search_pushes_breaker_after_terminal_transport_failure(self, searcher: YoutubeSearch) -> None:
        """After a fatal ConnectionError _primary_search pushes the circuit breaker.

        The retry adapter exhausts its attempts and raises ``ConnectionError``
        to ``_primary_search``, which must record the failure on the breaker.
        We mock ``Session.send`` (the transport layer) so the retry adapter's
        retry logic runs first; by returning ``ConnectionError`` every time the
        adapter eventually gives up and bubbles the exception.

        Args:
            searcher: YoutubeSearch fixture.
        """
        import requests as _requests

        # Disable the yt-dlp fallback so a primary failure surfaces as None.
        with (
            patch.object(searcher._session, "send", side_effect=_requests.exceptions.ConnectionError("DNS hiccup")),
            _patch_yt_dlp_no_result(),
        ):
            url = searcher.search("Fight Club", 1999)

        assert url is None
        # Circuit breaker must have recorded the failure.
        assert searcher._breaker._failure_count >= 1
