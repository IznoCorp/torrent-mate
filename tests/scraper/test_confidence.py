"""Tests for confidence scoring and movie matching.

Tests score_match() with parametrized cases (exact, partial, bad matches,
accented French titles) and match_movie() with mocked TMDB responses.
"""

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata._base import EpisodeInfo, MediaDetails, SearchResult, SeasonDetails, SeasonInfo
from personalscraper.scraper.confidence import (
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    MatchResult,
    _score_result,
    _superstring_penalty,
    get_episode_titles,
    match_movie,
    match_tvshow,
    match_tvshow_tvdb,
    prompt_user_choice,
    score_match,
)  # noqa: F401

# ---------------------------------------------------------------------------
# Helpers — adapt legacy dict-shaped TMDB/TVDB responses to api-unify
# SearchResult instances. These mirror what the typed API clients now emit.
# ---------------------------------------------------------------------------


def _sr_tmdb_movie(d: dict[str, Any]) -> SearchResult:
    """Build a SearchResult from a legacy TMDB movie response dict.

    Accepts the historical shape ``{"id": int, "title": str, "release_date": "YYYY-MM-DD"}``
    and reshapes it into the unified SearchResult model.
    """
    rd = d.get("release_date") or ""
    return SearchResult(
        provider="tmdb",
        provider_id=str(d.get("id", "")),
        title=d.get("title", ""),
        original_title=d.get("original_title", ""),
        year=int(rd[:4]) if rd[:4].isdigit() else None,
        media_type="movie",
    )


def _sr_tmdb_tv(d: dict[str, Any]) -> SearchResult:
    """Build a SearchResult from a legacy TMDB tv response dict.

    Accepts ``{"id": int, "name": str, "first_air_date": "YYYY-MM-DD"}``.
    """
    fad = d.get("first_air_date") or ""
    return SearchResult(
        provider="tmdb",
        provider_id=str(d.get("id", "")),
        title=d.get("name", ""),
        year=int(fad[:4]) if fad[:4].isdigit() else None,
        media_type="tv",
    )


def _sr_tvdb(d: dict[str, Any]) -> SearchResult:
    """Build a SearchResult from a legacy TVDB search response dict.

    Accepts ``{"tvdb_id": str, "name": str, "year": str}``.
    """
    y = str(d.get("year") or "")
    return SearchResult(
        provider="tvdb",
        provider_id=str(d.get("tvdb_id", "")),
        title=d.get("name", ""),
        year=int(y) if y.isdigit() else None,
        media_type="tv",
    )


def _md_tvdb_series(tvdb_id: int, season_numbers: list[int]) -> MediaDetails:
    """Build a typed MediaDetails for a TVDB series with the given season catalog.

    Phase-27 helper: replaces the legacy ``tvdb.get_series.return_value =
    {"seasons": [{"number": 1}, ...]}`` shape with a real MediaDetails
    instance whose ``seasons`` field carries SeasonInfo entries — the
    actual contract that ``_candidate_has_any_season`` consumes.
    """
    return MediaDetails(
        provider="tvdb",
        provider_id=str(tvdb_id),
        seasons=[SeasonInfo(season_number=n) for n in season_numbers],
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

    def _make_tmdb_client(
        self,
        search_results: list[dict[str, Any]],
        *,
        language: str = "fr-FR",
        fallback_language: str = "en-US",
    ) -> MagicMock:
        """Create a mock TMDBClient with preset search results.

        Accepts legacy dict shapes for ergonomic test bodies and converts
        them to typed SearchResult instances — matching what the real
        api-unify TMDBClient now emits.

        Args:
            search_results: Legacy TMDB search result dicts.
            language: Primary search language (default "fr-FR").
            fallback_language: Fallback search language (default "en-US").
        """
        client = MagicMock()
        client._language = language
        client._fallback_language = fallback_language
        client.search_movie.return_value = [_sr_tmdb_movie(r) for r in search_results]
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

    def test_original_title_used_for_localized_movie_score(self) -> None:
        """Original title should rescue localized TMDB titles with the same year.

        Pre-api-unify behavior: when TMDB returned a localized title (e.g.
        'L'Effet papillon' with original_title='The Butterfly Effect'), the
        match logic scored against both candidates and accepted the higher.
        api-unify's typed SearchResult dropped the original_title field.
        """
        client = self._make_tmdb_client(
            [
                {
                    "id": 1954,
                    "title": "L'Effet papillon",
                    "original_title": "The Butterfly Effect",
                    "release_date": "2004-01-22",
                },
            ]
        )

        result = match_movie(client, "The Butterfly Effect", 2004)

        assert result is not None
        assert result.api_id == 1954
        assert result.api_title == "L'Effet papillon"
        assert result.confidence >= HIGH_CONFIDENCE

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
        """Initial search uses primary language with title and year."""
        client = self._make_tmdb_client([])
        match_movie(client, "Inception", 2010)
        client.search_movie.assert_any_call("Inception", 2010, language="fr-FR")

    def test_year_filter_excludes_correct_film_rescued_by_window(self) -> None:
        """Year-window merge rescues a film TMDB's year= filter wrongly excludes.

        Regression test for the 'La Cité des Anges' mismatch (pipeline run
        2026-05-30): TMDB's `year=` param matches ANY region's release date,
        so a search for "La Cité des Anges" with year=1997 returns only
        'The Crow: City of Angels' (1996, which has a 1997 regional release)
        and excludes 'City of Angels' (1998, release 1998-04-10). The
        year-filtered result is non-empty, so the old code never ran the
        no-year fallback and auto-accepted the wrong film at confidence 0.9.

        The fix: when a year is present, always merge the no-year candidates
        within the ±5y window. 'City of Angels' (exact FR title, year off by
        one) then scores 1.0 and beats the Crow (partial title, 0.9).
        """
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        crow = {
            "id": 10546,
            "title": "The Crow : La Cité des Anges",
            "release_date": "1996-08-30",
        }
        city = {
            "id": 795,
            "title": "La Cité des anges",
            "release_date": "1998-04-10",
        }

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            # TMDB year= filter: 1997 catches the Crow's regional release only.
            if language == "fr-FR" and y == 1997:
                return [_sr_tmdb_movie(crow)]
            # No-year search returns both films.
            if language == "fr-FR" and y is None:
                return [_sr_tmdb_movie(crow), _sr_tmdb_movie(city)]
            return []

        client.search_movie.side_effect = search_side
        result = match_movie(client, "La Cité des Anges", 1997)

        assert result is not None
        assert result.api_id == 795  # City of Angels (1998), NOT the Crow
        assert result.api_year == 1998
        assert result.confidence >= HIGH_CONFIDENCE

    def test_window_merge_localized_title_beats_making_of(self) -> None:
        """original_title scoring stops a window-merge noise candidate winning.

        Regression test for The Frighteners (pipeline run 2026-05-30): with a
        year filter, year=1996 returned only 'Fantômes contre fantômes' (FR
        title of The Frighteners; original_title 'The Frighteners'). The
        no-year window merge then added "The Making of 'The Frighteners'"
        (1998), whose localized title contains the query as a substring (0.75)
        and beat the real film's localized title scored against the English
        query (0.57). Scoring against original_title lifts the real film to
        1.0 so it wins, and its localized title is kept for the NFO/folder.
        """
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        film = {
            "id": 25297,
            "title": "Fantômes contre fantômes",
            "original_title": "The Frighteners",
            "release_date": "1996-07-18",
        }
        making_of = {
            "id": 999999,
            "title": "The Making of 'The Frighteners'",
            "original_title": "The Making of 'The Frighteners'",
            "release_date": "1998-01-01",
        }

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if language == "fr-FR" and y == 1996:
                return [_sr_tmdb_movie(film)]
            if language == "fr-FR" and y is None:
                return [_sr_tmdb_movie(film), _sr_tmdb_movie(making_of)]
            return []

        client.search_movie.side_effect = search_side
        result = match_movie(client, "The Frighteners", 1996)

        assert result is not None
        assert result.api_id == 25297  # the real film, not the making-of
        assert result.api_title == "Fantômes contre fantômes"  # localized kept
        assert result.confidence >= HIGH_CONFIDENCE

    # -- year fallback --

    def test_year_fallback_triggers_when_no_results_with_year(self) -> None:
        """Initial search returns 0, fallback without year finds match in window."""
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if y == 2026 and language == "fr-FR":
                return []
            if y is None and language == "fr-FR":
                return [
                    _sr_tmdb_movie({"id": 42, "title": "De Si Remarquables Créatures", "release_date": "2024-06-01"})
                ]
            return []

        client.search_movie.side_effect = search_side
        result = match_movie(client, "De Si Remarquables Créatures", 2026)

        assert result is not None
        assert result.api_id == 42
        assert result.api_year == 2024
        assert result.confidence >= LOW_CONFIDENCE

    def test_year_fallback_filters_outside_window(self) -> None:
        """Fallback results outside ±5 year window are filtered out."""
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if y == 2010 and language == "fr-FR":
                return []
            if y is None:
                return [_sr_tmdb_movie({"id": 99, "title": "Test Movie", "release_date": "2000-01-01"})]
            return []

        client.search_movie.side_effect = search_side
        result = match_movie(client, "Test Movie", 2010)
        # 2000 is 10 years from 2010, outside ±5 window
        assert result is None

    def test_language_fallback_not_triggered_when_fr_results_exist(self) -> None:
        """Language fallback chain is not triggered while fr results exist.

        With the year-window merge, a present year always runs a second
        no-year fr search (the bug-fix path), so search_movie is called twice
        in fr-FR. But the en-US language fallback (steps 3-4) must NOT be
        reached while fr results exist, and a lone fr candidate is unchanged
        by the merge.
        """
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if language == "fr-FR":
                return [_sr_tmdb_movie({"id": 603, "title": "The Matrix", "release_date": "1999-03-31"})]
            # en-US must never be consulted while fr results exist.
            return [_sr_tmdb_movie({"id": 999, "title": "Wrong", "release_date": "1999-01-01"})]

        client.search_movie.side_effect = search_side
        result = match_movie(client, "The Matrix", 1999)

        assert result is not None
        assert result.api_id == 603
        # fr year-filtered + fr no-year window merge = exactly 2 fr searches;
        # the en-US language fallback is never reached (fr results exist).
        assert client.search_movie.call_count == 2
        assert all(c.kwargs.get("language") == "fr-FR" for c in client.search_movie.call_args_list)

    # -- language fallback --

    def test_language_fallback_triggers_after_year_fallback_fails(self) -> None:
        """Year fallback finds nothing, language fallback succeeds."""
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if language == "fr-FR":
                return []
            # en-US with year finds a match
            return [_sr_tmdb_movie({"id": 77, "title": "Some Movie", "release_date": "2024-01-01"})]

        client.search_movie.side_effect = search_side
        result = match_movie(client, "Some Movie", 2024)

        assert result is not None
        assert result.api_id == 77

    def test_year_language_fallback_triggers_when_all_previous_fail(self) -> None:
        """All prior searches fail, year+language fallback succeeds."""
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if language == "fr-FR":
                return []
            if y == 2026 and language == "en-US":
                return []
            # en-US without year
            return [_sr_tmdb_movie({"id": 88, "title": "Le Film", "release_date": "2024-05-01"})]

        client.search_movie.side_effect = search_side
        result = match_movie(client, "Le Film", 2026)

        assert result is not None
        assert result.api_id == 88
        assert result.api_year == 2024

    def test_language_fallback_not_triggered_when_year_fallback_succeeds(self) -> None:
        """Year fallback succeeds — language fallback is never reached."""
        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if y == 2026 and language == "fr-FR":
                return []
            if y is None and language == "fr-FR":
                return [_sr_tmdb_movie({"id": 42, "title": "Test", "release_date": "2024-01-01"})]
            # en-US should not be called
            return [_sr_tmdb_movie({"id": 999, "title": "Wrong", "release_date": "2024-01-01"})]

        client.search_movie.side_effect = search_side
        result = match_movie(client, "Test", 2026)

        assert result is not None
        assert result.api_id == 42  # fr-FR fallback wins, en-US never consulted

    # -- logging --

    def test_year_fallback_logs_event(self, caplog: pytest.LogCaptureFixture) -> None:
        """Year fallback emits movie_match_year_fallback."""
        import logging

        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if y == 2026 and language == "fr-FR":
                return []
            return [_sr_tmdb_movie({"id": 42, "title": "Test", "release_date": "2024-01-01"})]

        client.search_movie.side_effect = search_side

        with caplog.at_level(logging.INFO, logger="confidence"):
            result = match_movie(client, "Test", 2026)

        assert result is not None
        events = [r.msg.get("event") for r in caplog.records if isinstance(r.msg, dict)]
        assert "movie_match_year_fallback" in events

    def test_language_fallback_logs_event(self, caplog: pytest.LogCaptureFixture) -> None:
        """Language fallback emits movie_match_language_fallback."""
        import logging

        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if language == "fr-FR":
                return []
            return [_sr_tmdb_movie({"id": 55, "title": "Test", "release_date": "2024-01-01"})]

        client.search_movie.side_effect = search_side

        with caplog.at_level(logging.INFO, logger="confidence"):
            result = match_movie(client, "Test", 2024)

        assert result is not None
        events = [r.msg.get("event") for r in caplog.records if isinstance(r.msg, dict)]
        assert "movie_match_language_fallback" in events

    def test_year_language_fallback_logs_event(self, caplog: pytest.LogCaptureFixture) -> None:
        """year+language fallback emits movie_match_year_language_fallback."""
        import logging

        client = MagicMock()
        client._language = "fr-FR"
        client._fallback_language = "en-US"

        def search_side(t: str, y: int | None, *, language: str = "fr-FR") -> list[object]:
            if language == "fr-FR":
                return []
            if y == 2026 and language == "en-US":
                return []
            return [_sr_tmdb_movie({"id": 99, "title": "Test", "release_date": "2024-01-01"})]

        client.search_movie.side_effect = search_side

        with caplog.at_level(logging.INFO, logger="confidence"):
            result = match_movie(client, "Test", 2026)

        assert result is not None
        events = [r.msg.get("event") for r in caplog.records if isinstance(r.msg, dict)]
        assert "movie_match_year_language_fallback" in events


# ---------------------------------------------------------------------------
# match_tvshow — TVDB + TMDB fallback
# ---------------------------------------------------------------------------


class TestMatchTvshow:
    """Tests for TV show matching with TVDB/TMDB fallback."""

    def test_tvdb_match_found(self) -> None:
        """Should return TVDB match when found with high confidence."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "81189", "name": "Breaking Bad", "year": "2008"}),
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
            _sr_tvdb({"tvdb_id": "12345", "name": "Test Show", "year": "2020"}),
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
            _sr_tmdb_tv({"id": 67195, "name": "Lupin", "first_air_date": "2021-01-08"}),
        ]

        result = match_tvshow(tvdb, tmdb, "Lupin", 2021)

        assert result is not None
        assert result.source == "tmdb"
        assert result.api_id == 67195

    def test_french_documentary_subject_tmdb_fallback(self) -> None:
        """French documentary release titles should try a subject TMDB query."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = []

        tmdb = MagicMock()

        def fake_search_tv(query: str, year: int | None) -> list[SearchResult]:
            if query == "Prince Andrew":
                return [
                    _sr_tmdb_tv(
                        {
                            "id": 225658,
                            "name": "Andrew: The Problem Prince",
                            "first_air_date": "2023-05-01",
                        }
                    )
                ]
            return []

        tmdb.search_tv.side_effect = fake_search_tv

        result = match_tvshow(tvdb, tmdb, "Les secrets du Prince Andrew", 2023)

        assert result is not None
        assert result.source == "tmdb"
        assert result.api_id == 225658
        assert result.confidence >= HIGH_CONFIDENCE
        tmdb.search_tv.assert_any_call("Les secrets du Prince Andrew", 2023)
        tmdb.search_tv.assert_any_call("Prince Andrew", 2023)

    def test_tvdb_preferred_at_equal_confidence(self) -> None:
        """TVDB should win when both providers have equal confidence."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "100", "name": "Test Show", "year": "2020"}),
        ]

        tmdb = MagicMock()
        tmdb.search_tv.return_value = [
            _sr_tmdb_tv({"id": 200, "name": "Test Show", "first_air_date": "2020-01-01"}),
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
            _sr_tvdb({"tvdb_id": "346368", "name": "Top Chef France - Dans l'assiette", "year": "2016"}),
            # Main show: slightly lower title score but has S01..S17+
            _sr_tvdb({"tvdb_id": "77081", "name": "Top Chef", "year": "2010"}),
        ]

        def fake_get_series(tvdb_id: int) -> MediaDetails:
            if tvdb_id == 346368:
                return _md_tvdb_series(346368, [1, 2])
            if tvdb_id == 77081:
                return _md_tvdb_series(77081, list(range(1, 18)))
            return _md_tvdb_series(tvdb_id, [])

        tvdb.get_series.side_effect = fake_get_series

        result = match_tvshow_tvdb(tvdb, "Top Chef France", None, local_seasons={17})

        assert result is not None
        assert result.api_id == 77081

    def test_tvdb_no_local_seasons_keeps_score_based_winner(self) -> None:
        """Without local_seasons, the season veto is skipped — score decides.

        With the superstring penalty, an expansion candidate
        ("Top Chef France - Dans l'assiette", a distinct spin-off whose content
        words are a proper superset of the query) is demoted, so the base
        "Top Chef" wins on score. This is the desired behaviour: a folder named
        "Top Chef France" should resolve to the base show, not a "- Dans
        l'assiette" spin-off. The veto path is still NOT taken (get_series is
        never called) — selection remains purely score-based.
        """
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "346368", "name": "Top Chef France - Dans l'assiette", "year": "2016"}),
            _sr_tvdb({"tvdb_id": "77081", "name": "Top Chef", "year": "2010"}),
        ]

        result = match_tvshow_tvdb(tvdb, "Top Chef France", None)

        # get_series must not be called when no local_seasons provided.
        assert not tvdb.get_series.called
        assert result is not None
        # Superstring penalty demotes the expansion → base "Top Chef" wins on score.
        assert result.api_id == 77081

    def test_tvdb_local_seasons_no_survivor_falls_back_to_best_score(self) -> None:
        """If no candidate has the wanted season, fall back to best fuzzy score.

        Content-aware is a preference, not a veto — we must not return None
        on a fetch/coverage gap.
        """
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "1", "name": "Test Show", "year": "2020"}),
            _sr_tvdb({"tvdb_id": "2", "name": "Test Show B", "year": "2021"}),
        ]
        tvdb.get_series.return_value = _md_tvdb_series(0, [1])  # Only S01 everywhere

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
            _sr_tvdb({"tvdb_id": "475278", "name": "Top Chef: Le Concours Parallèle", "year": "2023"}),
            # Weak match, would normally be the second choice
            _sr_tvdb({"tvdb_id": "999", "name": "Unrelated", "year": "2020"}),
        ]
        tvdb.get_series.return_value = _md_tvdb_series(0, [1, 2])

        result = match_tvshow_tvdb(tvdb, "Top Chef Le Concours Parallèle", 2023, local_seasons={17})

        assert result is not None
        assert result.api_id == 475278

    def test_tvdb_candidate_fetch_failure_does_not_veto(self) -> None:
        """Transient get_series failure must not drop a candidate silently."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "1", "name": "Test Show", "year": "2020"}),
            _sr_tvdb({"tvdb_id": "2", "name": "Test Show B", "year": "2020"}),
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
        """TVDB episodes use typed SeasonDetails — titles come from EpisodeInfo.title."""
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(
            provider="tvdb",
            tv_id="81189",
            season_number=1,
            episodes=[
                EpisodeInfo(episode_number=1, title="Pilot", overview="", air_date="", runtime_minutes=None),
                EpisodeInfo(episode_number=2, title="Cat's in the Bag", overview="", air_date="", runtime_minutes=None),
            ],
        )

        match_r = MatchResult(api_id=81189, api_title="Breaking Bad", api_year=2008, confidence=0.95, source="tvdb")
        titles = get_episode_titles(match_r, 1, tvdb, MagicMock())

        assert titles == {1: "Pilot", 2: "Cat's in the Bag"}

    def test_tvdb_fallback_to_english(self) -> None:
        """Episode titles fall back to placeholder when title is empty."""
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(
            provider="tvdb",
            tv_id="1",
            season_number=1,
            episodes=[
                EpisodeInfo(episode_number=1, title="", overview="", air_date="", runtime_minutes=None),
            ],
        )

        match_r = MatchResult(api_id=1, api_title="Test", api_year=2020, confidence=0.9, source="tvdb")
        titles = get_episode_titles(match_r, 1, tvdb, MagicMock())

        assert titles == {1: "Episode 1"}

    def test_tvdb_fallback_to_original(self) -> None:
        """Episode title is used directly from the typed API response."""
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(
            provider="tvdb",
            tv_id="1",
            season_number=1,
            episodes=[
                EpisodeInfo(episode_number=1, title="Original Title", overview="", air_date="", runtime_minutes=None),
            ],
        )

        match_r = MatchResult(api_id=1, api_title="Test", api_year=2020, confidence=0.9, source="tvdb")
        titles = get_episode_titles(match_r, 1, tvdb, MagicMock())

        assert titles == {1: "Original Title"}

    def test_tmdb_episodes(self) -> None:
        """TMDB episodes use typed SeasonDetails from get_tv_season."""
        tmdb = MagicMock()
        tmdb.get_tv_season.return_value = SeasonDetails(
            provider="tmdb",
            tv_id="67195",
            season_number=1,
            episodes=[
                EpisodeInfo(episode_number=1, title="Chapitre 1", overview="", air_date="", runtime_minutes=None),
                EpisodeInfo(episode_number=2, title="Chapitre 2", overview="", air_date="", runtime_minutes=None),
            ],
        )

        match_r = MatchResult(api_id=67195, api_title="Lupin", api_year=2021, confidence=0.9, source="tmdb")
        titles = get_episode_titles(match_r, 1, MagicMock(), tmdb)

        assert titles == {1: "Chapitre 1", 2: "Chapitre 2"}

    def test_empty_season(self) -> None:
        """Should return empty dict for non-existent season."""
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(provider="tvdb", tv_id="1", season_number=99, episodes=[])

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
            _sr_tmdb_movie({"id": 999, "release_date": "2024-01-01"}),
        ]

        result = match_movie(tmdb, "Test Movie", 2024)

        # Should still return a result (with empty title, low score)
        assert result is not None
        assert result.api_title == ""

    def test_malformed_tmdb_missing_release_date(self) -> None:
        """TMDB result without 'release_date' should not crash."""
        tmdb = MagicMock()
        tmdb.search_movie.return_value = [
            _sr_tmdb_movie({"id": 999, "title": "Test"}),
        ]

        result = match_movie(tmdb, "Test", None)

        assert result is not None
        assert result.api_year is None

    def test_malformed_tvdb_missing_name(self) -> None:
        """TVDB result without 'name' key should not crash."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "123", "year": "2024"}),
        ]

        result = match_tvshow_tvdb(tvdb, "Test Show", 2024)

        assert result is not None
        assert result.api_title == ""

    def test_malformed_tvdb_missing_year(self) -> None:
        """TVDB result without 'year' should not crash."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "123", "name": "Test Show"}),
        ]

        result = match_tvshow_tvdb(tvdb, "Test Show", None)

        assert result is not None
        assert result.api_year is None

    def test_malformed_tvdb_invalid_tvdb_id(self) -> None:
        """TVDB result with non-numeric tvdb_id should not crash."""
        tvdb = MagicMock()
        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "", "name": "Test", "year": "2024"}),
        ]

        result = match_tvshow_tvdb(tvdb, "Test", 2024)

        assert result is not None
        assert result.api_id == 0


class TestConfidenceConflict:
    """Tests for TMDB/TVDB conflict resolution."""

    def test_tvdb_match_never_overridden_by_tmdb(self) -> None:
        """TVDB-found is final. TMDB never overrides a TVDB match for TV shows.

        Project rule: TMDB-for-TV is permitted **only** when TVDB has no
        match for the show. Even when TVDB returned a wrong / low-confidence
        match and TMDB has a strictly better one, the result must be the
        TVDB match. The caller decides whether to skip on low confidence;
        we never silently retag a show against TMDB. This guards against
        the "South Park indexed as 1992 instead of 1997" class of bug
        where TMDB's TV branch overrides TVDB's authoritative entry.
        """
        tvdb = MagicMock()
        tmdb = MagicMock()

        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "111", "name": "Wrong Show", "year": "2024"}),
        ]
        tmdb.search_tv.return_value = [
            _sr_tmdb_tv({"id": 222, "name": "Correct Show", "first_air_date": "2024-01-01"}),
        ]

        result = match_tvshow(tvdb, tmdb, "Correct Show", 2024)

        assert result is not None
        assert result.source == "tvdb"
        # TMDB must not have been queried — TVDB returned a match,
        # the function must short-circuit before any TMDB call.
        tmdb.search_tv.assert_not_called()

    def test_tvdb_high_confidence_no_tmdb_fallback(self) -> None:
        """TVDB with HIGH_CONFIDENCE should not trigger TMDB fallback."""
        tvdb = MagicMock()
        tmdb = MagicMock()

        tvdb.search_series.return_value = [
            _sr_tvdb({"tvdb_id": "111", "name": "Exact Match", "year": "2024"}),
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
            _sr_tmdb_movie({"id": 1, "title": "Totally Unrelated Movie", "release_date": "1985-01-01"}),
            _sr_tmdb_movie({"id": 2, "title": "Another Unrelated Film", "release_date": "1990-06-15"}),
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
        payload: dict[str, Any] = warning_records[0].msg  # type: ignore[assignment]
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
            _sr_tvdb({"tvdb_id": "1", "name": "Completely Unrelated Show", "year": "1980"}),
        ]

        with caplog.at_level(logging.WARNING, logger="confidence"):
            result = match_tvshow_tvdb(tvdb, "The Butterfly Effect", 2004)

        assert result is not None
        assert result.confidence < LOW_CONFIDENCE

        below_event = "scraper.match.below_threshold"
        warning_records = [r for r in caplog.records if isinstance(r.msg, dict) and r.msg.get("event") == below_event]
        assert warning_records, "expected scraper.match.below_threshold warning in caplog"
        payload: dict[str, Any] = warning_records[0].msg  # type: ignore[assignment]
        assert payload["title"] == "The Butterfly Effect"
        assert payload["candidates_count"] == 1
        assert payload["source"] == "tvdb"


# ---------------------------------------------------------------------------
# Maximal patch hardening — superstring penalty, original_title scoring,
# and TV year-filter parity (window merge). See pipeline run 2026-05-30.
# ---------------------------------------------------------------------------


class TestSuperstringPenalty:
    """Unit tests for _superstring_penalty (content-expansion demotion)."""

    def test_proper_superset_penalised(self) -> None:
        """A candidate adding a content word over the query is penalised."""
        # "The Crow : La Cité des Anges" adds the content word "crow".
        p = _superstring_penalty("La Cité des Anges", "The Crow : La Cité des Anges")
        assert p == pytest.approx(-0.08)

    def test_article_only_difference_not_penalised(self) -> None:
        """Differing only by an article ("Matrix" vs "The Matrix") → no penalty."""
        assert _superstring_penalty("Matrix", "The Matrix") == 0.0

    def test_equal_content_not_penalised(self) -> None:
        """Identical content words → no penalty."""
        assert _superstring_penalty("Heat", "Heat") == 0.0

    def test_disjoint_titles_not_penalised(self) -> None:
        """A localized title sharing no content words is not an expansion."""
        assert _superstring_penalty("The Frighteners", "Fantômes contre fantômes") == 0.0

    def test_penalty_scales_and_caps(self) -> None:
        """The penalty scales with extra words and is clamped to the -0.20 floor."""
        # 3 extra content words → -0.24 clamped to the -0.20 floor.
        assert _superstring_penalty("Show", "Show Alpha Beta Gamma") == pytest.approx(-0.20)


class TestScoreResult:
    """Unit tests for _score_result (title + original_title + penalty)."""

    def test_original_title_rescues_localized(self) -> None:
        """An English folder name scores high against a localized title via original_title."""
        r = SearchResult(
            provider="tmdb",
            provider_id="10779",
            title="Fantômes contre fantômes",
            original_title="The Frighteners",
            year=1996,
            media_type="movie",
        )
        # English folder name matches the original_title exactly → high score.
        assert _score_result("The Frighteners", 1996, r) >= HIGH_CONFIDENCE

    def test_superstring_demoted_below_exact(self) -> None:
        """An exact localized title outranks a prefixed-expansion candidate."""
        crow = SearchResult(
            provider="tmdb",
            provider_id="10546",
            title="The Crow : La Cité des Anges",
            original_title="The Crow: City of Angels",
            year=1996,
            media_type="movie",
        )
        city = SearchResult(
            provider="tmdb",
            provider_id="795",
            title="La Cité des anges",
            original_title="City of Angels",
            year=1998,
            media_type="movie",
        )
        crow_score = _score_result("La Cité des Anges", 1997, crow)
        city_score = _score_result("La Cité des Anges", 1997, city)
        # The exact localized title outranks the prefixed-expansion candidate.
        assert city_score > crow_score


class TestTvYearWindowParity:
    """TV matching must close the same year-filter exclusion gap as movies."""

    def test_tvshow_tvdb_year_window_rescues_excluded_show(self) -> None:
        """No-year window merge rescues a show the TVDB year filter excluded.

        The year filter returns only a wrong same-year show; the no-year window
        merge surfaces the correct show, which then wins on score.
        """
        tvdb = MagicMock()
        wrong = _sr_tvdb({"tvdb_id": "111", "name": "Galaxy Quest Show", "year": "2014"})
        right = _sr_tvdb({"tvdb_id": "222", "name": "My Detective", "year": "2016"})

        def side(t: str, y: int | None) -> list[object]:
            if y == 2014:
                return [wrong]  # year= filter excludes the correct 2016 show
            if y is None:
                return [wrong, right]
            return []

        tvdb.search_series.side_effect = side
        result = match_tvshow_tvdb(tvdb, "My Detective", 2014)

        assert result is not None
        assert result.api_id == 222  # rescued by the no-year window merge

    def test_tvshow_tvdb_original_title_rescues_localized(self) -> None:
        """A localized TVDB title is rescued by original_title.

        It must not be beaten by a content-expansion candidate.
        """
        tvdb = MagicMock()
        loc = SearchResult(
            provider="tvdb",
            provider_id="500",
            title="Les Soprano",
            original_title="The Sopranos",
            year=1999,
            media_type="tv",
        )
        expansion = SearchResult(
            provider="tvdb",
            provider_id="501",
            title="The Sopranos Family Values",
            original_title="The Sopranos Family Values",
            year=2001,
            media_type="tv",
        )
        tvdb.search_series.return_value = [loc, expansion]

        result = match_tvshow_tvdb(tvdb, "The Sopranos", 1999)

        assert result is not None
        assert result.api_id == 500


class TestAliasMatching:
    """Regression (DEV #2): a translated-title folder matches via aliases.

    Reproduces the production miss: folder "Murder Mindfully" against the
    German-primary TVDB candidate "Achtsam Morden". Before the fix the candidate
    only exposed its primary title, scoring ~0.38 (below LOW_CONFIDENCE), so the
    real show was left unscraped.
    """

    def test_alias_rescues_translated_folder(self) -> None:
        """The English alias makes the German-primary candidate score >= LOW."""
        candidate = SearchResult(
            provider="tvdb",
            provider_id="420001",
            title="Achtsam Morden",
            year=2024,
            original_title="Murder Mindfully",
            aliases=("Murder Mindfully", "Mindful Murder"),
        )
        score = _score_result("Murder Mindfully", 2024, candidate)
        assert score >= LOW_CONFIDENCE

    def test_primary_title_only_would_miss(self) -> None:
        """Without aliases/original (the old shape) the same folder scores low."""
        bare = SearchResult(
            provider="tvdb",
            provider_id="420001",
            title="Achtsam Morden",
            year=2024,
        )
        assert _score_result("Murder Mindfully", 2024, bare) < LOW_CONFIDENCE

    def test_aliases_only_raise_score(self) -> None:
        """Best-of scoring: an alias can only raise, never lower, the score."""
        with_alias = SearchResult(
            provider="tvdb",
            provider_id="1",
            title="Exact Title",
            year=2020,
            aliases=("totally different",),
        )
        assert _score_result("Exact Title", 2020, with_alias) == pytest.approx(
            _score_result(
                "Exact Title", 2020, SearchResult(provider="tvdb", provider_id="1", title="Exact Title", year=2020)
            )
        )


class TestAliasCollision:
    """Regression (review REG-1): an alias cannot make a wrong show win."""

    def test_exact_title_beats_different_year_colliding_alias(self) -> None:
        """A colliding alias does not outrank an exact-title, correct-year match."""
        right = SearchResult(provider="tvdb", provider_id="1", title="The Office", year=2005)
        wrong = SearchResult(
            provider="tvdb",
            provider_id="2",
            title="Parks and Recreation",
            year=2009,
            aliases=("The Office",),  # wrong show carries the query as an alias
        )
        assert _score_result("The Office", 2005, right) > _score_result("The Office", 2005, wrong)

    def test_superstring_alias_is_penalized(self) -> None:
        """An alias that is a superstring of the query is penalized vs the exact."""
        exact = SearchResult(provider="tvdb", provider_id="1", title="The Office", year=2005)
        superstring = SearchResult(
            provider="tvdb",
            provider_id="2",
            title="Whatever",
            year=2005,
            aliases=("The Office: Special Edition Extended",),
        )
        assert _score_result("The Office", 2005, exact) > _score_result("The Office", 2005, superstring)
