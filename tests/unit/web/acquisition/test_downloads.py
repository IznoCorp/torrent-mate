"""Unit tests for the acquisition downloads read-model (A4).

Guards ``list_active_downloads``: the join of grabbed ``wanted`` rows with the
torrent client's per-hash state, the case-insensitive hash match, the honest
``missing`` state for a hash the client forgot, and the fail-soft
``client_available=False`` on a client outage (never a 500 / empty-looks-like-none).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.downloads import list_active_downloads

_REF = MediaRef(tmdb_id=1184918)

_MOD = "personalscraper.web.acquisition.downloads"


def _wanted(
    info_hash: str, *, kind: str = "movie", season: int | None = None, episode: int | None = None
) -> WantedItem:
    """Build a grabbed wanted row for follow id 7."""
    return WantedItem(
        media_ref=_REF,
        kind=kind,  # type: ignore[arg-type]
        status="grabbed",  # type: ignore[arg-type]
        enqueued_at=1,
        followed_id=7,
        season=season,
        episode=episode,
        grabbed_hash=info_hash,
        id=25,
    )


def _titem(info_hash: str, progress: float, state: str, *, name: str = "X.mkv", size: int = 100) -> TorrentItem:
    """Build a client TorrentItem."""
    return TorrentItem(hash=info_hash, name=name, size_bytes=size, progress=progress, state=state)


def _store(grabbed: list[WantedItem], follows: list[FollowedSeries]) -> MagicMock:
    """A mock store whose wanted/follow substores return the given rows."""
    store = MagicMock()
    store.wanted.list_grabbed.return_value = grabbed
    store.follow.list_all.return_value = follows
    return store


def _follow_robot() -> FollowedSeries:
    """The « Le Robot sauvage » movie follow (id 7)."""
    return FollowedSeries(id=7, media_ref=_REF, title="Le Robot sauvage", added_at=1, kind="movie")  # type: ignore[arg-type]


def test_join_maps_progress_title_and_state_case_insensitive() -> None:
    """A grabbed row joins to its torrent by hash (case-insensitive) → live fields."""
    grabbed = [_wanted("ABCDEF")]  # stored upper-case
    client = MagicMock()
    client.get_by_hashes.return_value = [_titem("abcdef", 0.42, "downloading", name="Robot.mkv", size=999)]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_MOD}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(MagicMock())

    assert resp.client_available is True
    assert len(resp.downloads) == 1
    d = resp.downloads[0]
    assert d.title == "Le Robot sauvage"
    assert d.kind == "movie"
    assert d.progress == 0.42
    assert d.state == "downloading"
    assert d.name == "Robot.mkv"
    assert d.size_bytes == 999


def test_missing_hash_surfaces_as_missing_state() -> None:
    """A grabbed row whose hash the client does not know reads state='missing'."""
    grabbed = [_wanted("DEADBEEF")]
    client = MagicMock()
    client.get_by_hashes.return_value = []  # client forgot the torrent
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_MOD}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(MagicMock())

    assert resp.client_available is True
    assert resp.downloads[0].state == "missing"
    assert resp.downloads[0].progress == 0.0


def test_client_outage_is_fail_soft() -> None:
    """A torrent-client error → client_available=False, rows still listed (missing)."""
    grabbed = [_wanted("ABCDEF")]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_MOD}.build_active_torrent_client", side_effect=OSError("connection refused")),
    ):
        resp = list_active_downloads(MagicMock())

    assert resp.client_available is False
    assert len(resp.downloads) == 1
    assert resp.downloads[0].state == "missing"


def test_no_grabbed_rows_skips_client_entirely() -> None:
    """Zero grabbed rows → no client call, empty list, client_available stays True."""
    client = MagicMock()
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store([], [])),
        patch(f"{_MOD}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(MagicMock())

    assert resp.downloads == []
    assert resp.client_available is True
    client.get_by_hashes.assert_not_called()


def test_in_progress_sorts_before_seeding() -> None:
    """Downloads sort in-progress (least-done first) ahead of completed/seeding."""
    grabbed = [_wanted("AAAA"), _wanted("BBBB"), _wanted("CCCC")]
    client = MagicMock()
    client.get_by_hashes.return_value = [
        _titem("aaaa", 1.0, "uploading"),  # complete
        _titem("bbbb", 0.10, "downloading"),  # barely started
        _titem("cccc", 0.80, "downloading"),  # nearly done
    ]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_MOD}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(MagicMock())

    progresses = [d.progress for d in resp.downloads]
    assert progresses == [0.10, 0.80, 1.0]  # incomplete (asc) before complete
