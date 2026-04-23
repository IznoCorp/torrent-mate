"""Idempotence tests for the ENFORCE pipeline step.

Each test: setup fixture → run 1 (fix) → assert corrections → run 2 (no-op).
"""

from unittest.mock import MagicMock

import pytest

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


class TestIdempotenceMovies:
    """Idempotence tests for movie items."""

    def test_colon_files_fixed_then_noop(self, tmp_path, settings, enforce_config):
        """Files with : → renamed on run 1, no-op on run 2."""
        movie = tmp_path / "001-MOVIES" / "Avatar (2025)"
        movie.mkdir(parents=True)
        (movie / "Avatar.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></movie>'
        )
        (movie / "Avatar.mkv").write_bytes(b"\x00")
        (movie / "Avatar : poster.jpg").write_bytes(b"\x00")

        r1 = run_enforce(settings, enforce_config, dry_run=False)
        assert r1.success_count > 0
        assert not (movie / "Avatar : poster.jpg").exists()
        assert (movie / "Avatar poster.jpg").exists()

        r2 = run_enforce(settings, enforce_config, dry_run=False)
        assert r2.success_count == 0

    def test_duplicate_nfos_fixed_then_noop(self, tmp_path, settings, enforce_config):
        """Extra NFOs → removed on run 1, no-op on run 2."""
        movie = tmp_path / "001-MOVIES" / "Scream 7 (2026)"
        movie.mkdir(parents=True)
        (movie / "Scream 7.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></movie>'
        )
        (movie / "Scream 7.mkv").write_bytes(b"\x00")
        (movie / "Scream.7.MULTI.nfo").write_text("<movie/>")

        r1 = run_enforce(settings, enforce_config, dry_run=False)
        assert r1.success_count > 0
        assert not (movie / "Scream.7.MULTI.nfo").exists()
        assert (movie / "Scream 7.nfo").exists()

        r2 = run_enforce(settings, enforce_config, dry_run=False)
        assert r2.success_count == 0

    def test_ds_store_cleaned_then_noop(self, tmp_path, settings, enforce_config):
        """.DS_Store → deleted on run 1, no-op on run 2."""
        movie = tmp_path / "001-MOVIES" / "Film (2025)"
        movie.mkdir(parents=True)
        (movie / "Film.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></movie>'
        )
        (movie / "Film.mkv").write_bytes(b"\x00")
        (movie / ".DS_Store").write_bytes(b"\x00")
        actors = movie / ".actors"
        actors.mkdir()
        (actors / ".DS_Store").write_bytes(b"\x00")

        r1 = run_enforce(settings, enforce_config, dry_run=False)
        assert r1.success_count >= 2
        assert not (movie / ".DS_Store").exists()

        r2 = run_enforce(settings, enforce_config, dry_run=False)
        assert r2.success_count == 0

    def test_colon_directory_renamed_then_noop(self, tmp_path, settings, enforce_config):
        """Directory with : → renamed on run 1, no-op on run 2."""
        movies = tmp_path / "001-MOVIES"
        movies.mkdir(parents=True)
        bad = movies / "Spirale : Test (2021)"
        bad.mkdir()
        (bad / "Spirale Test.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></movie>'
        )
        (bad / "Spirale Test.mkv").write_bytes(b"\x00")

        r1 = run_enforce(settings, enforce_config, dry_run=False)
        assert r1.success_count > 0
        assert not bad.exists()
        assert (movies / "Spirale Test (2021)").exists()

        r2 = run_enforce(settings, enforce_config, dry_run=False)
        assert r2.success_count == 0


class TestIdempotenceTvshows:
    """Idempotence tests for TV show items."""

    def test_empty_torrent_dir_cleaned_then_noop(self, tmp_path, settings, enforce_config):
        """Empty torrent subdir → removed on run 1, no-op on run 2."""
        show = tmp_path / "002-TVSHOWS" / "Show (2025)"
        show.mkdir(parents=True)
        (show / "tvshow.nfo").write_text(
            '<tvshow><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></tvshow>'
        )
        empty = show / "Show.S01E01.MULTI.1080p"
        empty.mkdir()

        run_enforce(settings, enforce_config, dry_run=False)
        assert not empty.exists()

        r2 = run_enforce(settings, enforce_config, dry_run=False)
        assert r2.success_count == 0

    def test_resource_forks_cleaned_then_noop(self, tmp_path, settings, enforce_config):
        """._* files → deleted on run 1, no-op on run 2."""
        show = tmp_path / "002-TVSHOWS" / "Show (2025)"
        show.mkdir(parents=True)
        (show / "tvshow.nfo").write_text(
            '<tvshow><uniqueid type="tmdb">1</uniqueid><uniqueid type="imdb">tt1</uniqueid></tvshow>'
        )
        (show / "._poster.jpg").write_bytes(b"\x00")

        r1 = run_enforce(settings, enforce_config, dry_run=False)
        assert r1.success_count > 0
        assert not (show / "._poster.jpg").exists()

        r2 = run_enforce(settings, enforce_config, dry_run=False)
        assert r2.success_count == 0


class TestIdempotenceCoherence:
    """Idempotence for coherence checks (read-only, always same warnings)."""

    def test_missing_ids_warns_consistently(self, tmp_path, settings, enforce_config):
        """Missing IDs → same warnings on both runs."""
        movie = tmp_path / "001-MOVIES" / "Bad (2025)"
        movie.mkdir(parents=True)
        (movie / "Bad.nfo").write_text("<movie><title>Bad</title></movie>")

        r1 = run_enforce(settings, enforce_config, dry_run=False)
        r2 = run_enforce(settings, enforce_config, dry_run=False)
        assert r1.warnings == r2.warnings
        assert len(r1.warnings) > 0


@pytest.mark.e2e_idempotence
class TestRealStagingIdempotence:
    """Run enforce on actual staging data. Manual only."""

    def test_enforce_runs_without_error(self, test_config):
        """First run should complete without errors."""
        from personalscraper.config import Settings

        settings = Settings()
        report = run_enforce(settings, test_config, dry_run=False)
        print(f"Run 1: {report.success_count} fixed, {report.skip_count} OK")
        for d in report.details:
            print(f"  {d}")
        assert report.error_count == 0

    def test_enforce_second_run_noop(self, test_config):
        """Second run should change nothing (idempotent)."""
        from personalscraper.config import Settings

        settings = Settings()
        report = run_enforce(settings, test_config, dry_run=False)
        assert report.success_count == 0, f"Expected no-op, got {report.success_count} fixes: {report.details}"
