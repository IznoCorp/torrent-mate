"""Unit tests for api/torrent/transmission.py.

Plan S11.4 coverage: TorrentItem mapping, status enum filtering, percent_done
preservation, multi/single-file content_path resolution, factory pre-check.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import transmission_rpc

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.api.torrent.transmission import (
    TransmissionClient,
    _torrent_item,
    build_client,
)
from personalscraper.conf.models.api_config import TorrentClientEntry


def _entry() -> TorrentClientEntry:
    """Default entry pointing at localhost:9091 (Transmission default port)."""
    return TorrentClientEntry(host="localhost", port=9091)


def _env() -> dict[str, str]:
    """Valid Transmission credentials."""
    return {"TRANSMISSION_USERNAME": "user", "TRANSMISSION_PASSWORD": "pass"}


def _mock_torrent(
    *,
    hash_string: str = "abc123",
    name: str = "Test",
    total_size: int = 1_000_000,
    percent_done: float = 1.0,
    status: str = transmission_rpc.Status.SEEDING,
    ratio: float = 0.0,
    download_dir: str = "/data",
    added_date: datetime | int | None = 1712345678,
    files: list[MagicMock] | None = None,
    labels: list[str] | None = None,
) -> MagicMock:
    """Build a MagicMock that mimics a transmission_rpc.Torrent object."""
    t = MagicMock(spec=transmission_rpc.Torrent)
    t.hash_string = hash_string
    t.name = name
    t.total_size = total_size
    t.percent_done = percent_done
    t.status = status
    t.ratio = ratio
    t.download_dir = download_dir
    t.added_date = added_date
    t.labels = labels
    if files is None:
        f = MagicMock()
        f.name = name
        files = [f]
    t.get_files = MagicMock(return_value=files)
    return t


# -- _torrent_item mapping --------------------------------------------------


class TestTorrentItemMapping:
    """transmission_rpc.Torrent → TorrentItem conversion."""

    def test_basic_mapping_single_file(self) -> None:
        """Single-file torrent: content_path is download_dir / file.name."""
        t = _mock_torrent(name="movie.mkv")
        item = _torrent_item(t)
        assert isinstance(item, TorrentItem)
        assert item.hash == "abc123"
        assert item.name == "movie.mkv"
        assert item.size_bytes == 1_000_000
        assert item.progress == 1.0
        assert item.state == str(transmission_rpc.Status.SEEDING)
        assert item.content_path == Path("/data/movie.mkv")

    def test_multi_file_uses_torrent_name(self) -> None:
        """Multi-file torrent: content_path is download_dir / torrent_name."""
        files = [MagicMock(name="ep1"), MagicMock(name="ep2"), MagicMock(name="ep3")]
        t = _mock_torrent(name="Series.S01", files=files)
        item = _torrent_item(t)
        assert item.content_path == Path("/data/Series.S01")

    def test_added_date_int_converted_to_datetime(self) -> None:
        """Integer epoch added_date is converted to datetime."""
        t = _mock_torrent(added_date=1712345678)
        item = _torrent_item(t)
        assert isinstance(item.added_on, datetime)
        assert item.added_on == datetime.fromtimestamp(1712345678)

    def test_added_date_datetime_passthrough(self) -> None:
        """Already-datetime added_date passes through."""
        dt = datetime(2026, 1, 1, 12, 0, 0)
        t = _mock_torrent(added_date=dt)
        item = _torrent_item(t)
        assert item.added_on == dt

    def test_no_labels_yields_none_category(self) -> None:
        """Empty labels → category is None."""
        t = _mock_torrent(labels=None)
        item = _torrent_item(t)
        assert item.category is None

    def test_first_label_is_category(self) -> None:
        """First label is mapped to category."""
        t = _mock_torrent(labels=["movies", "1080p"])
        item = _torrent_item(t)
        assert item.category == "movies"

    def test_ratio_field_present_on_item(self) -> None:
        """Regression for BUG #8: TorrentItem must carry a `ratio` attribute.

        Same parity check as test_qbittorrent.py — both adapters must populate
        the `ratio` field that the ingest min_ratio gate relies on.
        """
        t = _mock_torrent(ratio=2.5)
        item = _torrent_item(t)
        assert hasattr(item, "ratio")
        assert isinstance(item.ratio, float)
        assert item.ratio == 2.5

    def test_no_download_dir_yields_none_content_path(self) -> None:
        """Empty download_dir → content_path is None."""
        t = _mock_torrent(download_dir="")
        item = _torrent_item(t)
        assert item.content_path is None


# -- TransmissionClient Protocol implementation -----------------------------


class TestTransmissionClient:
    """TransmissionClient methods (transport-mocked)."""

    def _client(self) -> TransmissionClient:
        """Build a TransmissionClient with the underlying rpc client mocked."""
        with patch("personalscraper.api.torrent.transmission.transmission_rpc.Client"):
            c = TransmissionClient("localhost", 9091, "u", "p")
        c._client = MagicMock()
        return c

    def test_provider_name(self) -> None:
        """provider_name == 'transmission'."""
        assert TransmissionClient.provider_name == "transmission"

    def test_required_creds(self) -> None:
        """REQUIRED_CREDS lists username + password."""
        assert TransmissionClient.REQUIRED_CREDS == [
            "TRANSMISSION_USERNAME",
            "TRANSMISSION_PASSWORD",
        ]

    def test_get_completed_filters_seeding_and_seed_pending(self) -> None:
        """Only SEEDING and SEED_PENDING statuses are 'completed'."""
        client = self._client()
        seeding = _mock_torrent(hash_string="seed1", status=transmission_rpc.Status.SEEDING)
        pending = _mock_torrent(hash_string="seed2", status=transmission_rpc.Status.SEED_PENDING)
        downloading = _mock_torrent(hash_string="dl1", status=transmission_rpc.Status.DOWNLOADING)
        stopped = _mock_torrent(hash_string="stop1", status=transmission_rpc.Status.STOPPED)
        client._client.get_torrents.return_value = [seeding, pending, downloading, stopped]

        items = client.get_completed()
        hashes = {item.hash for item in items}
        assert hashes == {"seed1", "seed2"}

    def test_get_all_hashes(self) -> None:
        """get_all_hashes returns the set of every hash, regardless of status."""
        client = self._client()
        client._client.get_torrents.return_value = [
            _mock_torrent(hash_string="a"),
            _mock_torrent(hash_string="b"),
            _mock_torrent(hash_string="c"),
        ]
        assert client.get_all_hashes() == {"a", "b", "c"}

    def test_get_by_hashes_maps_all_states(self) -> None:
        """get_by_hashes returns TorrentItems for the given ids, any status (A4)."""
        client = self._client()
        client._client.get_torrents.return_value = [
            _mock_torrent(hash_string="dl1", status=transmission_rpc.Status.DOWNLOADING),
            _mock_torrent(hash_string="seed1", status=transmission_rpc.Status.SEEDING),
        ]
        items = client.get_by_hashes({"dl1", "seed1"})
        assert {item.hash for item in items} == {"dl1", "seed1"}
        # ids forwarded to the RPC layer.
        assert client._client.get_torrents.call_args.kwargs["ids"] == ["dl1", "seed1"] or sorted(
            client._client.get_torrents.call_args.kwargs["ids"]
        ) == ["dl1", "seed1"]

    def test_get_by_hashes_empty_short_circuits(self) -> None:
        """get_by_hashes(set()) returns [] without an RPC call."""
        client = self._client()
        assert client.get_by_hashes(set()) == []
        client._client.get_torrents.assert_not_called()

    def test_is_seeding_true_for_seeding_status(self) -> None:
        """is_seeding returns True only for SEEDING (not SEED_PENDING)."""
        client = self._client()
        client._client.get_torrent.return_value = _mock_torrent(status=transmission_rpc.Status.SEEDING)
        item = TorrentItem(hash="abc", name="t", size_bytes=1, progress=1.0, state="seeding")
        assert client.is_seeding(item) is True

    def test_is_seeding_false_for_seed_pending(self) -> None:
        """SEED_PENDING is NOT actively seeding."""
        client = self._client()
        client._client.get_torrent.return_value = _mock_torrent(status=transmission_rpc.Status.SEED_PENDING)
        item = TorrentItem(hash="abc", name="t", size_bytes=1, progress=1.0, state="seed_pending")
        assert client.is_seeding(item) is False

    def test_is_seeding_handles_transmission_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """TransmissionError during is_seeding is swallowed → False AND logs warning."""
        client = self._client()
        client._client.get_torrent.side_effect = transmission_rpc.TransmissionError("boom")
        item = TorrentItem(hash="abc", name="t", size_bytes=1, progress=1.0, state="?")
        with caplog.at_level("WARNING", logger="api.torrent.transmission"):
            assert client.is_seeding(item) is False
        assert any("transmission_is_seeding_failed" in rec.message for rec in caplog.records)

    def test_get_content_path_single_file(self) -> None:
        """Single-file torrent path: download_dir / files[0].name."""
        client = self._client()
        f = MagicMock()
        f.name = "movie.mkv"
        client._client.get_torrent.return_value = MagicMock(
            download_dir="/data", name="ignored", get_files=MagicMock(return_value=[f])
        )
        item = TorrentItem(hash="abc", name="?", size_bytes=1, progress=1.0, state="seeding")
        assert client.get_content_path(item) == Path("/data/movie.mkv")

    def test_get_content_path_multi_file(self) -> None:
        """Multi-file torrent path: download_dir / torrent.name."""
        client = self._client()
        rpc_torrent = MagicMock(
            download_dir="/data",
            get_files=MagicMock(return_value=[MagicMock(), MagicMock()]),
        )
        # MagicMock(name=...) sets the mock's own repr name, not the .name attribute.
        rpc_torrent.name = "Series.S01"
        client._client.get_torrent.return_value = rpc_torrent
        item = TorrentItem(hash="abc", name="?", size_bytes=1, progress=1.0, state="seeding")
        assert client.get_content_path(item) == Path("/data/Series.S01")

    def test_get_content_path_not_found_raises_api_error(self) -> None:
        """Missing torrent → ApiError(http_status=404)."""
        client = self._client()
        client._client.get_torrent.side_effect = transmission_rpc.TransmissionError("not found")
        item = TorrentItem(hash="ghost", name="?", size_bytes=1, progress=0.0, state="?")
        with pytest.raises(ApiError) as exc_info:
            client.get_content_path(item)
        assert exc_info.value.http_status == 404

    def test_pause_resume_delete(self) -> None:
        """Mutations delegate to transmission_rpc methods with correct kwargs."""
        client = self._client()
        client.pause("hash1")
        client._client.stop_torrent.assert_called_once_with(ids="hash1")
        client.resume("hash2")
        client._client.start_torrent.assert_called_once_with(ids="hash2")
        client.delete("hash3", delete_files=True)
        client._client.remove_torrent.assert_called_once_with(ids="hash3", delete_data=True)

    def test_delete_default_keeps_files(self) -> None:
        """delete(delete_files=False) → remove_torrent(delete_data=False)."""
        client = self._client()
        client.delete("hash4")
        client._client.remove_torrent.assert_called_once_with(ids="hash4", delete_data=False)


# -- build_client factory ---------------------------------------------------


class TestBuildClient:
    """build_client() pre-check + construction."""

    def test_missing_username_raises(self) -> None:
        """Missing TRANSMISSION_USERNAME → ApiError."""
        with pytest.raises(ApiError, match="Missing TRANSMISSION_USERNAME"):
            build_client("transmission", _entry(), {"TRANSMISSION_PASSWORD": "p"})

    def test_missing_password_raises(self) -> None:
        """Missing TRANSMISSION_PASSWORD → ApiError."""
        with pytest.raises(ApiError, match="Missing TRANSMISSION_USERNAME"):
            build_client("transmission", _entry(), {"TRANSMISSION_USERNAME": "u"})

    @patch("personalscraper.api.torrent.transmission.transmission_rpc.Client")
    @patch("personalscraper.api.torrent.transmission.HttpTransport")
    def test_pre_check_409_csrf_is_tolerated(self, mock_transport_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        """409 from pre-check (CSRF dance) does NOT abort construction."""
        mock_transport = mock_transport_cls.return_value
        mock_transport.post.side_effect = ApiError(provider="transmission-precheck", http_status=409)
        result = build_client("transmission", _entry(), _env())
        assert isinstance(result, TransmissionClient)

    @patch("personalscraper.api.torrent.transmission.transmission_rpc.Client")
    @patch("personalscraper.api.torrent.transmission.HttpTransport")
    def test_pre_check_401_aborts(self, mock_transport_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        """401 from pre-check (bad creds) → ApiError propagated."""
        mock_transport = mock_transport_cls.return_value
        mock_transport.post.side_effect = ApiError(provider="transmission-precheck", http_status=401)
        with pytest.raises(ApiError) as exc_info:
            build_client("transmission", _entry(), _env())
        assert exc_info.value.http_status == 401

    @patch("personalscraper.api.torrent.transmission.transmission_rpc.Client")
    @patch("personalscraper.api.torrent.transmission.HttpTransport")
    def test_pre_check_other_error_aborts(self, mock_transport_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        """Any non-409 error (other than 401, e.g. 500) → ApiError propagated."""
        mock_transport = mock_transport_cls.return_value
        mock_transport.post.side_effect = ApiError(provider="transmission-precheck", http_status=500)
        with pytest.raises(ApiError) as exc_info:
            build_client("transmission", _entry(), _env())
        assert exc_info.value.http_status == 500

    @patch("personalscraper.api.torrent.transmission.transmission_rpc.Client")
    @patch("personalscraper.api.torrent.transmission.HttpTransport")
    def test_success_returns_transmission_client(
        self, mock_transport_cls: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        """Successful pre-check → TransmissionClient with credentials wired."""
        result = build_client("transmission", _entry(), _env())
        assert isinstance(result, TransmissionClient)
        mock_client_cls.assert_called_once_with(host="localhost", port=9091, username="user", password="pass")
