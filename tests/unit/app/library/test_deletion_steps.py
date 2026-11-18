"""The steps after a medium's folder goes: empty parents, index rows, Plex (K2-10)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.app.library.deletion import (
    PLEX_SCAN_WAIT_S,
    PlexOutcome,
    TrashKept,
    follow_up_plex,
    remove_empty_parents,
)
from personalscraper.indexer.deletion import remove_items
from tests.unit.app.library.plex_fakes import FakePlex, FakeTime
from tests.unit.app.library.world import FixtureIndex


class TestRemoveEmptyParents:
    """Parents left empty go, up to the library root, never the root itself."""

    def test_an_emptied_parent_is_removed_and_the_root_kept(self, tmp_path: Path) -> None:
        """The category folder the deletion emptied goes; the root stays, even empty."""
        root = tmp_path / "disk"
        folder = root / "films" / "Movie (2020)"
        folder.mkdir(parents=True)
        folder.rmdir()

        assert remove_empty_parents(folder, root) == (root / "films",)
        assert not (root / "films").exists()
        assert root.is_dir()

    def test_a_parent_holding_something_else_stays(self, tmp_path: Path) -> None:
        """A parent still holding another medium stays, untouched."""
        root = tmp_path / "disk"
        (root / "films" / "Other (2019)").mkdir(parents=True)
        folder = root / "films" / "Movie (2020)"

        assert remove_empty_parents(folder, root) == ()
        assert (root / "films" / "Other (2019)").is_dir()

    def test_every_emptied_level_goes_up_to_the_root(self, tmp_path: Path) -> None:
        """Nested empty parents go, from the nearest up, and the walk stops at the root."""
        root = tmp_path / "disk"
        folder = root / "a" / "b" / "Movie"
        (root / "a" / "b").mkdir(parents=True)

        assert remove_empty_parents(folder, root) == (root / "a" / "b", root / "a")
        assert root.is_dir()
        assert list(root.iterdir()) == []

    def test_never_climbs_outside_the_root(self, tmp_path: Path) -> None:
        """A folder outside the root removes nothing, whatever is empty around it."""
        root = tmp_path / "disk"
        root.mkdir()
        (tmp_path / "elsewhere").mkdir()

        assert remove_empty_parents(tmp_path / "elsewhere" / "Movie", root) == ()
        assert (tmp_path / "elsewhere").is_dir()


class TestRemoveItemRows:
    """Index rows go with their cascade, a tombstone each, and a journal row each."""

    def test_rows_files_tombstone_and_journal(self, tmp_path: Path) -> None:
        """The row, its release and file go; a tombstone and a journal row name it with the actor."""
        index = FixtureIndex(tmp_path / "library.db")
        kept = index.item("Kept", tmdb="1")
        doomed = index.item("Doomed", tmdb="2")
        index.movie_file(doomed, "films/Doomed")
        index.movie_file(kept, "films/Kept")

        assert remove_items(index.path, [doomed, doomed], actor="web:owner", reason="media_deleted") == 1

        conn = index.conn
        assert [r[0] for r in conn.execute("SELECT id FROM media_item")] == [kept]
        assert conn.execute("SELECT COUNT(*) FROM media_release").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0] == 1
        assert conn.execute("SELECT original_id, reason FROM deleted_item").fetchall() == [(doomed, "media_deleted")]
        assert conn.execute("SELECT op, path, actor FROM destructive_op").fetchall() == [
            ("delete", f"index:media_item/{doomed}", "web:owner")
        ]
        index.conn.close()

    def test_a_row_already_gone_is_not_counted(self, tmp_path: Path) -> None:
        """An id no row holds any more removes nothing and journals nothing."""
        index = FixtureIndex(tmp_path / "library.db")

        assert remove_items(index.path, [999], actor="web:owner", reason="media_deleted") == 0
        assert index.conn.execute("SELECT COUNT(*) FROM destructive_op").fetchone()[0] == 0
        index.conn.close()


class TestFollowUpPlex:
    """Per section: rescan where each deleted folder stood, wait once, empty the trash; then one bundle clean."""

    @staticmethod
    def _disk(tmp_path: Path) -> tuple[Path, Path, Path]:
        """Two section locations on a disk, each still holding a medium.

        Returns:
            ``(films location, series location, the disk)``.
        """
        disk = tmp_path / "d1"
        (disk / "films" / "Kept").mkdir(parents=True)
        (disk / "series" / "Kept").mkdir(parents=True)
        return disk / "films", disk / "series", disk

    def test_one_wait_and_one_trash_per_section_then_one_bundle_clean(self, tmp_path: Path) -> None:
        """Two folders of one section and one of another: one rescan per refresh path, one wait and trash each."""
        films, series, _ = self._disk(tmp_path)
        (films / "Sub" / "Kept").mkdir(parents=True)
        plex = FakePlex({str(films): "1", str(series): "2"})
        t = FakeTime()
        deleted = [films / "A", films / "Sub" / "B", series / "C"]

        steps = follow_up_plex(plex, deleted, sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert plex.calls == [
            ("refresh", str(films)),
            ("refresh", str(films / "Sub")),
            ("scan_state", "1"),
            ("empty_trash", "1"),
            ("refresh", str(series)),
            ("scan_state", "2"),
            ("empty_trash", "2"),
            ("clean_bundles", ""),
        ]
        assert {p: s.outcome for p, s in steps.items()} == dict.fromkeys(deleted, PlexOutcome.REFRESHED)
        assert steps[films / "A"].section == "1"

    def test_the_wait_polls_until_the_scan_ends(self, tmp_path: Path) -> None:
        """A section still scanning is read again until idle, then its trash is emptied."""
        films, _, _ = self._disk(tmp_path)
        plex = FakePlex({str(films): "1"}, scans={"1": [True, True, False]})
        t = FakeTime()

        steps = follow_up_plex(plex, [films / "A"], sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert [c for c in plex.calls if c[0] == "scan_state"] == [("scan_state", "1")] * 3
        assert plex.calls[-2:] == [("empty_trash", "1"), ("clean_bundles", "")]
        assert steps[films / "A"].scan_ended is True

    def test_the_wait_is_bounded(self, tmp_path: Path) -> None:
        """A scan that never ends stops the wait at the cap; the trash is still emptied, the outcome failed."""
        films, _, _ = self._disk(tmp_path)
        plex = FakePlex({str(films): "1"}, scans={"1": [True] * 1000})
        t = FakeTime()

        steps = follow_up_plex(plex, [films / "A"], sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert t.now <= PLEX_SCAN_WAIT_S
        assert ("empty_trash", "1") in plex.calls
        step = steps[films / "A"]
        assert (step.scan_ended, step.trash_emptied, step.outcome) == (False, True, PlexOutcome.FAILED)

    def test_an_unreadable_scan_state_ends_the_wait_as_failed(self, tmp_path: Path) -> None:
        """Plex not answering the scan state: no endless wait, the step reported failed."""
        films, _, _ = self._disk(tmp_path)
        plex = FakePlex({str(films): "1"}, scans={"1": [None]})
        t = FakeTime()

        steps = follow_up_plex(plex, [films / "A"], sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert steps[films / "A"].scan_ended is False
        assert steps[films / "A"].outcome is PlexOutcome.FAILED

    @pytest.mark.parametrize(
        ("failing", "field"),
        [("refresh_ok", "refreshed"), ("trash_ok", "trash_emptied"), ("bundles_ok", "bundles_cleaned")],
    )
    def test_each_failed_step_is_reported(self, tmp_path: Path, failing: str, field: str) -> None:
        """A refused rescan, trash or bundle clean shows on its own step, and the outcome is failed."""
        films, _, _ = self._disk(tmp_path)
        plex = FakePlex({str(films): "1"}, **{failing: False})  # type: ignore[arg-type]
        t = FakeTime()

        step = follow_up_plex(plex, [films / "A"], sleep=t.sleep, clock=t.clock)[films / "A"]  # type: ignore[arg-type]

        assert getattr(step, field) is False
        assert step.outcome is PlexOutcome.FAILED

    def test_a_folder_no_section_indexes_asks_nothing(self, tmp_path: Path) -> None:
        """No section indexes the deleted folder: no call at all, the step reported failed with no section."""
        films, _, disk = self._disk(tmp_path)
        plex = FakePlex({str(films): "1"})
        t = FakeTime()

        step = follow_up_plex(plex, [disk / "elsewhere" / "A"], sleep=t.sleep, clock=t.clock)[disk / "elsewhere" / "A"]  # type: ignore[arg-type]

        assert plex.calls == []
        assert step.section is None
        assert step.outcome is PlexOutcome.FAILED

    def test_a_location_the_request_removed_is_rescanned_and_its_trash_emptied(self, tmp_path: Path) -> None:
        """The deletion emptied and removed the section's location: the location rescanned, the trash emptied."""
        films, _, _ = self._disk(tmp_path)
        (films / "Kept").rmdir()
        films.rmdir()
        plex = FakePlex({str(films): "1"})
        t = FakeTime()

        step = follow_up_plex(plex, [films / "A"], removed={films}, sleep=t.sleep, clock=t.clock)[films / "A"]  # type: ignore[arg-type]

        assert plex.calls == [("refresh", str(films)), ("scan_state", "1"), ("empty_trash", "1"), ("clean_bundles", "")]
        assert (step.trash_kept, step.outcome) == (None, PlexOutcome.REFRESHED)


class TestTrashKept:
    """A section's trash is kept while a disk it may index is not there: emptying it would purge that disk's items."""

    def test_a_location_missing_before_the_request_keeps_the_trash(self, tmp_path: Path) -> None:
        """One of the section's locations is no directory (its disk is gone): no emptyTrash, the reason named."""
        films, _, disk = TestFollowUpPlex._disk(tmp_path)
        plex = FakePlex({str(films): "1"})
        plex.extra_locations["1"] = [str(disk.parent / "d2" / "films")]
        t = FakeTime()

        step = follow_up_plex(plex, [films / "A"], sleep=t.sleep, clock=t.clock)[films / "A"]  # type: ignore[arg-type]

        assert ("empty_trash", "1") not in plex.calls
        assert plex.calls == [("refresh", str(films)), ("scan_state", "1"), ("clean_bundles", "")]
        assert (step.trash_emptied, step.trash_kept) == (False, TrashKept.LOCATION_MISSING)
        assert step.outcome is PlexOutcome.TRASH_KEPT

    def test_every_location_present_empties_the_trash(self, tmp_path: Path) -> None:
        """Every location of the section stands: the trash is emptied as before."""
        films, _, disk = TestFollowUpPlex._disk(tmp_path)
        (disk.parent / "d2" / "films").mkdir(parents=True)
        plex = FakePlex({str(films): "1"})
        plex.extra_locations["1"] = [str(disk.parent / "d2" / "films")]
        t = FakeTime()

        step = follow_up_plex(plex, [films / "A"], sleep=t.sleep, clock=t.clock)[films / "A"]  # type: ignore[arg-type]

        assert ("empty_trash", "1") in plex.calls
        assert (step.trash_emptied, step.trash_kept, step.outcome) == (True, None, PlexOutcome.REFRESHED)

    def test_a_disk_the_index_knows_unmounted_keeps_the_trash(self, tmp_path: Path) -> None:
        """Every location stands but a disk is unmounted: no emptyTrash, the reason named."""
        films, _, _ = TestFollowUpPlex._disk(tmp_path)
        plex = FakePlex({str(films): "1"})
        t = FakeTime()

        step = follow_up_plex(plex, [films / "A"], disk_unmounted=True, sleep=t.sleep, clock=t.clock)[films / "A"]  # type: ignore[arg-type]

        assert ("empty_trash", "1") not in plex.calls
        assert step.trash_kept is TrashKept.DISK_UNMOUNTED


def test_tombstone_snapshot_is_readable(tmp_path: Path) -> None:
    """The tombstone keeps the row's columns, so a deletion can be read back."""
    index = FixtureIndex(tmp_path / "library.db")
    doomed = index.item("Doomed", tmdb="2")

    remove_items(index.path, [doomed], actor="web:owner", reason="media_deleted")

    conn = sqlite3.connect(str(index.path))
    payload = conn.execute("SELECT payload_json FROM deleted_item").fetchone()[0]
    conn.close()
    assert '"title": "Doomed"' in payload
    index.conn.close()
