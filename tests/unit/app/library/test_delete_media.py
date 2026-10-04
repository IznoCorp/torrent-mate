"""Deletion by medium: a medium named by its provider id goes from the disks, the index and Plex (K2-10).

Temporary folders, a temporary index, a fake Plex and a fake deletion authority only.
"""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from personalscraper.acquire.catalogue import CatalogueStore, ProviderClients
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.errors import AppConflict, AppInternalError, AppNotFound, RefusalCode
from personalscraper.app.library.deletion import PlexOutcome
from personalscraper.app.library.service import LibraryService
from personalscraper.core.delete_permit import ALLOW, PermitDecision, veto
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.ownership import IndexerOwnershipChecker
from tests.unit.app.library.plex_fakes import FakePlex, FakeTime
from tests.unit.app.library.world import FixtureIndex


class _Permit:
    """A deletion authority vetoing the paths it is told to keep."""

    def __init__(self) -> None:
        """Keep nothing."""
        self.kept: set[Path] = set()
        self.asked: list[Path] = []

    def may_delete(self, path: Path) -> PermitDecision:
        """Veto a kept path, allow any other."""
        self.asked.append(path)
        return veto("seed obligation") if path in self.kept else ALLOW


@dataclass
class Shelf:
    """Everything one deletion test touches."""

    index: FixtureIndex
    service: LibraryService
    plex: FakePlex
    time: FakeTime
    permit: _Permit
    root: Path
    data_dir: Path
    actor: Actor
    mounts: set[Path]

    def movie(self, title: str, tmdb: str, *, folder: str | None = None, disk: int = 1) -> tuple[int, Path]:
        """A movie row with one file, its folder on disk holding the film and its artwork.

        Args:
            title: The row's title, and its folder's name when *folder* is absent.
            tmdb: Its TMDB id.
            folder: Its folder below the disk's root; ``films/<title>`` when absent.
            disk: The index disk holding it.

        Returns:
            The row id and the folder's path.
        """
        rel = folder or f"films/{title}"
        item = self.index.item(title, tmdb=tmdb)
        self.index.movie_file(item, rel, disk=disk)
        path = self.root / rel
        path.mkdir(parents=True, exist_ok=True)
        for name in ("movie.mkv", "poster.jpg", "fanart.jpg", "clearlogo.png", "movie.nfo"):
            (path / name).write_bytes(b"x")
        return item, path

    def rows(self) -> list[int]:
        """The ids of every ``media_item`` row."""
        return [r[0] for r in self.index.conn.execute("SELECT id FROM media_item ORDER BY id")]

    def journal(self) -> list[tuple[str, str, str]]:
        """Every ``destructive_op`` row: op, path, actor."""
        return self.index.conn.execute("SELECT op, path, actor FROM destructive_op ORDER BY id").fetchall()


@pytest.fixture
def shelf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Shelf]:
    """A service over a temporary index whose disk 1 is a temporary folder, with a fake Plex.

    The disk's temporary folder stands in for a mount point: ``os.path.ismount`` answers
    true for the folders of ``Shelf.mounts`` alone.

    Args:
        tmp_path: Pytest's temporary directory.
        monkeypatch: Pytest's patcher, faking the mount points.

    Yields:
        The shelf; its stores are closed after the test.
    """
    root = tmp_path / "disk1"
    root.mkdir()
    mounts = {root.resolve()}
    monkeypatch.setattr(os.path, "ismount", lambda path: Path(path) in mounts)
    index = FixtureIndex(tmp_path / "library.db")
    index.conn.execute("UPDATE disk SET mount_path = ? WHERE id = 1", (str(root),))
    index.conn.execute("UPDATE disk SET mount_path = NULL, is_mounted = 0 WHERE id = 2")
    store = CatalogueStore(tmp_path / "acquire.db")
    ownership = IndexerOwnershipChecker(index.path)
    plex = FakePlex({str(root): "1"})
    clock = FakeTime()
    permit = _Permit()
    service = LibraryService(
        index_db=index.path,
        data_dir=tmp_path,
        catalogue=store,
        ownership=ownership,
        providers=ProviderClients(tvdb=None, tmdb=None),
        plex=plex,  # type: ignore[arg-type]
        delete_permit=permit,
        sleep=clock.sleep,
        monotonic=clock.clock,
    )
    actor = Actor.system(InstanceCeiling(forbidden=frozenset(), read_only=False), account_id="owner", name="Owner")
    yield Shelf(index, service, plex, clock, permit, root, tmp_path, actor, mounts)
    service.close()
    ownership.close()
    store.close()
    index.conn.close()


def test_one_movie_goes_from_the_disk_the_index_and_plex(shelf: Shelf) -> None:
    """Folder and every artwork gone, one journal row with the actor, rows gone, Plex rescanned then cleaned."""
    item, folder = shelf.movie("Movie (2020)", "11")
    _, other = shelf.movie("Other (2019)", "12")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert not folder.exists()
    assert other.is_dir()
    assert shelf.rows() == [item + 1]
    assert shelf.journal() == [
        ("delete", str(folder), "web:owner"),
        ("delete", f"index:media_item/{item}", "web:owner"),
    ]
    assert shelf.plex.calls == [
        ("refresh", str(shelf.root / "films")),
        ("scan_state", "1"),
        ("empty_trash", "1"),
        ("clean_bundles", ""),
    ]
    assert report.deleted == 1
    [one] = report.media
    assert (one.folders_deleted, one.folders_vetoed, one.parents_removed, one.rows_removed) == (1, 0, 0, 1)
    assert one.plex is PlexOutcome.REFRESHED
    assert one.plex_steps is not None and one.plex_steps.section == "1"
    assert shelf.permit.asked == [folder]
    assert not (shelf.data_dir / "pipeline.lock").exists()


def test_the_emptied_parent_goes_and_the_library_root_stays(shelf: Shelf) -> None:
    """The last medium of a category: its category folder goes, the disk's root never; Plex rescans the root."""
    _, folder = shelf.movie("Movie (2020)", "11")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert not folder.parent.exists()
    assert shelf.root.is_dir()
    assert report.media[0].parents_removed == 1
    assert shelf.plex.calls[0] == ("refresh", str(shelf.root))


def test_a_show_folder_goes_whole(shelf: Shelf) -> None:
    """A show's media folder goes with its seasons, its episodes and its season posters."""
    item = shelf.index.item("Show", kind="show", tvdb="77")
    shelf.index.episodes(item, 1, [1, 2], folder="series/Show/Saison 01")
    season = shelf.root / "series" / "Show" / "Saison 01"
    season.mkdir(parents=True)
    (season / "s1e1.mkv").write_bytes(b"x")
    (shelf.root / "series" / "Show" / "season01-poster.jpg").write_bytes(b"x")
    (shelf.root / "series" / "Keep").mkdir()

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tvdb_id=77)])

    assert not (shelf.root / "series" / "Show").exists()
    assert (shelf.root / "series" / "Keep").is_dir()
    assert report.deleted == 1
    assert shelf.index.conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0] == 0


def test_a_vetoed_folder_is_kept_counted_and_not_deleted(shelf: Shelf) -> None:
    """The deletion authority keeps the folder: rows kept, Plex left alone, the medium not counted."""
    item, folder = shelf.movie("Movie (2020)", "11")
    shelf.permit.kept.add(folder)

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert (folder / "movie.mkv").is_file()
    assert shelf.rows() == [item]
    assert shelf.journal() == []
    assert shelf.plex.calls == []
    assert report.deleted == 0
    [one] = report.media
    assert (one.folders_deleted, one.folders_vetoed, one.rows_removed, one.plex) == (0, 1, 0, PlexOutcome.NOT_NEEDED)


@pytest.mark.parametrize("shape", ["two-rows", "two-folders"])
def test_an_ambiguous_id_touches_nothing(shelf: Shelf, shape: str) -> None:
    """Two rows, or one row in two folders, hold the id: 409 ``media.ambiguous`` naming it, nothing deleted."""
    item, folder = shelf.movie("Friends", "5")
    if shape == "two-rows":
        shelf.index.item("Friends [UNCUT]", tmdb="5")
    else:
        shelf.index.movie_file(item, "films/Friends [UNCUT]")

    with pytest.raises(AppConflict) as refused:
        shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=5)])

    assert refused.value.code is RefusalCode.MEDIA_AMBIGUOUS
    assert refused.value.params == {"provider": "tmdb", "providerId": "5"}
    assert (folder / "movie.mkv").is_file()
    assert len(shelf.rows()) == (2 if shape == "two-rows" else 1)
    assert shelf.journal() == []
    assert shelf.plex.calls == []
    assert not (shelf.data_dir / "pipeline.lock").exists()


def test_every_ref_is_checked_before_anything_goes(shelf: Shelf) -> None:
    """A valid medium then an unknown id: 404 ``media.not_found`` naming it, the valid one untouched."""
    item, folder = shelf.movie("Movie (2020)", "11")

    with pytest.raises(AppNotFound) as refused:
        shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11), MediaRef(tvdb_id=404)])

    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND
    assert refused.value.params == {"provider": "tvdb", "providerId": "404"}
    assert folder.is_dir()
    assert shelf.rows() == [item]
    assert shelf.journal() == []


def test_a_held_pipeline_lock_refuses_and_touches_nothing(shelf: Shelf) -> None:
    """A live run holds ``pipeline.lock``: 409 ``library.locked``, nothing deleted, the run's lock left in place."""
    item, folder = shelf.movie("Movie (2020)", "11")
    lock = shelf.data_dir / "pipeline.lock"
    lock.write_text(str(os.getpid()))

    with pytest.raises(AppConflict) as refused:
        shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert refused.value.code is RefusalCode.LIBRARY_LOCKED
    assert folder.is_dir()
    assert shelf.rows() == [item]
    assert lock.read_text() == str(os.getpid())


@pytest.mark.parametrize("down", ["refresh_ok", "trash_ok", "bundles_ok"])
def test_plex_down_leaves_the_files_gone_and_reports_failed(shelf: Shelf, down: str) -> None:
    """A Plex step fails: the files and rows are gone all the same, the medium deleted, its Plex outcome failed."""
    shelf.plex = FakePlex({str(shelf.root): "1"}, **{down: False})  # type: ignore[arg-type]
    shelf.service._plex = shelf.plex  # type: ignore[assignment]
    _, folder = shelf.movie("Movie (2020)", "11")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert not folder.exists()
    assert shelf.rows() == []
    assert report.deleted == 1
    assert report.media[0].plex is PlexOutcome.FAILED


def test_no_plex_configured_is_reported(shelf: Shelf) -> None:
    """No Plex server: the medium goes, its Plex outcome is « not configured »."""
    shelf.service._plex = None
    _, folder = shelf.movie("Movie (2020)", "11")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert not folder.exists()
    assert report.media[0].plex is PlexOutcome.NOT_CONFIGURED


def test_two_media_in_one_section_ask_plex_once(shelf: Shelf) -> None:
    """Two media of one section: one rescan of their shared parent, one wait, one trash, one bundle clean."""
    shelf.movie("A (2020)", "11")
    shelf.movie("B (2021)", "12")
    shelf.movie("C (2022)", "13")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11), MediaRef(tmdb_id=12)])

    assert report.deleted == 2
    assert shelf.plex.calls == [
        ("refresh", str(shelf.root / "films")),
        ("scan_state", "1"),
        ("empty_trash", "1"),
        ("clean_bundles", ""),
    ]


def test_a_folder_on_an_unmounted_disk_is_kept_and_counted(shelf: Shelf) -> None:
    """The index says the disk is not mounted: no refusal, the folder counted unreachable, the rows kept."""
    item = shelf.index.item("Away", tmdb="21")
    shelf.index.movie_file(item, "films/Away", disk=2)

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=21)])

    assert shelf.rows() == [item]
    assert report.deleted == 0
    assert (report.media[0].folders_unreachable, report.media[0].plex) == (1, PlexOutcome.NOT_NEEDED)


def test_a_row_without_files_goes_from_the_index(shelf: Shelf) -> None:
    """A row holding no live file: its row goes, Plex is not asked, the medium counted."""
    item = shelf.index.item("Phantom", tmdb="31")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=31)])

    assert shelf.rows() == []
    assert shelf.journal() == [("delete", f"index:media_item/{item}", "web:owner")]
    assert shelf.plex.calls == []
    assert report.deleted == 1


def test_a_medium_named_twice_is_deleted_once(shelf: Shelf) -> None:
    """The same id twice in one request: one deletion, one report."""
    shelf.movie("Movie (2020)", "11")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11), MediaRef(tmdb_id=11)])

    assert (report.deleted, len(report.media)) == (1, 1)


def test_a_folder_escaping_its_disk_is_never_deleted(shelf: Shelf, tmp_path: Path) -> None:
    """A media folder that is a symlink out of the disk: nothing outside is touched, the folder counted failed."""
    outside = tmp_path / "outside" / "precious"
    outside.mkdir(parents=True)
    (outside / "keep.txt").write_bytes(b"x")
    (shelf.root / "films").mkdir()
    (shelf.root / "films" / "Evil").symlink_to(outside, target_is_directory=True)
    item = shelf.index.item("Evil", tmdb="66")
    shelf.index.movie_file(item, "films/Evil")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=66)])

    assert (outside / "keep.txt").is_file()
    assert shelf.rows() == [item]
    assert (report.deleted, report.media[0].folders_failed) == (0, 1)


def test_under_staging_the_preprod_guard_refuses_a_folder_outside_its_roots(
    shelf: Shelf, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preprod's roots do not hold the folder: the guard refuses it, nothing is deleted, the folder counted failed."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    shelf.service._config = SimpleNamespace(  # type: ignore[assignment]
        disks=[SimpleNamespace(path=tmp_path / "preprod")],
        paths=SimpleNamespace(staging_dir=tmp_path / "preprod-staging"),
        torrent=SimpleNamespace(clients={}),
    )
    item, folder = shelf.movie("Movie (2020)", "11")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert (folder / "movie.mkv").is_file()
    assert shelf.rows() == [item]
    assert shelf.journal() == []
    assert (report.deleted, report.media[0].folders_failed) == (0, 1)


def test_no_deletion_authority_refuses_and_touches_nothing(shelf: Shelf) -> None:
    """No permit wired: the request is refused before the lock is taken; folder, rows and Plex untouched."""
    item, folder = shelf.movie("Movie (2020)", "11")
    service = LibraryService(
        index_db=shelf.index.path,
        data_dir=shelf.data_dir,
        catalogue=shelf.service._catalogue,
        ownership=shelf.service._ownership,
        providers=ProviderClients(tvdb=None, tmdb=None),
        plex=shelf.plex,  # type: ignore[arg-type]
    )

    with pytest.raises(AppInternalError) as refused:
        service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert refused.value.code is RefusalCode.INTERNAL
    assert (folder / "movie.mkv").is_file()
    assert shelf.rows() == [item]
    assert shelf.journal() == []
    assert shelf.plex.calls == []
    assert not (shelf.data_dir / "pipeline.lock").exists()


def test_one_row_named_by_two_ids_is_deleted_once(shelf: Shelf) -> None:
    """One show row named by its TVDB id and its TMDB id: one deletion, one report, the medium deleted."""
    item = shelf.index.item("Show", kind="show", tvdb="77", tmdb="11")
    shelf.index.episodes(item, 1, [1], folder="series/Show/Saison 01")
    folder = shelf.root / "series" / "Show"
    (folder / "Saison 01").mkdir(parents=True)

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tvdb_id=77), MediaRef(tmdb_id=11)])

    assert not folder.exists()
    assert shelf.rows() == []
    assert (report.deleted, len(report.media)) == (1, 1)
    assert report.media[0].ref == MediaRef(tvdb_id=77)


def test_another_rows_files_in_the_folder_refuse_and_touch_nothing(shelf: Shelf) -> None:
    """Another row holds live files in the medium's folder: 409 ``media.ambiguous``, nothing deleted."""
    item, folder = shelf.movie("Movie (2020)", "11")
    other = shelf.index.item("Movie (2020) [Extended]", tmdb="12")
    shelf.index.movie_file(other, "films/Movie (2020)/extended")

    with pytest.raises(AppConflict) as refused:
        shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert refused.value.code is RefusalCode.MEDIA_AMBIGUOUS
    assert refused.value.params == {"provider": "tmdb", "providerId": "11"}
    assert (folder / "movie.mkv").is_file()
    assert shelf.rows() == [item, other]
    assert shelf.journal() == []
    assert shelf.plex.calls == []
    assert not (shelf.data_dir / "pipeline.lock").exists()


def test_two_unicode_spellings_of_one_folder_delete_it_once(shelf: Shelf) -> None:
    """The index spells the folder NFC and NFD, the disk holds it once: deleted once, rows gone, medium deleted."""
    nfc = unicodedata.normalize("NFC", "Amélie (2001)")
    nfd = unicodedata.normalize("NFD", nfc)
    item, folder = shelf.movie(nfc, "11")
    if not (shelf.root / "films" / nfd).is_dir():
        pytest.skip("this filesystem tells NFC and NFD names apart: the two spellings are two folders")
    shelf.index.movie_file(item, f"films/{nfd}")

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=11)])

    assert not folder.exists()
    assert shelf.rows() == []
    assert report.deleted == 1
    [one] = report.media
    assert (one.folders_deleted, one.folders_failed, one.rows_removed) == (1, 0, 1)


def test_a_disk_root_that_is_no_mount_point_is_never_deleted_from(shelf: Shelf, tmp_path: Path) -> None:
    """The index says disk 2 is mounted, its root is a plain folder: the folder kept and failed, the rows kept."""
    plain = tmp_path / "disk2"
    folder = plain / "films" / "Away"
    folder.mkdir(parents=True)
    (folder / "movie.mkv").write_bytes(b"x")
    shelf.index.mount(2, plain)
    item = shelf.index.item("Away", tmdb="21")
    shelf.index.movie_file(item, "films/Away", disk=2)

    report = shelf.service.delete_media(shelf.actor, [MediaRef(tmdb_id=21)])

    assert (folder / "movie.mkv").is_file()
    assert shelf.rows() == [item]
    assert shelf.journal() == []
    assert shelf.plex.calls == []
    assert (report.deleted, report.media[0].folders_failed) == (0, 1)
