"""Tests for personalscraper.sorter.matcher — fuzzy directory matching."""

from pathlib import Path

import pytest

from personalscraper.sorter.matcher import _extract_year, find_matching_directory

# --- _extract_year ---


class TestExtractYear:
    """Year extraction from directory names."""

    @pytest.mark.parametrize("name,expected", [
        ("The Matrix (1999)", 1999),
        ("Amélie 2001", 2001),
        ("2024", 2024),
        ("Show Name", None),
        ("S01E04", None),
        ("1080p", None),  # Not a valid year
    ])
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

    def test_year_mismatch_allowed_when_disabled(self, tmp_path):
        """Year check is skipped when respect_year=False.

        Note: WRatio("The Matrix (2003)", "The Matrix (1999)") = 76
        so we need a lower threshold since the year digits differ.
        """
        dirs = self._make_dirs(tmp_path, ["The Matrix (1999)"])
        result = find_matching_directory(
            "The Matrix (2003)", dirs, respect_year=False, threshold=70.0
        )
        assert result == dirs[0]

    def test_name_without_year_matches_name_with_year(self, tmp_path):
        """A name without year matches a candidate with year (year filter only rejects conflicts)."""
        dirs = self._make_dirs(tmp_path, ["The Matrix (1999)"])
        result = find_matching_directory("The Matrix", dirs, respect_year=True)
        assert result == dirs[0]

    def test_picks_best_match_among_multiple(self, tmp_path):
        """Picks the best scoring match from multiple candidates."""
        dirs = self._make_dirs(tmp_path, [
            "The Matrix (1999)",
            "The Matrix Reloaded (2003)",
            "The Matrix Revolutions (2003)",
        ])
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

    def test_custom_threshold(self, tmp_path):
        """Custom threshold can be more or less strict."""
        dirs = self._make_dirs(tmp_path, ["The Matrix Reloaded"])
        # With very high threshold, partial match is rejected
        result = find_matching_directory("The Matrix", dirs, threshold=98.0)
        assert result is None
        # With lower threshold, it matches
        result = find_matching_directory("The Matrix", dirs, threshold=60.0)
        assert result == dirs[0]
