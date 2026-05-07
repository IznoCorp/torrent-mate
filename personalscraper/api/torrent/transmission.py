"""Transmission client implementing the TorrentClient Protocol.

Wraps transmission-rpc with an HttpTransport pre-check (Option A from Phase 10).
Transmission uses JSON-RPC 2.0 over a single POST endpoint, with HTTP Basic Auth
and CSRF session-id dance handled by the library.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import transmission_rpc

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentClient, TorrentItem
from personalscraper.api.transport._auth import LoginAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import TransportPolicy
from personalscraper.conf.models.api_config import TorrentClientEntry
from personalscraper.logger import get_logger

log = get_logger("api.torrent.transmission")

# Status values that mean "download complete"
_COMPLETED_STATES = frozenset({transmission_rpc.Status.SEEDING, transmission_rpc.Status.SEED_PENDING})


class TransmissionClient:
    """Transmission client wrapping transmission-rpc.

    Implements the TorrentClient Protocol. A pre-check via HttpTransport
    verifies reachability and credentials before the library client is
    instantiated.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["TRANSMISSION_USERNAME", "TRANSMISSION_PASSWORD"]
    provider_name = "transmission"

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        """Initialize the Transmission RPC client.

        Args:
            host: Transmission RPC hostname.
            port: Transmission RPC port.
            username: HTTP Basic Auth username.
            password: HTTP Basic Auth password.
        """
        self._host = host
        self._port = port
        self._client = transmission_rpc.Client(
            host=host,
            port=port,
            username=username,
            password=password,
        )

    # -- Protocol: queries ---------------------------------------------------

    def get_completed(self) -> list[TorrentItem]:
        """List all completed torrents (status seeding or seed_pending).

        Returns:
            TorrentItem list for completed torrents.
        """
        torrents = self._client.get_torrents(
            arguments=[
                "id",
                "hashString",
                "name",
                "totalSize",
                "percentDone",
                "status",
                "downloadDir",
                "addedDate",
                "rateUpload",
                "uploadRatio",
                "labels",
                "error",
                "errorString",
            ]
        )
        return [_torrent_item(t) for t in torrents if t.status in _COMPLETED_STATES]

    def get_all_hashes(self) -> set[str]:
        """Return the set of all torrent hash strings in Transmission.

        Returns:
            Set of torrent hash strings (any status).
        """
        torrents = self._client.get_torrents(arguments=["hashString"])
        return {t.hash_string for t in torrents}

    def is_seeding(self, torrent: TorrentItem) -> bool:
        """Check if a torrent is seeding.

        Args:
            torrent: The torrent to check.

        Returns:
            True if the torrent is actively seeding.
        """
        try:
            t = self._client.get_torrent(torrent.hash, arguments=["status"])
            return t.status == transmission_rpc.Status.SEEDING
        except transmission_rpc.TransmissionError as exc:
            log.warning(
                "transmission_is_seeding_failed",
                hash=torrent.hash,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return False

    def get_content_path(self, torrent: TorrentItem) -> Path:
        """Resolve the filesystem path of a torrent's content.

        Single-file torrents return download_dir/filename.
        Multi-file torrents return download_dir/torrent_name.

        Args:
            torrent: The torrent to resolve.

        Returns:
            Path to the torrent's content on disk.

        Raises:
            ApiError: Torrent hash not found.
        """
        try:
            t = self._client.get_torrent(torrent.hash, arguments=["downloadDir", "name", "files"])
        except transmission_rpc.TransmissionError as exc:
            raise ApiError(
                provider="transmission",
                http_status=404,
                message=f"Torrent {torrent.hash} not found: {exc}",
            ) from exc
        files = t.get_files()
        if len(files) == 1:
            return Path(t.download_dir) / files[0].name
        return Path(t.download_dir) / t.name

    # -- Protocol: mutations -------------------------------------------------

    def pause(self, hash: str) -> None:
        """Stop a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.stop_torrent(ids=hash)

    def resume(self, hash: str) -> None:
        """Start a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.start_torrent(ids=hash)

    def delete(self, hash: str, *, delete_files: bool = False) -> None:
        """Remove a torrent by hash.

        Args:
            hash: Torrent info hash.
            delete_files: If True, also delete the downloaded data.
        """
        self._client.remove_torrent(ids=hash, delete_data=delete_files)


# -- Factory entry point -----------------------------------------------------


def build_client(name: str, entry: TorrentClientEntry, env: Mapping[str, str]) -> TorrentClient:
    """Construct a TransmissionClient with pre-check.

    Args:
        name: Provider name (must be ``"transmission"``).
        entry: Client configuration from torrent.json5.
        env: Credential source.

    Returns:
        A TransmissionClient instance.

    Raises:
        ApiError: Missing required credentials or bad auth.
        ConnectionError: Transmission unreachable.
    """
    username = env.get("TRANSMISSION_USERNAME", "")
    password = env.get("TRANSMISSION_PASSWORD", "")
    if not username or not password:
        raise ApiError(
            provider="transmission",
            http_status=0,
            message="Missing TRANSMISSION_USERNAME or TRANSMISSION_PASSWORD",
        )

    base_url = f"http://{entry.host}:{entry.port}"
    transport = HttpTransport(
        TransportPolicy(
            provider_name="transmission-precheck",
            base_url=base_url,
            auth=LoginAuth(username, password),
            timeout_seconds=5,
        )
    )

    # Pre-check: POST a lightweight session_get to exercise auth + RPC stack.
    # 200 = reachable, 401 = bad creds, 409 = CSRF dance needed (normal).
    try:
        transport.post(
            "/transmission/rpc",
            data={
                "method": "session_get",
                "params": {"fields": ["version"]},
                "id": 1,
            },
        )
    except ApiError as e:
        if e.http_status == 401:
            raise
        if e.http_status != 409:
            raise

    log.debug("transmission_pre_check_ok", host=entry.host, port=entry.port)
    return TransmissionClient(entry.host, entry.port, username, password)


# -- Internal helpers --------------------------------------------------------


def _torrent_item(t: transmission_rpc.Torrent) -> TorrentItem:
    """Map a transmission-rpc Torrent object to a TorrentItem."""
    content_path = ""
    if t.download_dir:
        files = t.get_files()
        if len(files) == 1:
            content_path = str(Path(t.download_dir) / files[0].name)
        elif t.name:
            content_path = str(Path(t.download_dir) / t.name)

    labels = getattr(t, "labels", None)
    category = labels[0] if labels else None

    added_on = None
    if t.added_date:
        if isinstance(t.added_date, datetime):
            added_on = t.added_date
        else:
            added_on = datetime.fromtimestamp(t.added_date)

    return TorrentItem(
        hash=t.hash_string,
        name=t.name,
        size_bytes=t.total_size,
        progress=float(t.percent_done),
        state=str(t.status),
        ratio=float(getattr(t, "ratio", 0.0) or 0.0),
        content_path=Path(content_path) if content_path else None,
        category=category,
        added_on=added_on,
    )
