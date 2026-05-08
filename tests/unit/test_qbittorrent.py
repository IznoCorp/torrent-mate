"""Tests for api/torrent/qbittorrent.py."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import qbittorrentapi

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.api.torrent.qbittorrent import (
    QBitAuthLockoutError,
    QBitClient,
    _torrent_item,
    build_client,
)
from personalscraper.conf.models.api_config import TorrentClientEntry


class TestTorrentItemMapping:
    """qBit TorrentDictionary → TorrentItem conversion."""

    def test_basic_mapping(self) -> None:
        """All fields are mapped correctly."""
        mock = MagicMock()
        mock.hash = "abc123"
        mock.name = "Test Movie"
        mock.total_size = 5000000000
        mock.progress = 1
        mock.state = "uploading"
        mock.ratio = 1.5
        mock.content_path = "/data/movie"
        mock.category = "movies"
        mock.added_on = 1712345678

        item = _torrent_item(mock)
        assert item.hash == "abc123"
        assert item.name == "Test Movie"
        assert item.size_bytes == 5000000000
        assert item.progress == 1.0
        assert item.state == "uploading"
        assert item.ratio == 1.5
        assert item.content_path == Path("/data/movie")
        assert item.category == "movies"
        assert item.added_on == datetime.fromtimestamp(1712345678)

    def test_ratio_field_present_on_item(self) -> None:
        """Regression for BUG #8: every TorrentItem must carry a `ratio` attribute.

        Pre-fix, TorrentItem did not declare a `ratio` field and `_torrent_item()`
        did not populate one, so `getattr(item, 'ratio', None)` returned None for
        every qBit torrent in production. The min_ratio gate in ingest.py treated
        None as 0.0, silently bypassing the seeding-ratio check (fail-open).

        The integration test fixture `FakeTorrent` had its own `ratio` field with
        a default of 0.0, masking the missing mapping in real `TorrentItem`.
        This test exercises the real mapping with a non-default ratio value.
        """
        mock = MagicMock()
        mock.ratio = 2.5
        mock.content_path = "/x"
        mock.category = ""
        mock.added_on = 0
        item = _torrent_item(mock)
        assert hasattr(item, "ratio")
        assert isinstance(item.ratio, float)
        assert item.ratio == 2.5

    def test_ratio_falls_back_to_zero_when_missing(self) -> None:
        """When qBit returns ratio=None (rare), TorrentItem.ratio is 0.0 (not None)."""
        mock = MagicMock()
        mock.ratio = None
        mock.content_path = "/x"
        mock.category = ""
        mock.added_on = 0
        item = _torrent_item(mock)
        assert item.ratio == 0.0
        assert isinstance(item.ratio, float)

    def test_progress_casts_int_to_float(self) -> None:
        """Progress int (qBit 5.x) is cast to float."""
        mock = MagicMock()
        mock.progress = 1
        mock.content_path = "/x"
        mock.category = ""
        mock.added_on = 0
        item = _torrent_item(mock)
        assert isinstance(item.progress, float)
        assert item.progress == 1.0

    def test_empty_category_maps_to_none(self) -> None:
        """Empty string category becomes None."""
        mock = MagicMock()
        mock.category = ""
        mock.content_path = "/x"
        mock.added_on = 0
        item = _torrent_item(mock)
        assert item.category is None

    def test_empty_content_path_maps_to_none(self) -> None:
        """Empty string content_path becomes None."""
        mock = MagicMock()
        mock.content_path = ""
        mock.category = ""
        mock.added_on = 0
        item = _torrent_item(mock)
        assert item.content_path is None


class TestBuildClient:
    """build_client() factory function."""

    def _entry(self) -> TorrentClientEntry:
        """Build a default TorrentClientEntry matching the production template defaults."""
        return TorrentClientEntry()

    def _env(self) -> dict[str, str]:
        """Build an env dict with valid credentials."""
        return {"QBIT_USERNAME": "admin", "QBIT_PASSWORD": "pass"}

    @patch("personalscraper.api.torrent.qbittorrent.requests.get")
    @patch("personalscraper.api.torrent.qbittorrent.qbittorrentapi.Client")
    def test_returns_authenticated_client(self, mock_client_cls: MagicMock, mock_get: MagicMock) -> None:
        """Pre-check passes, valid creds → authenticated QBitClient."""
        mock_get.return_value.status_code = 200
        mock_client = mock_client_cls.return_value

        result = build_client("qbittorrent", self._entry(), self._env())

        assert isinstance(result, QBitClient)
        mock_client.auth_log_in.assert_called_once()

    def test_missing_credentials_raises(self) -> None:
        """Empty env → ApiError for missing credentials."""
        with pytest.raises(ApiError, match="Missing QBIT_USERNAME"):
            build_client("qbittorrent", self._entry(), {})

    @patch("personalscraper.api.torrent.qbittorrent.requests.get")
    def test_unreachable_raises(self, mock_get: MagicMock) -> None:
        """Connection error during pre-check → ApiError(http_status=0) per DESIGN §1.1."""
        import requests as req

        mock_get.side_effect = req.ConnectionError("boom")
        with pytest.raises(ApiError, match="unreachable") as exc_info:
            build_client("qbittorrent", self._entry(), self._env())
        assert exc_info.value.http_status == 0
        assert exc_info.value.provider == "qbittorrent"

    @patch("personalscraper.api.torrent.qbittorrent.requests.get")
    @patch("personalscraper.api.torrent.qbittorrent._LOCKOUT_FILE")
    def test_lockout_blocks_login(self, mock_lockout: MagicMock, mock_get: MagicMock) -> None:
        """Active lockout file → QBitAuthLockoutError before login."""
        mock_get.return_value.status_code = 200
        mock_lockout.exists.return_value = True
        mock_lockout.stat.return_value.st_mtime = __import__("time").time()

        with pytest.raises(QBitAuthLockoutError):
            build_client("qbittorrent", self._entry(), self._env())


class TestQBitClient:
    """QBitClient Protocol implementation."""

    def _client(self) -> QBitClient:
        """Build a QBitClient with a mocked underlying client."""
        c = QBitClient("localhost", 8081, "admin", "pass")
        c._client = MagicMock()
        return c

    def test_provider_name(self) -> None:
        """provider_name is qbittorrent."""
        client = self._client()
        assert client.provider_name == "qbittorrent"

    def test_required_creds(self) -> None:
        """REQUIRED_CREDS lists QBIT_USERNAME and QBIT_PASSWORD."""
        assert QBitClient.REQUIRED_CREDS == ["QBIT_USERNAME", "QBIT_PASSWORD"]

    def test_get_completed_returns_torrent_items(self) -> None:
        """get_completed() maps qBit results to TorrentItem list."""
        client = self._client()
        mock_t = MagicMock()
        mock_t.hash = "abc"
        mock_t.name = "Test"
        mock_t.total_size = 1000
        mock_t.progress = 1.0
        mock_t.state = "uploading"
        mock_t.content_path = "/data"
        mock_t.category = "cat"
        mock_t.added_on = 1712345678
        client._client.torrents_info.return_value = [mock_t]  # type: ignore[attr-defined]

        items = client.get_completed()
        assert len(items) == 1
        assert isinstance(items[0], TorrentItem)
        client._client.torrents_info.assert_called_once_with(status_filter="completed")  # type: ignore[attr-defined]

    def test_get_all_hashes(self) -> None:
        """get_all_hashes() returns set of torrent hashes."""
        client = self._client()
        mock_t = MagicMock()
        mock_t.hash = "abc"
        client._client.torrents_info.return_value = [mock_t]  # type: ignore[attr-defined]

        hashes = client.get_all_hashes()
        assert hashes == {"abc"}

    def test_is_seeding_uses_state_enum(self) -> None:
        """is_seeding() delegates to qbittorrentapi state_enum.is_uploading."""
        client = self._client()
        mock_t = MagicMock()
        mock_t.state_enum.is_uploading = True
        client._client.torrents_info.return_value = [mock_t]  # type: ignore[attr-defined]

        torrent = TorrentItem(hash="abc", name="t", size_bytes=1, progress=1.0, state="uploading")
        assert client.is_seeding(torrent) is True

    def test_pause_resume_delete(self) -> None:
        """pause/resume/delete delegate to qbittorrentapi methods."""
        client = self._client()
        client.pause("abc")
        client._client.torrents_pause.assert_called_once_with(torrent_hashes="abc")  # type: ignore[attr-defined]

        client.resume("abc")
        client._client.torrents_resume.assert_called_once_with(torrent_hashes="abc")  # type: ignore[attr-defined]

        client.delete("abc", delete_files=True)
        client._client.torrents_delete.assert_called_once_with(torrent_hashes="abc", delete_files=True)  # type: ignore[attr-defined]

    def test_login_logout(self) -> None:
        """login() and logout() call the underlying auth methods."""
        client = self._client()
        client._client.auth_log_in.return_value = None  # type: ignore[attr-defined]
        client._client.auth_log_out.return_value = None  # type: ignore[attr-defined]

        client.login()
        client._client.auth_log_in.assert_called_once()  # type: ignore[attr-defined]

        client.logout()
        client._client.auth_log_out.assert_called_once()  # type: ignore[attr-defined]

    def test_login_failed_raises_apierror_401(self) -> None:
        """qbittorrentapi.LoginFailed → ApiError(http_status=401) per DESIGN §1.1."""
        from personalscraper.api.torrent.qbittorrent import _LOCKOUT_FILE  # noqa: PLC0415

        client = self._client()
        client._client.auth_log_in.side_effect = qbittorrentapi.LoginFailed("bad creds")  # type: ignore[attr-defined]

        # Ensure no stale lockout file from a prior test
        if _LOCKOUT_FILE.exists():
            _LOCKOUT_FILE.unlink()

        try:
            with pytest.raises(ApiError, match="login failed") as exc_info:
                client.login()
            assert exc_info.value.http_status == 401
            assert exc_info.value.provider == "qbittorrent"
        finally:
            if _LOCKOUT_FILE.exists():
                _LOCKOUT_FILE.unlink()

    def test_forbidden_raises_apierror_403(self) -> None:
        """qbittorrentapi.Forbidden403Error → ApiError(http_status=403)."""
        client = self._client()
        client._client.auth_log_in.side_effect = qbittorrentapi.Forbidden403Error("ip banned")  # type: ignore[attr-defined]

        with pytest.raises(ApiError, match="IP banned") as exc_info:
            client.login()
        assert exc_info.value.http_status == 403
        assert exc_info.value.provider == "qbittorrent"
