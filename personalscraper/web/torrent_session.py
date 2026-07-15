"""Process-wide cached torrent-client session for web endpoints.

The web UI polls acquisition endpoints every few seconds (downloads panel,
watcher status, dashboard summary). Building a fresh torrent client per
request performs a full qBittorrent WebUI login each time — a sustained
login storm whose transient rejections feed qBittorrent's failed-auth
counter and eventually trip its IP ban (observed in prod 2026-07-15).

This module keeps ONE authenticated client per web process, guarded by a
lock (the underlying ``requests.Session`` is not thread-safe, and FastAPI
sync endpoints run in a threadpool). Endpoints borrow the client through a
context manager that holds the lock for the duration of the request's
client work — operations are short (localhost round-trips), so
serialization is negligible next to the polling interval.

The cached session is dropped on any error raised while borrowed (next
borrow rebuilds and re-authenticates) and refreshed after a TTL so config
changes are eventually picked up without a web restart.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

from personalscraper.api.torrent._factory import build_active_torrent_client
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.conf.models.api_config import TorrentConfig

    # The factory returns the union of the two concrete implementations
    # (the monolithic TorrentClient protocol was dropped in 0.16.0).
    TorrentClient = QBitClient | TransmissionClient

log = get_logger(__name__)

#: Cached session lifetime. With 3-second polls the session never idles
#: server-side; the TTL only bounds how long a stale config can linger.
_TTL_SECONDS = 900.0

_lock = threading.Lock()
_client: TorrentClient | None = None
_built_at: float = 0.0


@contextmanager
def shared_torrent_client(torrent_config: TorrentConfig) -> Iterator[TorrentClient | None]:
    """Borrow the process-wide torrent client, building it on first use.

    Holds the module lock while the caller uses the client, so concurrent
    web requests are serialized instead of racing on one HTTP session.

    Args:
        torrent_config: The ``torrent`` section of the loaded config.

    Yields:
        The cached authenticated client, or ``None`` when no torrent client
        is configured/active (``None`` is never cached — a client enabled
        later is picked up on the next borrow).

    Raises:
        Exception: Whatever the factory or the caller's client work raises;
            the cached session is invalidated first so the next borrow
            starts from a fresh login.
    """
    global _client, _built_at
    with _lock:
        now = time.monotonic()
        if _client is None or now - _built_at > _TTL_SECONDS:
            _client = build_active_torrent_client(torrent_config)
            _built_at = now
            if _client is not None:
                log.debug("torrent_session_built")
        try:
            yield _client
        except Exception:
            # Fail-closed on ANY error: a dead/expired session must not be
            # served to the next request — drop it and let the next borrow
            # re-authenticate once instead of erroring forever.
            _client = None
            raise


def invalidate_torrent_session() -> None:
    """Drop the cached client so the next borrow rebuilds it (test hook)."""
    global _client
    with _lock:
        _client = None


__all__ = ["invalidate_torrent_session", "shared_torrent_client"]
