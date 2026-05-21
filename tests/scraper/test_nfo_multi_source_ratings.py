"""Tests for the multi-source ``_add_ratings`` path on :class:`NFOGenerator` (phase 6).

Pins :

- Backward-compat — without ``notations``, behaviour is identical to
  the legacy single-source path.
- Multi-source — one ``<rating>`` per :class:`Notations`, correct
  ``name`` / ``max`` / ``value`` / ``votes`` on each.
- ``default="true"`` is applied to exactly one row, on the
  canonical source.
- Unknown sources fall back to their internal name unchanged.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from personalscraper.api.metadata._base import Notations
from personalscraper.scraper.nfo_generator import NFOGenerator


def _ratings_xml(
    notations: list[Notations] | None = None,
    canonical_source: str | None = None,
    legacy_data: dict | None = None,
    rating_name: str = "themoviedb",
) -> ET.Element:
    """Drive ``_add_ratings`` and return the resulting ``<ratings>`` element."""
    nfo = NFOGenerator()
    root = ET.Element("root")
    nfo._add_ratings(
        root,
        legacy_data or {},
        rating_name=rating_name,
        notations=notations,
        canonical_source=canonical_source,
    )
    ratings = root.find("ratings")
    assert ratings is not None
    return ratings


# ---------------------------------------------------------------------------
# Backward compatibility — legacy single-source path
# ---------------------------------------------------------------------------


def test_add_ratings_legacy_path_unchanged() -> None:
    """Without ``notations``, legacy single-source emission is preserved."""
    ratings = _ratings_xml(legacy_data={"vote_average": 8.4, "vote_count": 1234}, rating_name="themoviedb")
    rows = ratings.findall("rating")
    assert len(rows) == 1
    row = rows[0]
    assert row.get("name") == "themoviedb"
    assert row.get("default") == "true"
    assert row.get("max") == "10"
    assert row.findtext("value") == "8.4"
    assert row.findtext("votes") == "1234"


# ---------------------------------------------------------------------------
# Multi-source — one <rating> per Notations row
# ---------------------------------------------------------------------------


def test_add_ratings_multi_source_one_row_per_notation() -> None:
    """A list of three :class:`Notations` produces three ``<rating>`` children."""
    notations = [
        Notations(provider="omdb", source="imdb", score=8.5, votes_count=1_000_000),
        Notations(provider="omdb", source="rotten_tomatoes", score=91.0, votes_count=0),
        Notations(provider="tmdb", source="tmdb", score=8.2, votes_count=4_321),
    ]
    ratings = _ratings_xml(notations=notations, canonical_source="themoviedb")
    rows = ratings.findall("rating")
    names = [r.get("name") for r in rows]
    assert names == ["imdb", "rottentomatoes", "themoviedb"]


def test_add_ratings_canonical_source_receives_default_true() -> None:
    """Only the canonical row carries ``default="true"``."""
    notations = [
        Notations(provider="omdb", source="imdb", score=8.5, votes_count=10),
        Notations(provider="tmdb", source="tmdb", score=8.2, votes_count=1),
    ]
    ratings = _ratings_xml(notations=notations, canonical_source="imdb")
    defaults = [r.get("name") for r in ratings.findall("rating") if r.get("default") == "true"]
    assert defaults == ["imdb"]


def test_add_ratings_default_falls_back_to_first_when_no_canonical_match() -> None:
    """When ``canonical_source`` is ``None``, the first row receives ``default="true"``."""
    notations = [
        Notations(provider="omdb", source="rotten_tomatoes", score=91.0, votes_count=0),
        Notations(provider="omdb", source="imdb", score=8.5, votes_count=10),
    ]
    ratings = _ratings_xml(notations=notations, canonical_source=None)
    defaults = [r.get("name") for r in ratings.findall("rating") if r.get("default") == "true"]
    assert defaults == ["rottentomatoes"]


def test_add_ratings_max_attribute_matches_source_range() -> None:
    """IMDb / TMDb use ``max=10`` ; Rotten Tomatoes uses ``max=100``."""
    notations = [
        Notations(provider="omdb", source="imdb", score=8.5, votes_count=10),
        Notations(provider="omdb", source="rotten_tomatoes", score=91.0, votes_count=0),
        Notations(provider="tmdb", source="tmdb", score=8.2, votes_count=1),
    ]
    ratings = _ratings_xml(notations=notations, canonical_source="imdb")
    max_by_name = {r.get("name"): r.get("max") for r in ratings.findall("rating")}
    assert max_by_name == {"imdb": "10", "rottentomatoes": "100", "themoviedb": "10"}


def test_add_ratings_score_and_votes_serialised() -> None:
    """``Notations.score`` and ``votes_count`` land verbatim in the XML."""
    notations = [
        Notations(provider="omdb", source="imdb", score=8.5, votes_count=999),
    ]
    ratings = _ratings_xml(notations=notations, canonical_source="imdb")
    row = ratings.find("rating")
    assert row is not None
    assert row.findtext("value") == "8.5"
    assert row.findtext("votes") == "999"


# ---------------------------------------------------------------------------
# 6.3 — uniqueid default attribute reflects canonical provider
# ---------------------------------------------------------------------------


def _episode_xml(**episode_data) -> ET.Element:  # type: ignore[no-untyped-def]
    nfo = NFOGenerator()
    xml = nfo.generate_episode_nfo(
        {
            "name": "Pilot",
            "showtitle": "Show",
            "season_number": 1,
            "episode_number": 1,
            "overview": "",
            "mpaa": "",
            "studio": "",
            "crew": [],
            "still_path": "",
            **episode_data,
        }
    )
    return ET.fromstring(xml)


def test_generate_episode_nfo_tvdb_canonical_writes_uniqueid_tvdb_default() -> None:
    """``canonical_provider="tvdb"`` → tvdb gets ``default="true"``."""
    root = _episode_xml(
        canonical_provider="tvdb",
        tvdb_id="9001",
        tmdb_id="5001",
        imdb_id="tt0000001",
    )
    by_type = {u.get("type"): u for u in root.findall("uniqueid")}
    assert by_type["tvdb"].get("default") == "true"
    assert by_type["tmdb"].get("default") is None
    assert by_type["imdb"].get("default") is None


def test_generate_episode_nfo_tmdb_canonical_writes_uniqueid_tmdb_default() -> None:
    """``canonical_provider="tmdb"`` → tmdb gets ``default="true"``."""
    root = _episode_xml(
        canonical_provider="tmdb",
        tvdb_id="9001",
        tmdb_id="5001",
        imdb_id="tt0000001",
    )
    by_type = {u.get("type"): u for u in root.findall("uniqueid")}
    assert by_type["tmdb"].get("default") == "true"
    assert by_type["tvdb"].get("default") is None


def test_generate_episode_nfo_imdb_uniqueid_written_when_id_propagated() -> None:
    """The ``imdb_id`` row appears in the XML when the matched dict carries it."""
    root = _episode_xml(
        canonical_provider="tvdb",
        tvdb_id="9001",
        imdb_id="tt0000001",
    )
    by_type = {u.get("type"): u.text for u in root.findall("uniqueid")}
    assert by_type["imdb"] == "tt0000001"


def test_generate_episode_nfo_default_falls_back_when_canonical_missing() -> None:
    """No ``canonical_provider`` → legacy "tvdb default when present" behaviour."""
    root = _episode_xml(tvdb_id="9001", tmdb_id="5001")
    by_type = {u.get("type"): u for u in root.findall("uniqueid")}
    assert by_type["tvdb"].get("default") == "true"


def test_generate_episode_nfo_default_falls_back_to_tmdb_when_no_tvdb() -> None:
    """Canonical absent + no TVDB id → tmdb takes the default."""
    root = _episode_xml(tmdb_id="5001")
    by_type = {u.get("type"): u for u in root.findall("uniqueid")}
    assert by_type["tmdb"].get("default") == "true"


def test_add_ratings_deduplicates_same_source() -> None:
    """Two ``Notations`` from the same source surface as one ``<rating>`` row."""
    notations = [
        Notations(provider="omdb", source="imdb", score=8.5, votes_count=10),
        Notations(provider="trakt", source="imdb", score=9.0, votes_count=999),  # duplicate source
    ]
    ratings = _ratings_xml(notations=notations, canonical_source="imdb")
    rows = ratings.findall("rating")
    assert len(rows) == 1
    assert rows[0].get("name") == "imdb"
    # First entry wins.
    assert rows[0].findtext("value") == "8.5"
