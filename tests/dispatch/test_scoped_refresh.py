"""``run_scoped_refresh``: a targeted refresh touches only the given subtrees.

Every test builds its library in ``tmp_path`` and drives the real scanner visitor, the
real linker and the real repair drain over a migrated indexer database.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.dispatch.post_maintenance import (
    ScopedRefreshIncomplete,
    _run_fix_season_counts,
    _run_relink,
    _run_repair_drain,
    _Scope,
    run_scoped_refresh,
)
from tests.commands._e2e_helpers import make_synthetic_db, make_test_config_with_db, seed_disk

_NTFS_QMARK = ""


@pytest.fixture
def library(tmp_path: Path, test_config):
    """A migrated indexer DB plus a config whose first disk is rooted in ``tmp_path``."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    disk = cfg.disks[0]
    mount = Path(disk.path)
    mount.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    disk_id = seed_disk(conn, disk.id, mount)
    conn.close()
    return cfg, disk.id, disk_id, mount, db_path


def _make_show(mount: Path, name: str, episodes: list[str]) -> Path:
    show = mount / "series" / name / "Season 01"
    show.mkdir(parents=True, exist_ok=True)
    for ep in episodes:
        (show / ep).write_bytes(b"x" * 2048)
    return mount / "series" / name


def _rows(db_path: Path, like: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT p.rel_path, mf.filename, mf.size_bytes, mf.mtime_ns, mf.scan_generation, mf.miss_strikes, "
            "mf.deleted_at FROM media_file mf JOIN path p ON p.id = mf.path_id "
            "WHERE p.rel_path LIKE ? ORDER BY 1, 2",
            (like,),
        ).fetchall()
    finally:
        conn.close()


def _path_rows(db_path: Path, like: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT rel_path, dir_mtime_ns, last_walked_at FROM path WHERE rel_path LIKE ? ORDER BY 1", (like,)
        ).fetchall()
    finally:
        conn.close()


def test_refresh_touches_only_the_given_path(library) -> None:
    """A second show on the same disk keeps every row; only the given show is rescanned."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    show_b = _make_show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show_a, show_b])
    b_files_before = _rows(db_path, "series/Show B%")
    b_paths_before = _path_rows(db_path, "series/Show B%")
    assert b_files_before

    (show_a / "Season 01" / "Show.A.S01E02.mkv").write_bytes(b"y" * 4096)
    (show_b / "Season 01" / "Show.B.S01E02.mkv").write_bytes(b"y" * 4096)
    run_scoped_refresh(cfg, label, [show_a])

    assert {r[1] for r in _rows(db_path, "series/Show A%")} == {"Show.A.S01E01.mkv", "Show.A.S01E02.mkv"}
    assert _rows(db_path, "series/Show B%") == b_files_before
    assert _path_rows(db_path, "series/Show B%") == b_paths_before


def test_refresh_does_not_walk_the_rest_of_the_disk(library, monkeypatch) -> None:
    """The scan visits only files under the given path (no whole-disk incremental)."""
    cfg, label, _disk_id, mount, _db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    _make_show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    seen: list[str] = []
    from personalscraper.indexer.scanner._modes import incremental

    original = incremental.IncrementalVisitor.visit_file

    def spy(self, entry, st, parent_rel):
        seen.append(entry.path)
        return original(self, entry, st, parent_rel)

    monkeypatch.setattr(incremental.IncrementalVisitor, "visit_file", spy)
    run_scoped_refresh(cfg, label, [show_a])

    assert seen
    assert all(p.startswith(str(show_a)) for p in seen)


def test_deleted_path_is_removed_from_the_index(library) -> None:
    """A path gone from the disk has its live files soft-deleted with a tombstone; others are untouched."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv", "Show.A.S01E02.mkv"])
    show_b = _make_show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show_a, show_b])
    b_before = _rows(db_path, "series/Show B%")

    for f in (show_a / "Season 01").iterdir():
        f.unlink()
    (show_a / "Season 01").rmdir()
    show_a.rmdir()
    report = run_scoped_refresh(cfg, label, [show_a])

    assert report.files_removed == 2
    assert all(r[6] is not None for r in _rows(db_path, "series/Show A%"))
    assert _rows(db_path, "series/Show B%") == b_before
    conn = sqlite3.connect(db_path)
    reasons = {r[0] for r in conn.execute("SELECT reason FROM deleted_item WHERE kind = 'file'")}
    conn.close()
    assert reasons == {"refresh_path"}


def test_dry_run_writes_nothing(library) -> None:
    """--dry-run reports the removal and leaves the database byte-identical."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show_a])
    (show_a / "Season 01" / "Show.A.S01E01.mkv").unlink()
    (show_a / "Season 01").rmdir()
    show_a.rmdir()
    new_show = _make_show(mount, "Show C (2022)", ["Show.C.S01E01.mkv"])
    before = _dump(db_path)

    report = run_scoped_refresh(cfg, label, [show_a, new_show], dry_run=True)

    assert report.files_removed == 1
    assert report.removed == [show_a]
    assert report.scanned == [new_show]
    assert _dump(db_path) == before


def test_question_mark_path_finds_its_private_use_twin_on_disk(library) -> None:
    """A path typed with « ? » that exists on disk as U+F025 is refreshed, not treated as deleted."""
    cfg, label, _disk_id, mount, db_path = library
    real = _make_show(mount, f"What Is It{_NTFS_QMARK} (2020)", ["What.S01E01.mkv"])
    typed = mount / "series" / "What Is It? (2020)"

    report = run_scoped_refresh(cfg, label, [typed])

    assert report.scanned == [real]
    assert report.files_removed == 0
    assert [r[6] for r in _rows(db_path, "series/What%")] == [None]


def test_deleted_path_typed_with_question_mark_matches_rows_stored_with_private_use(library) -> None:
    """Rows stored under U+F025 are removed when the vanished path is typed with « ? »."""
    cfg, label, _disk_id, mount, db_path = library
    real = _make_show(mount, f"What Is It{_NTFS_QMARK} (2020)", ["What.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [real])
    (real / "Season 01" / "What.S01E01.mkv").unlink()
    (real / "Season 01").rmdir()
    real.rmdir()

    report = run_scoped_refresh(cfg, label, [mount / "series" / "What Is It? (2020)"])

    assert report.files_removed == 1


def test_path_outside_the_disk_is_refused(library) -> None:
    """A path that is not under the disk's mount raises instead of touching anything."""
    cfg, label, _disk_id, _mount, _db_path = library
    with pytest.raises(ValueError, match="not under"):
        run_scoped_refresh(cfg, label, [Path("/nowhere/at/all")])


# ---------------------------------------------------------------------------
# The DB-only passes, scoped
# ---------------------------------------------------------------------------


def _seed_two_movies(db_path: Path, mount: Path) -> None:
    """Two unlinked movie files, each with an item + release findable by dispatch_path."""
    conn = sqlite3.connect(db_path)
    disk_id = conn.execute("SELECT id FROM disk").fetchone()[0]
    for n, title in enumerate(("Movie A", "Movie B"), start=1):
        folder = mount / "movies" / f"{title} (2020)"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{title.replace(' ', '.')}.2020.1080p.mkv").write_bytes(b"x" * 100)
        conn.execute(
            "INSERT INTO media_item (id, kind, title, title_sort, year, category_id, date_created, date_modified,"
            " preferred_lang) VALUES (?, 'movie', ?, ?, 2020, 'movies', 1, 1, 'fr')",
            (n, title, title),
        )
        conn.execute("INSERT INTO media_release (id, item_id) VALUES (?, ?)", (n, n))
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)", (n, str(folder))
        )
        cur = conn.execute(
            "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)", (disk_id, f"movies/{title} (2020)")
        )
        conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, scan_generation,"
            " last_verified_at) VALUES (NULL, ?, ?, 100, 1, 1, 1)",
            (cur.lastrowid, f"{title.replace(' ', '.')}.2020.1080p.mkv"),
        )
    conn.commit()
    conn.close()


def _scope_for(db_path: Path, mount: Path, rel: str) -> _Scope:
    conn = sqlite3.connect(db_path)
    disk_id = conn.execute("SELECT id FROM disk").fetchone()[0]
    conn.close()
    return _Scope(disk_id=disk_id, mount=str(mount), rel_variants=frozenset({rel}))


def test_relink_is_restricted_to_the_scope(library) -> None:
    """Only the scoped folder's unlinked files are linked; the other stays unlinked."""
    cfg, _label, _disk_id, mount, db_path = library
    _seed_two_movies(db_path, mount)

    counts = _run_relink(cfg, scopes=[_scope_for(db_path, mount, "movies/Movie A (2020)")])

    conn = sqlite3.connect(db_path)
    linked = dict(conn.execute("SELECT p.rel_path, mf.release_id FROM media_file mf JOIN path p ON p.id = mf.path_id"))
    conn.close()
    assert counts["linked"] == 1
    assert linked["movies/Movie A (2020)"] is not None
    assert linked["movies/Movie B (2020)"] is None


def test_fix_season_counts_is_restricted_to_the_scope(library) -> None:
    """Only the seasons of items living under the scope are corrected."""
    cfg, _label, _disk_id, mount, db_path = library
    conn = sqlite3.connect(db_path)
    for n, title in enumerate(("Show A", "Show B"), start=1):
        folder = mount / "series" / title
        conn.execute(
            "INSERT INTO media_item (id, kind, title, title_sort, year, category_id, date_created, date_modified,"
            " preferred_lang) VALUES (?, 'show', ?, ?, 2020, 'tv_shows', 1, 1, 'fr')",
            (n, title, title),
        )
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)", (n, str(folder))
        )
        conn.execute("INSERT INTO season (id, item_id, number) VALUES (?, ?, 1)", (n, n))
        conn.execute("INSERT INTO episode (season_id, number) VALUES (?, 1)", (n,))
    # The episode triggers keep the counts right; drift is forced afterwards.
    conn.execute("UPDATE season SET episode_count = 99")
    conn.commit()
    conn.close()

    fixed = _run_fix_season_counts(cfg, scopes=[_scope_for(db_path, mount, "series/Show A")])

    conn = sqlite3.connect(db_path)
    counts = dict(conn.execute("SELECT item_id, episode_count FROM season"))
    conn.close()
    assert fixed == 1
    assert counts == {1: 1, 2: 99}


def test_repair_drain_is_restricted_to_the_scope(library) -> None:
    """Pending repairs of files outside the scope stay pending."""
    cfg, _label, _disk_id, mount, db_path = library
    _seed_two_movies(db_path, mount)
    conn = sqlite3.connect(db_path)
    ids = {
        rel: fid
        for rel, fid in conn.execute("SELECT p.rel_path, mf.id FROM media_file mf JOIN path p ON p.id = mf.path_id")
    }
    for fid in ids.values():
        conn.execute(
            "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at, status)"
            " VALUES ('file', ?, 'noop', 1, 'pending')",
            (fid,),
        )
    conn.commit()
    conn.close()

    processed = _run_repair_drain(cfg, scopes=[_scope_for(db_path, mount, "movies/Movie A (2020)")])

    conn = sqlite3.connect(db_path)
    status = dict(conn.execute("SELECT scope_id, status FROM repair_queue"))
    conn.close()
    assert processed == 1
    assert status[ids["movies/Movie A (2020)"]] == "done"
    assert status[ids["movies/Movie B (2020)"]] == "pending"


# ---------------------------------------------------------------------------
# The mount guard
# ---------------------------------------------------------------------------


def _dump(db_path: Path) -> list[str]:
    """The whole database as SQL statements: equal dumps mean nothing was written."""
    conn = sqlite3.connect(db_path)
    try:
        return list(conn.iterdump())
    finally:
        conn.close()


def _indexed_show(library, name: str = "Show A (2020)") -> Path:
    """Index one show (plus a sibling, so the disk holds more than one folder) and return it."""
    cfg, label, _disk_id, mount, _db_path = library
    show = _make_show(mount, name, ["Show.A.S01E01.mkv"])
    other = _make_show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show, other])
    return show


def test_unmounted_disk_root_refuses_to_remove_a_path(library) -> None:
    """A mount root that is empty (disk not mounted) must not retire the subtree: nothing is written."""
    cfg, label, _disk_id, mount, db_path = library
    show = _indexed_show(library)
    shutil.rmtree(mount / "series")
    assert not any(mount.iterdir())
    before = _dump(db_path)

    with pytest.raises(ValueError, match="empty or missing"):
        run_scoped_refresh(cfg, label, [show])

    assert _dump(db_path) == before


def test_missing_disk_root_refuses_to_remove_a_path(library) -> None:
    """A mount root that is gone altogether is refused the same way."""
    cfg, label, _disk_id, mount, db_path = library
    show = _indexed_show(library)
    shutil.rmtree(mount)
    before = _dump(db_path)

    with pytest.raises(ValueError, match="empty or missing"):
        run_scoped_refresh(cfg, label, [show])

    assert _dump(db_path) == before


def test_vanished_path_whose_parent_is_gone_is_refused(library) -> None:
    """The mount is populated but the vanished path's parent folder is gone too: refused, nothing written."""
    cfg, label, _disk_id, mount, db_path = library
    show = _indexed_show(library)
    shutil.rmtree(mount / "series")
    (mount / "elsewhere").mkdir()
    (mount / "elsewhere" / "file.bin").write_bytes(b"x")
    before = _dump(db_path)

    with pytest.raises(ValueError, match="parent"):
        run_scoped_refresh(cfg, label, [show])

    assert _dump(db_path) == before


def test_dry_run_is_refused_by_the_same_guard(library) -> None:
    """A preview must not announce a removal the real run would refuse."""
    cfg, label, _disk_id, mount, _db_path = library
    show = _indexed_show(library)
    shutil.rmtree(mount / "series")

    with pytest.raises(ValueError, match="empty or missing"):
        run_scoped_refresh(cfg, label, [show], dry_run=True)


# ---------------------------------------------------------------------------
# Files that vanished inside a path that still exists
# ---------------------------------------------------------------------------


def test_file_gone_from_a_refreshed_path_is_soft_deleted(library) -> None:
    """A file the walk no longer sees under an existing path is tombstoned; its siblings and other shows are not."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv", "Show.A.S01E02.mkv"])
    show_b = _make_show(mount, "Show B (2021)", ["Show.B.S01E01.mkv", "Show.B.S01E02.mkv"])
    run_scoped_refresh(cfg, label, [show_a, show_b])
    b_before = _rows(db_path, "series/Show B%")
    (show_a / "Season 01" / "Show.A.S01E02.mkv").unlink()
    (show_b / "Season 01" / "Show.B.S01E02.mkv").unlink()

    report = run_scoped_refresh(cfg, label, [show_a])

    assert report.files_removed == 1
    deleted = {r[1]: r[6] for r in _rows(db_path, "series/Show A%")}
    assert deleted["Show.A.S01E01.mkv"] is None
    assert deleted["Show.A.S01E02.mkv"] is not None
    assert _rows(db_path, "series/Show B%") == b_before
    conn = sqlite3.connect(db_path)
    tombstones = conn.execute("SELECT reason FROM deleted_item WHERE kind = 'file'").fetchall()
    conn.close()
    assert tombstones == [("refresh_path",)]


def test_dry_run_counts_the_files_gone_from_a_refreshed_path(library) -> None:
    """The preview reports the same removal and writes nothing."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv", "Show.A.S01E02.mkv"])
    run_scoped_refresh(cfg, label, [show_a])
    (show_a / "Season 01" / "Show.A.S01E02.mkv").unlink()
    before = _dump(db_path)

    report = run_scoped_refresh(cfg, label, [show_a], dry_run=True)

    assert report.files_removed == 1
    assert _dump(db_path) == before


# ---------------------------------------------------------------------------
# A walk that did not finish
# ---------------------------------------------------------------------------


def test_stopped_walk_rolls_back_and_is_reported(library, monkeypatch) -> None:
    """A shutdown request mid-walk must not commit a half-seen subtree as a success."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv", "Show.A.S01E02.mkv"])
    run_scoped_refresh(cfg, label, [show_a])
    (show_a / "Season 01" / "Show.A.S01E03.mkv").write_bytes(b"z" * 512)
    before = _dump(db_path)
    monkeypatch.setattr("personalscraper.indexer.scanner._shutdown.is_shutdown_requested", lambda: True)

    with pytest.raises(ScopedRefreshIncomplete, match="did not finish"):
        run_scoped_refresh(cfg, label, [show_a])

    assert _dump(db_path) == before


@pytest.mark.parametrize(
    ("failing", "event", "step"),
    [
        ("_run_relink", "scoped_refresh_relink_exception", "relink"),
        ("_run_fix_season_counts", "scoped_refresh_fix_season_counts_exception", "fix-season-counts"),
        ("_run_repair_drain", "scoped_refresh_repair_drain_exception", "repair-drain"),
    ],
)
def test_failed_pass_is_logged_with_its_traceback(library, monkeypatch, failing, event, step) -> None:
    """A DB-only pass that raises lands in ``failed_steps`` and is logged with ``exc_info``."""
    cfg, label, _disk_id, mount, _db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])

    def boom(*args, **kwargs):
        raise RuntimeError("pass failed")

    monkeypatch.setattr(f"personalscraper.dispatch.post_maintenance.{failing}", boom)
    with patch("personalscraper.dispatch.post_maintenance._log") as fake_log:
        report = run_scoped_refresh(cfg, label, [show_a])

    assert report.failed_steps == [step]
    calls = [c for c in fake_log.warning.call_args_list if c.args[0] == event]
    assert len(calls) == 1
    assert calls[0].kwargs.get("exc_info") is True


# ---------------------------------------------------------------------------
# Edge inputs: a file, a path typed in another case
# ---------------------------------------------------------------------------


def test_a_file_given_as_path_is_refused(library) -> None:
    """A file is not a media folder: a clear error, not a raw NotADirectoryError inside the transaction."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show_a])
    before = _dump(db_path)

    with pytest.raises(ValueError, match="not a folder"):
        run_scoped_refresh(cfg, label, [show_a / "Season 01" / "Show.A.S01E01.mkv"])

    assert _dump(db_path) == before


def _stored_rel_paths(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute("SELECT rel_path FROM path")}
    finally:
        conn.close()


def test_path_typed_in_another_case_is_resolved_to_the_stored_spelling(library) -> None:
    """The filesystem ignores case, the index does not: the typed spelling must not create or hide rows."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show_a])
    paths_before = _stored_rel_paths(db_path)
    files_before = _rows(db_path, "%")

    report = run_scoped_refresh(cfg, label, [mount / "series" / "show a (2020)"])

    assert report.removed == []
    assert report.scanned == [show_a]
    assert report.files_removed == 0
    assert _stored_rel_paths(db_path) == paths_before
    assert [r[:2] + r[6:] for r in _rows(db_path, "%")] == [r[:2] + r[6:] for r in files_before]


def test_vanished_path_typed_in_another_case_removes_the_stored_rows(library) -> None:
    """A deleted folder typed with another case still retires the rows stored under its real spelling."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv", "Show.A.S01E02.mkv"])
    show_b = _make_show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show_a, show_b])
    shutil.rmtree(show_a)

    report = run_scoped_refresh(cfg, label, [mount / "series" / "SHOW A (2020)"])

    assert report.files_removed == 2
    assert all(r[6] is not None for r in _rows(db_path, "series/Show A%"))
    assert all(r[6] is None for r in _rows(db_path, "series/Show B%"))


# ---------------------------------------------------------------------------
# Scenarios the help text announces, and the prefix / strike / unknown-path edges
# ---------------------------------------------------------------------------


def _distinct_show(mount: Path, name: str, episodes: list[str], salt: int = 0) -> Path:
    """A show whose files differ in size and content, so each has its own OSHash (rename detection)."""
    season = mount / "series" / name / "Season 01"
    season.mkdir(parents=True, exist_ok=True)
    for n, ep in enumerate(episodes, start=1):
        (season / ep).write_bytes(bytes([n + salt]) * (70_000 + n * 1_000 + salt))
    return mount / "series" / name


def _file_ids(db_path: Path, like: str) -> dict[str, tuple[int, int | None]]:
    """``rel_path/filename -> (media_file.id, deleted_at)`` for the paths matching *like*."""
    conn = sqlite3.connect(db_path)
    try:
        return {
            f"{rel}/{name}": (fid, deleted)
            for rel, name, fid, deleted in conn.execute(
                "SELECT p.rel_path, mf.filename, mf.id, mf.deleted_at FROM media_file mf "
                "JOIN path p ON p.id = mf.path_id WHERE p.rel_path LIKE ?",
                (like,),
            )
        }
    finally:
        conn.close()


@pytest.mark.parametrize("new_first", [True, False])
def test_rename_given_as_new_and_old_keeps_the_file_rows(library, new_first) -> None:
    """Both paths given, new existing, old gone: the rows follow the files, whatever the order given."""
    cfg, label, _disk_id, mount, db_path = library
    old = _distinct_show(mount, "Old Name (2020)", ["E01.mkv", "E02.mkv"])
    _distinct_show(mount, "Other (2021)", ["E01.mkv"], salt=50)
    run_scoped_refresh(cfg, label, [old, mount / "series" / "Other (2021)"])
    ids_before = {name.rsplit("/", 1)[1]: fid for name, (fid, _) in _file_ids(db_path, "series/Old Name%").items()}
    assert len(ids_before) == 2
    new = mount / "series" / "New Name (2020)"
    old.rename(new)

    run_scoped_refresh(cfg, label, [new, old] if new_first else [old, new])

    moved = _file_ids(db_path, "series/New Name%")
    assert {name.rsplit("/", 1)[1]: fid for name, (fid, _) in moved.items()} == ids_before
    assert all(deleted is None for _, deleted in moved.values())
    assert all(deleted is None for _, deleted in _file_ids(db_path, "series/Other%").values())
    conn = sqlite3.connect(db_path)
    tombstones = conn.execute("SELECT COUNT(*) FROM deleted_item").fetchone()[0]
    conn.close()
    assert tombstones == 0


def test_sibling_prefix_is_not_touched_by_a_refresh_or_a_removal(library) -> None:
    """« Show » never reaches « Show 2 »; ``_`` and ``%`` in a name are literal, not wildcards."""
    cfg, label, _disk_id, mount, db_path = library
    names = ["Show", "Show 2", "Show_A", "ShowXA", "Show%B", "ShowQQB"]
    shows = {
        n: _make_show(mount, n, [f"{n.replace(' ', '.')}.S01E01.mkv", f"{n.replace(' ', '.')}.S01E02.mkv"])
        for n in names
    }
    run_scoped_refresh(cfg, label, list(shows.values()))
    # A file vanishes from every show; only the ones refreshed may notice.
    for n, show in shows.items():
        (show / "Season 01" / f"{n.replace(' ', '.')}.S01E02.mkv").unlink()
    shutil.rmtree(shows["Show_A"])
    shutil.rmtree(shows["Show%B"])

    run_scoped_refresh(cfg, label, [shows["Show"], shows["Show_A"], shows["Show%B"]])

    live = {name for name, (_, deleted) in _file_ids(db_path, "series/%").items() if deleted is None}
    assert "series/Show 2/Season 01/Show.2.S01E02.mkv" in live
    assert "series/ShowXA/Season 01/ShowXA.S01E02.mkv" in live
    assert "series/ShowQQB/Season 01/ShowQQB.S01E02.mkv" in live
    assert "series/ShowXA/Season 01/ShowXA.S01E01.mkv" in live
    assert "series/ShowQQB/Season 01/ShowQQB.S01E01.mkv" in live
    assert "series/Show 2/Season 01/Show.2.S01E01.mkv" in live
    assert "series/Show/Season 01/Show.S01E02.mkv" not in live
    assert "series/Show/Season 01/Show.S01E01.mkv" in live
    assert not any(n.startswith(("series/Show_A", "series/Show%B")) for n in live)


def test_deleted_path_tombstone_records_the_miss_strikes(library) -> None:
    """The tombstone keeps the strike count the retired row carried, as the helper's docstring promises."""
    cfg, label, _disk_id, mount, db_path = library
    show_a = _make_show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    show_b = _make_show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    run_scoped_refresh(cfg, label, [show_a, show_b])
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE media_file SET miss_strikes = 2")
    conn.commit()
    conn.close()
    shutil.rmtree(show_a)

    run_scoped_refresh(cfg, label, [show_a])

    conn = sqlite3.connect(db_path)
    payloads = [json.loads(r[0]) for r in conn.execute("SELECT payload_json FROM deleted_item WHERE kind = 'file'")]
    conn.close()
    assert [p["miss_strikes"] for p in payloads] == [2]


def test_path_never_on_disk_and_not_indexed_is_refused(library) -> None:
    """A typo is not a deletion: nothing to remove is an error naming the path, not a silent « removed »."""
    cfg, label, _disk_id, mount, db_path = library
    _indexed_show(library)
    before = _dump(db_path)

    with pytest.raises(ValueError, match="not indexed"):
        run_scoped_refresh(cfg, label, [mount / "series" / "Typo (2020)"])

    assert _dump(db_path) == before
