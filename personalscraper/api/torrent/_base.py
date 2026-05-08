"""Torrent family base — TorrentItem dataclass and TorrentClient Protocol.

Implements DESIGN §5.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable


@dataclass
class TorrentItem:
    """A torrent tracked by a torrent client.

    Attributes:
        hash: Torrent info hash.
        name: Torrent display name.
        size_bytes: Total size in bytes.
        progress: Download progress (0.0 to 1.0).
        state: Current torrent state (e.g. "uploading", "pausedUP").
        content_path: Filesystem path to torrent content.
        category: Torrent category label, if any.
        added_on: Timestamp when the torrent was added.
        ratio: Seed ratio (uploaded / downloaded). 0.0 if never seeded.
            Used by ``ingest`` to enforce ``config.ingest.min_ratio``.
    """

    hash: str
    name: str
    size_bytes: int
    progress: float
    state: str
    content_path: Path | None = None
    category: str | None = None
    added_on: datetime | None = None
    ratio: float = 0.0


@runtime_checkable
class TorrentClient(Protocol):
    """Protocol that all torrent client implementations must satisfy.

    Required members:
        provider_name: Human-readable provider identifier.
        REQUIRED_CREDS: List of .env variable names needed by this client.
        get_completed(): List all completed torrents.
        get_all_hashes(): Return the set of all torrent info hashes.
        is_seeding(): Check if a torrent is currently seeding.
        get_content_path(): Return the content path for a torrent.
        pause(): Pause a torrent by hash.
        resume(): Resume a torrent by hash.
        delete(): Delete a torrent by hash.
    """

    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def get_completed(self) -> list[TorrentItem]: ...
    def get_all_hashes(self) -> set[str]: ...
    def is_seeding(self, torrent: TorrentItem) -> bool: ...
    def get_content_path(self, torrent: TorrentItem) -> Path: ...
    def pause(self, hash: str) -> None: ...
    def resume(self, hash: str) -> None: ...
    def delete(self, hash: str, *, delete_files: bool = False) -> None: ...
