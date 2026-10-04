"""The steps after a medium's folder goes: empty parents, index rows, Plex (K2-10)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.api.plex import PlexSection
from personalscraper.app.library.deletion import (
    PLEX_SCAN_WAIT_S,
    PlexOutcome,
    follow_up_plex,
    remove_empty_parents,
    remove_item_rows,
)
from tests.unit.app.library.world import FixtureIndex


class TestRemoveEmptyParents:
    """Parents left empty go, up to the library root, never the root itself."""

    def test_an_emptied_parent_is_removed_and_the_root_kept(self, tmp_path: Path) -> None:
        """The category folder the deletion emptied goes; the root stays, even empty."""
        root = tmp_path / "disk"
        folder = root / "films" / "Movie (2020)"
        folder.mkdir(parents=True)
        folder.rmdir()

        removed, survivor = remove_empty_parents(folder, root)

        assert (removed, survivor) == (1, root)
        assert not (root / "films").exists()
        assert root.is_dir()

    def test_a_parent_holding_something_else_stays(self, tmp_path: Path) -> None:
        """A parent still holding another medium is the survivor, untouched."""
        root = tmp_path / "disk"
        (root / "films" / "Other (2019)").mkdir(parents=True)
        folder = root / "films" / "Movie (2020)"

        removed, survivor = remove_empty_parents(folder, root)

        assert (removed, survivor) == (0, root / "films")
        assert (root / "films" / "Other (2019)").is_dir()

    def test_every_emptied_level_goes_up_to_the_root(self, tmp_path: Path) -> None:
        """Nested empty parents go, from the nearest up, and the walk stops at the root."""
        root = tmp_path / "disk"
        folder = root / "a" / "b" / "Movie"
        (root / "a" / "b").mkdir(parents=True)

        removed, survivor = remove_empty_parents(folder, root)

        assert (removed, survivor) == (2, root)
        assert root.is_dir()
        assert list(root.iterdir()) == []

    def test_never_climbs_outside_the_root(self, tmp_path: Path) -> None:
        """A folder outside the root removes nothing, whatever is empty around it."""
        root = tmp_path / "disk"
        root.mkdir()
        (tmp_path / "elsewhere").mkdir()

        removed, _ = remove_empty_parents(tmp_path / "elsewhere" / "Movie", root)

        assert removed == 0
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

        assert remove_item_rows(index.path, [doomed, doomed], actor="web:owner") == 1

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

        assert remove_item_rows(index.path, [999], actor="web:owner") == 0
        assert index.conn.execute("SELECT COUNT(*) FROM destructive_op").fetchone()[0] == 0
        index.conn.close()


class _FakePlex:
    """Records every Plex call; scan states are replayed per section."""

    def __init__(
        self,
        sections: dict[str, str],
        *,
        scans: dict[str, list[bool | None]] | None = None,
        refresh_ok: bool = True,
        trash_ok: bool = True,
        bundles_ok: bool = True,
    ) -> None:
        self._sections = sections
        self._scans = scans or {}
        self._refresh_ok = refresh_ok
        self._trash_ok = trash_ok
        self._bundles_ok = bundles_ok
        self.calls: list[tuple[str, str]] = []

    def section_for(self, target: Path) -> PlexSection | None:
        """The section whose root prefixes *target*."""
        for root, key in self._sections.items():
            if str(target) == root or str(target).startswith(f"{root}/"):
                return PlexSection(key, key, [root])
        return None

    def refresh(self, target: Path) -> bool:
        """Record the partial scan."""
        self.calls.append(("refresh", str(target)))
        return self._refresh_ok

    def section_refreshing(self, section_key: str) -> bool | None:
        """Replay the next scan state (idle once exhausted)."""
        self.calls.append(("scan_state", section_key))
        states = self._scans.get(section_key, [])
        return states.pop(0) if states else False

    def empty_trash(self, section_key: str) -> bool:
        """Record the trash emptying."""
        self.calls.append(("empty_trash", section_key))
        return self._trash_ok

    def clean_bundles(self) -> bool:
        """Record the bundle clean."""
        self.calls.append(("clean_bundles", ""))
        return self._bundles_ok


class _Time:
    """A fake monotonic clock that sleeping advances."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        """Advance the clock."""
        self.slept.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        """Read the clock."""
        return self.now


class TestFollowUpPlex:
    """Per section: rescan each parent, wait once, empty the trash; then one bundle clean."""

    def test_one_wait_and_one_trash_per_section_then_one_bundle_clean(self) -> None:
        """Two parents in one section and one in another: two rescans then one wait and one trash per section."""
        plex = _FakePlex({"/d1/films": "1", "/d2/series": "2"})
        t = _Time()
        parents = [Path("/d1/films"), Path("/d1/films/Sub"), Path("/d2/series")]

        steps = follow_up_plex(plex, parents, sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert plex.calls == [
            ("refresh", "/d1/films"),
            ("refresh", "/d1/films/Sub"),
            ("scan_state", "1"),
            ("empty_trash", "1"),
            ("refresh", "/d2/series"),
            ("scan_state", "2"),
            ("empty_trash", "2"),
            ("clean_bundles", ""),
        ]
        assert {p: s.outcome for p, s in steps.items()} == dict.fromkeys(parents, PlexOutcome.REFRESHED)
        assert steps[Path("/d1/films")].section == "1"

    def test_the_wait_polls_until_the_scan_ends(self) -> None:
        """A section still scanning is read again until idle, then its trash is emptied."""
        plex = _FakePlex({"/d1/films": "1"}, scans={"1": [True, True, False]})
        t = _Time()

        steps = follow_up_plex(plex, [Path("/d1/films")], sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert [c for c in plex.calls if c[0] == "scan_state"] == [("scan_state", "1")] * 3
        assert plex.calls[-2:] == [("empty_trash", "1"), ("clean_bundles", "")]
        assert steps[Path("/d1/films")].scan_ended is True

    def test_the_wait_is_bounded(self) -> None:
        """A scan that never ends stops the wait at the cap; the trash is still emptied, the outcome failed."""
        plex = _FakePlex({"/d1/films": "1"}, scans={"1": [True] * 1000})
        t = _Time()

        steps = follow_up_plex(plex, [Path("/d1/films")], sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert t.now <= PLEX_SCAN_WAIT_S
        assert ("empty_trash", "1") in plex.calls
        step = steps[Path("/d1/films")]
        assert (step.scan_ended, step.trash_emptied, step.outcome) == (False, True, PlexOutcome.FAILED)

    def test_an_unreadable_scan_state_ends_the_wait_as_failed(self) -> None:
        """Plex not answering the scan state: no endless wait, the step reported failed."""
        plex = _FakePlex({"/d1/films": "1"}, scans={"1": [None]})
        t = _Time()

        steps = follow_up_plex(plex, [Path("/d1/films")], sleep=t.sleep, clock=t.clock)  # type: ignore[arg-type]

        assert steps[Path("/d1/films")].scan_ended is False
        assert steps[Path("/d1/films")].outcome is PlexOutcome.FAILED

    @pytest.mark.parametrize(
        ("failing", "field"),
        [("refresh_ok", "refreshed"), ("trash_ok", "trash_emptied"), ("bundles_ok", "bundles_cleaned")],
    )
    def test_each_failed_step_is_reported(self, failing: str, field: str) -> None:
        """A refused rescan, trash or bundle clean shows on its own step, and the outcome is failed."""
        plex = _FakePlex({"/d1/films": "1"}, **{failing: False})  # type: ignore[arg-type]
        t = _Time()

        step = follow_up_plex(plex, [Path("/d1/films")], sleep=t.sleep, clock=t.clock)[Path("/d1/films")]  # type: ignore[arg-type]

        assert getattr(step, field) is False
        assert step.outcome is PlexOutcome.FAILED

    def test_a_folder_no_section_indexes_asks_nothing(self) -> None:
        """No section indexes the parent: no call at all, the step reported failed with no section."""
        plex = _FakePlex({"/d1/films": "1"})
        t = _Time()

        step = follow_up_plex(plex, [Path("/elsewhere")], sleep=t.sleep, clock=t.clock)[Path("/elsewhere")]  # type: ignore[arg-type]

        assert plex.calls == []
        assert step.section is None
        assert step.outcome is PlexOutcome.FAILED


def test_tombstone_snapshot_is_readable(tmp_path: Path) -> None:
    """The tombstone keeps the row's columns, so a deletion can be read back."""
    index = FixtureIndex(tmp_path / "library.db")
    doomed = index.item("Doomed", tmdb="2")

    remove_item_rows(index.path, [doomed], actor="web:owner")

    conn = sqlite3.connect(str(index.path))
    payload = conn.execute("SELECT payload_json FROM deleted_item").fetchone()[0]
    conn.close()
    assert '"title": "Doomed"' in payload
    index.conn.close()
