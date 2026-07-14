"""Acquisition downloads read-model (Phase 5 A4).

Surfaces the live progress of grabbed torrents by joining ``wanted`` rows in
status ``'grabbed'`` (their torrent was added to the client but not yet
dispatched) with the torrent client's per-hash state.

Read-only and fail-soft: an unreachable / unconfigured torrent client yields
``client_available=False`` rather than a 500, and a grabbed row whose hash the
client no longer knows is surfaced honestly as ``state="missing"`` instead of
being dropped (so a removed torrent is visible, not silently gone).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from personalscraper.acquire.store import build_acquire_store
from personalscraper.api.torrent._factory import build_active_torrent_client
from personalscraper.logger import get_logger
from personalscraper.web.models.acquisition import (
    AcquisitionDownload,
    AcquisitionDownloadsResponse,
    DownloadState,
    MediaRefResponse,
)

if TYPE_CHECKING:
    from personalscraper.acquire.domain import FollowedSeries, WantedItem
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.conf.models.config import Config

log = get_logger(__name__)

#: Raw qBittorrent / Transmission state strings → normalised ``DownloadState``.
#: Keys are lower-cased; anything unmapped falls through to ``"in_client"``.
_STATE_MAP: dict[str, str] = {
    "downloading": "downloading",
    "forceddl": "downloading",
    "metadl": "downloading",
    "checkingdl": "downloading",
    "download": "downloading",
    "download pending": "queued",
    "stalleddl": "stalled",
    "uploading": "seeding",
    "stalledup": "seeding",
    "forcedup": "seeding",
    "queuedup": "seeding",
    "checkingup": "seeding",
    "seeding": "seeding",
    "seed_pending": "seeding",
    "seed pending": "seeding",
    "pauseddl": "paused",
    "pausedup": "paused",
    "paused": "paused",
    "stopped": "paused",
    "queueddl": "queued",
    "queued": "queued",
    "check pending": "queued",
}


def _normalise_state(raw: str) -> DownloadState:
    """Map a raw client state string to a normalised ``DownloadState``.

    Args:
        raw: The client's raw state (e.g. ``"stalledDL"``, ``"seeding"``).

    Returns:
        One of the ``DownloadState`` buckets; ``"in_client"`` for an unmapped
        state (the torrent exists but its state is not one we bucket).
    """
    return cast(DownloadState, _STATE_MAP.get(raw.strip().lower(), "in_client"))


def _to_download(
    wanted: WantedItem,
    title: str,
    item: TorrentItem | None,
) -> AcquisitionDownload:
    """Build one :class:`AcquisitionDownload` row.

    Args:
        wanted: The grabbed ``wanted`` item.
        title: The followed-series/film display title (may be empty).
        item: The matching :class:`TorrentItem` from the client, or ``None``
            when the client has no record of the hash (→ ``state="missing"``).

    Returns:
        The download row for the API response.
    """
    ref = wanted.media_ref
    return AcquisitionDownload(
        media_ref=MediaRefResponse(tvdb_id=ref.tvdb_id, tmdb_id=ref.tmdb_id, imdb_id=ref.imdb_id),
        title=title,
        kind=wanted.kind,
        season=wanted.season,
        episode=wanted.episode,
        info_hash=wanted.grabbed_hash or "",
        name="" if item is None else item.name,
        progress=0.0 if item is None else item.progress,
        state="missing" if item is None else _normalise_state(item.state),
        size_bytes=0 if item is None else item.size_bytes,
    )


def _sort_key(download: AcquisitionDownload) -> tuple[int, float]:
    """Order in-progress downloads first, then by ascending progress.

    Args:
        download: A download row.

    Returns:
        A sort key: ``missing`` last, incomplete before complete, then by
        progress (least-done first — the ones still arriving lead the list).
    """
    if download.state == "missing":
        return (2, 1.0)
    complete = 1 if download.progress >= 1.0 else 0
    return (complete, download.progress)


def list_active_downloads(config: Config) -> AcquisitionDownloadsResponse:
    """Return the live downloads for every ``grabbed`` wanted item (A4).

    Joins ``wanted`` rows in status ``'grabbed'`` with the torrent client's
    per-hash state. Fully fail-soft: a torrent-client error yields
    ``client_available=False`` with the grabbed rows still listed as
    ``state="missing"`` so the operator sees what was grabbed even when the
    client is down.

    Args:
        config: The loaded config (``acquire.db_path`` + ``torrent``).

    Returns:
        An :class:`AcquisitionDownloadsResponse`, downloads sorted in-progress
        first.
    """
    store = build_acquire_store(config.acquire)
    try:
        grabbed = store.wanted.list_grabbed()
        follows: list[FollowedSeries] = store.follow.list_all()
    finally:
        store.close()

    title_by_id = {f.id: f.title for f in follows if f.id is not None}
    hashes = {w.grabbed_hash for w in grabbed if w.grabbed_hash}

    by_hash: dict[str, TorrentItem] = {}
    client_available = True
    if hashes:
        try:
            client = build_active_torrent_client(config.torrent)
            # qBittorrent exposes login/logout; Transmission authenticates in its
            # constructor and omits them — call only when present.
            login = getattr(client, "login", None)
            if callable(login):
                login()
            try:
                by_hash = {t.hash.lower(): t for t in client.get_by_hashes(hashes)}
            finally:
                logout = getattr(client, "logout", None)
                if callable(logout):
                    logout()
        except Exception as exc:  # noqa: BLE001 — the panel must never 500 on a client outage
            log.warning("acquisition_downloads_client_unavailable", error=str(exc))
            client_available = False

    downloads = [
        _to_download(
            w,
            title_by_id.get(w.followed_id, "") if w.followed_id is not None else "",
            by_hash.get((w.grabbed_hash or "").lower()),
        )
        for w in grabbed
    ]
    downloads.sort(key=_sort_key)
    return AcquisitionDownloadsResponse(downloads=downloads, client_available=client_available)


__all__ = ["list_active_downloads"]
