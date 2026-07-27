"""Transport-class exception tuples and the torrent-family error hierarchy.

Centralised here so consumers (``personalscraper/ingest/ingest.py``,
``personalscraper/commands/pipeline.py``, ``…/watch.py``) can catch
torrent-client failures without importing ``qbittorrentapi`` /
``transmission_rpc`` / ``requests`` directly — keeping the third-party
transport dependencies behind the ``api/torrent/`` boundary.

Two families of symbols live here:

- **Family-neutral error hierarchy** (:class:`TorrentClientError` and its
  subclasses). The client layer (``qbittorrent.py`` / ``transmission.py``)
  translates its library exceptions into these at the protocol boundary so
  ingest catches ``TorrentAuthError`` / ``TorrentUnreachableError`` /
  ``TorrentLockoutError`` — never ``qbittorrentapi.LoginFailed`` and friends.
  They subclass :class:`ApiError` (the provider-uniform transport/response
  error) so the ``TORRENT_*_ERRORS`` tuples and the commands-layer consumers
  keep catching them via the existing ``ApiError`` entry, and their
  ``http_status`` carries the auth/connection distinction (401/403/0).

- **Transport-error tuples** (:data:`TORRENT_CONNECT_ERRORS` /
  :data:`TORRENT_LISTING_ERRORS`) — broad ``except`` sets for the commands
  layer, intentionally separated:

  - :data:`TORRENT_CONNECT_ERRORS` — connection setup
    (``build_active_torrent_client``, ``.login()``). Includes ``OSError``
    because building a client may touch the filesystem (cert bundle, config).

  - :data:`TORRENT_LISTING_ERRORS` — purely-network operations like
    ``get_completed()`` / ``get_all_hashes()``. ``OSError`` is deliberately
    dropped so a disk-full/permission error at the listing site surfaces as a
    bug instead of being masked as "transport failure".

Programmer-class exceptions (``TypeError``, ``AttributeError``) are excluded
from both tuples — they indicate a refactor regression and must bubble to
``handle_cli_errors`` for visibility.

:class:`UnsupportedCapabilityError` and :class:`QBitAuthLockoutError` are
defined here (not in ``qbittorrent.py``) so ``qbittorrent.py`` can import the
neutral hierarchy from this module without a circular import — this module
imports no sibling client module. ``qbittorrent.py`` re-exports
``QBitAuthLockoutError`` for backward compatibility.
"""

from __future__ import annotations

import qbittorrentapi
import requests

from personalscraper.api._contracts import ApiError


class QBitAuthLockoutError(Exception):
    """Raised when qBittorrent auth is blocked by a lockout file from a prior failure.

    Provider-specific (the anti-ban lockout file is a qBittorrent-only
    control). Defined here rather than in ``qbittorrent.py`` so the module can
    both raise it and be imported by the neutral hierarchy's consumers without
    a circular import. ``qbittorrent.py`` re-exports it under its historical
    name for callers that still import
    ``personalscraper.api.torrent.qbittorrent.QBitAuthLockoutError``.
    """


class UnsupportedCapabilityError(Exception):
    """Raised when a capability unsupported by the client is requested (D8).

    Raised e.g. by ``TransmissionClient.add()`` when ``limits`` is not None —
    Transmission has no ratio/bandwidth/seedtime limit fields. Gate via
    ``isinstance(client, TorrentLimiter)`` before passing limits.

    Intentionally not an :class:`ApiError` — this is a caller-contract
    violation (asking a client to do something it structurally cannot), not a
    transport or API failure. It must bubble uncaught for operator visibility.
    """


class TorrentClientError(ApiError):
    """Family-neutral base for torrent-client transport/auth failures.

    Raised at the client→consumer boundary in place of provider library
    exceptions (``qbittorrentapi.*`` / ``transmission_rpc.*``) so consumers
    (ingest, watch, pipeline) never import those libraries. An
    :class:`ApiError` subclass so the ``TORRENT_*_ERRORS`` tuples and the
    ``except ApiError`` consumers catch it unchanged and its ``http_status``
    field is available for branching (401 vs 403).
    """


class TorrentAuthError(TorrentClientError):
    """The torrent client rejected our credentials (bad login or IP-ban).

    ``http_status`` distinguishes the two operator remedies: 401 = wrong
    credentials, 403 = IP-banned by the client's Web-UI ban list.
    """


class TorrentUnreachableError(TorrentClientError):
    """The torrent client's API could not be reached (daemon down, network).

    Carries ``http_status=0`` (no HTTP response was obtained).
    """


class TorrentLockoutError(TorrentClientError):
    """A prior auth failure set an anti-ban lockout — the client is not queried.

    The family-neutral equivalent of :class:`QBitAuthLockoutError` surfaced to
    consumers so they need not import the qBittorrent-specific class.
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


__all__ = [
    "TORRENT_CONNECT_ERRORS",
    "TORRENT_LISTING_ERRORS",
    "QBitAuthLockoutError",
    "TorrentAuthError",
    "TorrentClientError",
    "TorrentLockoutError",
    "TorrentUnreachableError",
    "UnsupportedCapabilityError",
]
