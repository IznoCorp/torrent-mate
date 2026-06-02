"""Transmission client composing the atomic torrent capability protocols.

Wraps transmission-rpc with an HttpTransport pre-check: we issue a cheap
GET via the unified transport before instantiating transmission-rpc so
network/auth failures surface as a uniform ApiError instead of leaking the
library's exception types up the call stack. Composes
:class:`TorrentLister`, :class:`TorrentInspector`,
:class:`TorrentStateInspector`, :class:`TorrentController` and
:class:`TorrentAdder` from
:mod:`personalscraper.api.torrent._contracts`. Deliberately omits
:class:`AuthenticatedClient` — the transmission-rpc library performs HTTP
Basic Auth per request without an explicit login step (DESIGN §4 — phase 13).
Also deliberately omits :class:`TorrentLimiter` — Transmission has no ratio/
bandwidth/seedtime limits API (D2/D8).

Transmission itself uses JSON-RPC 2.0 over a single POST endpoint with
HTTP Basic Auth and the CSRF session-id dance handled by the library.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import transmission_rpc

from personalscraper.api._contracts import ApiError, ProviderName
from personalscraper.api.torrent._base import TorrentItem, TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import (
    TorrentAdder,
    TorrentController,
    TorrentInspector,
    TorrentLister,
    TorrentStateInspector,
)
from personalscraper.api.torrent._errors import UnsupportedCapabilityError
from personalscraper.api.transport._auth import LoginAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import TransportPolicy
from personalscraper.conf.models.api_config import TorrentClientEntry
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("api.torrent.transmission")

# Status values that mean "download complete"
_COMPLETED_STATES = frozenset({transmission_rpc.Status.SEEDING, transmission_rpc.Status.SEED_PENDING})


class TransmissionClient(
    TorrentLister,
    TorrentInspector,
    TorrentStateInspector,
    TorrentController,
    TorrentAdder,
):
    """Transmission client wrapping transmission-rpc.

    Composes :class:`TorrentLister`, :class:`TorrentInspector`,
    :class:`TorrentStateInspector`, :class:`TorrentController` and
    :class:`TorrentAdder`.
    Deliberately omits :class:`AuthenticatedClient` because
    transmission-rpc has no explicit login step (HTTP Basic Auth runs
    per-request). Also omits :class:`TorrentLimiter` — Transmission
    does not support ratio/bandwidth/seedtime limits (D2/D8).
    A pre-check via HttpTransport verifies reachability
    and credentials before the library client is instantiated.
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
                provider=ProviderName.TRANSMISSION,
                http_status=404,
                message=f"Torrent {torrent.hash} not found: {exc}",
            ) from exc
        files = t.get_files()
        if len(files) == 1:
            return Path(t.download_dir) / files[0].name
        return Path(t.download_dir) / t.name

    # -- Protocol: mutations -------------------------------------------------

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Add a torrent to Transmission (D1/D5/D7/D8).

        Labels encode category + tags per D5. Duplicate adds are idempotent
        (torrent-duplicate → return info_hash, no exception). Passing limits
        raises UnsupportedCapabilityError (D8 — no silent ignore).

        Args:
            source: TorrentSource — magnet or file bytes.
            category: Category (becomes labels[0]).
            tags: Tags (appended after category in labels).
            paused: Add in paused state if True.
            limits: Must be None; raises if set (D8).

        Returns:
            info_hash of the added (or already-present) torrent.

        Raises:
            UnsupportedCapabilityError: limits is not None.
        """
        if limits is not None:
            raise UnsupportedCapabilityError(
                "TransmissionClient does not support transfer limits. "
                "Gate via isinstance(client, TorrentLimiter) before passing limits."
            )
        torrent_arg: str | bytes
        if source.magnet is not None:
            torrent_arg = source.magnet
        else:
            assert source.file_bytes is not None  # guaranteed by TorrentSource.__post_init__
            torrent_arg = source.file_bytes
        try:
            result = self._client.add_torrent(
                torrent=torrent_arg,
                labels=_labels(category, list(tags)),
                paused=paused,
            )
            log.debug(
                "transmission_add_ok",
                echoed_hash=result.hash_string,
                source_hash=source.info_hash,
            )
            if result.hash_string.lower() != source.info_hash.lower():
                log.warning(
                    "transmission_add_hash_mismatch",
                    echoed_hash=result.hash_string,
                    source_hash=source.info_hash,
                    hint=(
                        "Transmission echoed a hash_string that differs"
                        " from the source-derived info_hash."
                        " Returning source.info_hash as canonical (D6)."
                    ),
                )
            return source.info_hash
        except transmission_rpc.TransmissionError as exc:
            if "torrent-duplicate" in str(exc).lower():  # D7 idempotence
                log.debug("transmission_add_duplicate", info_hash=source.info_hash)
                return source.info_hash
            raise

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


def build_client(name: str, entry: TorrentClientEntry, env: Mapping[str, str]) -> "TransmissionClient":
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
            provider=ProviderName.TRANSMISSION,
            http_status=0,
            message="Missing TRANSMISSION_USERNAME or TRANSMISSION_PASSWORD",
        )

    base_url = f"http://{entry.host}:{entry.port}"
    transport = HttpTransport(
        TransportPolicy(
            provider_name=f"{ProviderName.TRANSMISSION.value}-precheck",
            base_url=base_url,
            auth=LoginAuth(username, password),
            timeout_seconds=5,
        ),
        event_bus=EventBus(),
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


def _labels(category: str | None, tags: list[str]) -> list[str]:
    """Build Transmission labels list from category and tags (D5).

    Round-trip: write labels=[category, *tags]; read category=labels[0],
    tags=labels[1:]. Category is deduped if it also appears in tags.

    Args:
        category: Category string or None.
        tags: Tag strings.

    Returns:
        Ordered list [category, *deduped_tags].
    """
    result: list[str] = []
    if category is not None:
        result.append(category)
    for tag in tags:
        if tag not in result:
            result.append(tag)
    return result


def _torrent_item(t: transmission_rpc.Torrent) -> TorrentItem:
    """Map a transmission-rpc Torrent object to a TorrentItem."""
    content_path = ""
    if t.download_dir:
        files = t.get_files()
        if len(files) == 1:
            content_path = str(Path(t.download_dir) / files[0].name)
        elif t.name:
            content_path = str(Path(t.download_dir) / t.name)

    labels: list[str] = list(getattr(t, "labels", None) or [])
    category = labels[0] if labels else None
    tags = list(labels[1:]) if len(labels) > 1 else []

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
        tags=tags,
        added_on=added_on,
    )
