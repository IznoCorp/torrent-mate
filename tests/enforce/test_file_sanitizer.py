"""Tests for file_sanitizer module."""

import pytest

from personalscraper.enforce.file_sanitizer import sanitize_files
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture
def settings(tmp_path):
    """Minimal settings pointing to tmp_path as staging."""
    from unittest.mock import MagicMock

    s = MagicMock()
    s.staging_dir = tmp_path
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


@pytest.fixture
def config():
    """Minimal config mock with canonical staging_dirs."""
    from unittest.mock import MagicMock

    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    return c


def test_renames_colon_file(tmp_path, settings, config):
    """File with : in name → renamed to sanitized version."""
    movies = tmp_path / "001-MOVIES" / "Avatar (2025)"
    movies.mkdir(parents=True)
    colon_file = movies / "Avatar : De feu-poster.jpg"
    colon_file.write_bytes(b"\x00")

    results = sanitize_files(settings, config, dry_run=False)
    renamed = [r for r in results if r.action == "renamed"]
    assert len(renamed) == 1
    assert renamed[0].old_name == "Avatar : De feu-poster.jpg"
    assert not colon_file.exists()
    assert (movies / "Avatar De feu-poster.jpg").exists()


def test_deletes_duplicate_when_sanitized_exists(tmp_path, settings, config):
    """Legacy file with : deleted when sanitized version already exists."""
    movies = tmp_path / "001-MOVIES" / "Avatar (2025)"
    movies.mkdir(parents=True)
    (movies / "Avatar De feu-poster.jpg").write_bytes(b"good")
    (movies / "Avatar : De feu-poster.jpg").write_bytes(b"legacy")

    results = sanitize_files(settings, config, dry_run=False)
    deleted = [r for r in results if r.action == "deleted_duplicate"]
    assert len(deleted) == 1
    assert not (movies / "Avatar : De feu-poster.jpg").exists()
    assert (movies / "Avatar De feu-poster.jpg").read_bytes() == b"good"


def test_renames_directory_with_colon(tmp_path, settings, config):
    """Directory with : in name → renamed."""
    movies = tmp_path / "001-MOVIES"
    movies.mkdir(parents=True)
    bad_dir = movies / "Spirale : L'Héritage de Saw (2021)"
    bad_dir.mkdir()
    (bad_dir / "movie.nfo").write_text("<movie/>")

    results = sanitize_files(settings, config, dry_run=False)
    renamed_dirs = [r for r in results if r.action == "renamed" and "Spirale" in (r.old_name or "")]
    assert len(renamed_dirs) == 1
    assert (movies / "Spirale L'Héritage de Saw (2021)").exists()


def test_deletes_ds_store(tmp_path, settings, config):
    """All .DS_Store files are removed recursively."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    (movies / ".DS_Store").write_bytes(b"\x00")
    actors = movies / ".actors"
    actors.mkdir()
    (actors / ".DS_Store").write_bytes(b"\x00")

    results = sanitize_files(settings, config, dry_run=False)
    ds = [r for r in results if r.action == "deleted_ds_store"]
    assert len(ds) == 2


def test_deletes_resource_forks(tmp_path, settings, config):
    """._* resource fork files are removed."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    (movies / "._Film.mkv").write_bytes(b"\x00")

    results = sanitize_files(settings, config, dry_run=False)
    deleted = [r for r in results if r.action == "deleted_resource_fork"]
    assert len(deleted) == 1


def test_dry_run_no_changes(tmp_path, settings, config):
    """Dry run: report actions but don't modify filesystem."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    colon_file = movies / "Film : Title-poster.jpg"
    colon_file.write_bytes(b"\x00")

    results = sanitize_files(settings, config, dry_run=True)
    assert len(results) > 0
    assert colon_file.exists()


def test_idempotent_second_run(tmp_path, settings, config):
    """Second run after sanitization → 0 actions."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    (movies / "Film : Title-poster.jpg").write_bytes(b"\x00")

    sanitize_files(settings, config, dry_run=False)
    results2 = sanitize_files(settings, config, dry_run=False)
    actions = [r for r in results2 if r.action != "skipped"]
    assert len(actions) == 0
