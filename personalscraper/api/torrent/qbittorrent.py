"""qBittorrent client implementing the TorrentClient Protocol.

Wraps qbittorrentapi.Client with anti-ban protection (lockout file, pre-check)
and maps qBit API responses to TorrentItem dataclasses.

Provider-specific exceptions (QBitAuthLockoutError, LoginFailed, Forbidden403Error,
APIConnectionError) are preserved — they carry actionable user guidance in the
ingest step. This is the allowed escape hatch documented in _base.py.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import qbittorrentapi
import requests

from personalscraper.api._contracts import ApiError, ProviderName
from personalscraper.api.torrent._base import TorrentClient, TorrentItem
from personalscraper.conf.models.api_config import TorrentClientEntry
from personalscraper.logger import get_logger

log = get_logger("api.torrent.qbittorrent")

_LOCKOUT_FILE = Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"
_LOCKOUT_DURATION_SECONDS = 3600


class QBitAuthLockoutError(Exception):
    """Raised when auth is blocked by a lockout file from a prior failure."""


class QBitClient:
    """qBittorrent client wrapping qbittorrentapi.Client.

    Implements the TorrentClient Protocol. Login is handled by
    :func:`build_client` — this class assumes an already-authenticated
    underlying client.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["QBIT_USERNAME", "QBIT_PASSWORD"]
    provider_name = ProviderName.QBITTORRENT.value

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        """Initialize the qBittorrent API client.

        Args:
            host: qBittorrent Web UI hostname.
            port: qBittorrent Web UI port.
            username: Login username.
            password: Login password.
        """
        self._host = host
        self._port = port
        self._client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password,
            REQUESTS_ARGS={"timeout": 30},
            VERIFY_WEBUI_CERTIFICATE=False,
        )

    # -- Protocol: queries ---------------------------------------------------

    def get_completed(self) -> list[TorrentItem]:
        """List all completed torrents.

        Returns:
            TorrentItem list for torrents with progress == 1.0.
        """
        return [_torrent_item(t) for t in self._client.torrents_info(status_filter="completed")]

    def get_all_hashes(self) -> set[str]:
        """Return the set of all torrent info hashes in qBittorrent.

        Returns:
            Set of torrent hash strings (any state).
        """
        return {t.hash for t in self._client.torrents_info()}

    def is_seeding(self, torrent: TorrentItem) -> bool:
        """Check if a torrent is actively seeding.

        Uses state_enum.is_uploading which covers uploading, stalledUP,
        forcedUP, and queuedUP states.

        Args:
            torrent: The torrent to check.

        Returns:
            True if the torrent is seeding.
        """
        raw = self._client.torrents_info(hashes=torrent.hash)
        if not raw:
            return False
        return raw[0].state_enum.is_uploading

    def get_content_path(self, torrent: TorrentItem) -> Path:
        """Resolve the filesystem path of a torrent's content.

        Args:
            torrent: The torrent to resolve.

        Returns:
            Path to the torrent's content on disk.

        Raises:
            ApiError: Torrent hash not found in qBittorrent.
        """
        raw = self._client.torrents_info(hashes=torrent.hash)
        if not raw:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=404,
                message=f"Torrent {torrent.hash} not found",
            )
        return Path(raw[0].content_path)

    # -- Protocol: mutations -------------------------------------------------

    def pause(self, hash: str) -> None:
        """Pause a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.torrents_pause(torrent_hashes=hash)

    def resume(self, hash: str) -> None:
        """Resume a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.torrents_resume(torrent_hashes=hash)

    def delete(self, hash: str, *, delete_files: bool = False) -> None:
        """Delete a torrent by hash.

        Args:
            hash: Torrent info hash.
            delete_files: If True, also delete the downloaded files.
        """
        self._client.torrents_delete(torrent_hashes=hash, delete_files=delete_files)

    # -- Auth ----------------------------------------------------------------

    def login(self) -> None:
        """Log in to qBittorrent API.

        Checks for a lockout file before attempting auth. On login failure,
        writes a lockout file to prevent cron/launchd from accumulating
        failed attempts that trigger qBittorrent's IP ban.

        Raises:
            QBitAuthLockoutError: Recent auth failure lockout is active.
            ApiError: Provider-uniform error per DESIGN §1.1. http_status=401 for invalid
                credentials (`LoginFailed`), 403 for IP-ban (`Forbidden403Error`).
        """
        _check_lockout()
        try:
            self._client.auth_log_in()
        except qbittorrentapi.LoginFailed as exc:
            _set_lockout("login_failed")
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=401,
                message=f"qBittorrent login failed: {exc}",
            ) from exc
        except qbittorrentapi.Forbidden403Error as exc:
            log.error("qbit_ip_banned", hint="Unban IP in qBit > Preferences > Web UI, or restart qBit")
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=403,
                message=f"qBittorrent IP banned: {exc}",
            ) from exc
        log.debug("qbit_connected", host=self._host, port=self._port)

    def logout(self) -> None:
        """Log out from qBittorrent API."""
        try:
            self._client.auth_log_out()
        except (qbittorrentapi.APIConnectionError, OSError) as e:
            # Logout failure on a long-lived qBit daemon is always abnormal
            # (network drop, daemon killed). Log at warning — a debug event
            # would be silently dropped by prod log tiers.
            log.warning("qbit_logout_failed", error=str(e))


# -- Factory entry point -----------------------------------------------------


def build_client(name: str, entry: TorrentClientEntry, env: Mapping[str, str]) -> TorrentClient:
    """Construct and authenticate a QBitClient.

    Args:
        name: Provider name (must be ``"qbittorrent"``).
        entry: Client configuration from torrent.json5.
        env: Credential source.

    Returns:
        An authenticated QBitClient instance.

    Raises:
        ApiError: Provider-uniform error per DESIGN §1.1. http_status=0 for missing creds
            or unreachable host (network), 401 for bad credentials, 403 for IP-ban.
        QBitAuthLockoutError: Auth lockout active from prior failure.
    """
    username = env.get("QBIT_USERNAME", "")
    password = env.get("QBIT_PASSWORD", "")
    if not username or not password:
        raise ApiError(
            provider=ProviderName.QBITTORRENT,
            http_status=0,
            message="Missing QBIT_USERNAME or QBIT_PASSWORD",
        )

    try:
        resp = requests.get(f"http://{entry.host}:{entry.port}/", timeout=5)
        log.debug("qbit_pre_check_ok", status=resp.status_code)
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise ApiError(
            provider=ProviderName.QBITTORRENT,
            http_status=0,
            message=f"qBittorrent unreachable at {entry.host}:{entry.port}: {exc}",
        ) from exc

    client = QBitClient(entry.host, entry.port, username, password)
    client.login()
    return client


# -- Internal helpers --------------------------------------------------------


def _torrent_item(t: qbittorrentapi.TorrentDictionary) -> TorrentItem:
    """Map a qBittorrent torrent dictionary to a TorrentItem."""
    content_path = t.content_path or ""
    return TorrentItem(
        hash=t.hash,
        name=t.name,
        size_bytes=t.total_size,
        progress=float(t.progress),
        state=t.state,
        ratio=float(t.ratio or 0.0),
        content_path=Path(content_path) if content_path else None,
        category=t.category if t.category else None,
        added_on=datetime.fromtimestamp(t.added_on) if t.added_on else None,
    )


def _check_lockout() -> None:
    """Raise QBitAuthLockoutError if a recent auth failure lockout is active."""
    if not _LOCKOUT_FILE.exists():
        return
    try:
        age = time.time() - _LOCKOUT_FILE.stat().st_mtime
        if age < _LOCKOUT_DURATION_SECONDS:
            remaining = int(_LOCKOUT_DURATION_SECONDS - age)
            log.warning(
                "qbit_auth_lockout_active",
                remaining_seconds=remaining,
                lockout_file=str(_LOCKOUT_FILE),
            )
            raise QBitAuthLockoutError(
                f"Auth lockout active ({remaining}s remaining). Fix credentials and delete {_LOCKOUT_FILE} to retry."
            )
        _LOCKOUT_FILE.unlink(missing_ok=True)
    except OSError as e:
        log.warning("qbit_lockout_read_failed", error=str(e))


def _set_lockout(reason: str) -> None:
    """Write a lockout file to prevent further auth attempts."""
    try:
        _LOCKOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LOCKOUT_FILE.write_text(reason)
        log.error(
            "qbit_auth_lockout_set",
            reason=reason,
            duration_seconds=_LOCKOUT_DURATION_SECONDS,
            lockout_file=str(_LOCKOUT_FILE),
            hint=f"Fix credentials in .env, then delete {_LOCKOUT_FILE} to retry",
        )
    except OSError as e:
        # Lockout file write failure is a security-control regression: the next
        # caller will retry and may trip the IP-ban path again. Log loudly with
        # the actionable hint so operators see it in alerting.
        log.error(
            "qbit_lockout_write_failed",
            error=str(e),
            hint="Cannot enforce auth lockout — credentials may keep retrying. Check filesystem permissions on "
            f"{_LOCKOUT_FILE.parent}.",
        )
