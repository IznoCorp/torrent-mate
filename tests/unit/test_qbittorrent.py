"""Tests for api/torrent/qbittorrent.py."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import qbittorrentapi

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.api.torrent._errors import (
    QBitAuthLockoutError,
    TorrentAuthError,
    TorrentUnreachableError,
)
from personalscraper.api.torrent.qbittorrent import (
    QBitClient,
    _map_qbit_api_error,
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

    def test_healthy_state_has_no_error_reason(self) -> None:
        """A normal torrent carries error_reason=None."""
        mock = MagicMock()
        mock.state = "uploading"
        mock.content_path = "/x"
        mock.category = ""
        mock.added_on = 0
        assert _torrent_item(mock).error_reason is None

    def test_missing_files_state_sets_french_error_reason(self) -> None:
        """QBit ``missingFiles`` → a French error_reason (§8 — data vanished).

        Red-on-old: this state fell through to a neutral ``in_client`` bucket
        with no reason, so the operator never saw the breakage.
        """
        mock = MagicMock()
        mock.state = "missingFiles"
        mock.content_path = "/x"
        mock.category = ""
        mock.added_on = 0
        item = _torrent_item(mock)
        assert item.state == "missingFiles"
        assert item.error_reason == "Fichiers manquants sur le disque"

    def test_error_state_sets_error_reason(self) -> None:
        """QBit ``error`` state → a generic French error_reason."""
        mock = MagicMock()
        mock.state = "error"
        mock.content_path = "/x"
        mock.category = ""
        mock.added_on = 0
        assert _torrent_item(mock).error_reason == "Torrent en erreur (voir qBittorrent)"

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


class TestTorrentItemTagsField:
    """TorrentItem.tags field — D4."""

    def test_default_empty_list(self) -> None:
        """TorrentItem.tags defaults to empty list."""
        item = TorrentItem(hash="h", name="n", size_bytes=0, progress=0.0, state="up")
        assert item.tags == []
        assert isinstance(item.tags, list)

    def test_qbit_mapper_splits_csv(self) -> None:
        """QBit _torrent_item splits comma-separated tags string into list."""
        mock = MagicMock()
        mock.hash = "h"
        mock.name = "n"
        mock.total_size = 0
        mock.progress = 0.0
        mock.state = "up"
        mock.ratio = 0.0
        mock.content_path = ""
        mock.category = ""
        mock.added_on = 0
        mock.tags = "action,drama,2024"
        assert _torrent_item(mock).tags == ["action", "drama", "2024"]

    def test_qbit_mapper_empty_tags(self) -> None:
        """QBit _torrent_item handles empty tags string as empty list."""
        mock = MagicMock()
        mock.hash = "h"
        mock.name = "n"
        mock.total_size = 0
        mock.progress = 0.0
        mock.state = "up"
        mock.ratio = 0.0
        mock.content_path = ""
        mock.category = ""
        mock.added_on = 0
        mock.tags = ""
        assert _torrent_item(mock).tags == []


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

    def test_get_by_hashes_maps_and_filters(self) -> None:
        """get_by_hashes() forwards the hash filter and maps to TorrentItem (A4)."""
        client = self._client()
        mock_t = MagicMock()
        mock_t.hash = "abc"
        mock_t.name = "Robot"
        mock_t.total_size = 1000
        mock_t.progress = 0.5
        mock_t.state = "downloading"
        mock_t.content_path = "/data"
        mock_t.category = "cat"
        mock_t.added_on = 1712345678
        client._client.torrents_info.return_value = [mock_t]  # type: ignore[attr-defined]

        items = client.get_by_hashes({"abc"})
        assert len(items) == 1
        assert isinstance(items[0], TorrentItem)
        assert items[0].progress == 0.5
        client._client.torrents_info.assert_called_once_with(torrent_hashes=["abc"])  # type: ignore[attr-defined]

    def test_get_by_hashes_empty_short_circuits(self) -> None:
        """get_by_hashes(set()) returns [] WITHOUT querying (a bare query = all torrents)."""
        client = self._client()
        assert client.get_by_hashes(set()) == []
        client._client.torrents_info.assert_not_called()  # type: ignore[attr-defined]

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

    def test_resume_403_raises_apierror(self) -> None:
        """``resume()`` raises ``ApiError(http_status=403)`` on ``Forbidden403Error``.

        Typed-error mapping from the 10.3 API hardening — an auth/IP-ban error
        on resume must be observable as a uniform ``ApiError`` per the
        :class:`TorrentController` contract, not a raw library exception.
        """
        client = self._client()
        client._client.torrents_resume.side_effect = qbittorrentapi.Forbidden403Error(  # type: ignore[attr-defined]
            "ip banned"
        )
        with pytest.raises(ApiError, match="resume forbidden") as exc_info:
            client.resume("abc")
        assert exc_info.value.http_status == 403

    def test_delete_403_raises_apierror(self) -> None:
        """``delete()`` raises ``ApiError(http_status=403)`` on ``Forbidden403Error``.

        Typed-error mapping from the 10.3 API hardening — an auth/IP-ban error
        on delete must be observable as a uniform ``ApiError`` per the
        :class:`TorrentController` contract, not a raw library exception.
        """
        client = self._client()
        client._client.torrents_delete.side_effect = qbittorrentapi.Forbidden403Error(  # type: ignore[attr-defined]
            "ip banned"
        )
        with pytest.raises(ApiError, match="delete forbidden") as exc_info:
            client.delete("abc")
        assert exc_info.value.http_status == 403

    def test_login_logout_delegate_to_auth_methods(self) -> None:
        """``login()`` and ``logout()`` call the underlying auth methods."""
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


class TestQBitNeutralErrorTranslation:
    """The ingest-boundary read methods translate qbittorrentapi exceptions.

    ``get_completed`` / ``get_all_hashes`` / ``is_seeding`` / ``get_content_path``
    map the provider library's transport/auth exceptions onto the family-neutral
    :mod:`personalscraper.api.torrent._errors` hierarchy so the ingest step never
    imports ``qbittorrentapi`` (PIPELINE-CORE-06 / TORRENT-TRACKERS-08). The
    neutral errors subclass :class:`ApiError`, so ``http_status`` still carries
    the auth/connection distinction.
    """

    def _client(self) -> QBitClient:
        c = QBitClient("localhost", 8081, "admin", "pass")
        c._client = MagicMock()
        return c

    def test_get_completed_login_failed_maps_to_auth_error_401(self) -> None:
        """LoginFailed on the listing call → TorrentAuthError(401)."""
        client = self._client()
        client._client.torrents_info.side_effect = qbittorrentapi.LoginFailed("bad creds")  # type: ignore[attr-defined]
        with pytest.raises(TorrentAuthError, match="login failed") as exc_info:
            client.get_completed()
        assert exc_info.value.http_status == 401

    def test_get_completed_forbidden_maps_to_auth_error_403(self) -> None:
        """Forbidden403Error on the listing call → TorrentAuthError(403), IP-ban wording."""
        client = self._client()
        client._client.torrents_info.side_effect = qbittorrentapi.Forbidden403Error("ip banned")  # type: ignore[attr-defined]
        with pytest.raises(TorrentAuthError, match="banned") as exc_info:
            client.get_completed()
        assert exc_info.value.http_status == 403

    def test_get_completed_connection_error_maps_to_unreachable(self) -> None:
        """APIConnectionError on the listing call → TorrentUnreachableError(0)."""
        client = self._client()
        client._client.torrents_info.side_effect = qbittorrentapi.APIConnectionError("refused")  # type: ignore[attr-defined]
        with pytest.raises(TorrentUnreachableError, match="unreachable") as exc_info:
            client.get_completed()
        assert exc_info.value.http_status == 0

    def test_get_all_hashes_connection_error_maps_to_unreachable(self) -> None:
        """APIConnectionError on get_all_hashes → TorrentUnreachableError."""
        client = self._client()
        client._client.torrents_info.side_effect = qbittorrentapi.APIConnectionError("refused")  # type: ignore[attr-defined]
        with pytest.raises(TorrentUnreachableError):
            client.get_all_hashes()

    def test_get_content_path_connection_error_maps_to_unreachable(self) -> None:
        """APIConnectionError on get_content_path → TorrentUnreachableError."""
        client = self._client()
        client._client.torrents_info.side_effect = qbittorrentapi.APIConnectionError("refused")  # type: ignore[attr-defined]
        torrent = TorrentItem(hash="abc", name="t", size_bytes=1, progress=1.0, state="uploading")
        with pytest.raises(TorrentUnreachableError):
            client.get_content_path(torrent)

    def test_is_seeding_connection_error_maps_to_unreachable(self) -> None:
        """APIConnectionError on is_seeding → TorrentUnreachableError."""
        client = self._client()
        client._client.torrents_info.side_effect = qbittorrentapi.APIConnectionError("refused")  # type: ignore[attr-defined]
        torrent = TorrentItem(hash="abc", name="t", size_bytes=1, progress=1.0, state="uploading")
        with pytest.raises(TorrentUnreachableError):
            client.is_seeding(torrent)


class TestQBitProviderErrorMap:
    """One consolidated ``_map_qbit_api_error`` table for the mutation methods.

    ``list_files`` / ``properties`` / ``resume`` / ``delete`` / ``add`` /
    ``inject`` previously each duplicated the same except-chain (TORRENT-TRACKERS-01,
    audit ×6). They now route through this single helper; the dispatch must stay
    behaviour-preserving.
    """

    def _client(self) -> QBitClient:
        c = QBitClient("localhost", 8081, "admin", "pass")
        c._client = MagicMock()
        return c

    def test_map_not_found_with_id(self) -> None:
        """A NotFound404 with an id maps to a 404 naming the hash (list_files/properties)."""
        err = _map_qbit_api_error("list_files", qbittorrentapi.NotFound404Error("x"), not_found_id="deadbeef")
        assert err.http_status == 404
        assert "deadbeef" in err.message

    def test_map_not_found_without_id_falls_to_connection(self) -> None:
        """resume/delete pass no id → a 404 is an APIConnectionError subclass → 0."""
        err = _map_qbit_api_error("resume", qbittorrentapi.NotFound404Error("x"))
        assert err.http_status == 0
        assert "connection error" in err.message

    def test_map_forbidden(self) -> None:
        """Forbidden403Error → 403 with the op-scoped message."""
        err = _map_qbit_api_error("resume", qbittorrentapi.Forbidden403Error("ban"))
        assert err.http_status == 403
        assert "resume forbidden" in err.message

    def test_map_unauthorized_and_login_failed(self) -> None:
        """Both Unauthorized401Error and LoginFailed → 401."""
        assert _map_qbit_api_error("delete", qbittorrentapi.Unauthorized401Error("x")).http_status == 401
        assert _map_qbit_api_error("delete", qbittorrentapi.LoginFailed("x")).http_status == 401

    def test_map_corrupt_payload_and_torrent_file(self) -> None:
        """415 → corrupt payload; TorrentFileError family → 0 (unreadable .torrent)."""
        assert _map_qbit_api_error("add", qbittorrentapi.UnsupportedMediaType415Error("x")).http_status == 415
        tf = _map_qbit_api_error("add", qbittorrentapi.TorrentFileNotFoundError("x"))
        assert tf.http_status == 0
        assert "could not read torrent file" in tf.message

    def test_map_connection_and_generic(self) -> None:
        """APIConnectionError → 0; a bare/generic APIError → 502."""
        assert _map_qbit_api_error("properties", qbittorrentapi.APIConnectionError("x")).http_status == 0
        assert _map_qbit_api_error("properties", qbittorrentapi.APIError("x")).http_status == 502

    def test_list_files_not_found_maps_to_404(self) -> None:
        """list_files routes a NotFound404 through the helper with its info_hash → 404."""
        client = self._client()
        client._client.torrents_files.side_effect = qbittorrentapi.NotFound404Error("x")  # type: ignore[attr-defined]
        with pytest.raises(ApiError, match="not found") as ei:
            client.list_files("deadbeef")
        assert ei.value.http_status == 404

    def test_add_bare_connection_error_propagates_uncaught(self) -> None:
        """add() deliberately does NOT map a bare APIConnectionError (historical behaviour)."""
        client = self._client()
        client._client.torrents_add.side_effect = qbittorrentapi.APIConnectionError("refused")  # type: ignore[attr-defined]
        from personalscraper.api.torrent._base import TorrentSource

        src = TorrentSource.from_magnet("magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567")
        with pytest.raises(qbittorrentapi.APIConnectionError):
            client.add(src)
