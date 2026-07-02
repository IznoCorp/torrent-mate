"""Atomic capability protocols for the torrent family (DESIGN §4).

Decomposes the historical monolithic ``TorrentClient`` Protocol
(``api/torrent/_base.py``) into 7 atomic, single-purpose,
``@runtime_checkable`` protocols covering the 10 public methods of the
interface :

| Capability / method              | Atomic capability            |
| -------------------------------- | ---------------------------- |
| ``get_completed()``              | :class:`TorrentLister`       |
| ``get_all_hashes()``             | :class:`TorrentLister`       |
| ``get_content_path()``           | :class:`TorrentInspector`    |
| ``login()`` (optional)           | :class:`AuthenticatedClient` |
| ``is_seeding()``                 | :class:`TorrentStateInspector` |
| ``pause()``                      | :class:`TorrentController`   |
| ``resume()``                     | :class:`TorrentController`   |
| ``delete()``                     | :class:`TorrentController`   |
| ``add()``                        | :class:`TorrentAdder`        |
| ``apply_limits()``               | :class:`TorrentLimiter`      |

Composition under DESIGN §4 :

- ``QBitClient(TorrentLister, TorrentInspector, AuthenticatedClient,
  TorrentStateInspector, TorrentController, TorrentAdder,
  TorrentLimiter)`` — full set.
- ``TransmissionClient(TorrentLister, TorrentInspector,
  TorrentStateInspector, TorrentController, TorrentAdder)`` — no
  :class:`AuthenticatedClient` (no explicit ``login()`` step); no
  :class:`TorrentLimiter` (Transmission lacks per-torrent limit RPC
  methods, D2).

The split addresses two requirements raised by the
``provider-ids`` work : (1) the dispatch flow needs to query torrent
state without holding write authority (read-only consumers compose
only :class:`TorrentLister` + :class:`TorrentStateInspector`) ;
(2) future torrent clients without authenticated sessions skip
:class:`AuthenticatedClient` instead of raising
``NotImplementedError`` from a forced ``login()`` override.

The former composite ``TorrentClientFull`` Protocol was dropped in
0.16.0 (MUST-14, CF-B). Callers that previously used it now type
their dependency via the atomic protocols they actually consume.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from personalscraper.api.torrent._base import TorrentItem, TorrentLimits, TorrentSource


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
class TorrentAdder(Protocol):
    """Capability — add a torrent to the client (D1/§5.2).

    Composed by QBitClient and TransmissionClient. Returns info_hash (D6).
    Duplicate adds are idempotent (D7). Passing limits to a client without
    TorrentLimiter must raise UnsupportedCapabilityError (D8).
    """

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Add a torrent from a source.

        Args:
            source: Discriminated value object — magnet or file bytes.
            category: Category label.
            tags: Tag strings.
            paused: Add in paused state if True.
            limits: Transfer limits; raise UnsupportedCapabilityError if
                client lacks TorrentLimiter and limits is not None (D8).

        Returns:
            info_hash string of the added torrent.
        """
        ...


@runtime_checkable
class TorrentLimiter(Protocol):
    """Capability — apply transfer limits to an existing torrent (D2/§5.2).

    Composed by QBitClient only. Callers gate via
    isinstance(client, TorrentLimiter) before calling apply_limits.
    """

    def apply_limits(self, info_hash: str, limits: TorrentLimits) -> None:
        """Apply transfer limits to the torrent.

        Args:
            info_hash: Lowercase hex info_hash of the target torrent.
            limits: Limits to apply; None fields are no-ops.
        """
        ...


@runtime_checkable
class TorrentTagger(Protocol):
    """Capability — add or remove tags on an existing torrent.

    Implemented by both ``QBitClient`` and ``TransmissionClient``.
    Both methods are **idempotent**: adding a tag that is already present
    is a no-op; removing a tag that is absent is a no-op. The torrent is
    identified by its lowercase-hex ``info_hash`` (``TorrentItem.hash``).

    Transmission requires a read-first write to preserve ``labels[0]``
    (the category); callers need not know the implementation detail.
    """

    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Add tags to an existing torrent (idempotent).

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to add. Already-present tags are ignored.

        Raises:
            ApiError: Provider-uniform error on transport/API failure.
        """
        ...

    def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Remove tags from an existing torrent (idempotent).

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to remove. Absent tags are ignored.

        Raises:
            ApiError: Provider-uniform error on transport/API failure.
        """
        ...


@runtime_checkable
class TorrentInjector(Protocol):
    """Capability — inject a .torrent at a specified save path with recheck.

    Composed by :class:`~personalscraper.api.torrent.qbittorrent.QBitClient`.
    Not implemented by :class:`TransmissionClient` — Transmission lacks
    ``savepath`` on add (D2) and 1:1 recheck semantics.

    Duplicate injects are idempotent — injecting a torrent whose info-hash
    is already present in the client is a no-op (same contract as
    :class:`TorrentAdder`).
    """

    def inject(
        self,
        torrent_bytes: bytes,
        *,
        save_path: str,
        recheck: bool = True,
        paused: bool = True,
    ) -> str:
        """Inject a .torrent into the client, pointed at an existing data path.

        Args:
            torrent_bytes: Raw .torrent file bytes.
            save_path: Absolute path to the existing data directory
                (the source torrent's ``save_path``).
            recheck: Whether to run a recheck after adding (default True).
            paused: Whether to add in paused state (default True).

        Returns:
            The info-hash (v1) of the injected torrent.
        """
        ...

    def list_files(self, info_hash: str) -> list[tuple[str, int]]:
        """Return ``(name, size)`` for every file in a torrent.

        Wraps qBittorrent ``torrents/files``.

        Args:
            info_hash: V1 info-hash of an active torrent.

        Returns:
            Ordered list of (relative_path, byte_size) for each file.
        """
        ...

    def properties(self, info_hash: str) -> dict[str, object]:
        """Return the raw ``torrents/properties`` dict for *info_hash*.

        Args:
            info_hash: V1 info-hash.

        Returns:
            The full properties dictionary. The ``piece_size`` key is
            the torrent's ``piece_length`` in bytes.
        """
        ...


__all__ = [
    "AuthenticatedClient",
    "TorrentAdder",
    "TorrentController",
    "TorrentInjector",
    "TorrentInspector",
    "TorrentLimiter",
    "TorrentLister",
    "TorrentStateInspector",
    "TorrentTagger",
]
