"""Tests for personalscraper.text_utils — media_processor for fuzzy matching."""

import pytest

from personalscraper.text_utils import media_processor


class TestMediaProcessor:
    """Custom rapidfuzz processor for French media titles."""

    def test_lowercase(self):
        """Converts to lowercase."""
        assert "the matrix" in media_processor("The Matrix")

    def test_strips_accents(self):
        """NFD decomposition removes diacritical marks."""
        assert media_processor("Amélie") == media_processor("Amelie")
        assert media_processor("Les Évadés") == media_processor("Les Evades")
        assert media_processor("ça") == media_processor("ca")

    def test_strips_punctuation(self):
        """Non-alphanumeric chars are removed (via default_process)."""
        result = media_processor("Spider-Man: No Way Home")
        assert "-" not in result
        assert ":" not in result

    def test_empty_string(self):
        """Empty input returns empty output."""
        assert media_processor("") == ""

    def test_preserves_numbers(self):
        """Numbers in titles are preserved."""
        assert "2001" in media_processor("2001: A Space Odyssey")

    @pytest.mark.parametrize("title_a,title_b", [
        ("Amélie", "Amelie"),
        ("Les Évadés", "Les Evades"),
        ("Ça", "Ca"),
        ("Hôtel Rwanda", "Hotel Rwanda"),
        ("Pêle-Mêle", "Pele Mele"),
    ])
    def test_french_accent_pairs_match(self, title_a, title_b):
        """French accented and non-accented versions produce the same output."""
        assert media_processor(title_a) == media_processor(title_b)


# ---------------------------------------------------------------------------
# fuzzy_match_score — anti-false-positive guards
# ---------------------------------------------------------------------------

from personalscraper.text_utils import fuzzy_match_score


class TestFuzzyMatchScore:
    """Test fuzzy_match_score with year, length, and threshold guards."""

    def test_matrix_vs_matrix_reloaded_rejected(self):
        """'Matrix' vs 'Matrix Reloaded' rejected by length guard."""
        # len ratio: 6/15 = 0.40 < 0.67
        result = fuzzy_match_score("Matrix", "Matrix Reloaded")
        assert result is None

    def test_alien_vs_aliens_rejected(self):
        """'Alien' vs 'Aliens' rejected by adaptive threshold (short title)."""
        # 5 chars → threshold 95%, WRatio ≈ 90%
        result = fuzzy_match_score("Alien", "Aliens")
        assert result is None

    def test_exact_match_accepted(self):
        """Identical titles with same year produce a high score."""
        result = fuzzy_match_score(
            "The Matrix", "The Matrix",
            query_year=1999, candidate_year=1999,
        )
        assert result is not None
        assert result >= 95.0

    def test_year_off_by_one_accepted(self):
        """±1 year tolerance allows late-year releases."""
        result = fuzzy_match_score(
            "Jumanji", "Jumanji",
            query_year=1995, candidate_year=1996,
        )
        assert result is not None
        assert result >= 95.0

    def test_year_mismatch_rejected(self):
        """Year difference > 1 rejects the match (e.g. remakes)."""
        result = fuzzy_match_score(
            "Jumanji", "Jumanji",
            query_year=1995, candidate_year=2017,
        )
        assert result is None

    def test_accents_handled(self):
        """French accented and non-accented titles match."""
        result = fuzzy_match_score("Les Évadés", "Les Evades")
        assert result is not None
        assert result >= 95.0

    def test_no_years_skips_year_guard(self):
        """If neither has a year, the year guard is skipped."""
        result = fuzzy_match_score("The Matrix", "The Matrix")
        assert result is not None

    def test_one_year_only_skips_year_guard(self):
        """If only one has a year, the year guard is skipped."""
        result = fuzzy_match_score(
            "Jumanji", "Jumanji",
            query_year=1995, candidate_year=None,
        )
        assert result is not None

    def test_empty_string_rejected(self):
        """Empty strings are rejected."""
        assert fuzzy_match_score("", "Something") is None
        assert fuzzy_match_score("Something", "") is None

    def test_long_title_lower_threshold(self):
        """Titles > 10 chars use 90% threshold instead of 95%."""
        # "Avengers Endgame" (16 chars) vs "Avengers End Game" — slight diff
        result = fuzzy_match_score("Avengers Endgame", "Avengers End Game")
        assert result is not None
