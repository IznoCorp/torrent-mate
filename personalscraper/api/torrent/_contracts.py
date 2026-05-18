"""Atomic capability protocols for the torrent family (DESIGN §4).

Decomposes the historical monolithic ``TorrentClient`` Protocol
(``api/torrent/_base.py``) into 5 single-purpose,
``@runtime_checkable`` protocols covering the 7 public methods of the
legacy interface :

| Legacy ``TorrentClient`` method | Atomic capability         |
| ------------------------------- | ------------------------- |
| ``get_completed()``             | :class:`TorrentLister`    |
| ``get_all_hashes()``            | :class:`TorrentLister`    |
| ``get_content_path()``          | :class:`TorrentInspector` |
| ``login()`` (optional)          | :class:`AuthenticatedClient` |
| ``is_seeding()``                | :class:`TorrentStateInspector` |
| ``pause()``                     | :class:`TorrentController` |
| ``resume()``                    | :class:`TorrentController` |
| ``delete()``                    | :class:`TorrentController` |

Composition under DESIGN §4 :

- ``QBitClient(TorrentLister, TorrentInspector, AuthenticatedClient,
  TorrentStateInspector, TorrentController)`` — full set.
- ``TransmissionClient(TorrentLister, TorrentInspector,
  TorrentStateInspector, TorrentController)`` — no
  :class:`AuthenticatedClient` (no explicit ``login()`` step).

The split addresses two requirements raised by the
``provider-ids`` work : (1) the dispatch flow needs to query torrent
state without holding write authority (read-only consumers compose
only :class:`TorrentLister` + :class:`TorrentStateInspector`) ;
(2) future torrent clients without authenticated sessions skip
:class:`AuthenticatedClient` instead of raising
``NotImplementedError`` from a forced ``login()`` override.

Phase 1.4 ships only the contracts. Concrete clients (``QBitClient``,
``TransmissionClient``) continue to satisfy the monolithic
``TorrentClient`` Protocol ; phase 13 refactors them to compose the
atomic capabilities declared here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from personalscraper.api.torrent._base import TorrentItem


@runtime_checkable
class TorrentLister(Protocol):
    """Capability — enumerate torrents tracked by the client.

    Two complementary queries grouped under one capability because they
    are both pure listing primitives that every client of practical
    interest implements together :

    - :meth:`get_completed` returns the full :class:`TorrentItem`
      records for torrents whose download progress hit 100 %.
    - :meth:`get_all_hashes` returns just the info-hash set across all
      states (completed, downloading, paused), used by the ingest flow
      to detect duplicates without paying for the full payload.
    """

    def get_completed(self) -> list[TorrentItem]: ...

    def get_all_hashes(self) -> set[str]: ...


@runtime_checkable
class TorrentInspector(Protocol):
    """Capability — resolve the content path of a downloaded torrent.

    Returns the filesystem path that the dispatch flow reads from. The
    method takes a :class:`TorrentItem` rather than a bare hash because
    some clients (qBittorrent) need the in-memory item to disambiguate
    multi-file torrents from single-file ones.
    """

    def get_content_path(self, torrent: TorrentItem) -> Path: ...


@runtime_checkable
class AuthenticatedClient(Protocol):
    """Capability — establish an authenticated session against the client.

    Optional : only clients with an explicit login step compose this
    (qBittorrent). Stateless clients (Transmission with no auth, or
    RPC clients using per-request credentials) omit it.
    """

    def login(self) -> None: ...


@runtime_checkable
class TorrentStateInspector(Protocol):
    """Capability — read-only inspection of a torrent's runtime state.

    Held by every read-side consumer in the ingest / dispatch flow.
    The split from :class:`TorrentController` lets read-only callers
    type their dependency precisely and prevents accidental writes.
    """

    def is_seeding(self, torrent: TorrentItem) -> bool: ...


@runtime_checkable
class TorrentController(Protocol):
    """Capability — write actions that change a torrent's lifecycle state.

    Held only by callers authorised to mutate torrents (ingest cleanup,
    dispatch finalisation). Three actions grouped together because they
    share the same authorisation contract and are typically implemented
    via a single underlying API endpoint.
    """

    def pause(self, hash: str) -> None: ...

    def resume(self, hash: str) -> None: ...

    def delete(self, hash: str, *, delete_files: bool = False) -> None: ...


@runtime_checkable
class TorrentClientFull(
    TorrentLister,
    TorrentInspector,
    TorrentStateInspector,
    TorrentController,
    Protocol,
):
    """Composite capability — every torrent capability *except* authentication.

    Drop-in replacement for the historical ``TorrentClient`` Protocol,
    minus :class:`AuthenticatedClient` so :class:`TransmissionClient`
    (which has no explicit login step) still satisfies the type. The
    factory in :mod:`personalscraper.api.torrent._factory` returns
    this Protocol so existing call sites that touch every method keep
    type-checking ; callers that need authentication assert
    :class:`AuthenticatedClient` separately via ``isinstance``.
    """


__all__ = [
    "TorrentLister",
    "TorrentInspector",
    "AuthenticatedClient",
    "TorrentStateInspector",
    "TorrentController",
    "TorrentClientFull",
]
