"""Transport-class exception tuples and the capability-gap signal for torrent consumers.

Centralised here so the commands layer (``personalscraper/commands/pipeline.py``)
and any future consumer can ``except TORRENT_CONNECT_ERRORS`` without
importing ``qbittorrentapi`` / ``requests`` directly — keeping the
third-party transport dependencies behind the ``api/torrent/`` boundary.

Two flavours of transport-error tuples intentionally separated:

- :data:`TORRENT_CONNECT_ERRORS` — broad set covering connection setup
  (``build_active_torrent_client``, ``.login()``). Includes ``OSError``
  because ``build_active_torrent_client`` may touch the filesystem
  (loading a cert bundle, reading a config file).

- :data:`TORRENT_LISTING_ERRORS` — narrower set for purely-network
  operations like ``get_completed()`` / ``get_all_hashes()``. ``OSError``
  is deliberately dropped so a disk-full or permission error at the
  listing site surfaces as a bug instead of being masked as
  "transport failure".

Programmer-class exceptions (``TypeError``, ``AttributeError``) are
excluded from both — they indicate a refactor regression and must
bubble to ``handle_cli_errors`` for visibility.

This module lives separately from ``_contracts.py`` to avoid a circular
import: ``qbittorrent.py`` (where ``QBitAuthLockoutError`` is defined)
imports from ``_contracts.py``, so ``_contracts.py`` cannot import from
``qbittorrent.py``.
"""

from __future__ import annotations

import qbittorrentapi
import requests

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent.qbittorrent import QBitAuthLockoutError


class UnsupportedCapabilityError(Exception):
    """Raised when a capability unsupported by the client is requested (D8).

    Raised by TransmissionClient.add() when limits is not None — Transmission
    has no ratio/bandwidth/seedtime limit fields. Gate via
    isinstance(client, TorrentLimiter) before passing limits.

    Intentionally not an :class:`ApiError` — this is a caller-contract
    violation (passing limits to a client that doesn't support them), not a
    transport or API failure. It must bubble uncaught for operator visibility.
    """


TORRENT_CONNECT_ERRORS: tuple[type[BaseException], ...] = (
    QBitAuthLockoutError,
    ApiError,
    ConnectionError,
    OSError,
    requests.RequestException,
    qbittorrentapi.exceptions.APIError,
)

TORRENT_LISTING_ERRORS: tuple[type[BaseException], ...] = (
    QBitAuthLockoutError,
    ApiError,
    ConnectionError,
    requests.RequestException,
    qbittorrentapi.exceptions.APIError,
)


__all__ = ["TORRENT_CONNECT_ERRORS", "TORRENT_LISTING_ERRORS", "UnsupportedCapabilityError"]
