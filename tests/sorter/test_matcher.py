"""Tests for personalscraper.sorter.matcher — fuzzy directory matching."""

from pathlib import Path

import pytest

from personalscraper.sorter.matcher import _extract_year, find_matching_directory

# --- _extract_year ---


class TestExtractYear:
    """Year extraction from directory names."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("The Matrix (1999)", 1999),
            ("Amélie 2001", 2001),
            ("2024", 2024),
            ("Show Name", None),
            ("S01E04", None),
            ("1080p", None),  # Not a valid year
        ],
    )
    def test_year_extraction(self, name, expected):
        """Extracts 19xx/20xx years, ignores non-year numbers."""
        assert _extract_year(name) == expected


# --- find_matching_directory ---


class TestFindMatchingDirectory:
    """Fuzzy matching of media names against existing directories."""

    def _make_dirs(self, tmp_path: Path, names: list[str]) -> list[Path]:
        """Create directories and return their paths."""
        dirs = []
        for name in names:
            d = tmp_path / name
            d.mkdir(exist_ok=True)
            dirs.append(d)
        return dirs

    def test_exact_match(self, tmp_path):
        """Exact name matches are found."""
        dirs = self._make_dirs(tmp_path, ["The Matrix (1999)"])
        result = find_matching_directory("The Matrix (1999)", dirs)
        assert result == dirs[0]

    def test_case_insensitive_match(self, tmp_path):
        """Matching is case-insensitive."""
        dirs = self._make_dirs(tmp_path, ["The Matrix (1999)"])
        result = find_matching_directory("the matrix (1999)", dirs)
        assert result == dirs[0]

    def test_accent_insensitive_match(self, tmp_path):
        """French accented titles match non-accented versions."""
        dirs = self._make_dirs(tmp_path, ["Amélie (2001)"])
        result = find_matching_directory("Amelie (2001)", dirs)
        assert result == dirs[0]

    def test_no_match_below_threshold(self, tmp_path):
        """Returns None when best score is below threshold."""
        dirs = self._make_dirs(tmp_path, ["Totally Different Movie"])
        result = find_matching_directory("The Matrix", dirs)
        assert result is None

    def test_year_mismatch_rejected(self, tmp_path):
        """Different years are rejected when respect_year=True."""
        dirs = self._make_dirs(tmp_path, ["The Matrix (1999)"])
        result = find_matching_directory("The Matrix (2003)", dirs, respect_year=True)
        assert result is None

    def test_year_mismatch_rejected_even_when_disabled(self, tmp_path):
        """Year guard is skipped with respect_year=False, but adaptive
        threshold still rejects low scores from digit differences.

        V8: fuzzy_match_score's adaptive threshold (90%) means that
        different year digits lower the WRatio score below the cutoff.
        """
        dirs = self._make_dirs(tmp_path, ["The Matrix (1999)"])
        result = find_matching_directory("The Matrix (2003)", dirs, respect_year=False, threshold=70.0)
        # V8: rejected by adaptive threshold — year digits differ too much
        assert result is None

    def test_same_title_different_format_matches(self, tmp_path):
        """Same title with and without year matches when year is same."""
        dirs = self._make_dirs(tmp_path, ["The Matrix (1999)"])
        result = find_matching_directory("The Matrix (1999)", dirs, respect_year=True)
        assert result == dirs[0]

    def test_picks_best_match_among_multiple(self, tmp_path):
        """Picks the best scoring match from multiple candidates."""
        dirs = self._make_dirs(
            tmp_path,
            [
                "The Matrix (1999)",
                "The Matrix Reloaded (2003)",
                "The Matrix Revolutions (2003)",
            ],
        )
        result = find_matching_directory("The Matrix (1999)", dirs)
        assert result == dirs[0]

    def test_empty_candidates_returns_none(self, tmp_path):
        """Returns None for empty candidate list."""
        assert find_matching_directory("The Matrix", []) is None

    def test_tvshow_fuzzy_match(self, tmp_path):
        """TV show names with slight differences still match."""
        dirs = self._make_dirs(tmp_path, ["Shrinking"])
        result = find_matching_directory("Shrinking", dirs, respect_year=False)
        assert result == dirs[0]

    def test_length_guard_rejects_partial_titles(self, tmp_path):
        """V8: 'The Matrix' does NOT match 'The Matrix Reloaded' (length guard).

        Length ratio: 10/19 = 0.53 < 0.67 → rejected regardless of threshold.
        """
        dirs = self._make_dirs(tmp_path, ["The Matrix Reloaded"])
        # Old behavior: low threshold would accept. New: length guard rejects.
        result = find_matching_directory("The Matrix", dirs, threshold=60.0)
        assert result is None

    def test_short_title_needs_high_score(self, tmp_path):
        """V8: Short titles (≤10 chars) require 95% threshold."""
        dirs = self._make_dirs(tmp_path, ["Alien (1979)"])
        # "Alien" exact match → high score → accepted
        result = find_matching_directory("Alien (1979)", dirs)
        assert result == dirs[0]

    def test_long_title_accepts_at_90_percent(self, tmp_path):
        """V8: Long titles (>10 chars) use 90% threshold."""
        dirs = self._make_dirs(tmp_path, ["Avengers Endgame (2019)"])
        result = find_matching_directory("Avengers Endgame (2019)", dirs)
        assert result == dirs[0]
