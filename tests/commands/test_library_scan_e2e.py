"""E2E tests for ``personalscraper library-scan`` — CLI-level harness.

Covers smoke, dry-run, NFO-based media_item creation, --disk filter,
idempotence, and hidden-dir skipping.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_json_schema,
    assert_no_python_traceback,
    capture_event_bus,
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_GUARD = "personalscraper.indexer.scanner.guard_disk_mounted"

# ── helpers ───────────────────────────────────────────────────────────────────


def _tvshow_nfo_xml(tvdb_id: str = "12345", title: str = "My Show") -> str:
    """Return a valid tvshow.nfo XML string."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tvshow>\n"
        f"  <title>{title}</title>\n"
        f'  <uniqueid type="tvdb" default="true">{tvdb_id}</uniqueid>\n'
        '  <uniqueid type="tmdb">67890</uniqueid>\n'
        "</tvshow>\n"
    )


def _movie_nfo_xml(tmdb_id: str = "11111", title: str = "My Movie") -> str:
    """Return a valid movie.nfo XML string."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<movie>\n"
        f"  <title>{title}</title>\n"
        f'  <uniqueid type="tmdb" default="true">{tmdb_id}</uniqueid>\n'
        "</movie>\n"
    )


def _create_tvshow_on_disk(base: Path, show_name: str = "My Show (2020)", tvdb_id: str = "12345") -> Path:
    """Create a TV show dir with tvshow.nfo under base. Return the show dir."""
    show_dir = base / show_name
    show_dir.mkdir(parents=True)
    (show_dir / "tvshow.nfo").write_text(_tvshow_nfo_xml(tvdb_id, show_name.split(" (")[0]))
    return show_dir


def _create_movie_on_disk(base: Path, movie_name: str = "My Movie (2020)", tmdb_id: str = "11111") -> Path:
    """Create a movie dir with {title}.nfo under base. Return the movie dir."""
    movie_dir = base / movie_name
    movie_dir.mkdir(parents=True)
    title = movie_name.split(" (")[0]
    (movie_dir / f"{title}.nfo").write_text(_movie_nfo_xml(tmdb_id, title))
    return movie_dir


def _run_scan(args: list[str], config, db_path):
    """Run ``library-scan`` with config + guard patched, return CliRunner Result."""
    cfg = make_test_config_with_db(config, db_path)
    with (
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_GUARD, return_value=None),
    ):
        return run_cli(["library-scan", *args])


def _pre_seed_disk(db_path: Path, label: str, mount: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, label, mount)
    conn.close()
    return disk_id


# ── 1. Smoke ─────────────────────────────────────────────────────────────────


def test_scan_help_exits_zero() -> None:
    """``library-scan --help`` exits 0."""
    result = run_cli(["library-scan", "--help"])
    assert result.exit_code == 0


# ── 2. Dry-run ───────────────────────────────────────────────────────────────


def test_scan_dry_run_lists_without_writes(tmp_path, test_config) -> None:
    """Dry-run counts media dirs but does not write to DB."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    # Create a category dir with one TV show inside
    cat_dir = mount / "cat_tv_shows"
    _create_tvshow_on_disk(cat_dir, "My Show (2020)")
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-scan", "--dry-run"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["dry_run"] is True
    assert data["media_dirs_to_scan"] >= 1, f"Expected >=1 media dir, got {data}"

    # Verify no media_item rows were created.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    conn.close()
    assert count == 0, f"Dry-run should not write media_item, got {count}"


# ── 3. Realistic scan ────────────────────────────────────────────────────────


def test_scan_creates_media_items_from_nfo(tmp_path, test_config) -> None:
    """Scanning a TV show dir with a valid tvshow.nfo creates a media_item row."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _pre_seed_disk(db_path, "drive_a", mount)
    cat_dir = mount / "cat_tv_shows"
    _create_tvshow_on_disk(cat_dir, "My Show (2020)", tvdb_id="12345")

    result = _run_scan([], test_config, db_path)
    assert result.exit_code == 0, result.output

    # Verify media_item was created.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    items = conn.execute("SELECT kind, title, year, canonical_provider, nfo_status FROM media_item").fetchall()
    conn.close()
    assert len(items) >= 1, f"Expected at least 1 media_item, got {items}"
    item = items[0]
    assert item[0] == "show"  # kind
    # Title is parsed from "My Show (2020)" → "My Show" (year extracted separately)
    assert item[1] == "My Show"
    assert item[3] == "tvdb" or item[3] is None  # canonical_provider may be set or None


def test_scan_disk_filter_restricts_to_one_disk(tmp_path, test_config) -> None:
    """--disk flag only scans the requested disk."""
    db_path = make_synthetic_db(tmp_path)
    mount_a = tmp_path / "drive_a"
    mount_b = tmp_path / "drive_b"
    _pre_seed_disk(db_path, "drive_a", mount_a)
    _pre_seed_disk(db_path, "drive_b", mount_b)

    # Create TV shows on both disks
    _create_tvshow_on_disk(mount_a / "cat_tv_shows", "Show A (2022)")
    _create_tvshow_on_disk(mount_b / "cat_tv_shows_animation", "Show B (2023)")

    # Scan only drive_a.
    result = _run_scan(["--disk", "drive_a"], test_config, db_path)
    assert result.exit_code == 0, result.output

    # Only Show A should exist, not Show B.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    titles = [r[0] for r in conn.execute("SELECT title FROM media_item").fetchall()]
    conn.close()
    assert any("Show A" in t for t in titles), f"Show A should be present: {titles}"
    assert not any("Show B" in t for t in titles), f"Show B should be absent (filtered by --disk drive_a): {titles}"


# ── 4. Idempotence ───────────────────────────────────────────────────────────


def test_scan_idempotent_on_rerun(tmp_path, test_config) -> None:
    """Re-scanning the same directory produces the same item count."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _pre_seed_disk(db_path, "drive_a", mount)
    _create_tvshow_on_disk(mount / "cat_tv_shows", "My Show (2020)")

    # First scan.
    r1 = _run_scan([], test_config, db_path)
    assert r1.exit_code == 0, r1.output

    # Count items after first scan.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    count1 = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    conn.close()

    # Second scan.
    r2 = _run_scan([], test_config, db_path)
    assert r2.exit_code == 0, r2.output

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    count2 = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    conn.close()

    assert count2 == count1, f"Re-scan should be idempotent: {count1} → {count2}"


# ── 5. Hidden dirs ───────────────────────────────────────────────────────────


def test_scan_skips_hidden_dirs(tmp_path, test_config) -> None:
    """Directories starting with '.' are skipped by the scanner."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _pre_seed_disk(db_path, "drive_a", mount)
    cat_dir = mount / "cat_tv_shows"

    # Visible show — should be picked up.
    _create_tvshow_on_disk(cat_dir, "My Show (2020)")
    # Hidden dir — should be skipped.
    hidden = cat_dir / ".Trashes"
    hidden.mkdir(parents=True)
    (hidden / "tvshow.nfo").write_text(_tvshow_nfo_xml())

    result = _run_scan([], test_config, db_path)
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    titles = [r[0] for r in conn.execute("SELECT title FROM media_item").fetchall()]
    conn.close()
    assert len(titles) == 1, f"Expected only 1 media_item (hidden .Trashes skipped), got {titles}"


# ── 6. Errors ──


def test_scan_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-scan", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_scan_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with (
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_GUARD, return_value=None),
    ):
        result = run_cli(["library-scan"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_scan_nonexistent_disk_exits_gracefully(tmp_path, test_config) -> None:
    """``--disk`` pointing to a non-existent disk → friendly error, no traceback."""
    db_path = make_synthetic_db(tmp_path)
    result = _run_scan(["--disk", "nonexistent_disk_xyz123"], test_config, db_path)
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 7. Output ──


def test_scan_json_schema_valid(tmp_path, test_config) -> None:
    """``--format json`` output matches expected schema (live mode)."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _pre_seed_disk(db_path, "drive_a", mount)
    cat_dir = mount / "cat_tv_shows"
    _create_tvshow_on_disk(cat_dir, "Test Show (2022)")

    result = _run_scan([], test_config, db_path)
    assert result.exit_code == 0
    assert_json_schema(result, required_keys=["status", "disk_filter"])


def test_scan_error_exits_nonzero(tmp_path, test_config) -> None:
    """Non-existent disk → non-zero exit code."""
    db_path = make_synthetic_db(tmp_path)
    result = _run_scan(["--disk", "nonexistent_disk_xyz123"], test_config, db_path)
    assert result.exit_code != 0


# ── 8. Events ──


def test_scan_emits_library_scan_completed(tmp_path, test_config, monkeypatch) -> None:
    """Scanner emits ``LibraryScanCompleted`` on the EventBus."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _pre_seed_disk(db_path, "drive_a", mount)
    cat_dir = mount / "cat_tv_shows"
    _create_tvshow_on_disk(cat_dir, "Test Show (2022)")

    captured = capture_event_bus(monkeypatch)

    result = _run_scan([], test_config, db_path)
    assert result.exit_code == 0, result.output

    assert len(captured) >= 1, f"Expected at least 1 event, got {len(captured)}"
    event_types = {type(e).__name__ for e in captured}
    assert "LibraryScanCompleted" in event_types, f"LibraryScanCompleted not emitted. Captured: {event_types}"
