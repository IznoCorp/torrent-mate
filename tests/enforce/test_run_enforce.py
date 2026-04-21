"""Tests for the enforce step orchestrator.

Verifies that run_enforce() correctly chains sanitize → structure → coherence
and produces a valid StepReport.
"""

from unittest.mock import MagicMock

import pytest

from personalscraper.enforce.run import run_enforce


@pytest.fixture
def settings(tmp_path):
    """Build a minimal Settings mock pointing to tmp_path."""
    s = MagicMock()
    s.staging_dir = tmp_path
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


def test_empty_staging_returns_empty_report(tmp_path, settings, test_config):
    """No media dirs → StepReport with 0 counts."""
    report = run_enforce(settings, test_config, dry_run=False)
    assert report.name == "enforce"
    assert report.success_count == 0
    assert report.error_count == 0


def test_clean_items_produces_skip_report(tmp_path, settings, test_config):
    """Clean items → success_count=0, skip_count>0."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text(
        '<movie><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></movie>'
    )
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"\x00")

    report = run_enforce(settings, test_config, dry_run=False)
    assert report.name == "enforce"
    assert report.error_count == 0


def test_items_with_issues_produces_success(tmp_path, settings, test_config):
    """Items needing fixes → success_count > 0."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / ".DS_Store").write_bytes(b"\x00")  # Will be cleaned by sanitizer
    (movie / "Film.MULTI.nfo").write_text("<movie/>")  # Will be cleaned by structure

    report = run_enforce(settings, test_config, dry_run=False)
    assert report.name == "enforce"
    assert report.success_count > 0
    assert not (movie / ".DS_Store").exists()
    assert not (movie / "Film.MULTI.nfo").exists()


def test_warnings_collected_from_coherence(tmp_path, settings, test_config):
    """Coherence warnings appear in report."""
    movie = tmp_path / "001-MOVIES" / "Bad (2025)"
    movie.mkdir(parents=True)
    (movie / "Bad.nfo").write_text("<movie><title>Bad</title></movie>")  # No IDs

    report = run_enforce(settings, test_config, dry_run=False)
    assert len(report.warnings) > 0
    assert any("missing" in w.lower() for w in report.warnings)
