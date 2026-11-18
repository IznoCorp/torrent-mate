"""A rename matched by content hash must not leave the file on the release of its OLD path.

Regression for the institut-repair finding: a season pack moved from
``Saison 02/S02E0n …mkv`` to ``Saison 01/S01E0n …mkv`` was matched by
``indexer.drift.rename_applied``, which updated ``path_id`` / ``filename`` and kept
``release_id`` — the release of the old season-2 episode. Nothing relinks a file that
already has a release (the linker, ``library-relink`` and ``library-fix-orphan-files``
only handle ``release_id IS NULL``), and the phantom-episode purge spares any episode a
``media_release`` still references, so the stale rows survived every later scan.

The tests drive the REAL incremental walk over a real temporary directory and a
temporary database — never the library's.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.indexer import fingerprint
from personalscraper.indexer._fs_capability import NTFS_MACFUSE
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.release_linker import link_file_to_release
from personalscraper.indexer.repos import disk_repo, item_repo
from personalscraper.indexer.repos.item_repo import _ATTR_DISPATCH_PATH
from personalscraper.indexer.scanner._modes._item_stage import scan_and_stage_dir
from personalscraper.indexer.scanner._modes.incremental import _scan_disk_incremental
from personalscraper.indexer.schema import ItemAttributeRow, MediaItemRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_PACK_EPISODE = "Show.S02E03.MULTi.1080p.mkv"
_RENAMED_EPISODE = "Show.S01E03.MULTi.1080p.mkv"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with the full migration chain applied."""
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


class _Library:
    """A tiny indexed library: one show on one disk, files seeded and linked like a scan would."""

    def __init__(self, conn: sqlite3.Connection, mount: Path) -> None:
        """Create the disk row, the show item and its ``Show (2025)`` folder under *mount*."""
        self.conn = conn
        self.mount = mount
        self.show_dir = mount / "series" / "Show (2025)"
        self.show_dir.mkdir(parents=True)
        now = int(time.time())
        disk_id = conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, is_mounted, merkle_root, unreachable_strikes) "
            "VALUES ('uuid-relink', 'RelinkDisk', ?, 1, NULL, 0)",
            (str(mount),),
        ).lastrowid
        assert disk_id is not None
        self.disk_id = disk_id
        self.item_id = item_repo.insert(
            conn,
            MediaItemRow(
                id=0,
                kind="show",
                title="Show",
                title_sort="Show",
                original_title=None,
                year=2025,
                category_id=CID.TV_SHOWS,
                external_ids_json="{}",
                ratings_json=None,
                canonical_provider=None,
                nfo_status=None,
                artwork_json=None,
                date_created=now,
                date_modified=now,
                date_metadata_refreshed=None,
                is_locked=0,
                preferred_lang="fr",
            ),
        )
        item_repo.upsert_attr(
            conn, ItemAttributeRow(item_id=self.item_id, key=_ATTR_DISPATCH_PATH, value=str(self.show_dir))
        )

    def add_episode_file(self, season_dir: str, filename: str, content: bytes) -> tuple[int, Path]:
        """Write a real file, index it as a scan would, link and enrich it. Returns ``(file_id, path)``."""
        directory = self.show_dir / season_dir
        directory.mkdir(exist_ok=True)
        path = directory / filename
        path.write_bytes(content)
        st = path.stat()
        rel_path = f"series/Show (2025)/{season_dir}"
        path_row = self.conn.execute(
            "SELECT id FROM path WHERE disk_id = ? AND rel_path = ?", (self.disk_id, rel_path)
        ).fetchone()
        path_id = (
            path_row[0]
            if path_row
            else self.conn.execute(
                "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)", (self.disk_id, rel_path)
            ).lastrowid
        )
        file_id = self.conn.execute(
            "INSERT INTO media_file ("
            " release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,"
            " oshash, xxh3_partial, xxh3_full, scan_generation,"
            " last_verified_at, enriched_at, miss_strikes, deleted_at"
            ") VALUES (NULL, ?, ?, ?, ?, ?, ?, NULL, NULL, 1, ?, ?, 0, NULL)",
            (
                path_id,
                filename,
                st.st_size,
                st.st_mtime_ns,
                st.st_ctime_ns,
                fingerprint.oshash(path),
                int(time.time()),
                int(time.time()) + 10,  # enriched: the enrich pass does not pick it up again
            ),
        ).lastrowid
        assert file_id is not None
        assert link_file_to_release(self.conn, file_id, str(path)) is not None
        return file_id, path

    def incremental_scan(self) -> None:
        """Drive the real incremental walk over the mount."""
        disk_row = disk_repo.get_by_id(self.conn, self.disk_id)
        with patch("personalscraper.indexer.scanner.guard_disk_mounted", return_value=None):
            _scan_disk_incremental(
                self.conn, disk_row, str(self.mount), [0], [0], 2, [0], False, capability=NTFS_MACFUSE
            )

    def episode_of_file(self, file_id: int) -> tuple[int, int] | None:
        """Return the ``(season, episode)`` of the release a file is linked to, ``None`` when unlinked."""
        row = self.conn.execute(
            "SELECT s.number, e.number FROM media_file mf "
            "JOIN media_release mr ON mr.id = mf.release_id "
            "JOIN episode e ON e.id = mr.episode_id "
            "JOIN season s ON s.id = e.season_id WHERE mf.id = ?",
            (file_id,),
        ).fetchone()
        return None if row is None else (row[0], row[1])

    def episode_rows(self) -> set[tuple[int, int]]:
        """Return every ``(season, episode)`` row the show holds."""
        return {
            (r[0], r[1])
            for r in self.conn.execute(
                "SELECT s.number, e.number FROM episode e JOIN season s ON s.id = e.season_id WHERE s.item_id = ?",
                (self.item_id,),
            )
        }


def _row(conn: sqlite3.Connection, file_id: int) -> Any:
    """Fetch ``(release_id, enriched_at, filename)`` of a file."""
    return conn.execute("SELECT release_id, enriched_at, filename FROM media_file WHERE id = ?", (file_id,)).fetchone()


def test_a_rename_across_seasons_relinks_the_file_and_the_next_stage_purges_the_old_episode(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """S02E03 → ``Saison 01/S01E03``: the file ends on release 1x3, the 2x3 episode row goes.

    The relink and the removal of the file-less 2x3 release happen in the incremental scan
    itself; the 2x3 EPISODE row is removed by the next item stage (the full scan's pass 1),
    which is the only place that purges episode rows.
    """
    lib = _Library(conn, tmp_path / "mnt")
    moved_id, moved_path = lib.add_episode_file("Saison 02", _PACK_EPISODE, b"P" * 4096)
    sibling_id, _ = lib.add_episode_file("Saison 02", "Show.S02E01.mkv", b"Q" * 4096)
    sibling_release = _row(conn, sibling_id)[0]
    assert lib.episode_of_file(moved_id) == (2, 3)

    new_dir = lib.show_dir / "Saison 01"
    new_dir.mkdir()
    moved_path.rename(new_dir / _RENAMED_EPISODE)

    lib.incremental_scan()

    assert _row(conn, moved_id)[2] == _RENAMED_EPISODE, "the row was renamed in place, not duplicated"
    assert lib.episode_of_file(moved_id) == (1, 3), "the file must follow the episode its new path names"
    assert _row(conn, sibling_id)[0] == sibling_release, "a file nobody touched keeps its release"
    assert _row(conn, moved_id)[1] is None, "the file is re-enriched against its new release"
    assert (2, 3) in lib.episode_rows(), "the stage that purges episodes has not run yet"

    # The next item stage (full scan pass 1) purges the episode no file nor release names any more.
    disk_cfg = DiskConfig(id="relink", path=tmp_path / "mnt", categories=[CID.TV_SHOWS])
    staged_item = scan_and_stage_dir(conn, lib.show_dir, disk_cfg, CID.TV_SHOWS, "show", now_s=2000)
    assert staged_item == lib.item_id
    assert lib.episode_rows() == {(1, 3), (2, 1)}, "2x3 is gone, 1x3 and the untouched 2x1 remain"


def test_a_rename_that_keeps_the_episode_keeps_the_release(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Renaming ``S02E03 …`` to ``S02E03 .FRENCH …`` in the same season changes nothing on the links."""
    lib = _Library(conn, tmp_path / "mnt")
    file_id, path = lib.add_episode_file("Saison 02", _PACK_EPISODE, b"P" * 4096)
    before = _row(conn, file_id)

    path.rename(path.with_name("Show.S02E03.FRENCH.mkv"))
    lib.incremental_scan()

    after = _row(conn, file_id)
    assert after[2] == "Show.S02E03.FRENCH.mkv"
    assert after[0] == before[0], "same episode, same release"
    assert after[1] == before[1], "and no re-enrichment is forced"
    assert lib.episode_of_file(file_id) == (2, 3)


def test_a_rename_out_of_any_known_item_unlinks_the_file(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """A file moved where no item owns it no longer belongs to the old release: it is left for the linker."""
    lib = _Library(conn, tmp_path / "mnt")
    file_id, path = lib.add_episode_file("Saison 02", _PACK_EPISODE, b"P" * 4096)
    old_release = _row(conn, file_id)[0]

    elsewhere = lib.mount / "unsorted"
    elsewhere.mkdir()
    path.rename(elsewhere / "mystery.mkv")
    lib.incremental_scan()

    release_id, enriched_at, filename = _row(conn, file_id)
    assert filename == "mystery.mkv"
    assert release_id is None, "no item owns the new path, so no release may claim the file"
    assert enriched_at is None, "the enrich pass picks it up and the linker links it once an item owns the path"
    assert conn.execute("SELECT 1 FROM media_release WHERE id = ?", (old_release,)).fetchone() is None


def test_the_old_release_survives_while_another_file_still_uses_it(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Two files on one release (a duplicate): moving one must not delete the release under the other."""
    lib = _Library(conn, tmp_path / "mnt")
    moved_id, moved_path = lib.add_episode_file("Saison 02", _PACK_EPISODE, b"P" * 4096)
    twin_id, _ = lib.add_episode_file("Saison 02", "Show.S02E03.twin.mkv", b"T" * 4096)
    shared_release = _row(conn, twin_id)[0]
    assert _row(conn, moved_id)[0] == shared_release

    new_dir = lib.show_dir / "Saison 01"
    new_dir.mkdir()
    moved_path.rename(new_dir / _RENAMED_EPISODE)
    lib.incremental_scan()

    assert lib.episode_of_file(moved_id) == (1, 3)
    assert _row(conn, twin_id)[0] == shared_release, "the twin keeps its release"
    assert conn.execute("SELECT 1 FROM media_release WHERE id = ?", (shared_release,)).fetchone() is not None
