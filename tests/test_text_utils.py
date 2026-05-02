"""Tests for personalscraper.text_utils — media_processor for fuzzy matching."""

import pytest

from personalscraper.text_utils import fuzzy_match_score, media_processor


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

    @pytest.mark.parametrize(
        "title_a,title_b",
        [
            ("Amélie", "Amelie"),
            ("Les Évadés", "Les Evades"),
            ("Ça", "Ca"),
            ("Hôtel Rwanda", "Hotel Rwanda"),
            ("Pêle-Mêle", "Pele Mele"),
        ],
    )
    def test_french_accent_pairs_match(self, title_a, title_b):
        """French accented and non-accented versions produce the same output."""
        assert media_processor(title_a) == media_processor(title_b)


# ---------------------------------------------------------------------------
# fuzzy_match_score — anti-false-positive guards
# ---------------------------------------------------------------------------


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
            "The Matrix",
            "The Matrix",
            query_year=1999,
            candidate_year=1999,
        )
        assert result is not None
        assert result >= 95.0

    def test_year_off_by_one_accepted(self):
        """±1 year tolerance allows late-year releases."""
        result = fuzzy_match_score(
            "Jumanji",
            "Jumanji",
            query_year=1995,
            candidate_year=1996,
        )
        assert result is not None
        assert result >= 95.0

    def test_year_mismatch_rejected(self):
        """Year difference > 1 rejects the match (e.g. remakes)."""
        result = fuzzy_match_score(
            "Jumanji",
            "Jumanji",
            query_year=1995,
            candidate_year=2017,
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
            "Jumanji",
            "Jumanji",
            query_year=1995,
            candidate_year=None,
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

    def test_year_suffix_not_rejected_by_length_guard(self):
        """Title without year matches title with year (year suffix stripped before length check)."""
        # "Shrinking" (9 chars) vs "Shrinking (2023)" (16 chars)
        # Without year stripping: 9/16 = 0.56 < 0.67 → rejected
        # With year stripping: 9/9 = 1.0 → accepted
        result = fuzzy_match_score("Shrinking", "Shrinking (2023)")
        assert result is not None
        assert result >= 90.0

    def test_year_suffix_both_directions(self):
        """Year suffix stripping works regardless of which side has the year."""
        assert fuzzy_match_score("Shrinking (2023)", "Shrinking") is not None
        assert fuzzy_match_score("The Boys", "The Boys (2019)") is not None
        assert fuzzy_match_score("The Boys (2019)", "The Boys") is not None


class TestSanitizeFilename:
    """Tests for sanitize_filename — NTFS safety + space normalisation.

    The sanitizer strips every NTFS-illegal character outright (including
    the colon). It does NOT introduce a separator like `` - `` in place of
    the colon: the project's filename patterns use `-` as a structural
    separator (``{Title}-poster.jpg``, ``S01E01 - {EpisodeTitle}``), so
    injecting another dash inside the title would create filenames with
    two semantically different dashes that the round-trip parsers in
    ``naming_patterns.py`` cannot disambiguate.
    """

    def test_colon_stripped_keeps_pattern_consistency(self):
        """Colon is stripped; the resulting double space collapses to one."""
        from personalscraper.text_utils import sanitize_filename

        # "Peaky Blinders : L'Immortel" → "Peaky Blinders L'Immortel"
        # (colon stripped, double space collapsed). Subtitle separation is
        # lost cosmetically but no extra dash is introduced — patterns
        # that key on `-` keep their meaning.
        assert sanitize_filename("Peaky Blinders : L'Immortel") == "Peaky Blinders L'Immortel"
        assert sanitize_filename("Star Trek: TNG (1987)") == "Star Trek TNG (1987)"

    def test_other_ntfs_illegal_chars_stripped(self):
        r"""``<>"/\|?*`` are still removed outright (no useful replacement)."""
        from personalscraper.text_utils import sanitize_filename

        assert sanitize_filename('Title<bad>"end') == "Titlebadend"
        assert sanitize_filename("a/b\\c|d?e*f") == "abcdef"

    def test_non_breaking_space_normalised(self):
        """U+00A0 NBSP is normalised to a regular space."""
        from personalscraper.text_utils import sanitize_filename

        assert sanitize_filename("Title (2024)") == "Title (2024)"

    def test_double_spaces_collapsed(self):
        """Resulting double spaces from substitutions collapse to one."""
        from personalscraper.text_utils import sanitize_filename

        assert sanitize_filename("Multi  Space") == "Multi Space"

    def test_ntfs_illegal_regex_includes_colon(self):
        """``_NTFS_ILLEGAL`` flags a raw colon for post-sanitisation checks.

        Used by downstream consumers scanning the filesystem (e.g. the
        dispatch pre-rsync NTFS guard) to detect any colon that slipped
        through manual file placement, even though the sanitizer would
        have replaced it on entry through the normal pipeline.
        """
        from personalscraper.text_utils import _NTFS_ILLEGAL

        assert _NTFS_ILLEGAL.search("Title : Subtitle.mkv") is not None
        assert _NTFS_ILLEGAL.search("clean_title.mkv") is None
