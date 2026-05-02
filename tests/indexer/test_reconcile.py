"""Tests for personalscraper.indexer.reconcile.

Six detectors + an orchestrator covered with focused unit tests:
each detector gets one positive (divergence present, expected count)
and one negative (clean DB, zero count) scenario, plus an integration
test that asserts the orchestrator enqueues into ``repair_queue`` and
that re-running is idempotent thanks to migration 003.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.db import apply_migrations, open_db
from personalscraper.indexer.reconcile import (
    detect_dispatch_path_missing,
    detect_enrich_stale,
    detect_items_without_files,
    detect_release_orphans,
    detect_season_count_drift,
    reconcile,
)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> sqlite3.Connection:
    """Return a fully-migrated file-based DB."""
    db_path = tmp_path / "lib.db"
    conn = open_db(db_path)
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _seed_disk(conn: sqlite3.Connection, *, mount_path: str, label: str = "disk_a") -> int:
    """Insert a disk row and return its id."""
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (label, label, mount_path, int(time.time())),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_path(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> int:
    """Insert a path row and return its id."""
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_item(
    conn: sqlite3.Connection,
    *,
    title: str = "Item",
    kind: str = "movie",
    category_id: str = "movies",
) -> int:
    """Insert a minimal media_item row and return its id."""
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, category_id,
            date_created, date_modified, is_locked, preferred_lang
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 'fr')
        """,
        (kind, title, title, category_id, now, now),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_release(conn: sqlite3.Connection, item_id: int) -> int:
    """Insert a default media_release for ``item_id`` and return its id."""
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (?, NULL, NULL, NULL, NULL)",
        (item_id,),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_file(
    conn: sqlite3.Connection,
    *,
    release_id: int | None,
    path_id: int,
    filename: str = "video.mkv",
    size_bytes: int = 1000,
    mtime_ns: int = 1_700_000_000_000_000_000,
    enriched_at: int | None = None,
) -> int:
    """Insert a media_file row and return its id."""
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, enriched_at, scan_generation, last_verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 1, ?)
        """,
        (release_id, path_id, filename, size_bytes, mtime_ns, mtime_ns, enriched_at, now),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_season(
    conn: sqlite3.Connection,
    item_id: int,
    *,
    number: int = 1,
    episode_count: int = 0,
) -> int:
    """Insert a season row and return its id."""
    cursor = conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, ?, ?, 0, 0)",
        (item_id, number, episode_count),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_episode(conn: sqlite3.Connection, season_id: int, number: int) -> int:
    """Insert an episode row and return its id."""
    cursor = conn.execute(
        "INSERT INTO episode (season_id, number, title) VALUES (?, ?, NULL)",
        (season_id, number),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# detect_dispatch_path_missing
# ---------------------------------------------------------------------------


class TestDispatchPathMissing:
    """Detector returns item IDs whose dispatch_path is gone from disk."""

    def test_existing_path_not_flagged(self, tmp_path: Path) -> None:
        """An item whose dispatch_path exists on disk is NOT flagged."""
        conn = _make_db(tmp_path)
        present_dir = tmp_path / "present"
        present_dir.mkdir()

        item_id = _seed_item(conn)
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, str(present_dir)),
        )
        assert detect_dispatch_path_missing(conn) == []

    def test_missing_path_flagged(self, tmp_path: Path) -> None:
        """An item whose dispatch_path is gone IS flagged."""
        conn = _make_db(tmp_path)
        item_id = _seed_item(conn)
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, str(tmp_path / "absent")),
        )
        assert detect_dispatch_path_missing(conn) == [item_id]


# ---------------------------------------------------------------------------
# detect_enrich_stale
# ---------------------------------------------------------------------------


class TestEnrichStale:
    """Detector counts files whose enriched_at < mtime_ns/1e9."""

    def test_fresh_enrich_not_flagged(self, tmp_path: Path) -> None:
        """A file enriched after its last mtime is NOT counted."""
        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "category")
        # mtime_ns = 1700000000_000000000 → seconds = 1700000000
        # enriched_at = 1700000010 (10s after mtime) → fresh
        _seed_file(
            conn, release_id=None, path_id=path_id, mtime_ns=1_700_000_000_000_000_000, enriched_at=1_700_000_010
        )
        assert detect_enrich_stale(conn) == 0

    def test_stale_enrich_flagged(self, tmp_path: Path) -> None:
        """A file modified after its last enrich IS counted."""
        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "category")
        # enriched_at = 1700000000 - 100 (100s before mtime) → stale
        _seed_file(
            conn,
            release_id=None,
            path_id=path_id,
            mtime_ns=1_700_000_000_000_000_000,
            enriched_at=1_699_999_900,
        )
        assert detect_enrich_stale(conn) == 1


# ---------------------------------------------------------------------------
# detect_release_orphans
# ---------------------------------------------------------------------------


class TestReleaseOrphans:
    """Detector returns release rows with no live file + counts NULL-release files."""

    def test_release_with_file_not_orphan(self, tmp_path: Path) -> None:
        """A release with at least one live file is NOT an orphan."""
        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "category")
        item_id = _seed_item(conn)
        release_id = _seed_release(conn, item_id)
        _seed_file(conn, release_id=release_id, path_id=path_id)
        orphans, null_count = detect_release_orphans(conn)
        assert orphans == []
        assert null_count == 0

    def test_release_without_file_is_orphan(self, tmp_path: Path) -> None:
        """A release with zero linked files IS an orphan."""
        conn = _make_db(tmp_path)
        item_id = _seed_item(conn)
        release_id = _seed_release(conn, item_id)
        orphans, _ = detect_release_orphans(conn)
        assert orphans == [release_id]

    def test_null_release_file_with_enrich_counted(self, tmp_path: Path) -> None:
        """A media_file with release_id NULL but enriched_at set IS counted."""
        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "category")
        _seed_file(conn, release_id=None, path_id=path_id, enriched_at=int(time.time()))
        _, null_count = detect_release_orphans(conn)
        assert null_count == 1


# ---------------------------------------------------------------------------
# detect_season_count_drift
# ---------------------------------------------------------------------------


class TestSeasonCountDrift:
    """Detector returns seasons whose episode_count != actual count."""

    def test_count_matches_not_flagged(self, tmp_path: Path) -> None:
        """A season whose stored count matches actual episodes is NOT flagged."""
        conn = _make_db(tmp_path)
        item_id = _seed_item(conn, kind="show")
        season_id = _seed_season(conn, item_id, episode_count=2)
        _seed_episode(conn, season_id, 1)
        _seed_episode(conn, season_id, 2)
        assert detect_season_count_drift(conn) == []

    def test_count_drift_flagged(self, tmp_path: Path) -> None:
        """A season whose stored count is wrong IS flagged."""
        conn = _make_db(tmp_path)
        item_id = _seed_item(conn, kind="show")
        season_id = _seed_season(conn, item_id, episode_count=5)  # claims 5
        _seed_episode(conn, season_id, 1)  # but only 1 exists
        assert detect_season_count_drift(conn) == [season_id]


# ---------------------------------------------------------------------------
# detect_items_without_files
# ---------------------------------------------------------------------------


class TestItemsWithoutFiles:
    """Detector returns item IDs that have no surviving file evidence."""

    def test_item_with_file_not_flagged(self, tmp_path: Path) -> None:
        """An item with at least one live file is NOT flagged."""
        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "category")
        item_id = _seed_item(conn)
        release_id = _seed_release(conn, item_id)
        _seed_file(conn, release_id=release_id, path_id=path_id)
        assert detect_items_without_files(conn) == []

    def test_orphan_item_flagged(self, tmp_path: Path) -> None:
        """An item with no release/file linkage IS flagged."""
        conn = _make_db(tmp_path)
        item_id = _seed_item(conn)
        assert detect_items_without_files(conn) == [item_id]


# ---------------------------------------------------------------------------
# Orchestrator: reconcile()
# ---------------------------------------------------------------------------


class TestReconcileOrchestrator:
    """End-to-end orchestrator behaviour."""

    def test_clean_db_zero_findings(self, tmp_path: Path) -> None:
        """A freshly-migrated DB has no divergences."""
        conn = _make_db(tmp_path)
        report = reconcile(conn)
        assert report.total_findings == 0
        assert report.enqueued_repairs == 0

    def test_findings_enqueue_repairs(self, tmp_path: Path) -> None:
        """``enqueue_repairs=True`` populates repair_queue with one row per finding."""
        conn = _make_db(tmp_path)
        # Seed one orphan item and one season-count drift.
        item_id = _seed_item(conn, kind="show")  # no files → items_without_files
        season_id = _seed_season(conn, item_id, episode_count=3)  # claims 3, has 0

        report = reconcile(conn, enqueue_repairs=True)
        assert season_id in report.season_count_drift
        assert item_id in report.items_without_files
        assert report.enqueued_repairs >= 2

        rows = conn.execute(
            "SELECT scope, scope_id, reason FROM repair_queue WHERE status='pending' ORDER BY id"
        ).fetchall()
        scopes = {(r[0], r[1]) for r in rows}
        assert ("item", item_id) in scopes
        assert ("release", season_id) in scopes  # season uses release scope per design

    def test_re_run_is_dedup_safe(self, tmp_path: Path) -> None:
        """Two successive enqueue runs with the same findings produce the same row count.

        Migration 003's partial UNIQUE INDEX on
        ``(scope, scope_id) WHERE status='pending'`` deduplicates on the
        producer side via ``INSERT OR IGNORE``.  ``enqueued_repairs`` on
        the second run should report ``0`` net new rows.
        """
        conn = _make_db(tmp_path)
        item_id = _seed_item(conn)  # orphan item

        first = reconcile(conn, enqueue_repairs=True)
        assert first.enqueued_repairs >= 1

        second = reconcile(conn, enqueue_repairs=True)
        assert second.enqueued_repairs == 0

        rows = conn.execute(
            "SELECT COUNT(*) FROM repair_queue WHERE status='pending' AND scope='item' AND scope_id=?",
            (item_id,),
        ).fetchone()
        assert rows[0] == 1

    def test_scope_filter_runs_subset(self, tmp_path: Path) -> None:
        """Passing ``scopes=['enrich']`` skips every other detector."""
        conn = _make_db(tmp_path)
        # Seed an orphan item that ``item`` would flag.
        _seed_item(conn)
        # And a stale-enrich file for ``enrich``.
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "category")
        _seed_file(
            conn,
            release_id=None,
            path_id=path_id,
            mtime_ns=1_700_000_000_000_000_000,
            enriched_at=1_699_999_900,
        )

        report = reconcile(conn, scopes=["enrich"])
        # Enrich count populated:
        assert report.enrich_stale == 1
        # Item-only finding skipped:
        assert report.items_without_files == []

    def test_payload_carries_detector_label(self, tmp_path: Path) -> None:
        """Each enqueued repair row's payload_json names the detector that fired."""
        conn = _make_db(tmp_path)
        _seed_item(conn)
        reconcile(conn, scopes=["item"], enqueue_repairs=True)
        rows = conn.execute("SELECT payload_json FROM repair_queue WHERE reason = 'reconcile.item.no_files'").fetchall()
        assert len(rows) == 1
        payload = json.loads(rows[0][0])
        assert payload.get("detector") == "item"
