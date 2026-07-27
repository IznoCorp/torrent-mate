"""Tests for structure_validator module."""

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.enforce.structure_validator import validate_structure
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture
def settings():
    """Minimal settings mock (staging resolved from config.paths)."""
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def config(tmp_path):
    """Minimal config mock with canonical staging_dirs and staging path."""
    from unittest.mock import MagicMock

    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    return c


def test_movie_extra_nfo_removed(tmp_path, settings, config):
    """Movie with 2 NFOs: residual removed, correct kept."""
    movie = tmp_path / "001-MOVIES" / "Scream 7 (2026)"
    movie.mkdir(parents=True)
    good = movie / "Scream 7.nfo"
    good.write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    bad = movie / "Scream.7.2026.MULTI.nfo"
    bad.write_text("<movie/>")
    (movie / "Scream 7.mkv").write_bytes(b"\x00")

    results = validate_structure(settings, config, dry_run=False, bus=EventBus())
    repaired = [r for r in results if r.action == "repaired"]
    assert len(repaired) == 1
    assert good.exists()
    assert not bad.exists()


def test_movie_valid_misnamed_nfo_renamed_not_deleted(tmp_path, settings, config):
    """A valid identification under a non-canonical name is RENAMED to canonical, not deleted.

    Regression (operator loop): a manual resolve wrote "Obsession (2026).nfo" (with the
    year) into "Obsession (2026)/"; enforce used to delete it as an 'extra NFO', silently
    re-un-identifying the movie every pipeline run. The pipeline must NEVER overwrite an
    identification — a NFO carrying a <uniqueid> is preserved (renamed to canonical here).
    """
    movie = tmp_path / "001-MOVIES" / "Obsession (2026)"
    movie.mkdir(parents=True)
    manual = movie / "Obsession (2026).nfo"  # valid identification, non-canonical name
    manual.write_text('<movie><uniqueid type="tmdb">1339713</uniqueid></movie>')
    (movie / "Obsession (2026).mkv").write_bytes(b"\x00")

    validate_structure(settings, config, dry_run=False, bus=EventBus())

    # The identification survives — renamed to the canonical name verify expects,
    # never deleted.
    assert not manual.exists()  # old misnamed file moved, not left behind
    canonical = movie / "Obsession.nfo"
    assert canonical.exists(), "the valid NFO must survive (renamed to canonical), never deleted"
    assert "1339713" in canonical.read_text(encoding="utf-8")


def test_movie_duplicate_artwork_legacy_removed(tmp_path, settings, config):
    """Artwork with same type but different names: keep sanitized, delete legacy."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"good")
    (movie / "Film-poster (1).jpg").write_bytes(b"dup")

    results = validate_structure(settings, config, dry_run=False, bus=EventBus())
    repaired = [r for r in results if r.action == "repaired"]
    assert len(repaired) == 1
    assert not (movie / "Film-poster (1).jpg").exists()


def test_tvshow_empty_torrent_subdir_removed(tmp_path, settings, config):
    """Empty torrent subdirectory removed."""
    show = tmp_path / "002-TVSHOWS" / "Show (2025)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
    empty_dir = show / "Show.S01E01.MULTi.1080p"
    empty_dir.mkdir()

    validate_structure(settings, config, dry_run=False, bus=EventBus())
    assert not empty_dir.exists()


def test_clean_movie_no_action(tmp_path, settings, config):
    """Clean movie → validated, no fixes."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"\x00")
    (movie / "Film-landscape.jpg").write_bytes(b"\x00")

    results = validate_structure(settings, config, dry_run=False, bus=EventBus())
    validated = [r for r in results if r.action == "validated"]
    assert len(validated) == 1


def test_idempotent_second_run(tmp_path, settings, config):
    """Run 2 after fixes → no more repairs."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film.MULTI.nfo").write_text("<movie/>")

    validate_structure(settings, config, dry_run=False, bus=EventBus())
    results2 = validate_structure(settings, config, dry_run=False, bus=EventBus())
    repaired = [r for r in results2 if r.action == "repaired"]
    assert len(repaired) == 0
