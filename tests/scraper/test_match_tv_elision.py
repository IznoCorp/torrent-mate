"""A French title whose elision apostrophe was lost still matches on TVDB.

Release names cannot carry an apostrophe (``L.Institut.S02E01…``), so the cleaned folder title
reaches the scraper as ``L Institut``. TVDB's ``/search`` tokenises ``L'Institut`` as one word and
returns NOTHING for ``L Institut`` — verified on the live API on 2026-11-18, recorded in
``tests/fixtures/search/``. The scraper then fell to TMDB, which tolerates the missing apostrophe, and a
TVDB-canonical show (L'Institut, tvdb 451177) got a TMDB-only episode NFO.

Both payloads are REAL responses captured by ``scripts/capture_search_fixtures.py``; no live API is
called here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata._base import SearchResult
from personalscraper.api.metadata._tvdb_parsers import parse_search_result, unwrap
from personalscraper.scraper._match_tv import (
    _exact_title_hits,
    _restore_french_elisions,
    match_tvshow,
    match_tvshow_tvdb_detailed,
)
from personalscraper.scraper.search_ranking import gather_tv_candidates

FIXTURES = Path("tests/fixtures/search")

#: tvdb id of « The Institute » / « L'Institut » (2025) in the recorded payload.
INSTITUTE_TVDB_ID = 451177


def _load(label: str) -> list[SearchResult]:
    """Parse a recorded TVDB ``/search`` payload into SearchResult objects.

    Args:
        label: Fixture label, e.g. ``l-apostrophe-institut``.

    Returns:
        The parsed results, in provider order.
    """
    raw: Any = json.loads((FIXTURES / f"tvdb-search-{label}.json").read_text(encoding="utf-8"))
    return [parse_search_result(item, "tvdb") for item in unwrap(raw)]


def _recorded_tvdb() -> MagicMock:
    """Build a TVDB client double that answers with the two recorded payloads.

    The recorded behaviour of the live API: ``L'Institut`` finds the show, ``L Institut`` finds
    nothing. Any other query is a test bug, so it raises.

    Returns:
        A mock whose ``search_series`` replays the recorded responses and records its queries.
    """
    by_query = {
        "L'Institut": _load("l-apostrophe-institut"),
        "L Institut": _load("l-institut-no-apostrophe"),
        # A title the show list does not carry: TVDB's fuzzy answer to the restored query is noise.
        "L Insti": _load("l-institut-no-apostrophe"),
        "L'Insti": _load("l-apostrophe-institut"),
    }
    client = MagicMock()

    def search_series(title: str, year: int | None = None) -> list[SearchResult]:
        """Replay the recorded response for ``title`` (the year filter is ignored)."""
        return list(by_query[title])

    client.search_series.side_effect = search_series
    return client


def test_recorded_payloads_show_the_provider_behaviour() -> None:
    """The fixtures prove the premise: the apostrophe form finds the show, the spaced form finds nothing."""
    assert _load("l-institut-no-apostrophe") == []
    assert str(INSTITUTE_TVDB_ID) in {r.provider_id for r in _load("l-apostrophe-institut")}


def test_title_without_apostrophe_matches_on_tvdb() -> None:
    """`L Institut` (apostrophe lost in the release name) matches tvdb 451177, not nothing."""
    tvdb = _recorded_tvdb()

    match, candidates = match_tvshow_tvdb_detailed(tvdb, "L Institut", None)

    assert match is not None
    assert match.source == "tvdb"
    assert match.api_id == INSTITUTE_TVDB_ID
    assert match.confidence >= 0.95
    assert candidates[0].provider == "tvdb"
    assert candidates[0].provider_id == INSTITUTE_TVDB_ID
    # The literal query ran first; the restored form only because it found nothing.
    queries = [call.args[0] for call in tvdb.search_series.call_args_list]
    assert queries[0] == "L Institut"
    assert "L'Institut" in queries


def test_restored_query_with_a_year_merges_the_no_year_window() -> None:
    """With a folder year the retry also runs the no-year window query, as the literal search does."""
    tvdb = _recorded_tvdb()

    match, _ = match_tvshow_tvdb_detailed(tvdb, "L Institut", 2025)

    assert match is not None
    assert match.api_id == INSTITUTE_TVDB_ID
    calls = [(call.args[0], call.args[1]) for call in tvdb.search_series.call_args_list]
    assert ("L'Institut", 2025) in calls
    assert ("L'Institut", None) in calls


def test_exact_title_hits_keeps_only_the_show_carrying_the_title() -> None:
    """Of the 26 fuzzy rows TVDB returns for `L'Institut`, only tvdb 451177 carries that title."""
    hits = _exact_title_hits(_load("l-apostrophe-institut"), "L Institut")

    assert [r.provider_id for r in hits] == [str(INSTITUTE_TVDB_ID)]


def test_noise_from_the_restored_query_leaves_tvdb_silent() -> None:
    """A fuzzy answer with no row carrying the title is not a match: TVDB stays silent, TMDB runs."""
    tvdb = _recorded_tvdb()
    tmdb = MagicMock()
    tmdb.search_tv.return_value = []

    assert match_tvshow_tvdb_detailed(tvdb, "L Insti", None) == (None, [])
    match_tvshow(tvdb, tmdb, "L Insti", None)

    tmdb.search_tv.assert_called()


def test_tmdb_is_not_consulted_when_the_restored_query_finds_the_show() -> None:
    """TVDB stays canonical: the TMDB fallback never runs for `L Institut`."""
    tvdb = _recorded_tvdb()
    tmdb = MagicMock()

    match = match_tvshow(tvdb, tmdb, "L Institut", None)

    assert match is not None
    assert match.source == "tvdb"
    assert match.api_id == INSTITUTE_TVDB_ID
    tmdb.search_tv.assert_not_called()


def test_a_literal_hit_is_never_retried() -> None:
    """A title that already finds results issues no restored-apostrophe query."""
    tvdb = _recorded_tvdb()

    match_tvshow_tvdb_detailed(tvdb, "L'Institut", None)

    assert {call.args[0] for call in tvdb.search_series.call_args_list} == {"L'Institut"}


def test_a_title_without_elision_issues_no_extra_query() -> None:
    """No elided article, no second query: an unknown show costs the same calls as before."""
    tvdb = MagicMock()
    tvdb.search_series.return_value = []

    match, candidates = match_tvshow_tvdb_detailed(tvdb, "Nonexistent Show", None)

    assert (match, candidates) == (None, [])
    assert [call.args[0] for call in tvdb.search_series.call_args_list] == ["Nonexistent Show"]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("L Institut", "L'Institut"),
        ("l institut", "l'institut"),
        ("D Artagnan", "D'Artagnan"),
        ("Anatomie d un instant", "Anatomie d'un instant"),
        ("J ai tue ma mere", "J'ai tue ma mere"),
        ("C Est La Vie", "C'Est La Vie"),
        ("Aujourd Hui", None),
        ("Les Experts", None),
        ("L Dernier", None),
        ("The Institute", None),
        ("Nonexistent Show", None),
        ("", None),
    ],
)
def test_restore_french_elisions(title: str, expected: str | None) -> None:
    """Only an elision letter followed by a vowel or h gets its apostrophe back."""
    assert _restore_french_elisions(title) == expected


def test_manual_search_finds_the_show_typed_without_its_apostrophe() -> None:
    """The operator's manual search gets the same retry: `L Institut` surfaces tvdb 451177."""
    tvdb = _recorded_tvdb()
    tmdb = MagicMock()
    tmdb.search_tv.return_value = []

    rows = gather_tv_candidates(tvdb, tmdb, "L Institut")

    assert [r.provider_id for r in rows] == [str(INSTITUTE_TVDB_ID)]
    assert [call.args[0] for call in tvdb.search_series.call_args_list] == ["L Institut", "L'Institut"]


def test_manual_search_drops_the_noise_of_the_restored_query() -> None:
    """A fuzzy restored answer with no row carrying the typed title adds nothing to the search."""
    tvdb = _recorded_tvdb()
    tmdb = MagicMock()
    tmdb.search_tv.return_value = []

    assert gather_tv_candidates(tvdb, tmdb, "L Insti") == []


def test_manual_search_does_not_retry_a_literal_hit() -> None:
    """A query TVDB already answers issues no second TVDB call."""
    tvdb = _recorded_tvdb()
    tmdb = MagicMock()
    tmdb.search_tv.return_value = []

    gather_tv_candidates(tvdb, tmdb, "L'Institut")

    assert [call.args[0] for call in tvdb.search_series.call_args_list] == ["L'Institut"]
