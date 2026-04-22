"""Tests for coherence_checker module."""

import pytest

from personalscraper.enforce.coherence_checker import check_coherence


@pytest.fixture
def settings(tmp_path):
    """Build a mocked Settings object pointing at ``tmp_path`` for isolation."""
    from unittest.mock import MagicMock

    s = MagicMock()
    s.staging_dir = tmp_path
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


def test_tvshow_in_movies_warns(tmp_path, settings, test_config):
    """tvshow.nfo in 001-MOVIES → warning."""
    movie = tmp_path / "001-MOVIES" / "Fake Show (2026)"
    movie.mkdir(parents=True)
    (movie / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')

    results = check_coherence(settings, test_config, dry_run=False)
    warns = [w for r in results for w in r.warnings if "wrong category" in w.lower()]
    assert len(warns) >= 1


def test_nfo_missing_both_ids_warns(tmp_path, settings, test_config):
    """NFO without TMDB or IMDB ID → warning."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text("<movie><title>Film</title></movie>")

    results = check_coherence(settings, test_config, dry_run=False)
    warns = [w for r in results for w in r.warnings if "missing" in w.lower() and "id" in w.lower()]
    assert len(warns) >= 1


def test_clean_items_no_warnings(tmp_path, settings, test_config):
    """Properly structured items → no warnings."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text(
        '<movie><uniqueid type="tmdb">123</uniqueid><uniqueid type="imdb">tt123</uniqueid></movie>'
    )

    results = check_coherence(settings, test_config, dry_run=False)
    warns = [w for r in results for w in r.warnings]
    assert len(warns) == 0


def test_genre_emission_in_series_warns(tmp_path, settings, test_config):
    """NFO with French TMDB genre 'Émission' in 002-TVSHOWS → warning about tv_programs.

    The V15 classifier rule ``tmdb_genre_contains="mission"`` maps the French
    TMDB genre ``Émission`` to ``CID.TV_PROGRAMS``. The coherence checker
    must surface that mismatch as a warning.
    """
    show = tmp_path / "002-TVSHOWS" / "Show (2026)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text('<tvshow><genre>Émission</genre><uniqueid type="tmdb">312697</uniqueid></tvshow>')

    results = check_coherence(settings, test_config, dry_run=False)

    # Verify genre_coherence check was performed without error
    assert any("genre_coherence" in r.checks for r in results)

    tv_program_warns = [w for r in results for w in r.warnings if "tv program" in w.lower()]
    assert len(tv_program_warns) >= 1, "Classifier should flag tv_programs category mismatch"
