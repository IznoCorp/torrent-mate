"""Tests for coherence_checker module."""

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.enforce.coherence_checker import check_coherence
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture
def settings():
    """Minimal settings mock (staging resolved from config.paths)."""
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def test_config_at_tmp(tmp_path, test_config):
    """Build a config mock combining test_config rules with tmp_path staging.

    The coherence checker uses config.paths.staging_dir and config.staging_dirs
    to locate staging category dirs. This fixture wraps the real test_config
    so that category_rules and genre mappings are available, while directing
    staging to tmp_path.

    Args:
        tmp_path: Pytest temporary directory.
        test_config: Full Config fixture from tests/fixtures/config.py.

    Returns:
        MagicMock with staging_dirs from CANONICAL_STAGING_DIRS,
        paths.staging_dir set to tmp_path, and categories/rules from
        test_config forwarded for classifier use.
    """
    from unittest.mock import MagicMock

    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    # Forward classifier-relevant attributes from the real test_config
    c.category_rules = test_config.category_rules
    c.genre_mapping = test_config.genre_mapping
    c.anime_rule = test_config.anime_rule
    c.categories = test_config.categories
    return c


def test_tvshow_in_movies_warns(tmp_path, settings, test_config_at_tmp):
    """tvshow.nfo in 001-MOVIES → warning."""
    movie = tmp_path / "001-MOVIES" / "Fake Show (2026)"
    movie.mkdir(parents=True)
    (movie / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')

    results = check_coherence(settings, test_config_at_tmp, dry_run=False, bus=EventBus())
    warns = [w for r in results for w in r.warnings if "wrong category" in w.lower()]
    assert len(warns) >= 1


def test_nfo_missing_both_ids_warns(tmp_path, settings, test_config_at_tmp):
    """NFO without TMDB or IMDB ID → warning."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text("<movie><title>Film</title></movie>")

    results = check_coherence(settings, test_config_at_tmp, dry_run=False, bus=EventBus())
    warns = [w for r in results for w in r.warnings if "missing" in w.lower() and "id" in w.lower()]
    assert len(warns) >= 1


def test_clean_items_no_warnings(tmp_path, settings, test_config_at_tmp):
    """Properly structured items → no warnings."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text(
        '<movie><uniqueid type="tmdb">123</uniqueid><uniqueid type="imdb">tt123</uniqueid></movie>'
    )

    results = check_coherence(settings, test_config_at_tmp, dry_run=False, bus=EventBus())
    warns = [w for r in results for w in r.warnings]
    assert len(warns) == 0


def test_coherence_checker_skips_apple_double_in_movie_dir(tmp_path, settings, test_config_at_tmp):
    """Regression: ``_check_movie`` must use ``glob_nfo_candidates``.

    Before commit c296e41 (phase 11.3) ``_check_movie`` used a raw
    ``movie_dir.glob("*.nfo")``.  On NTFS / SMB shares macOS creates
    ``._<name>.nfo`` AppleDouble sidecars that sort BEFORE the real NFO
    alphabetically, so ``nfos[0]`` was the binary blob and ``_check_nfo_ids``
    silently parsed garbage — masking ID problems and emitting spurious
    "missing IDs" warnings.

    With the fix, the real NFO is selected and the IDs are correctly
    validated → no spurious "missing" warning.
    """
    movie = tmp_path / "001-MOVIES" / "Inception (2010)"
    movie.mkdir(parents=True)
    # Binary AppleDouble sidecar that would shadow the real NFO under raw glob.
    (movie / "._Inception (2010).nfo").write_bytes(b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        ")
    # Real NFO with both required IDs — must be picked up by the checker.
    (movie / "Inception (2010).nfo").write_text(
        '<movie><uniqueid type="tmdb">27205</uniqueid><uniqueid type="imdb">tt1375666</uniqueid></movie>',
        encoding="utf-8",
    )

    results = check_coherence(settings, test_config_at_tmp, dry_run=False, bus=EventBus())
    missing_id_warns = [w for r in results for w in r.warnings if "missing" in w.lower() and "id" in w.lower()]

    assert missing_id_warns == [], f"expected no missing-ID warnings, got {missing_id_warns}"


def test_genre_emission_in_series_warns(tmp_path, settings, test_config_at_tmp):
    """NFO with French TMDB genre 'Émission' in 002-TVSHOWS → warning about tv_programs.

    The V15 classifier rule ``tmdb_genre_contains="mission"`` maps the French
    TMDB genre ``Émission`` to ``CID.TV_PROGRAMS``. The coherence checker
    must surface that mismatch as a warning.
    """
    show = tmp_path / "002-TVSHOWS" / "Show (2026)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text('<tvshow><genre>Émission</genre><uniqueid type="tmdb">312697</uniqueid></tvshow>')

    results = check_coherence(settings, test_config_at_tmp, dry_run=False, bus=EventBus())

    # Verify genre_coherence check was performed without error
    assert any("genre_coherence" in r.checks for r in results)

    tv_program_warns = [w for r in results for w in r.warnings if "tv program" in w.lower()]
    assert len(tv_program_warns) >= 1, "Classifier should flag tv_programs category mismatch"
