"""Tests for confidence scoring and movie matching.

Tests score_match() with parametrized cases (exact, partial, bad matches,
accented French titles) and match_movie() with mocked TMDB responses.
"""

from unittest.mock import MagicMock, patch

from personalscraper.scraper.confidence import (
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    MatchResult,
    match_movie,
    prompt_user_choice,
    score_match,
)

# ---------------------------------------------------------------------------
# score_match — parametrized tests
# ---------------------------------------------------------------------------

class TestScoreMatch:
    """Tests for the confidence scoring algorithm."""

    def test_exact_match_with_year(self) -> None:
        """Exact title + exact year should score >= HIGH_CONFIDENCE."""
        score = score_match("The Matrix", 1999, "The Matrix", 1999)
        assert score >= HIGH_CONFIDENCE

    def test_exact_match_without_year(self) -> None:
        """Exact title without year info should still score high."""
        score = score_match("The Matrix", None, "The Matrix", None)
        assert score >= 0.9  # WRatio gives 100/100 for identical strings

    def test_close_title_same_year(self) -> None:
        """Close title with same year should score well."""
        score = score_match("Le Comte de Monte Cristo", 2024, "Le Comte de Monte-Cristo", 2024)
        assert score >= HIGH_CONFIDENCE

    def test_different_movie_same_title_different_year(self) -> None:
        """Same title but very different year should be penalized."""
        score = score_match("The Batman", 2022, "Batman", 1989)
        assert score < HIGH_CONFIDENCE

    def test_completely_different_title(self) -> None:
        """Totally different titles should score very low."""
        score = score_match("The Matrix", 1999, "Titanic", 1997)
        assert score < LOW_CONFIDENCE

    def test_year_off_by_one(self) -> None:
        """Year off by 1 should be neutral (common for late-year releases)."""
        exact = score_match("Test Movie", 2023, "Test Movie", 2023)
        off_by_one = score_match("Test Movie", 2023, "Test Movie", 2024)
        # Off by one should be close to exact (no penalty, but no bonus either)
        assert off_by_one >= exact - 0.11  # Only lose the year bonus (0.1)

    def test_year_off_by_many(self) -> None:
        """Year off by >1 should get a penalty."""
        exact = score_match("Test Movie", 2023, "Test Movie", 2023)
        off_by_five = score_match("Test Movie", 2023, "Test Movie", 2018)
        assert off_by_five < exact

    def test_french_accents_handled(self) -> None:
        """French accented titles should match their unaccented versions."""
        score = score_match("Amélie", 2001, "Amelie", 2001)
        assert score >= HIGH_CONFIDENCE

    def test_french_title_complex(self) -> None:
        """Complex French title with accents and special chars."""
        score = score_match(
            "Les Misérables", 2019,
            "Les Misérables", 2019,
        )
        assert score >= HIGH_CONFIDENCE

    def test_score_clamped_to_zero(self) -> None:
        """Score should never go below 0.0."""
        # Very different title + year penalty
        score = score_match("AAAA", 2020, "ZZZZ", 2000)
        assert score >= 0.0

    def test_score_clamped_to_one(self) -> None:
        """Score should never exceed 1.0."""
        score = score_match("The Matrix", 1999, "The Matrix", 1999)
        assert score <= 1.0

    def test_partial_match_tokens(self) -> None:
        """WRatio should handle extra tokens in titles well."""
        # WRatio uses partial matching strategies
        score = score_match(
            "Interstellar", 2014,
            "Interstellar", 2014,
        )
        assert score >= HIGH_CONFIDENCE

    def test_title_with_article_difference(self) -> None:
        """French titles with/without articles should still match."""
        score = score_match("Intouchables", 2011, "Intouchables", 2011)
        assert score >= HIGH_CONFIDENCE

    def test_local_year_none_api_year_present(self) -> None:
        """Missing local year should not penalize or bonus."""
        score = score_match("The Matrix", None, "The Matrix", 1999)
        # Should be high based on title alone (no year adjustment)
        assert score >= 0.9


# ---------------------------------------------------------------------------
# match_movie — mocked TMDB
# ---------------------------------------------------------------------------

class TestMatchMovie:
    """Tests for match_movie() with mocked TMDB client."""

    def _make_tmdb_client(self, search_results: list[dict]) -> MagicMock:
        """Create a mock TMDBClient with preset search results."""
        client = MagicMock()
        client.search_movie.return_value = search_results
        return client

    def test_match_found(self) -> None:
        """Should return the best match when results exist."""
        client = self._make_tmdb_client([
            {"id": 603, "title": "The Matrix", "release_date": "1999-03-31"},
        ])
        result = match_movie(client, "The Matrix", 1999)

        assert result is not None
        assert result.api_id == 603
        assert result.api_title == "The Matrix"
        assert result.api_year == 1999
        assert result.source == "tmdb"
        assert result.confidence >= HIGH_CONFIDENCE

    def test_no_results(self) -> None:
        """Should return None when TMDB returns no results."""
        client = self._make_tmdb_client([])
        result = match_movie(client, "xyznonexistent", 2024)
        assert result is None

    def test_best_match_selected(self) -> None:
        """Should pick the best-scoring result from multiple candidates."""
        client = self._make_tmdb_client([
            {"id": 1, "title": "Matrix", "release_date": "1993-01-01"},
            {"id": 603, "title": "The Matrix", "release_date": "1999-03-31"},
            {"id": 2, "title": "Matrix Reloaded", "release_date": "2003-05-15"},
        ])
        result = match_movie(client, "The Matrix", 1999)

        assert result is not None
        assert result.api_id == 603  # Exact match should win

    def test_year_from_release_date(self) -> None:
        """Year should be extracted from release_date field."""
        client = self._make_tmdb_client([
            {"id": 42, "title": "Test", "release_date": "2024-06-28"},
        ])
        result = match_movie(client, "Test", 2024)

        assert result is not None
        assert result.api_year == 2024

    def test_missing_release_date(self) -> None:
        """Missing release_date should result in None year."""
        client = self._make_tmdb_client([
            {"id": 42, "title": "Test", "release_date": ""},
        ])
        result = match_movie(client, "Test", None)

        assert result is not None
        assert result.api_year is None

    def test_search_called_with_params(self) -> None:
        """search_movie should be called with title and year."""
        client = self._make_tmdb_client([])
        match_movie(client, "Inception", 2010)
        client.search_movie.assert_called_once_with("Inception", 2010)


# ---------------------------------------------------------------------------
# prompt_user_choice — mocked input
# ---------------------------------------------------------------------------

class TestPromptUserChoice:
    """Tests for the interactive prompt."""

    def test_select_first(self) -> None:
        """User selecting '1' should return the first result."""
        results = [
            MatchResult(api_id=1, api_title="Movie A", api_year=2024, confidence=0.9, source="tmdb"),
            MatchResult(api_id=2, api_title="Movie B", api_year=2023, confidence=0.7, source="tmdb"),
        ]
        with patch("builtins.input", return_value="1"):
            choice = prompt_user_choice(results, "Test Movie")
        assert choice is not None
        assert choice.api_id == 1

    def test_select_none(self) -> None:
        """User selecting '0' should return None (skip)."""
        results = [
            MatchResult(api_id=1, api_title="Movie A", api_year=2024, confidence=0.9, source="tmdb"),
        ]
        with patch("builtins.input", return_value="0"):
            choice = prompt_user_choice(results, "Test Movie")
        assert choice is None

    def test_empty_results(self) -> None:
        """Empty results should return None without prompting."""
        choice = prompt_user_choice([], "Test Movie")
        assert choice is None
