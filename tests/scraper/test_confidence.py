"""Tests for confidence scoring and movie matching.

Tests score_match() with parametrized cases (exact, partial, bad matches,
accented French titles) and match_movie() with mocked TMDB responses.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.scraper.confidence import (
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    MatchResult,
    get_episode_titles,
    match_movie,
    match_tvshow,
    match_tvshow_tvdb,
    prompt_user_choice,
    score_match,
)  # noqa: F401

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
            "Les Misérables",
            2019,
            "Les Misérables",
            2019,
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
            "Interstellar",
            2014,
            "Interstellar",
            2014,
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
        client = self._make_tmdb_client(
            [
                {"id": 603, "title": "The Matrix", "release_date": "1999-03-31"},
            ]
        )
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
        client = self._make_tmdb_client(
            [
                {"id": 1, "title": "Matrix", "release_date": "1993-01-01"},
                {"id": 603, "title": "The Matrix", "release_date": "1999-03-31"},
                {"id": 2, "title": "Matrix Reloaded", "release_date": "2003-05-15"},
            ]
        )
        result = match_movie(client, "The Matrix", 1999)

        assert result is not None
        assert result.api_id == 603  # Exact match should win

    def test_year_from_release_date(self) -> None:
        """Year should be extracted from release_date field."""
        client = self._make_tmdb_client(
            [
                {"id": 42, "title": "Test", "release_date": "2024-06-28"},
            ]
        )
        result = match_movie(client, "Test", 2024)

        assert result is not None
        assert result.api_year == 2024

    def test_missing_release_date(self) -> None:
        """Missing release_date should result in None year."""
        client = self._make_tmdb_client(
            [
                {"id": 42, "title": "Test", "release_date": ""},
            ]
        )
        result = match_movie(client, "Test", None)

        assert result is not None
        assert result.api_year is None

    def test_search_called_with_params(self) -> None:
        """search_movie should be called with title and year."""
        client = self._make_tmdb_client([])
        match_movie(client, "Inception", 2010)
        client.search_movie.assert_called_once_with("Inception", 2010)


# ---------------------------------------------------------------------------
# match_tvshow — TVDB + TMDB fallback
# ---------------------------------------------------------------------------


class TestMatchTvshow:
    """Tests for TV show matching with TVDB/TMDB fallback."""

    def test_tvdb_match_found(self) -> None:
        """Should return TVDB match when found with high confidence."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "81189", "name": "Breaking Bad", "year": "2008"},
        ]

        result = match_tvshow_tvdb(tvdb, "Breaking Bad", 2008)

        assert result is not None
        assert result.api_id == 81189
        assert result.source == "tvdb"
        assert result.confidence >= HIGH_CONFIDENCE

    def test_tvdb_no_results(self) -> None:
        """Should return None when TVDB has no results."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = []

        result = match_tvshow_tvdb(tvdb, "nonexistent", 2024)
        assert result is None

    def test_tvdb_uses_tvdb_id_not_id(self) -> None:
        """Should use tvdb_id field (not id) from search results."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "12345", "name": "Test Show", "year": "2020"},
        ]

        result = match_tvshow_tvdb(tvdb, "Test Show", 2020)
        assert result is not None
        assert result.api_id == 12345

    def test_fallback_to_tmdb(self) -> None:
        """Should use TMDB when TVDB has no results."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = []

        tmdb = MagicMock()
        tmdb.search_tv.return_value = [
            {"id": 67195, "name": "Lupin", "first_air_date": "2021-01-08"},
        ]

        result = match_tvshow(tvdb, tmdb, "Lupin", 2021)

        assert result is not None
        assert result.source == "tmdb"
        assert result.api_id == 67195

    def test_tvdb_preferred_at_equal_confidence(self) -> None:
        """TVDB should win when both providers have equal confidence."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "100", "name": "Test Show", "year": "2020"},
        ]

        tmdb = MagicMock()
        tmdb.search_tv.return_value = [
            {"id": 200, "name": "Test Show", "first_air_date": "2020-01-01"},
        ]

        result = match_tvshow(tvdb, tmdb, "Test Show", 2020)

        assert result is not None
        assert result.source == "tvdb"

    def test_both_no_results(self) -> None:
        """Should return None when neither provider has results."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = []
        tmdb = MagicMock()
        tmdb.search_tv.return_value = []

        result = match_tvshow(tvdb, tmdb, "nonexistent", 2024)
        assert result is None

    def test_tvdb_match_spin_off_filtered_by_local_seasons(self) -> None:
        """Candidate without the wanted season in its catalog is rejected.

        Regression: "Top Chef France" used to match a 2016 one-season
        spin-off because it was ranked first by TVDB search. When the
        local folder holds a S17 file, only candidates whose catalog
        contains S17 should survive.
        """
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            # Spin-off: matches keyword but only has S01-S02
            {"tvdb_id": "346368", "name": "Top Chef France - Dans l'assiette", "year": "2016"},
            # Main show: slightly lower title score but has S01..S17+
            {"tvdb_id": "77081", "name": "Top Chef", "year": "2010"},
        ]

        def fake_get_series(tvdb_id: int) -> dict:
            if tvdb_id == 346368:
                return {"seasons": [{"number": 1}, {"number": 2}]}
            if tvdb_id == 77081:
                return {"seasons": [{"number": s} for s in range(1, 18)]}
            return {}

        tvdb.get_series.side_effect = fake_get_series

        result = match_tvshow_tvdb(tvdb, "Top Chef France", None, local_seasons={17})

        assert result is not None
        assert result.api_id == 77081

    def test_tvdb_no_local_seasons_keeps_score_based_winner(self) -> None:
        """Without local_seasons, behavior is backwards-compatible (best score)."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "346368", "name": "Top Chef France - Dans l'assiette", "year": "2016"},
            {"tvdb_id": "77081", "name": "Top Chef", "year": "2010"},
        ]

        result = match_tvshow_tvdb(tvdb, "Top Chef France", None)

        # get_series must not be called when no local_seasons provided.
        assert not tvdb.get_series.called
        assert result is not None
        # Best fuzzy score wins (as before) — title "Top Chef France - Dans l'assiette"
        # contains the full query, so it scores higher than "Top Chef".
        assert result.api_id == 346368

    def test_tvdb_local_seasons_no_survivor_falls_back_to_best_score(self) -> None:
        """If no candidate has the wanted season, fall back to best fuzzy score.

        Content-aware is a preference, not a veto — we must not return None
        on a fetch/coverage gap.
        """
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "1", "name": "Test Show", "year": "2020"},
            {"tvdb_id": "2", "name": "Test Show B", "year": "2021"},
        ]
        tvdb.get_series.return_value = {"seasons": [{"number": 1}]}  # Only S01 everywhere

        result = match_tvshow_tvdb(tvdb, "Test Show", 2020, local_seasons={99})

        assert result is not None
        assert result.api_id == 1  # Best score winner (exact title + exact year)

    def test_tvdb_high_score_bypasses_season_veto(self) -> None:
        """Score >= 0.95 survives the content-aware filter even without season overlap.

        Covers parallel-numbering spin-offs whose own catalog is e.g. S01..S04
        but whose releases mirror the main show's season label (S17). A 0.95+
        title match is assumed unambiguous.
        """
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            # Very high title match, but catalog only has S01..S04
            {"tvdb_id": "475278", "name": "Top Chef: Le Concours Parallèle", "year": "2023"},
            # Weak match, would normally be the second choice
            {"tvdb_id": "999", "name": "Unrelated", "year": "2020"},
        ]
        tvdb.get_series.return_value = {"seasons": [{"number": 1}, {"number": 2}]}

        result = match_tvshow_tvdb(tvdb, "Top Chef Le Concours Parallèle", 2023, local_seasons={17})

        assert result is not None
        assert result.api_id == 475278

    def test_tvdb_candidate_fetch_failure_does_not_veto(self) -> None:
        """Transient get_series failure must not drop a candidate silently."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "1", "name": "Test Show", "year": "2020"},
            {"tvdb_id": "2", "name": "Test Show B", "year": "2020"},
        ]
        tvdb.get_series.side_effect = RuntimeError("network glitch")

        result = match_tvshow_tvdb(tvdb, "Test Show", 2020, local_seasons={1})

        # Both candidates survive (fetch error → keep), best score wins.
        assert result is not None
        assert result.api_id == 1


# ---------------------------------------------------------------------------
# get_episode_titles
# ---------------------------------------------------------------------------


class TestGetEpisodeTitles:
    """Tests for episode title fetching."""

    def test_tvdb_episodes_with_translation(self) -> None:
        """TVDB episodes should be translated to French."""
        tvdb = MagicMock()
        tvdb.get_season_episodes.return_value = [
            {"id": 100, "name": "Pilot", "number": 1},
            {"id": 101, "name": "Cat's in the Bag", "number": 2},
        ]
        tvdb.get_episode_translation.side_effect = [
            {"name": "Épisode pilote", "language": "fra"},
            {"name": "Le Chat dans le sac", "language": "fra"},
        ]

        match_r = MatchResult(api_id=81189, api_title="Breaking Bad", api_year=2008, confidence=0.95, source="tvdb")
        titles = get_episode_titles(match_r, 1, tvdb, MagicMock())

        assert titles == {1: "Épisode pilote", 2: "Le Chat dans le sac"}

    def test_tvdb_fallback_to_english(self) -> None:
        """Should fall back to English if French translation is missing."""
        tvdb = MagicMock()
        tvdb.get_season_episodes.return_value = [
            {"id": 100, "name": "Pilot", "number": 1},
        ]
        tvdb.get_episode_translation.side_effect = [
            None,
            {"name": "The Pilot", "language": "eng"},
        ]

        match_r = MatchResult(api_id=1, api_title="Test", api_year=2020, confidence=0.9, source="tvdb")
        titles = get_episode_titles(match_r, 1, tvdb, MagicMock())

        assert titles == {1: "The Pilot"}

    def test_tvdb_fallback_to_original(self) -> None:
        """Should use original name if no translations available."""
        tvdb = MagicMock()
        tvdb.get_season_episodes.return_value = [
            {"id": 100, "name": "Original Title", "number": 1},
        ]
        tvdb.get_episode_translation.return_value = None

        match_r = MatchResult(api_id=1, api_title="Test", api_year=2020, confidence=0.9, source="tvdb")
        titles = get_episode_titles(match_r, 1, tvdb, MagicMock())

        assert titles == {1: "Original Title"}

    def test_tmdb_episodes(self) -> None:
        """TMDB episodes should already be in French."""
        tmdb = MagicMock()
        tmdb.get_tv_season.return_value = {
            "episodes": [
                {"episode_number": 1, "name": "Chapitre 1"},
                {"episode_number": 2, "name": "Chapitre 2"},
            ],
        }

        match_r = MatchResult(api_id=67195, api_title="Lupin", api_year=2021, confidence=0.9, source="tmdb")
        titles = get_episode_titles(match_r, 1, MagicMock(), tmdb)

        assert titles == {1: "Chapitre 1", 2: "Chapitre 2"}

    def test_empty_season(self) -> None:
        """Should return empty dict for non-existent season."""
        tvdb = MagicMock()
        tvdb.get_season_episodes.return_value = []

        match_r = MatchResult(api_id=1, api_title="Test", api_year=2020, confidence=0.9, source="tvdb")
        titles = get_episode_titles(match_r, 99, tvdb, MagicMock())

        assert titles == {}


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


# ---------------------------------------------------------------------------
# Malformed API responses (V7.x)
# ---------------------------------------------------------------------------


class TestMalformedResponses:
    """Tests for resilience to malformed API responses."""

    def test_malformed_tmdb_missing_title(self) -> None:
        """TMDB result without 'title' key should not crash."""
        tmdb = MagicMock()
        tmdb.search_movie.return_value = [
            {"id": 999, "release_date": "2024-01-01"},
        ]

        result = match_movie(tmdb, "Test Movie", 2024)

        # Should still return a result (with empty title, low score)
        assert result is not None
        assert result.api_title == ""

    def test_malformed_tmdb_missing_release_date(self) -> None:
        """TMDB result without 'release_date' should not crash."""
        tmdb = MagicMock()
        tmdb.search_movie.return_value = [
            {"id": 999, "title": "Test"},
        ]

        result = match_movie(tmdb, "Test", None)

        assert result is not None
        assert result.api_year is None

    def test_malformed_tvdb_missing_name(self) -> None:
        """TVDB result without 'name' key should not crash."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "123", "year": "2024"},
        ]

        result = match_tvshow_tvdb(tvdb, "Test Show", 2024)

        assert result is not None
        assert result.api_title == ""

    def test_malformed_tvdb_missing_year(self) -> None:
        """TVDB result without 'year' should not crash."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "123", "name": "Test Show"},
        ]

        result = match_tvshow_tvdb(tvdb, "Test Show", None)

        assert result is not None
        assert result.api_year is None

    def test_malformed_tvdb_invalid_tvdb_id(self) -> None:
        """TVDB result with non-numeric tvdb_id should not crash."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "", "name": "Test", "year": "2024"},
        ]

        result = match_tvshow_tvdb(tvdb, "Test", 2024)

        assert result is not None
        assert result.api_id == 0


class TestConfidenceConflict:
    """Tests for TMDB/TVDB conflict resolution."""

    def test_tmdb_tvdb_conflict_prefer_higher_confidence(self) -> None:
        """When TMDB and TVDB differ, prefer the higher confidence match."""
        tvdb = MagicMock()
        tmdb = MagicMock()

        # TVDB returns a low-confidence match
        tvdb.search_series.return_value = [
            {"tvdb_id": "111", "name": "Wrong Show", "year": "2024"},
        ]

        # TMDB returns a high-confidence match
        tmdb.search_tv.return_value = [
            {"id": 222, "name": "Correct Show", "first_air_date": "2024-01-01"},
        ]

        result = match_tvshow(tvdb, tmdb, "Correct Show", 2024)

        assert result is not None
        assert result.api_title == "Correct Show"
        assert result.source == "tmdb"

    def test_tvdb_high_confidence_no_tmdb_fallback(self) -> None:
        """TVDB with HIGH_CONFIDENCE should not trigger TMDB fallback."""
        tvdb = MagicMock()
        tmdb = MagicMock()

        tvdb.search_series.return_value = [
            {"tvdb_id": "111", "name": "Exact Match", "year": "2024"},
        ]

        result = match_tvshow(tvdb, tmdb, "Exact Match", 2024)

        assert result is not None
        assert result.source == "tvdb"
        # TMDB should not have been called
        tmdb.search_tv.assert_not_called()

    def test_both_providers_no_results(self) -> None:
        """Both providers returning empty should return None."""
        tvdb = MagicMock()
        tmdb = MagicMock()

        tvdb.search_series.return_value = []
        tmdb.search_tv.return_value = []

        result = match_tvshow(tvdb, tmdb, "Nonexistent", 2024)

        assert result is None


# ---------------------------------------------------------------------------
# Below-threshold warning (10.1 — silent scrape failure observability)
# ---------------------------------------------------------------------------


class TestBelowThresholdWarning:
    """Tests for scraper.match.below_threshold warning emission.

    When match_movie or match_tvshow_tvdb returns candidates that all score
    below LOW_CONFIDENCE, a structured warning must be logged so the
    silent-skip does not go unnoticed in the pipeline output.
    """

    def test_match_movie_zero_candidates_returns_none_no_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Zero TMDB results → None returned, no below_threshold warning (nothing to warn about)."""
        tmdb = MagicMock()
        tmdb.search_movie.return_value = []

        with caplog.at_level(logging.WARNING, logger="confidence"):
            result = match_movie(tmdb, "The Butterfly Effect", 2004)

        assert result is None
        events = [r.msg.get("event") for r in caplog.records if isinstance(r.msg, dict)]
        assert "scraper.match.below_threshold" not in events

    def test_match_movie_below_threshold_emits_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TMDB returns candidates but all score < LOW_CONFIDENCE → warning logged."""
        tmdb = MagicMock()
        # A result that will score low against "The Butterfly Effect 2004"
        tmdb.search_movie.return_value = [
            {"id": 1, "title": "Totally Unrelated Movie", "release_date": "1985-01-01"},
            {"id": 2, "title": "Another Unrelated Film", "release_date": "1990-06-15"},
        ]

        with caplog.at_level(logging.WARNING, logger="confidence"):
            result = match_movie(tmdb, "The Butterfly Effect", 2004)

        # Should return the best candidate (not None), but it has low confidence
        assert result is not None
        assert result.confidence < LOW_CONFIDENCE

        # The warning event must be present
        target_event = "scraper.match.below_threshold"
        warning_records = [r for r in caplog.records if isinstance(r.msg, dict) and r.msg.get("event") == target_event]
        assert warning_records, "expected scraper.match.below_threshold warning in caplog"
        payload = warning_records[0].msg
        assert payload["title"] == "The Butterfly Effect"
        assert payload["year"] == 2004
        assert payload["candidates_count"] == 2
        assert payload["top_score"] == round(result.confidence, 2)
        assert payload["source"] == "tmdb"

    def test_match_tvshow_tvdb_below_threshold_emits_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TVDB returns candidates that all score < LOW_CONFIDENCE → warning logged."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            {"tvdb_id": "1", "name": "Completely Unrelated Show", "year": "1980"},
        ]

        with caplog.at_level(logging.WARNING, logger="confidence"):
            result = match_tvshow_tvdb(tvdb, "The Butterfly Effect", 2004)

        assert result is not None
        assert result.confidence < LOW_CONFIDENCE

        below_event = "scraper.match.below_threshold"
        warning_records = [r for r in caplog.records if isinstance(r.msg, dict) and r.msg.get("event") == below_event]
        assert warning_records, "expected scraper.match.below_threshold warning in caplog"
        payload = warning_records[0].msg
        assert payload["title"] == "The Butterfly Effect"
        assert payload["candidates_count"] == 1
        assert payload["source"] == "tvdb"
