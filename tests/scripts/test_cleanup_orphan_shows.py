"""Tests for scripts/cleanup-2026-05-21-orphan-shows.py.

Covers:
- Script exists at the documented path.
- Script is syntactically valid (importable via importlib).
- ``describe_cleanup`` returns expected metadata (8 shows, correct split).
- ``build_class_a_runbook_steps`` returns the correct CLI commands in order.
- ``build_class_b_runbook_steps`` returns the correct CLI commands in order.
- ``build_verification_steps`` returns the reconcile command.
- ``assert_reconcile_report_clean`` validates clean reports correctly.
- ``assert_reconcile_report_clean`` surfaces violations for dirty reports.
- Runbook logic on a synthetic DB: reconcile detects phantom paths,
  repair queue drains them, items_without_files is populated for
  FS-exists-but-missing-item scenario.
"""

from __future__ import annotations

import importlib.util as _util
import json
import sqlite3
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate and import the script under test
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cleanup-2026-05-21-orphan-shows.py"

# Load the module via importlib so the hyphen in the filename is not a problem.
_spec = _util.spec_from_file_location("cleanup_orphan_shows", SCRIPT)
assert _spec is not None
_mod = _util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

describe_cleanup = _mod.describe_cleanup
build_class_a_runbook_steps = _mod.build_class_a_runbook_steps
build_class_b_runbook_steps = _mod.build_class_b_runbook_steps
build_verification_steps = _mod.build_verification_steps
assert_reconcile_report_clean = _mod.assert_reconcile_report_clean
CLASS_A_DELETED_PATH_SHOWS: tuple[str, ...] = _mod.CLASS_A_DELETED_PATH_SHOWS
CLASS_B_FS_EXISTS_SHOWS: tuple[str, ...] = _mod.CLASS_B_FS_EXISTS_SHOWS


# ---------------------------------------------------------------------------
# DB helpers (mirrors tests/indexer/test_reconcile.py for independence)
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "personalscraper" / "indexer" / "migrations"


def _make_db(tmp_path: Path) -> sqlite3.Connection:
    """Return a fully-migrated in-memory-like file-based DB.

    Args:
        tmp_path: pytest tmp_path fixture for DB file placement.

    Returns:
        Open, migrated sqlite3.Connection.
    """
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

    db_path = tmp_path / "lib.db"
    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _seed_disk(conn: sqlite3.Connection, *, mount_path: str, label: str = "disk_a") -> int:
    """Insert a mounted disk row and return its id."""
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


def _seed_item(conn: sqlite3.Connection, *, title: str = "Show", kind: str = "show") -> int:
    """Insert a minimal media_item row and return its id."""
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, category_id,
            date_created, date_modified, is_locked, preferred_lang
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 'fr')
        """,
        (kind, title, title, "tv_shows", now, now),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_release(conn: sqlite3.Connection, item_id: int) -> int:
    """Insert a minimal media_release and return its id."""
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (?, NULL, NULL, NULL, NULL)",
        (item_id,),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_file(conn: sqlite3.Connection, *, release_id: int, path_id: int, filename: str = "ep.mkv") -> int:
    """Insert a media_file row and return its id."""
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, enriched_at, scan_generation, last_verified_at
        ) VALUES (?, ?, ?, 1000, ?, ?, NULL, NULL, 1, ?)
        """,
        (release_id, path_id, filename, now * 1_000_000_000, now * 1_000_000_000, now),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# 1 — Script exists and is syntactically valid
# ---------------------------------------------------------------------------


def test_script_exists() -> None:
    """The cleanup script exists at its documented path."""
    assert SCRIPT.is_file(), f"Script not found at {SCRIPT}"


def test_script_importable() -> None:
    """The script can be imported without syntax errors (already done at module level).

    If the module-level importlib.exec_module above raised SyntaxError,
    collection would have failed — reaching this test proves import worked.
    """
    assert _mod is not None


def test_script_runs_directly(tmp_path: Path) -> None:
    """Running the script as __main__ exits 0 and emits JSON to stdout."""
    import subprocess  # noqa: PLC0415

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Script exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # First non-empty line must be valid JSON.
    first_line = next(line for line in result.stdout.splitlines() if line.strip().startswith("{"))
    parsed = json.loads(first_line if first_line.endswith("}") else result.stdout.split("\n\n")[0])
    assert parsed.get("total_shows") == 7


# ---------------------------------------------------------------------------
# 2 — describe_cleanup
# ---------------------------------------------------------------------------


def test_describe_cleanup_total_shows() -> None:
    """Total shows is 7 (5 Class-A + 2 Class-B)."""
    summary = describe_cleanup()
    assert summary["total_shows"] == 7


def test_describe_cleanup_class_a_count() -> None:
    """Class-A (deleted-path shows) has 5 entries."""
    summary = describe_cleanup()
    assert len(summary["class_a"]) == 5  # type: ignore[arg-type]


def test_describe_cleanup_class_b_count() -> None:
    """Class-B (FS-exists shows) has 2 entries."""
    summary = describe_cleanup()
    assert len(summary["class_b"]) == 2  # type: ignore[arg-type]


def test_describe_cleanup_class_a_contains_expected_shows() -> None:
    """All 5 known Class-A phantom shows are present in the metadata."""
    class_a = describe_cleanup()["class_a"]
    assert isinstance(class_a, tuple)
    expected = {"Bloqués", "Avez-vous déjà...", "Corneil et Bernie", "Star Trek Enterprise", "Star Trek Voyager"}
    assert expected == set(class_a)


def test_describe_cleanup_class_b_contains_expected_shows() -> None:
    """Both known Class-B re-index shows are present in the metadata."""
    class_b = describe_cleanup()["class_b"]
    assert isinstance(class_b, tuple)
    assert set(class_b) == {"Monk", "Squid Game"}


# ---------------------------------------------------------------------------
# 3 — Runbook steps helpers
# ---------------------------------------------------------------------------


def test_class_a_runbook_has_reconcile_first() -> None:
    """Class-A runbook starts with library-reconcile --enqueue-repairs."""
    steps = build_class_a_runbook_steps()
    assert len(steps) >= 1
    assert "library-reconcile" in steps[0]
    assert "--enqueue-repairs" in steps[0]
    assert "--scope path_missing" in steps[0]


def test_class_a_runbook_has_repair_second() -> None:
    """Class-A runbook drains the queue with library-repair as second step."""
    steps = build_class_a_runbook_steps()
    assert len(steps) >= 2
    assert "library-repair" in steps[1]


def test_class_b_runbook_has_incremental_scan() -> None:
    """Class-B runbook includes library-index --mode incremental."""
    steps = build_class_b_runbook_steps()
    assert any("library-index" in s and "--mode incremental" in s for s in steps)


def test_class_b_runbook_has_enrich_scan() -> None:
    """Class-B runbook includes library-index --mode enrich for Stage B."""
    steps = build_class_b_runbook_steps()
    assert any("library-index" in s and "--mode enrich" in s for s in steps)


def test_verification_steps_include_reconcile() -> None:
    """Verification commands include a bare library-reconcile for final check."""
    steps = build_verification_steps()
    assert any("library-reconcile" in s for s in steps)


# ---------------------------------------------------------------------------
# 4 — assert_reconcile_report_clean
# ---------------------------------------------------------------------------


def test_clean_report_returns_no_violations() -> None:
    """A report with path_missing_count=0 and items_without_files_count=0 is clean."""
    report = {
        "path_missing_count": 0,
        "items_without_files_count": 0,
        "total_findings": 0,
    }
    violations = assert_reconcile_report_clean(report)
    assert violations == []


def test_dirty_path_missing_surfaces_violation() -> None:
    """A report with path_missing_count > 0 surfaces a violation message."""
    report = {
        "path_missing_count": 3,
        "items_without_files_count": 0,
        "total_findings": 3,
    }
    violations = assert_reconcile_report_clean(report)
    assert len(violations) >= 1
    assert any("path_missing_count" in v for v in violations)


def test_dirty_items_without_files_surfaces_violation() -> None:
    """A report with items_without_files_count > 0 surfaces a violation."""
    report = {
        "path_missing_count": 0,
        "items_without_files_count": 2,
        "total_findings": 2,
    }
    violations = assert_reconcile_report_clean(report)
    assert len(violations) >= 1
    assert any("items_without_files_count" in v for v in violations)


def test_both_dirty_surfaces_two_violations() -> None:
    """A report dirty on both fields surfaces at least two violations."""
    report = {
        "path_missing_count": 5,
        "items_without_files_count": 2,
        "total_findings": 7,
    }
    violations = assert_reconcile_report_clean(report)
    assert len(violations) >= 2


# ---------------------------------------------------------------------------
# 5 — Runbook logic on a synthetic DB (Class A)
# ---------------------------------------------------------------------------


class TestClassARunbookLogicOnSyntheticDB:
    """Verify that Class-A runbook machinery works on a tiny in-memory fixture.

    Regression for MUST-18 / BD-F: phantom shows must be detectable via
    reconcile and drainable via repair without touching the live DB.
    """

    def test_reconcile_detects_phantom_paths(self, tmp_path: Path) -> None:
        """detect_path_missing finds paths whose directories are gone from FS.

        This exercises the Phase 4.1 detector that is invoked by the Class-A
        runbook step ('library-reconcile --scope path_missing --enqueue-repairs').
        """
        from personalscraper.indexer.reconcile import detect_path_missing  # noqa: PLC0415

        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))

        # Simulate 5 Class-A phantom show paths (directories do NOT exist).
        phantom_ids: list[int] = []
        for show in CLASS_A_DELETED_PATH_SHOWS:
            path_id = _seed_path(conn, disk_id, f"TV/{show}")
            phantom_ids.append(path_id)

        missing = detect_path_missing(conn)
        assert set(phantom_ids) == set(missing), (
            f"Expected all phantom path IDs to be detected; detected={set(missing)}, expected={set(phantom_ids)}"
        )

    def test_reconcile_enqueues_repair_for_phantom_paths(self, tmp_path: Path) -> None:
        """Missing paths are enqueued into repair_queue with soft_delete_subtree action.

        Regression: without the 'action' key in payload_json, library-repair
        cannot dispatch the correct handler (BD-D).
        """
        from personalscraper.indexer.reconcile import reconcile  # noqa: PLC0415

        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))

        # One phantom path is enough to exercise the enqueue path.
        _seed_path(conn, disk_id, "TV/Star Trek Enterprise")

        report = reconcile(conn, scopes=["path_missing"], enqueue_repairs=True)
        conn.commit()

        assert report.enqueued_repairs >= 1, "Expected at least one repair to be enqueued"

        row = conn.execute(
            "SELECT scope, payload_json FROM repair_queue WHERE reason='reconcile.path.missing'"
        ).fetchone()
        assert row is not None, "No repair_queue row found for reconcile.path.missing"
        assert row[0] == "path"
        payload = json.loads(row[1])
        assert payload.get("action") == "soft_delete_subtree", (
            "payload['action'] must be 'soft_delete_subtree' so library-repair "
            "routes to the correct handler (BD-D regression)"
        )

    def test_soft_delete_subtree_marks_files_deleted(self, tmp_path: Path) -> None:
        """soft_delete_subtree sets deleted_at on every media_file under a path.

        Verifies the repair action consumed by library-repair when draining
        Class-A repair_queue entries (BD-D, Phase 4.2 machinery).
        """
        from personalscraper.indexer.repair import soft_delete_subtree  # noqa: PLC0415

        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "TV/Bloqués")

        item_id = _seed_item(conn, title="Bloqués")
        release_id = _seed_release(conn, item_id)
        _seed_file(conn, release_id=release_id, path_id=path_id, filename="s01e01.mkv")
        _seed_file(conn, release_id=release_id, path_id=path_id, filename="s01e02.mkv")

        # Confirm files are live before the repair.
        live_before = conn.execute(
            "SELECT COUNT(*) FROM media_file WHERE path_id = ? AND deleted_at IS NULL",
            (path_id,),
        ).fetchone()[0]
        assert live_before == 2

        soft_delete_subtree(conn, path_id)
        conn.commit()

        live_after = conn.execute(
            "SELECT COUNT(*) FROM media_file WHERE path_id = ? AND deleted_at IS NULL",
            (path_id,),
        ).fetchone()[0]
        assert live_after == 0, "All files under the phantom path must be soft-deleted"

    def test_rerun_is_idempotent(self, tmp_path: Path) -> None:
        """Running reconcile + enqueue twice produces no duplicate repair_queue rows.

        Migration 003's partial UNIQUE INDEX deduplicates via INSERT OR IGNORE.
        The second run's enqueued_repairs must be 0.
        """
        from personalscraper.indexer.reconcile import reconcile  # noqa: PLC0415

        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        _seed_path(conn, disk_id, "TV/Corneil et Bernie")

        first = reconcile(conn, scopes=["path_missing"], enqueue_repairs=True)
        conn.commit()
        assert first.enqueued_repairs >= 1

        second = reconcile(conn, scopes=["path_missing"], enqueue_repairs=True)
        conn.commit()
        # Partial UNIQUE INDEX must prevent duplicate enqueue.
        assert second.enqueued_repairs == 0, (
            "Second reconcile run must not re-enqueue already-pending repairs (idempotence)"
        )


# ---------------------------------------------------------------------------
# 6 — Runbook logic on a synthetic DB (Class B)
# ---------------------------------------------------------------------------


class TestClassBRunbookLogicOnSyntheticDB:
    """Verify that Class-B items_without_files scenario is detectable.

    The actual re-indexing (library-index --mode incremental) is an E2E
    operation that requires a live config and disk mount; it is NOT run here.
    Instead, we verify that ``detect_items_without_files`` correctly identifies
    media_item rows with no file evidence — the condition that makes Class-B
    shows invisible in the library.
    """

    def test_item_without_files_is_detected(self, tmp_path: Path) -> None:
        """An item with no media_file rows is flagged by items_without_files detector.

        Regression for Class-B shows (Monk, Squid Game): their media_item rows
        were present but had no media_file linkage, making them phantom items.
        """
        from personalscraper.indexer.reconcile import detect_items_without_files  # noqa: PLC0415

        conn = _make_db(tmp_path)

        monk_id = _seed_item(conn, title="Monk")
        squid_id = _seed_item(conn, title="Squid Game")

        missing = detect_items_without_files(conn)
        assert monk_id in missing, "Monk item with no files must be flagged"
        assert squid_id in missing, "Squid Game item with no files must be flagged"

    def test_item_with_files_is_not_detected(self, tmp_path: Path) -> None:
        """An item with at least one live media_file is NOT flagged as empty.

        Simulates the state after Class-B re-indexing completes successfully:
        the item must no longer appear in items_without_files.
        """
        from personalscraper.indexer.reconcile import detect_items_without_files  # noqa: PLC0415

        conn = _make_db(tmp_path)
        disk_id = _seed_disk(conn, mount_path=str(tmp_path))
        path_id = _seed_path(conn, disk_id, "TV/Monk")

        monk_id = _seed_item(conn, title="Monk")
        release_id = _seed_release(conn, monk_id)
        _seed_file(conn, release_id=release_id, path_id=path_id)

        missing = detect_items_without_files(conn)
        assert monk_id not in missing, (
            "Monk item with a linked media_file must NOT appear in items_without_files (post-reindex clean state)"
        )

    def test_assert_reconcile_report_clean_passes_after_reindex(self) -> None:
        """assert_reconcile_report_clean returns no violations for a fully-clean report.

        Simulates the expected output of 'library-reconcile' after both
        Class-A soft-delete and Class-B re-index are complete.
        """
        # Simulate a fully-clean reconcile JSON output.
        clean_report = {
            "path_missing_count": 0,
            "items_without_files_count": 0,
            "total_findings": 6655,  # legitimate sidecars only
        }
        violations = assert_reconcile_report_clean(clean_report)
        assert violations == [], f"Expected no violations, got: {violations}"
