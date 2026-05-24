"""E2E tests for ``personalscraper library-validate`` — CLI-level harness.

Validates NFO, artwork, naming conformity checks against storage disks.
Covers --from-index path, --fix --apply closure-of-loop, and missing
NFO/poster detection.  Reads results from the JSON output file written by
the command (no --format flag on this command).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _ansi_clean(output: str) -> str:
    """Strip Rich ANSI escape codes for plain-text assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _read_validate_json(tmp_path: Path) -> dict:
    """Read the validation output JSON written by library-validate."""
    output_path = tmp_path / ".data" / "library_validation.json"
    return json.loads(output_path.read_text())


_MOVIE_NFO_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>TestMovie</title>
  <originaltitle>TestMovie Original</originaltitle>
  <year>2020</year>
  <uniqueid type="tmdb">12345</uniqueid>
  <uniqueid type="imdb">tt0123456</uniqueid>
  <plot>A test movie for validation.</plot>
  <genre>Action</genre>
  <country>US</country>
  <streamdetails>
    <video>
      <codec>h264</codec>
      <width>1920</width>
      <height>1080</height>
    </video>
  </streamdetails>
</movie>
"""


def _seed_movie_fs(
    base_dir: Path,
    dirname: str = "TestMovie (2020)",
    *,
    with_nfo: bool = True,
    with_poster: bool = True,
    with_landscape: bool = True,
    with_video: bool = True,
    create_category_file: bool = True,
) -> Path:
    """Create a complete movie directory under *base_dir*, returning its path.

    *base_dir* is expected to be ``<disk>/<category_folder>``.
    """
    movie_dir = base_dir / dirname
    movie_dir.mkdir(parents=True, exist_ok=True)

    if with_video:
        (movie_dir / "movie.mkv").write_bytes(b"f" * (1024 * 1024))  # 1 MB dummy

    if with_nfo:
        title = dirname.split(" (")[0]
        (movie_dir / f"{title}.nfo").write_text(_MOVIE_NFO_XML)

    if with_poster:
        title = dirname.split(" (")[0]
        (movie_dir / f"{title}-poster.jpg").write_text("poster")

    if with_landscape:
        title = dirname.split(" (")[0]
        (movie_dir / f"{title}-landscape.jpg").write_text("landscape")

    if create_category_file:
        (movie_dir / ".category").write_text("movies")

    return movie_dir


# ── 1. Smoke ─────────────────────────────────────────────────────────────────────


def test_validate_help_exits_zero(test_config) -> None:
    """``library-validate --help`` exits 0."""
    result = run_cli(["library-validate", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-validate" in result.output


# ── 2. Clean library ─────────────────────────────────────────────────────────────


def test_validate_clean_library_reports_no_issues(tmp_path, test_config) -> None:
    """Item with NFO + poster + landscape + correct naming → status 'valid'."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Ensure data_dir exists so write_json can write the output file.
    (tmp_path / ".data").mkdir(exist_ok=True)

    # Ensure data_dir exists so write_json can write the output file.
    (tmp_path / ".data").mkdir(exist_ok=True)

    cat_dir = tmp_path / "drive_a" / "cat_movies"
    _seed_movie_fs(cat_dir, "TestMovie (2020)")

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-validate"])

    assert result.exit_code == 0, result.output
    data = _read_validate_json(tmp_path)
    assert data["valid_count"] >= 1, f"Expected >=1 valid, got: {data}"
    assert data["issues_count"] == 0, f"Expected 0 issues, got: {data}"


# ── 3. Missing NFO ───────────────────────────────────────────────────────────────


def test_validate_missing_nfo_reported(tmp_path, test_config) -> None:
    """Item without NFO → flagged as issue."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Ensure data_dir exists so write_json can write the output file.
    (tmp_path / ".data").mkdir(exist_ok=True)

    cat_dir = tmp_path / "drive_a" / "cat_movies"
    _seed_movie_fs(cat_dir, "NoNfo (2015)", with_nfo=False, create_category_file=False)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-validate"])

    assert result.exit_code == 0, result.output
    data = _read_validate_json(tmp_path)
    assert data["issues_count"] >= 1, f"Expected >=1 issue, got: {data}"
    item = data["items"][0]
    assert "nfo_present" in item["errors"], f"Expected nfo_present error, got: {item['errors']}"


# ── 4. Missing poster ────────────────────────────────────────────────────────────


def test_validate_missing_poster_reported(tmp_path, test_config) -> None:
    """Item with NFO but no poster → flagged as issue."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Ensure data_dir exists so write_json can write the output file.
    (tmp_path / ".data").mkdir(exist_ok=True)

    cat_dir = tmp_path / "drive_a" / "cat_movies"
    _seed_movie_fs(cat_dir, "NoPoster (2018)", with_poster=False)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-validate"])

    assert result.exit_code == 0, result.output
    data = _read_validate_json(tmp_path)
    assert data["issues_count"] >= 1, f"Expected >=1 issue, got: {data}"
    item = data["items"][0]
    assert "poster_present" in item["errors"], f"Expected poster_present error, got: {item['errors']}"


# ── 5. --from-index ──────────────────────────────────────────────────────────────


def test_validate_from_index_skips_structural_checks(tmp_path, test_config) -> None:
    """``--from-index`` reads NFO + artwork from DB, skipping FS structural checks.

    Seeds an item with valid nfo_status and artwork_json.  Does NOT create
    any files on disk — structural issues (missing dirs, NTFS chars, etc.)
    would only surface from a filesystem walk.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Ensure data_dir exists so write_json can write the output file.
    (tmp_path / ".data").mkdir(exist_ok=True)

    now = int(time.time())
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    seed_disk(conn, "drive_a", tmp_path / "drive_a")
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "nfo_status, artwork_json, date_created, date_modified) "
        "VALUES ('movie', 'FromIndex', 'FromIndex', 2022, 'movies', "
        "'valid', ?, ?, ?)",
        (
            json.dumps({"poster": True, "landscape": True, "fanart": True}),
            now,
            now,
        ),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_disk', 'drive_a')",
        (item_id,),
    )
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', '/nonexistent/FromIndex (2022)')",
        (item_id,),
    )
    conn.commit()
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-validate", "--from-index"])

    assert result.exit_code == 0, result.output
    data = _read_validate_json(tmp_path)
    assert data["valid_count"] >= 1, f"Expected valid item via --from-index, got: {data}"
    assert data["issues_count"] == 0, f"Expected 0 issues via --from-index, got: {data}"


# ── 6. --fix --apply closure-of-loop (CRITICAL) ──────────────────────────────────


def test_validate_fix_apply_corrects_issue(tmp_path, test_config) -> None:
    """Seed issue (empty subdir) → validate finds it → --fix --apply removes it → re-validate = 0.

    Closure-of-loop: the fix must ACTUALLY resolve the issue so a follow-up
    validate reports zero findings.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Ensure data_dir exists so write_json can write the output file.
    (tmp_path / ".data").mkdir(exist_ok=True)

    cat_dir = tmp_path / "drive_a" / "cat_movies"
    movie_dir = _seed_movie_fs(cat_dir, "FixMe (2023)")
    empty_sub = movie_dir / "empty_extra"
    empty_sub.mkdir()

    # ── Phase 1: detect the issue ──
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["library-validate"])

    assert r1.exit_code == 0, r1.output
    d1 = _read_validate_json(tmp_path)
    assert d1["issues_count"] >= 1, f"Expected >=1 issue (empty dir) before fix, got: {d1}"

    # ── Phase 2: fix it ──
    # Remove the previous JSON output so we read the new one.
    (tmp_path / ".data" / "library_validation.json").unlink()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(["library-validate", "--fix", "--apply"])

    assert r2.exit_code == 0, r2.output
    d2 = _read_validate_json(tmp_path)
    assert d2["fixed_count"] >= 1, f"Expected >=1 fixed, got: {d2}"
    assert not empty_sub.exists(), f"Fix did not remove empty dir: {empty_sub}"

    # ── Phase 3: closure-of-loop — re-validate finds zero ──
    (tmp_path / ".data" / "library_validation.json").unlink()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r3 = run_cli(["library-validate"])

    assert r3.exit_code == 0, r3.output
    d3 = _read_validate_json(tmp_path)
    assert d3["issues_count"] == 0, f"CLOSURE-OF-LOOP BROKEN: {d3['issues_count']} issues remain after fix: {d3}"
    assert d3["valid_count"] >= 1, f"Expected valid_count >= 1 after fix, got: {d3}"
