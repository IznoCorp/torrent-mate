"""Unit tests for the acquisition downloads read-model (A4).

Guards ``list_active_downloads``: the join of grabbed ``wanted`` rows with the
torrent client's per-hash state, the case-insensitive hash match, the honest
``missing`` state for a hash the client forgot, and the fail-soft
``client_available=False`` on a client outage (never a 500 / empty-looks-like-none).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf.models.api_config import TorrentScope
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.downloads import list_active_downloads

_REF = MediaRef(tmdb_id=1184918)

_MOD = "personalscraper.web.acquisition.downloads"
# The client is borrowed through the shared cached session — the factory now
# lives (and is patched) in the torrent_session module, not in downloads.
# Cache reset between tests: global autouse fixture in tests/conftest.py.
_SESSION = "personalscraper.app.torrent_session"


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


def _titem(
    info_hash: str,
    progress: float,
    state: str,
    *,
    name: str = "X.mkv",
    size: int = 100,
    error_reason: str | None = None,
) -> TorrentItem:
    """Build a client TorrentItem."""
    return TorrentItem(
        hash=info_hash,
        name=name,
        size_bytes=size,
        progress=progress,
        state=state,
        error_reason=error_reason,
    )


def _config(scope: TorrentScope | None = None) -> MagicMock:
    """A config whose active torrent client carries *scope* (``None`` = the whole client)."""
    config = MagicMock()
    config.torrent.active_scope.return_value = scope
    return config


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
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(_config())

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
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(_config())

    assert resp.client_available is True
    assert resp.downloads[0].state == "missing"
    assert resp.downloads[0].progress == 0.0


def test_errored_torrent_surfaces_state_and_reason() -> None:
    """A client-reported error wins over the raw state bucket (§8).

    Red-on-old: a torrent whose payload vanished (qBit ``missingFiles``) was
    mapped by its raw state to a neutral ``in_client`` bucket with no reason;
    now it reads ``errored`` and carries the French reason so the operator sees
    what is not advancing AND why.
    """
    grabbed = [_wanted("ABCDEF")]
    client = MagicMock()
    client.get_by_hashes.return_value = [
        _titem("abcdef", 1.0, "missingFiles", error_reason="Fichiers manquants sur le disque"),
    ]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(_config())

    d = resp.downloads[0]
    assert d.state == "errored"
    assert d.error_reason == "Fichiers manquants sur le disque"


def test_errored_torrent_sorts_first() -> None:
    """An errored torrent leads the list — it needs the operator now (§8)."""
    grabbed = [_wanted("AAAA", season=1, episode=1), _wanted("BBBB", season=1, episode=2)]
    client = MagicMock()
    client.get_by_hashes.return_value = [
        _titem("aaaa", 0.5, "downloading"),
        _titem("bbbb", 1.0, "missingFiles", error_reason="Fichiers manquants sur le disque"),
    ]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(_config())

    assert resp.downloads[0].state == "errored"
    assert resp.downloads[0].info_hash == "BBBB"


def test_client_outage_is_fail_soft() -> None:
    """A torrent-client error → client_available=False, rows still listed (missing)."""
    grabbed = [_wanted("ABCDEF")]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_SESSION}.build_active_torrent_client", side_effect=OSError("connection refused")),
    ):
        resp = list_active_downloads(_config())

    assert resp.client_available is False
    assert len(resp.downloads) == 1
    assert resp.downloads[0].state == "missing"


def test_no_grabbed_rows_skips_client_entirely() -> None:
    """Zero grabbed rows → no client call, empty list, client_available stays True."""
    client = MagicMock()
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store([], [])),
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(_config())

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
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(_config())

    progresses = [d.progress for d in resp.downloads]
    assert progresses == [0.10, 0.80, 1.0]  # incomplete (asc) before complete


def test_eta_seconds_passes_through_and_missing_is_none() -> None:
    """Addition B: the client's eta reaches the row; a missing torrent has none."""
    grabbed = [_wanted("aa11"), _wanted("bb22")]
    client = MagicMock()
    client.get_by_hashes.return_value = [
        TorrentItem(
            hash="aa11",
            name="d.mkv",
            size_bytes=1,
            progress=0.4,
            state="downloading",
            eta_seconds=720,
        ),
    ]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        resp = list_active_downloads(_config())

    by_hash = {d.info_hash: d for d in resp.downloads}
    assert by_hash["aa11"].eta_seconds == 720
    assert by_hash["bb22"].eta_seconds is None


_SCOPE = TorrentScope(category="tm-preprod", download_root=Path("/srv/preprod"))


def _in_category(item: TorrentItem, category: str | None) -> TorrentItem:
    """Return *item* filed under *category*."""
    return replace(item, category=category)


def _downloads_under(scope: TorrentScope | None, grabbed: list[WantedItem], held: list[TorrentItem]):
    """Run the downloads view over a client holding *held*."""
    client = MagicMock()
    client.get_by_hashes.side_effect = lambda hashes: [i for i in held if i.hash in hashes]
    with (
        patch(f"{_MOD}.build_acquire_store", return_value=_store(grabbed, [_follow_robot()])),
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
    ):
        return list_active_downloads(_config(scope))


def test_scoped_view_does_not_report_another_instances_torrent_as_ours() -> None:
    """Under a scope, a grabbed hash held in another category is not this instance's download."""
    grabbed = [_wanted("a" * 40), _wanted("b" * 40)]
    held = [
        _in_category(_titem("a" * 40, 0.5, "downloading"), "tm-preprod"),
        _in_category(_titem("b" * 40, 1.0, "uploading", name="Theirs.mkv"), "prod"),
    ]

    resp = _downloads_under(_SCOPE, grabbed, held)

    assert [d.info_hash for d in resp.downloads] == ["a" * 40]
    assert resp.client_available is True


def test_unscoped_view_reports_every_grabbed_torrent() -> None:
    """Without a scope the by-hash read keeps every torrent, whatever its category."""
    grabbed = [_wanted("a" * 40), _wanted("b" * 40)]
    held = [
        _in_category(_titem("a" * 40, 0.5, "downloading"), "tm-preprod"),
        _in_category(_titem("b" * 40, 1.0, "uploading"), "prod"),
    ]

    resp = _downloads_under(None, grabbed, held)

    assert {d.info_hash for d in resp.downloads} == {"a" * 40, "b" * 40}
    assert {d.state for d in resp.downloads} == {"downloading", "seeding"}
