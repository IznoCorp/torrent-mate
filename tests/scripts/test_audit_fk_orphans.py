"""Tests for scripts/audit-fk-orphans.py (SH-5 / BD-AE — Phase 4.4).

Coverage:
- Script exists at the documented path.
- Script is syntactically importable.
- ``audit_all`` returns zero orphans on a clean, fully-migrated DB.
- ``audit_all`` detects a seeded FK orphan (media_release → media_item).
- ``audit_all`` detects a seeded orphan on a nullable FK (media_file.release_id → media_release).
- ``main()`` exits 0 on a clean DB.
- ``main()`` exits 1 when at least one orphan is present.
- ``main()`` exits 2 on a non-existent DB path.

Regression pin (SH-5):
  The script must detect orphans that bypass ``open_db`` (raw sqlite3.connect
  with FK enforcement OFF) — exactly the scenario ``open_db`` boot-checks for.
  Without this independent audit tool, the only feedback path is the
  IndexerFKOrphansError raised at boot which prevents the indexer from starting
  at all; operators need a way to *inspect* before *fixing*.
"""

from __future__ import annotations

import importlib.util as _util
import sqlite3
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate and import the script under test (hyphen in filename → importlib)
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit-fk-orphans.py"

_spec = _util.spec_from_file_location("audit_fk_orphans", SCRIPT)
assert _spec is not None, f"Could not load spec from {SCRIPT}"
_mod = _util.module_from_spec(_spec)
assert _spec.loader is not None
# Register in sys.modules BEFORE exec_module so @dataclass(frozen=True) can
# resolve cls.__module__ back to sys.modules — without this the decorator
# raises AttributeError: 'NoneType' object has no attribute '__dict__'.
sys.modules["audit_fk_orphans"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

audit_all = _mod.audit_all
main = _mod.main
FKConstraint = _mod.FKConstraint
OrphanRow = _mod.OrphanRow
ConstraintReport = _mod.ConstraintReport

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "personalscraper" / "indexer" / "migrations"


def _make_migrated_db(tmp_path: Path) -> Path:
    """Create a fully-migrated SQLite DB and return its path.

    Uses a raw ``sqlite3.connect`` (not ``open_db``) so that the boot-guard
    in ``open_db`` does not interfere with test setup.

    Args:
        tmp_path: pytest tmp_path fixture for DB file placement.

    Returns:
        Path to the created and migrated database file.
    """
    from personalscraper.indexer.db import apply_migrations  # noqa: PLC0415

    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    # Keep FK OFF during migration (migration 002 requires it for table recreation).
    apply_migrations(conn, _MIGRATIONS_DIR)
    conn.close()
    return db_path


def _open_raw(db_path: Path) -> sqlite3.Connection:
    """Open DB with FK enforcement OFF — mimics a script bypassing open_db.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=OFF``.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def _seed_disk(conn: sqlite3.Connection, label: str = "DiskA") -> int:
    """Insert a minimal disk row and return its id.

    Args:
        conn: Open SQLite connection.
        label: Disk label (also used as UUID to keep tests isolated).

    Returns:
        The ``disk.id`` of the inserted row.
    """
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (label, label, f"/tmp/{label}", int(time.time())),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_item(conn: sqlite3.Connection, *, title: str = "Test Movie", kind: str = "movie") -> int:
    """Insert a minimal media_item row and return its id.

    Args:
        conn: Open SQLite connection.
        title: Title for the item.
        kind: ``'movie'`` or ``'show'``.

    Returns:
        The ``media_item.id`` of the inserted row.
    """
    now = int(time.time())
    cur = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, category_id,
            date_created, date_modified, is_locked, preferred_lang
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 'fr')
        """,
        (kind, title, title, "movies" if kind == "movie" else "tv_shows", now, now),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_release(conn: sqlite3.Connection, item_id: int) -> int:
    """Insert a minimal media_release linked to *item_id* and return its id.

    Args:
        conn: Open SQLite connection.
        item_id: FK to ``media_item.id``.

    Returns:
        The ``media_release.id`` of the inserted row.
    """
    cur = conn.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (?, NULL, NULL, NULL, NULL)",
        (item_id,),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


# ---------------------------------------------------------------------------
# 1 — Script discovery
# ---------------------------------------------------------------------------


def test_script_exists() -> None:
    """The audit script exists at its documented path."""
    assert SCRIPT.is_file(), f"Script not found at {SCRIPT}"


def test_script_importable() -> None:
    """The script can be imported without syntax errors (already done at module level)."""
    assert audit_all is not None
    assert main is not None


# ---------------------------------------------------------------------------
# 2 — Zero orphans on a clean DB (regression pin: clean path must never break)
# ---------------------------------------------------------------------------


def test_audit_all_clean_db_returns_no_orphans(tmp_path: Path) -> None:
    """A freshly migrated DB has zero FK orphans across all constraints.

    Regression pin: the audit must NOT produce false positives on a valid DB.
    This is the most critical guard — if this fails, every operator run would
    report phantom orphans and destroy confidence in the tool.
    """
    db_path = _make_migrated_db(tmp_path)
    conn = _open_raw(db_path)
    try:
        reports = audit_all(conn)
    finally:
        conn.close()

    all_orphans = [o for r in reports for o in r.orphans]
    assert all_orphans == [], f"Expected zero orphans on a clean DB, got {len(all_orphans)}: {all_orphans}"


def test_audit_all_clean_db_all_constraints_checked(tmp_path: Path) -> None:
    """audit_all runs all constraints and all return is_clean=True on a fresh DB.

    Verifies completeness: if a constraint is accidentally skipped the count
    would be lower than the known catalogue size.
    """
    db_path = _make_migrated_db(tmp_path)
    conn = _open_raw(db_path)
    try:
        reports = audit_all(conn)
    finally:
        conn.close()

    assert len(reports) > 0, "audit_all returned an empty list — catalogue is empty"
    dirty = [r for r in reports if not r.is_clean]
    assert dirty == [], f"Expected all clean, got dirty constraints: {[r.constraint.description for r in dirty]}"


# ---------------------------------------------------------------------------
# 3 — Orphan detection: non-nullable FK (media_release.item_id → media_item)
# ---------------------------------------------------------------------------


def test_audit_detects_orphan_release_item_id(tmp_path: Path) -> None:
    """Seeding a media_release with a bogus item_id must be detected as an orphan.

    Scenario: bypass open_db (FK OFF), insert media_release.item_id=99999
    (no such media_item row), then run audit_all.  The constraint
    ``media_release.item_id → media_item.id`` must report one orphan.

    Regression pin (SH-5): this is the canonical example of orphans that
    Phase 1.2 added the boot-guard for.  The audit script must independently
    confirm the same finding without triggering the boot-guard abort.
    """
    db_path = _make_migrated_db(tmp_path)

    # Insert orphan via raw connection with FK OFF
    raw = _open_raw(db_path)
    try:
        raw.execute(
            "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
            "VALUES (99999, NULL, NULL, NULL, NULL)"
        )
    finally:
        raw.close()

    # Audit must find it
    conn = _open_raw(db_path)
    try:
        reports = audit_all(conn)
    finally:
        conn.close()

    release_item_reports = [
        r for r in reports if r.constraint.child_table == "media_release" and r.constraint.fk_column == "item_id"
    ]
    assert len(release_item_reports) == 1, "Expected exactly one report for media_release.item_id"
    report = release_item_reports[0]
    assert not report.is_clean, "Expected the report to be dirty (orphan present)"
    assert len(report.orphans) == 1, f"Expected 1 orphan, got {len(report.orphans)}"
    orphan = report.orphans[0]
    assert orphan.fk_value == 99999, f"Expected fk_value=99999, got {orphan.fk_value}"
    assert orphan.child_table == "media_release"
    assert orphan.fk_column == "item_id"


# ---------------------------------------------------------------------------
# 4 — Nullable FK: NULL values must NOT be counted as orphans
# ---------------------------------------------------------------------------


def test_audit_nullable_fk_null_not_counted_as_orphan(tmp_path: Path) -> None:
    """NULL values in a nullable FK column are valid and must not be flagged.

    media_file.release_id is nullable (migration 002 ON DELETE SET NULL).
    A media_file with release_id=NULL is a Stage-A file awaiting release linkage
    — it is NOT an orphan.
    """
    db_path = _make_migrated_db(tmp_path)

    raw = _open_raw(db_path)
    try:
        disk_id = _seed_disk(raw, "DiskNullable")
        raw.execute(
            "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
            (disk_id, "001-MOVIES/NullReleaseMovie"),
        )
        path_id = raw.execute(
            "SELECT id FROM path WHERE disk_id=? AND rel_path=?",
            (disk_id, "001-MOVIES/NullReleaseMovie"),
        ).fetchone()[0]
        now = int(time.time())
        # Insert file with release_id=NULL (Stage-A, no release yet)
        raw.execute(
            """
            INSERT INTO media_file (
                release_id, path_id, filename, size_bytes, mtime_ns,
                oshash, scan_generation, last_verified_at
            ) VALUES (NULL, ?, ?, 1000, ?, NULL, 1, ?)
            """,
            (path_id, "movie.mkv", now * 1_000_000_000, now),
        )
    finally:
        raw.close()

    conn = _open_raw(db_path)
    try:
        reports = audit_all(conn)
    finally:
        conn.close()

    # media_file.release_id=NULL must not appear as an orphan
    release_reports = [
        r for r in reports if r.constraint.child_table == "media_file" and r.constraint.fk_column == "release_id"
    ]
    assert len(release_reports) == 1
    report = release_reports[0]
    assert report.is_clean, f"NULL release_id should NOT be an orphan, but got {report.orphans}"


# ---------------------------------------------------------------------------
# 5 — Nullable FK: non-NULL dangling value IS an orphan
# ---------------------------------------------------------------------------


def test_audit_detects_orphan_nullable_fk_with_dangling_value(tmp_path: Path) -> None:
    """A non-NULL dangling release_id in media_file is a real orphan.

    media_file.release_id=NULL → valid (Stage A, no release linked yet).
    media_file.release_id=99999 where no media_release row 99999 exists → orphan.
    The audit must distinguish these two cases.
    """
    db_path = _make_migrated_db(tmp_path)

    raw = _open_raw(db_path)
    try:
        disk_id = _seed_disk(raw, "DiskDangling")
        raw.execute(
            "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
            (disk_id, "001-MOVIES/DanglingReleaseMovie"),
        )
        path_id = raw.execute(
            "SELECT id FROM path WHERE disk_id=? AND rel_path=?",
            (disk_id, "001-MOVIES/DanglingReleaseMovie"),
        ).fetchone()[0]
        now = int(time.time())
        # Insert file with a bogus release_id (non-NULL dangling reference)
        raw.execute(
            """
            INSERT INTO media_file (
                release_id, path_id, filename, size_bytes, mtime_ns,
                oshash, scan_generation, last_verified_at
            ) VALUES (99999, ?, ?, 1000, ?, NULL, 1, ?)
            """,
            (path_id, "movie.mkv", now * 1_000_000_000, now),
        )
    finally:
        raw.close()

    conn = _open_raw(db_path)
    try:
        reports = audit_all(conn)
    finally:
        conn.close()

    release_reports = [
        r for r in reports if r.constraint.child_table == "media_file" and r.constraint.fk_column == "release_id"
    ]
    assert len(release_reports) == 1
    report = release_reports[0]
    assert not report.is_clean, "Dangling non-NULL release_id must be flagged as an orphan"
    assert len(report.orphans) == 1
    assert report.orphans[0].fk_value == 99999


# ---------------------------------------------------------------------------
# 6 — main() exit codes
# ---------------------------------------------------------------------------


def test_main_exits_0_on_clean_db(tmp_path: Path) -> None:
    """main() returns 0 for a clean, fully-migrated database."""
    db_path = _make_migrated_db(tmp_path)
    exit_code = main([str(db_path)])
    assert exit_code == 0, f"Expected exit code 0 on clean DB, got {exit_code}"


def test_main_exits_1_on_orphan_db(tmp_path: Path) -> None:
    """main() returns 1 when at least one FK orphan is present.

    This verifies the operator-visible exit-code contract:
    non-zero exit = action required.
    """
    db_path = _make_migrated_db(tmp_path)

    # Seed an orphan via raw connection
    raw = _open_raw(db_path)
    try:
        raw.execute(
            "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
            "VALUES (55555, NULL, NULL, NULL, NULL)"
        )
    finally:
        raw.close()

    exit_code = main([str(db_path)])
    assert exit_code == 1, f"Expected exit code 1 when orphans present, got {exit_code}"


def test_main_exits_2_on_missing_db(tmp_path: Path) -> None:
    """main() returns 2 when the specified DB path does not exist."""
    missing = tmp_path / "does_not_exist.db"
    with pytest.raises(SystemExit) as exc_info:
        main([str(missing)])
    assert exc_info.value.code == 2, f"Expected SystemExit(2) for missing DB path, got {exc_info.value.code}"


def test_main_exits_2_on_extra_args(tmp_path: Path) -> None:
    """main() exits 2 when more than one positional argument is provided."""
    db_path = _make_migrated_db(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        main([str(db_path), "extra_arg"])
    assert exc_info.value.code == 2, f"Expected SystemExit(2) for extra args, got {exc_info.value.code}"


# ---------------------------------------------------------------------------
# 7 — Multiple orphans across different constraints
# ---------------------------------------------------------------------------


def test_audit_detects_multiple_orphans_across_constraints(tmp_path: Path) -> None:
    """Seeding orphans in two different FK constraints both appear in the report."""
    db_path = _make_migrated_db(tmp_path)

    raw = _open_raw(db_path)
    try:
        # Orphan 1: media_release.item_id → media_item (non-existent)
        raw.execute(
            "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
            "VALUES (88888, NULL, NULL, NULL, NULL)"
        )

        # Orphan 2: path.disk_id → disk (non-existent)
        raw.execute("INSERT INTO path (disk_id, rel_path) VALUES (77777, 'orphan/path')")
    finally:
        raw.close()

    conn = _open_raw(db_path)
    try:
        reports = audit_all(conn)
    finally:
        conn.close()

    dirty = [r for r in reports if not r.is_clean]
    dirty_descriptions = {r.constraint.description for r in dirty}

    # At least two distinct constraints must show orphans
    assert len(dirty) >= 2, f"Expected ≥2 dirty constraints, got {len(dirty)}: {dirty_descriptions}"

    # Verify the specific constraints we seeded
    has_release_orphan = any(
        r.constraint.child_table == "media_release" and r.constraint.fk_column == "item_id" for r in dirty
    )
    has_path_orphan = any(r.constraint.child_table == "path" and r.constraint.fk_column == "disk_id" for r in dirty)
    assert has_release_orphan, "Expected media_release.item_id orphan in dirty reports"
    assert has_path_orphan, "Expected path.disk_id orphan in dirty reports"
