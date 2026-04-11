"""Wrapper around qbittorrent-api for the ingest pipeline.

Provides QBitClient for listing completed torrents, checking seed status,
and resolving content paths. Uses the qbittorrent-api library which handles
auth, CSRF, and qBit v4.x/v5.0+ compatibility transparently.
"""

from pathlib import Path
from types import TracebackType

import qbittorrentapi

from personalscraper.logger import get_logger

log = get_logger("qbit_client")


class QBitClient:
    """Wrapper around qbittorrent-api for the ingest pipeline.

    Handles authentication, torrent listing, seed status detection,
    and content path resolution. Use as a context manager for
    automatic login/logout.

    Attributes:
        _client: The underlying qbittorrent-api Client instance.
    """

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        """Initialize the qBittorrent client.

        Args:
            host: qBittorrent Web API hostname.
            port: qBittorrent Web API port.
            username: Login username.
            password: Login password.
        """
        self._client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password,
            REQUESTS_ARGS={"timeout": 30},  # Default 15.1s too short for scheduled runs
            VERIFY_WEBUI_CERTIFICATE=False,  # Local API, no SSL cert
        )

    def __enter__(self) -> "QBitClient":
        """Log in to qBittorrent API.

        Returns:
            Self for use in with-statement.

        Raises:
            qbittorrentapi.LoginFailed: If credentials are invalid.
            qbittorrentapi.APIConnectionError: If qBittorrent is unreachable.
        """
        self._client.auth_log_in()
        log.debug("qbit_connected", host=self._client.host, port=self._client.port)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Log out from qBittorrent API.

        Args:
            exc_type: Exception type, if any.
            exc_val: Exception value, if any.
            exc_tb: Exception traceback, if any.
        """
        try:
            self._client.auth_log_out()
        except Exception:
            pass  # Logout failure is non-critical

    def get_completed_torrents(self) -> list[qbittorrentapi.TorrentDictionary]:
        """List all completed torrents.

        Returns:
            List of TorrentDictionary objects for torrents with progress == 1.0.
        """
        return list(self._client.torrents_info(status_filter="completed"))

    def is_seeding(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        """Check if a torrent is actively seeding.

        Uses state_enum.is_uploading which covers uploading, stalledUP,
        forcedUP, and queuedUP states. Returns False for stopped states
        (pausedUP/stoppedUP) which are safe for move operations.

        Args:
            torrent: The torrent to check.

        Returns:
            True if the torrent is seeding (should be copied, not moved).
        """
        return torrent.state_enum.is_uploading

    def get_content_path(self, torrent: qbittorrentapi.TorrentDictionary) -> Path:
        """Resolve the filesystem path of a torrent's content.

        The content_path may point to a single file (e.g. a .mkv)
        or a directory containing multiple files.

        Args:
            torrent: The torrent to resolve.

        Returns:
            Path to the torrent's content on disk.
        """
        return Path(torrent.content_path)

    def get_all_torrent_hashes(self) -> set[str]:
        """Get hashes of all torrents in qBittorrent (any state).

        Used by the tracker to clean up entries for deleted torrents.

        Returns:
            Set of torrent hash strings.
        """
        return {t.hash for t in self._client.torrents_info()}
