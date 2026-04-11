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
