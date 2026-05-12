"""Tests for the enforce step orchestrator.

Verifies that run_enforce(event_bus=EventBus()) correctly chains sanitize → structure → coherence
and produces a valid StepReport.
"""

from unittest.mock import MagicMock

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.enforce.run import run_enforce
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture
def settings():
    """Minimal settings mock (staging resolved from config.paths)."""
    return MagicMock()


@pytest.fixture
def enforce_config(tmp_path, test_config):
    """Config mock with staging_dirs and staging path set to tmp_path.

    Forwards classifier-relevant attributes from test_config so that
    coherence checks (classify_from_nfo) function correctly.

    Args:
        tmp_path: Pytest temporary directory used as staging root.
        test_config: Full Config fixture from tests/fixtures/config.py.

    Returns:
        MagicMock with staging_dirs, paths.staging_dir, and classifier
        attributes forwarded from test_config.
    """
    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    c.category_rules = test_config.category_rules
    c.genre_mapping = test_config.genre_mapping
    c.anime_rule = test_config.anime_rule
    c.categories = test_config.categories
    return c


def test_empty_staging_returns_empty_report(tmp_path, settings, enforce_config):
    """No media dirs → StepReport with 0 counts."""
    report = run_enforce(settings, enforce_config, dry_run=False, event_bus=EventBus())
    assert report.name == "enforce"
    assert report.success_count == 0
    assert report.error_count == 0


def test_clean_items_produces_skip_report(tmp_path, settings, enforce_config):
    """Clean items → success_count=0, skip_count>0."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text(
        '<movie><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></movie>'
    )
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"\x00")

    report = run_enforce(settings, enforce_config, dry_run=False, event_bus=EventBus())
    assert report.name == "enforce"
    assert report.error_count == 0


def test_items_with_issues_produces_success(tmp_path, settings, enforce_config):
    """Items needing fixes → success_count > 0."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / ".DS_Store").write_bytes(b"\x00")  # Will be cleaned by sanitizer
    (movie / "Film.MULTI.nfo").write_text("<movie/>")  # Will be cleaned by structure

    report = run_enforce(settings, enforce_config, dry_run=False, event_bus=EventBus())
    assert report.name == "enforce"
    assert report.success_count > 0
    assert not (movie / ".DS_Store").exists()
    assert not (movie / "Film.MULTI.nfo").exists()


def test_warnings_collected_from_coherence(tmp_path, settings, enforce_config):
    """Coherence warnings appear in report."""
    movie = tmp_path / "001-MOVIES" / "Bad (2025)"
    movie.mkdir(parents=True)
    (movie / "Bad.nfo").write_text("<movie><title>Bad</title></movie>")  # No IDs

    report = run_enforce(settings, enforce_config, dry_run=False, event_bus=EventBus())
    assert len(report.warnings) > 0
    assert any("missing" in w.lower() for w in report.warnings)
