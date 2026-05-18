"""End-to-end shape tests for NFOs with multi-source ratings + canonical default.

Replays the DESIGN §5 nominal data flow : a TVDB-canonical TV show
with TMDb and IMDb cross-references, IMDb + Rotten Tomatoes ratings,
and asserts the resulting NFO carries every expected fragment in the
right order. These tests act as "golden" guards for Plex / Kodi
compatibility — readers expect ``<ratings>`` after ``<title>`` /
``<showtitle>`` and a single ``default="true"`` on each of
``<uniqueid>`` and ``<rating>``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from personalscraper.api.metadata._base import Notations
from personalscraper.scraper.nfo_generator import NFOGenerator


def _imdb() -> Notations:
    return Notations(provider="omdb", source="imdb", score=8.7, votes_count=1_234_567)


def _rt() -> Notations:
    return Notations(provider="omdb", source="rotten_tomatoes", score=92.0, votes_count=0)


def _tmdb_rating() -> Notations:
    return Notations(provider="tmdb", source="tmdb", score=8.4, votes_count=10_000)


def _generate_episode_nfo(**overrides) -> ET.Element:  # type: ignore[no-untyped-def]
    nfo = NFOGenerator()
    payload = {
        "name": "Pilot",
        "showtitle": "The Show",
        "season_number": 1,
        "episode_number": 1,
        "overview": "An origin story.",
        "mpaa": "TV-MA",
        "studio": "HBO",
        "crew": [],
        "still_path": "",
        "canonical_provider": "tvdb",
        "tvdb_id": "9001",
        "tmdb_id": "5001",
        "imdb_id": "tt0000001",
        "notations": [_imdb(), _rt(), _tmdb_rating()],
        "canonical_source": "themoviedb",  # NFO-name of the TMDb rating row
    }
    payload.update(overrides)
    xml = nfo.generate_episode_nfo(payload)
    return ET.fromstring(xml)


def test_episode_nfo_carries_all_uniqueid_families_with_canonical_default() -> None:
    """All three uniqueid families present, canonical tvdb is the only default."""
    root = _generate_episode_nfo()
    by_type = {u.get("type"): u for u in root.findall("uniqueid")}
    assert set(by_type) == {"tvdb", "tmdb", "imdb"}
    assert by_type["tvdb"].get("default") == "true"
    assert by_type["tmdb"].get("default") is None
    assert by_type["imdb"].get("default") is None


def test_episode_nfo_carries_three_rating_rows_with_canonical_default() -> None:
    """One ``<rating>`` per source ; exactly one default on the canonical row."""
    root = _generate_episode_nfo()
    ratings_block = root.find("ratings")
    assert ratings_block is not None
    rows = ratings_block.findall("rating")
    names = [r.get("name") for r in rows]
    assert sorted(names) == ["imdb", "rottentomatoes", "themoviedb"]
    defaults = [r.get("name") for r in rows if r.get("default") == "true"]
    assert defaults == ["themoviedb"]


def test_episode_nfo_rating_max_attributes_match_source_range() -> None:
    """``max=10`` for IMDb/TMDb, ``max=100`` for Rotten Tomatoes."""
    root = _generate_episode_nfo()
    max_by_name = {r.get("name"): r.get("max") for r in root.find("ratings").findall("rating")}  # type: ignore[union-attr]
    assert max_by_name == {"imdb": "10", "themoviedb": "10", "rottentomatoes": "100"}


def test_episode_nfo_tmdb_canonical_inverts_default() -> None:
    """TMDB-canonical show puts the default on the TMDB uniqueid row instead.

    Symmetric counterpart to the TVDB-canonical case ; together they
    cover the two canonical providers DESIGN §3 supports.
    """
    root = _generate_episode_nfo(canonical_provider="tmdb")
    by_type = {u.get("type"): u for u in root.findall("uniqueid")}
    assert by_type["tmdb"].get("default") == "true"
    assert by_type["tvdb"].get("default") is None
