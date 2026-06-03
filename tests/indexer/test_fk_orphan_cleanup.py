"""Tests for foreign-key orphan cleanup (DEV #3).

Reproduces the production scenario: migration 007 deleted ``media_item`` rows
with FK enforcement OFF, leaving ``media_release`` + ``item_issue`` children
orphaned while their own ``media_file`` / ``media_stream`` descendants survived
(proof the cascade never fired). ``open_db``'s strict FK guard then blocks every
indexer command. :func:`clean_fk_orphans` deletes the orphan rows under
``foreign_keys=ON`` so the declared CASCADE removes the descendants too.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import IndexerFKOrphansError, apply_migrations, open_db
from personalscraper.indexer.reconcile import clean_fk_orphans, detect_fk_orphans

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _bootstrap(db_path: Path) -> None:
    """Create a migrated DB with FK enforcement on."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    conn.close()


def _seed_orphan_chain(db_path: Path) -> None:
    """Seed item→release→file→stream + item_issue, then FK-OFF delete the item.

    Leaves the release + item_issue orphaned (parent media_item gone) while the
    file + stream survive — exactly the migration-007 FK-off scenario.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        disk = conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("u", "D", "/tmp/x", 0, None, 1, 0),
        ).lastrowid
        path_id = conn.execute("INSERT INTO path (disk_id, rel_path) VALUES (?, ?)", (disk, "r")).lastrowid
        item = conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("movie", "Victim", "victim", "movies", 0, 0),
        ).lastrowid
        rel = conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (item,)).lastrowid
        fid = conn.execute(
            "INSERT INTO media_file (path_id, release_id, filename, size_bytes, mtime_ns, scan_generation, "
            "last_verified_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (path_id, rel, "v.mkv", 1, 1, 1, 0),
        ).lastrowid
        conn.execute("INSERT INTO media_stream (file_id, idx, kind) VALUES (?, ?, ?)", (fid, 0, "video"))
        conn.execute(
            "INSERT INTO item_issue (item_id, type, detected_at) VALUES (?, ?, ?)",
            (item, "nfo_missing", 0),
        )
        # FK-OFF delete: orphans release + item_issue, descendants survive.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM media_item WHERE id = ?", (item,))
    finally:
        conn.close()


class TestDetectFkOrphans:
    """``detect_fk_orphans`` reports without modifying the DB."""

    def test_reports_counts_and_cascade(self, tmp_path: Path) -> None:
        """Detection surfaces per-table counts + cascade impact, deletes nothing."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_orphan_chain(db)

        conn = open_db(db, allow_fk_orphans=True, event_bus=EventBus())
        try:
            report = detect_fk_orphans(conn)
            assert report.by_table.get("media_release") == 1
            assert report.by_table.get("item_issue") == 1
            assert report.cascade_media_files == 1
            assert report.cascade_media_streams == 1
            # Nothing deleted by detection.
            assert conn.execute("PRAGMA foreign_key_check").fetchall() != []
        finally:
            conn.close()


class TestCleanFkOrphans:
    """``clean_fk_orphans`` removes orphans and cascades to descendants."""

    def test_clean_removes_orphans_and_cascades(self, tmp_path: Path) -> None:
        """After cleanup: no FK orphans, and file+stream cascade-deleted."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_orphan_chain(db)

        conn = open_db(db, allow_fk_orphans=True, event_bus=EventBus())
        try:
            assert conn.execute("PRAGMA foreign_key_check").fetchall() != []  # before

            report = clean_fk_orphans(conn, dry_run=False)

            assert report.by_table.get("media_release") == 1
            assert report.cascade_media_files == 1
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []  # after
            assert conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM media_stream").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM item_issue").fetchone()[0] == 0
        finally:
            conn.close()

    def test_dry_run_reports_without_deleting(self, tmp_path: Path) -> None:
        """Dry-run returns the same counts but leaves the orphans in place."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_orphan_chain(db)

        conn = open_db(db, allow_fk_orphans=True, event_bus=EventBus())
        try:
            report = clean_fk_orphans(conn, dry_run=True)
            assert report.total_orphans == 2
            assert conn.execute("PRAGMA foreign_key_check").fetchall() != []  # untouched
        finally:
            conn.close()

    def test_clean_on_clean_db_is_noop(self, tmp_path: Path) -> None:
        """A DB with no orphans yields an empty report and no error."""
        db = tmp_path / "library.db"
        _bootstrap(db)

        conn = open_db(db, event_bus=EventBus())
        try:
            report = clean_fk_orphans(conn, dry_run=False)
            assert report.total_orphans == 0
        finally:
            conn.close()


class TestOpenDbAllowFkOrphans:
    """The tolerant ``allow_fk_orphans`` escape hatch (default stays strict)."""

    def test_allow_fk_orphans_returns_connection(self, tmp_path: Path) -> None:
        """With allow_fk_orphans=True a dirty DB opens (warning, no raise)."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_orphan_chain(db)

        conn = open_db(db, allow_fk_orphans=True, event_bus=EventBus())
        try:
            # Usable connection on a dirty DB — the orphans are still present.
            assert conn.execute("PRAGMA foreign_key_check").fetchall() != []
        finally:
            conn.close()

    def test_default_open_still_raises_on_same_dirty_db(self, tmp_path: Path) -> None:
        """The default open stays strict (fail-loud DEV #19 contract preserved)."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_orphan_chain(db)

        with pytest.raises(IndexerFKOrphansError):
            open_db(db, event_bus=EventBus())


def _seed_tv_orphan_chain(db_path: Path) -> None:
    """Seed a TV chain then FK-OFF delete the show's media_item.

    Chain: item → season → episode → release → file → stream.
    The episode media_release links via episode_id with item_id NULL (the
    media_release CHECK is item_id XOR episode_id), so deleting the show orphans
    the SEASON (season.item_id), NOT the release — the BUG-4 scenario where the
    cascade impact is reachable only via season → episode → media_release.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        disk = conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("u", "D", "/tmp/x", 0, None, 1, 0),
        ).lastrowid
        path_id = conn.execute("INSERT INTO path (disk_id, rel_path) VALUES (?, ?)", (disk, "r")).lastrowid
        show = conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("show", "Show", "show", "tv_shows", 0, 0),
        ).lastrowid
        season = conn.execute("INSERT INTO season (item_id, number) VALUES (?, ?)", (show, 1)).lastrowid
        episode = conn.execute("INSERT INTO episode (season_id, number) VALUES (?, ?)", (season, 1)).lastrowid
        rel = conn.execute("INSERT INTO media_release (episode_id) VALUES (?)", (episode,)).lastrowid
        fid = conn.execute(
            "INSERT INTO media_file (path_id, release_id, filename, size_bytes, mtime_ns, scan_generation, "
            "last_verified_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (path_id, rel, "e01.mkv", 1, 1, 1, 0),
        ).lastrowid
        conn.execute("INSERT INTO media_stream (file_id, idx, kind) VALUES (?, ?, ?)", (fid, 0, "video"))
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM media_item WHERE id = ?", (show,))
    finally:
        conn.close()


class TestSeasonRootedCascadeCount:
    """BUG-4: cascade impact counts the season → episode → release path too."""

    def test_season_orphan_cascade_counted(self, tmp_path: Path) -> None:
        """A deleted show orphans the season; its file/stream cascade is counted."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_tv_orphan_chain(db)

        conn = open_db(db, allow_fk_orphans=True, event_bus=EventBus())
        try:
            report = detect_fk_orphans(conn)
            # The orphan is the season (not a media_release), yet the cascade
            # via season->episode->release->file/stream must be counted.
            assert report.by_table.get("season") == 1
            assert "media_release" not in report.by_table
            assert report.cascade_media_files == 1
            assert report.cascade_media_streams == 1
        finally:
            conn.close()

    def test_season_clean_cascades_to_file_and_stream(self, tmp_path: Path) -> None:
        """Cleaning the orphan season cascades episode->release->file->stream."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_tv_orphan_chain(db)

        conn = open_db(db, allow_fk_orphans=True, event_bus=EventBus())
        try:
            clean_fk_orphans(conn, dry_run=False)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            assert conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM media_stream").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0] == 0
        finally:
            conn.close()


class _FlakyConn:
    """Connection proxy that raises on the 2nd executemany (atomicity probe)."""

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real
        self._em = 0

    def execute(self, *a: object, **k: object) -> object:
        return self._real.execute(*a, **k)

    def executemany(self, *a: object, **k: object) -> object:
        self._em += 1
        if self._em >= 2:
            raise sqlite3.OperationalError("injected mid-loop failure")
        return self._real.executemany(*a, **k)

    def commit(self) -> None:
        self._real.commit()

    def rollback(self) -> None:
        self._real.rollback()


class TestCleanFkOrphansAtomicity:
    """BUG-2: a mid-loop failure rolls back ALL deletes (no half-cleaned DB)."""

    def test_partial_failure_rolls_back(self, tmp_path: Path) -> None:
        """When the 2nd table's delete fails, the 1st table's deletes are undone."""
        db = tmp_path / "library.db"
        _bootstrap(db)
        _seed_orphan_chain(db)  # orphans across 2 tables: media_release + item_issue

        conn = open_db(db, allow_fk_orphans=True, event_bus=EventBus())
        try:
            before = len(conn.execute("PRAGMA foreign_key_check").fetchall())
            assert before >= 2  # two orphan tables → two executemany calls

            with pytest.raises(sqlite3.OperationalError):
                clean_fk_orphans(_FlakyConn(conn), dry_run=False)

            # Rolled back: every orphan still present (no partial cleanup).
            after = len(conn.execute("PRAGMA foreign_key_check").fetchall())
            assert after == before
        finally:
            conn.close()
