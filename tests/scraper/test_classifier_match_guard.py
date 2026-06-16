"""Unit tests for is_degenerate_title — AC-6 of the match-guard feature.

AC-6: is_degenerate_title returns True for ' S03'/'S3'/'S01E01',
      False for 'FROM'/'The Hack'/'Among'/'Top Chef France'/'S.W.A.T.'/'Sense8'.
"""

import pytest

from personalscraper.scraper.classifier import is_degenerate_title


class TestIsDegenerateTitle:
    """Tests for the degenerate-title predicate (AC-6)."""

    @pytest.mark.parametrize(
        "title",
        [
            " S03",  # Orville case — leading space + season token
            "S03",  # no leading space
            "S3",  # single-digit season
            "S01E01",  # season + episode token
            "S12E99",  # large numbers
            "  S02  ",  # extra whitespace
        ],
    )
    def test_degenerate_titles_return_true(self, title: str) -> None:
        """Pure season/episode tokens must be recognised as degenerate."""
        assert is_degenerate_title(title) is True, f"Expected is_degenerate_title({title!r}) to be True"

    @pytest.mark.parametrize(
        "title",
        [
            "FROM",  # short but legit — single word, no Sxx pattern
            "The Hack",  # short legit title
            "Among",  # guessit-stripped remainder — still not a season token
            "Top Chef France",  # multiword legit
            "S.W.A.T.",  # starts with S but has dots — not a season token
            "Sense8",  # starts with S, has digit, but not Sxx form
            "S Club 7",  # starts with S, has digit, but not Sxx form
            "S-Town",  # starts with S but not Sxx form
            "S4C",  # channel name — not Sxx form
            "Station 19",  # legit show title with digits
        ],
    )
    def test_legit_titles_return_false(self, title: str) -> None:
        """Legit show titles must NOT be classified as degenerate."""
        assert is_degenerate_title(title) is False, (
            f"Expected is_degenerate_title({title!r}) to be False "
            f"(would wrongly trigger fallback and break this legit title)"
        )
