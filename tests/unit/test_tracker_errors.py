"""Tests for api/tracker/_errors.py.

Design: §5.3 (D4) — TrackerAuthError and TorrentFetchError are field-free
ApiError subclasses; they inherit __init__, __eq__, and str() from ApiError.
Contract: construction, isinstance hierarchy, and message propagation.
"""

from __future__ import annotations

from personalscraper.api._contracts import ApiError
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError


class TestTrackerAuthError:
    """TrackerAuthError is an ApiError subclass for 401/403 download failures."""

    def test_is_api_error(self) -> None:
        """TrackerAuthError must be catchable as ApiError."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="Unauthorized")
        assert isinstance(err, ApiError)

    def test_is_tracker_auth_error(self) -> None:
        """Isinstance check works for the concrete type."""
        err = TrackerAuthError(provider="lacale", http_status=403, provider_code=0, message="Forbidden")
        assert isinstance(err, TrackerAuthError)

    def test_http_status_preserved(self) -> None:
        """http_status is stored and accessible."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="Unauthorized")
        assert err.http_status == 401

    def test_message_preserved(self) -> None:
        """The message string is propagated through ApiError.__init__."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="token expired")
        assert "token expired" in str(err)

    def test_403_also_valid(self) -> None:
        """403 Forbidden is a valid auth failure status."""
        err = TrackerAuthError(provider="lacale", http_status=403, provider_code=0, message="Forbidden")
        assert err.http_status == 403


class TestTorrentFetchError:
    """TorrentFetchError is an ApiError subclass for bad/empty/oversize content."""

    def test_is_api_error(self) -> None:
        """TorrentFetchError must be catchable as ApiError."""
        err = TorrentFetchError(provider="c411", http_status=200, provider_code=0, message="empty body")
        assert isinstance(err, ApiError)

    def test_is_torrent_fetch_error(self) -> None:
        """Isinstance check works for the concrete type."""
        err = TorrentFetchError(provider="lacale", http_status=200, provider_code=0, message="not a torrent")
        assert isinstance(err, TorrentFetchError)

    def test_message_preserved(self) -> None:
        """Error message describes the failure context."""
        err = TorrentFetchError(
            provider="c411", http_status=200, provider_code=0, message="body is not a bencoded dict: b'<html>'"
        )
        assert "bencoded" in str(err)

    def test_not_auth_error(self) -> None:
        """TorrentFetchError must NOT be a TrackerAuthError."""
        err = TorrentFetchError(provider="c411", http_status=200, provider_code=0, message="bad")
        assert not isinstance(err, TrackerAuthError)

    def test_auth_error_not_fetch_error(self) -> None:
        """TrackerAuthError must NOT be a TorrentFetchError."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="auth")
        assert not isinstance(err, TorrentFetchError)
