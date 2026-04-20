"""Tests for structure_validator module."""

import pytest

from personalscraper.enforce.structure_validator import validate_structure


@pytest.fixture
def settings(tmp_path):
    """Build a mocked Settings object pointing at ``tmp_path`` for isolation."""
    from unittest.mock import MagicMock

    s = MagicMock()
    s.staging_dir = tmp_path
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


def test_movie_extra_nfo_removed(tmp_path, settings):
    """Movie with 2 NFOs: residual removed, correct kept."""
    movie = tmp_path / "001-MOVIES" / "Scream 7 (2026)"
    movie.mkdir(parents=True)
    good = movie / "Scream 7.nfo"
    good.write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    bad = movie / "Scream.7.2026.MULTI.nfo"
    bad.write_text("<movie/>")
    (movie / "Scream 7.mkv").write_bytes(b"\x00")

    results = validate_structure(settings, dry_run=False)
    repaired = [r for r in results if r.action == "repaired"]
    assert len(repaired) == 1
    assert good.exists()
    assert not bad.exists()


def test_movie_duplicate_artwork_legacy_removed(tmp_path, settings):
    """Artwork with same type but different names: keep sanitized, delete legacy."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"good")
    (movie / "Film-poster (1).jpg").write_bytes(b"dup")

    results = validate_structure(settings, dry_run=False)
    repaired = [r for r in results if r.action == "repaired"]
    assert len(repaired) == 1
    assert not (movie / "Film-poster (1).jpg").exists()


def test_tvshow_empty_torrent_subdir_removed(tmp_path, settings):
    """Empty torrent subdirectory removed."""
    show = tmp_path / "002-TVSHOWS" / "Show (2025)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
    empty_dir = show / "Show.S01E01.MULTi.1080p"
    empty_dir.mkdir()

    validate_structure(settings, dry_run=False)
    assert not empty_dir.exists()


def test_clean_movie_no_action(tmp_path, settings):
    """Clean movie → validated, no fixes."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"\x00")
    (movie / "Film-landscape.jpg").write_bytes(b"\x00")

    results = validate_structure(settings, dry_run=False)
    validated = [r for r in results if r.action == "validated"]
    assert len(validated) == 1


def test_idempotent_second_run(tmp_path, settings):
    """Run 2 after fixes → no more repairs."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film.MULTI.nfo").write_text("<movie/>")

    validate_structure(settings, dry_run=False)
    results2 = validate_structure(settings, dry_run=False)
    repaired = [r for r in results2 if r.action == "repaired"]
    assert len(repaired) == 0
