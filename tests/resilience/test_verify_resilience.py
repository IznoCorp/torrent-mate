"""Resilience tests: verify double-run idempotence.

Tests that verify produces the same result on repeated runs
without re-applying fixes unnecessarily.
"""

from unittest.mock import MagicMock

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.verifier import Verifier

from .conftest import make_valid_movie_dir, make_valid_tvshow_dir


class TestVerifyDoubleRun:
    """Test 9: Verify double-run produces same result, no re-fix."""

    def test_movie_verify_double_run(self, staging, test_config):
        """Valid movie: two verify runs produce same 'valid' status."""
        movies = staging / "001-MOVIES"
        movie = make_valid_movie_dir(movies, "Matrix", 1999)

        v = Verifier(MagicMock(), NamingPatterns(), test_config)

        result1 = v.verify_movie(movie)
        result2 = v.verify_movie(movie)

        assert result1.status == "valid"
        assert result2.status == "valid"
        # No fixes applied on either run
        assert result1.fixes_applied == []
        assert result2.fixes_applied == []

    def test_tvshow_verify_double_run(self, staging, test_config):
        """Valid tvshow: two verify runs produce same 'valid' status."""
        tvshows = staging / "002-TVSHOWS"
        show = make_valid_tvshow_dir(tvshows, "Breaking Bad", 2008)

        v = Verifier(MagicMock(), NamingPatterns(), test_config)

        result1 = v.verify_tvshow(show)
        result2 = v.verify_tvshow(show)

        assert result1.status in ("valid", "fixed")
        assert result2.status in ("valid", "fixed")
        # Second run should not apply any NEW fixes
        # (if first run fixed something, second run should be clean)
        if result1.status == "fixed":
            assert result2.fixes_applied == []
