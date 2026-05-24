"""E2E tests for ``personalscraper library-clean`` — CLI-level harness.

Validates dry-run-by-default invariant: the default invocation must NEVER
delete anything from the filesystem.  Covers .actors/ removal, empty dirs,
junk files, --only / --disk filters, and mutual-exclusion of --apply/--dry-run.
"""

from __future__ import annotations

import re
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _ansi_clean(output: str) -> str:
    """Strip Rich ANSI escape codes for plain-text assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _setup_movie_with_actors(tmp_path, test_config):
    """Create drive_a/cat_movies/TestMovie/.actors/dummy.txt and return the actors path."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    drive_a = tmp_path / "drive_a"
    movie_dir = drive_a / "cat_movies" / "TestMovie (2020)"
    actors_dir = movie_dir / ".actors"
    actors_dir.mkdir(parents=True)
    (actors_dir / "dummy.txt").write_text("actor thumb content")
    (movie_dir / "test.mkv").write_bytes(b"fake video content")

    return cfg, actors_dir, db_path


# ── 1. Smoke ─────────────────────────────────────────────────────────────────────


def test_clean_help_exits_zero(test_config) -> None:
    """``library-clean --help`` exits 0."""
    result = run_cli(["library-clean", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-clean" in result.output


# ── 2. Empty storage ────────────────────────────────────────────────────────────


def test_clean_empty_storage_zero_actions(tmp_path, test_config) -> None:
    """No media directories exist → zero deletions reported."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Drive directories exist but category subdirs do not.
    (tmp_path / "drive_a").mkdir(exist_ok=True)
    (tmp_path / "drive_b").mkdir(exist_ok=True)
    (tmp_path / "drive_c").mkdir(exist_ok=True)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean"])

    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    assert "Would delete 0 items" in clean, f"Expected 0 items deleted, got: {clean}"


# ── 3. Dry-run safety (CRITICAL) ────────────────────────────────────────────────


def test_clean_dry_run_no_writes_actors_dir(tmp_path, test_config) -> None:
    """Default invocation (no ``--apply``) MUST NOT delete the .actors/ directory."""
    cfg, actors_dir, _ = _setup_movie_with_actors(tmp_path, test_config)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean"])

    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    assert "DRY-RUN" in clean, f"Expected DRY-RUN marker, got: {clean}"
    assert "Would delete" in clean, f"Expected 'Would delete', got: {clean}"

    # The .actors/ dir MUST still exist.
    assert actors_dir.exists(), f"DRY-RUN leaked deletion: {actors_dir} no longer exists"
    assert (actors_dir / "dummy.txt").exists(), "DRY-RUN leaked deletion of file inside .actors/"


# ── 4. Apply mode ───────────────────────────────────────────────────────────────


def test_clean_apply_removes_actors_dir(tmp_path, test_config) -> None:
    """``--apply`` deletes the .actors/ directory."""
    cfg, actors_dir, _ = _setup_movie_with_actors(tmp_path, test_config)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply"])

    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    assert "Deleted:" in clean, result.output

    # The .actors/ dir MUST be gone.
    assert not actors_dir.exists(), f"--apply did not delete .actors/: still exists at {actors_dir}"


# ── 5. --only filter ────────────────────────────────────────────────────────────


def test_clean_only_filter_restricts_scope(tmp_path, test_config) -> None:
    """``--only actors`` removes .actors/ but NOT empty dirs or junk files."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    drive_a = tmp_path / "drive_a"
    movie_dir = drive_a / "cat_movies" / "TestMovie (2020)"
    actors_dir = movie_dir / ".actors"
    actors_dir.mkdir(parents=True)
    (actors_dir / "thumb.jpg").write_text("thumb")
    (movie_dir / "test.mkv").write_bytes(b"fake video")

    # Also create an empty dir and a junk file in the same movie dir.
    empty_subdir = movie_dir / "empty_subdir"
    empty_subdir.mkdir()
    junk_file = movie_dir / ".DS_Store"
    junk_file.write_text("junk")

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply", "--only", "actors"])

    assert result.exit_code == 0, result.output

    # .actors/ removed.
    assert not actors_dir.exists(), f".actors/ should be removed, but exists at {actors_dir}"

    # Empty dir NOT removed.
    assert empty_subdir.exists(), f"--only actors leaked to empty dirs: {empty_subdir} was removed"

    # Junk file NOT removed.
    assert junk_file.exists(), f"--only actors leaked to junk files: {junk_file} was removed"


# ── 6. --disk filter ────────────────────────────────────────────────────────────


def test_clean_disk_filter_restricts_scope(tmp_path, test_config) -> None:
    """``--disk drive_a`` only cleans drive_a, NOT drive_b."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # drive_a: .actors/ dir
    drive_a = tmp_path / "drive_a"
    actors_a = drive_a / "cat_movies" / "MovieA (2020)" / ".actors"
    actors_a.mkdir(parents=True)
    (actors_a / "dummy.txt").write_text("actor")

    # drive_b: .actors/ dir
    drive_b = tmp_path / "drive_b"
    actors_b = drive_b / "cat_movies_animation" / "MovieB (2020)" / ".actors"
    actors_b.mkdir(parents=True)
    (actors_b / "dummy.txt").write_text("actor")

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply", "--disk", "drive_a"])

    assert result.exit_code == 0, result.output

    # drive_a actors removed.
    assert not actors_a.exists(), f"drive_a .actors/ should be removed, but exists at {actors_a}"

    # drive_b actors NOT removed.
    assert actors_b.exists(), f"--disk drive_a leaked to drive_b: {actors_b} was removed"


# ── 7. Mutual exclusion ─────────────────────────────────────────────────────────


def test_clean_apply_mutually_exclusive_with_dry_run(tmp_path, test_config) -> None:
    """Passing both ``--apply`` and ``--dry-run`` exits non-zero."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply", "--dry-run"])

    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}: {result.output}"
    assert "mutually exclusive" in result.output.lower(), result.output
