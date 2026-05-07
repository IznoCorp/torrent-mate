"""Tests for ``_tvdb_series_to_show_data`` — phase 27 typed branch.

The function bridges TVDB-typed metadata into the legacy show_data dict
shape that downstream consumers (NFO generator, artwork downloader)
still expect. Phase 27 added a typed branch so production callers can
hand it the ``MediaDetails`` returned by ``TVDBClient.get_series``.
The legacy raw-dict branch is preserved for tests and rare callers.

These tests pin both branches: same TVDB show fed through either input
shape must produce the same minimum-viable ``show_data`` keys, and the
typed branch must populate the phase-27 fields the parser fills
(``seasons``, ``original_name``).
"""

from __future__ import annotations

from personalscraper.api.metadata._base import MediaDetails, SeasonInfo
from personalscraper.scraper.tv_service import _tvdb_series_to_show_data


class TestTypedBranch:
    """``MediaDetails`` input — phase-27 path."""

    def test_basic_fields_propagate(self) -> None:
        """Title, original_title, overview, year all surface in the output."""
        md = MediaDetails(
            provider="tvdb",
            provider_id="123",
            title="Le Bureau des Légendes",
            original_title="The Bureau",
            overview="French spy series.",
            year=2015,
        )
        out = _tvdb_series_to_show_data(md, tvdb_id=123)
        assert out["name"] == "Le Bureau des Légendes"
        assert out["original_name"] == "The Bureau"
        assert out["overview"] == "French spy series."
        assert out["first_air_date"] == "2015-01-01"

    def test_genres_become_dict_list(self) -> None:
        """MediaDetails.genres → ``[{"name": ...}]`` for legacy NFO consumer."""
        md = MediaDetails(provider="tvdb", provider_id="1", genres=["Drama", "Crime"])
        out = _tvdb_series_to_show_data(md, tvdb_id=1)
        assert out["genres"] == [{"name": "Drama"}, {"name": "Crime"}]

    def test_seasons_become_legacy_shape(self) -> None:
        """SeasonInfo entries map to ``[{"season_number", "poster_path"}]``."""
        md = MediaDetails(
            provider="tvdb",
            provider_id="1",
            seasons=[
                SeasonInfo(season_number=0, poster_url="http://x/specials.jpg"),  # specials skipped
                SeasonInfo(season_number=1, poster_url="http://x/s1.jpg"),
                SeasonInfo(season_number=2, poster_url=""),
            ],
        )
        out = _tvdb_series_to_show_data(md, tvdb_id=1)
        # Specials (season 0) are skipped; positive seasons survive.
        assert {s["season_number"] for s in out["seasons"]} == {1, 2}
        # Poster URL preserved (empty string for missing posters).
        s1 = next(s for s in out["seasons"] if s["season_number"] == 1)
        assert s1["poster_path"] == "http://x/s1.jpg"

    def test_external_ids_built_from_args(self) -> None:
        """tmdb_id and imdb_id args populate external_ids."""
        md = MediaDetails(provider="tvdb", provider_id="123")
        out = _tvdb_series_to_show_data(md, tvdb_id=123, tmdb_id=456, imdb_id="tt0001")
        assert out["external_ids"]["tvdb_id"] == 123
        assert out["external_ids"]["tmdb_id"] == 456
        assert out["external_ids"]["imdb_id"] == "tt0001"

    def test_lossy_fields_default_to_empty(self) -> None:
        """Status / contentRatings absent from MediaDetails default to empty values."""
        md = MediaDetails(provider="tvdb", provider_id="1", title="X")
        out = _tvdb_series_to_show_data(md, tvdb_id=1)
        assert out["status"] == ""
        assert out["content_ratings"]["results"] == []

    def test_no_year_no_first_air_date(self) -> None:
        """Missing year produces empty first_air_date (not "None-01-01")."""
        md = MediaDetails(provider="tvdb", provider_id="1", title="X", year=None)
        out = _tvdb_series_to_show_data(md, tvdb_id=1)
        assert out["first_air_date"] == ""


class TestLegacyDictBranch:
    """Backward-compat: raw dict input still works."""

    def test_dict_path_status_extracted(self) -> None:
        """status.name extracted from dict-shape input (preserved feature)."""
        raw = {
            "name": "X",
            "originalName": "X-orig",
            "overview": "...",
            "status": {"name": "Continuing"},
            "genres": [{"name": "Drama"}],
            "seasons": [{"number": 1}],
            "contentRatings": [{"name": "TV-14", "country": "USA"}],
            "firstAired": "2010-01-01",
        }
        out = _tvdb_series_to_show_data(raw, tvdb_id=1)
        assert out["status"] == "Continuing"
        assert out["content_ratings"]["results"] == [{"rating": "TV-14", "iso_3166_1": "USA"}]
        assert out["original_name"] == "X-orig"
        assert out["first_air_date"] == "2010-01-01"
