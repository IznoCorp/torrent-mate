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
    _restore_french_elisions,
    match_tvshow,
    match_tvshow_tvdb_detailed,
)

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
