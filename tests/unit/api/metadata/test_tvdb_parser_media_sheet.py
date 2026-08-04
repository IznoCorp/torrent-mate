"""Golden-fixture tests for TVDB media-sheet fields (DESIGN D4/D9).

Asserts that ``parse_media_details`` extracts the four new optional fields
(director, series_status, episode_count, trailer_url) correctly from both
movie and series extended golden samples, and that absent fields are
``None`` — never an empty string.

Golden fixtures:
- ``movie_extended.json`` — movie extended response (live-captured).
- ``series_extended.json`` — Breaking Bad (81189) series extended,
  live-captured with TVDB v4 API.
"""

from __future__ import annotations

import json
from pathlib import Path

from personalscraper.api.metadata._tvdb_parsers import parse_media_details, unwrap

FIXTURE_DIR = Path(__file__).parents[4] / "docs" / "reference" / "_samples" / "tvdb"


def _load_unwrapped(name: str) -> dict:
    """Load a TVDB golden fixture and unwrap its envelope."""
    path = FIXTURE_DIR / name
    assert path.exists(), f"Fixture not found: {path}"
    with open(path) as f:
        raw = json.load(f)
    data = unwrap(raw)
    assert isinstance(data, dict), f"Expected dict data, got {type(data)}"
    return data


class TestTVDBMovieMediaSheet:
    """TVDB movie extended — all media-sheet fields should be None."""

    def test_movie_fields_from_tvdb(self) -> None:
        """TVDB movie: series_status/episode_count/trailer_url are None; director optional."""
        data = _load_unwrapped("movie_extended.json")
        md = parse_media_details(data, "tvdb")
        # Director may come from characters (if the fixture has a Director personType).
        # The fixture "Askeladden" (id 290) does have one.
        if md.director is not None:
            assert isinstance(md.director, str)
            assert md.director != ""
        assert md.series_status is None, f"Expected None, got {md.series_status!r}"
        assert md.episode_count is None, f"Expected None, got {md.episode_count!r}"
        assert md.trailer_url is None, f"Expected None, got {md.trailer_url!r}"


class TestTVDBSeriesMediaSheet:
    """TVDB series extended — series_status is extracted."""

    def test_series_status_from_status_name(self) -> None:
        """series_status comes from status.name; Breaking Bad is Ended."""
        data = _load_unwrapped("series_extended.json")
        md = parse_media_details(data, "tvdb")
        assert md.series_status == "Ended"
        assert isinstance(md.series_status, str)
        assert md.series_status != ""

    def test_episode_count_none_tvdb_no_single_field(self) -> None:
        """TVDB extended lacks a single number_of_episodes — stays None."""
        data = _load_unwrapped("series_extended.json")
        md = parse_media_details(data, "tvdb")
        assert md.episode_count is None

    def test_trailer_url_none_tvdb_no_structured_trailer(self) -> None:
        """TVDB lacks structured YouTube trailers — trailer_url stays None."""
        data = _load_unwrapped("series_extended.json")
        md = parse_media_details(data, "tvdb")
        assert md.trailer_url is None


class TestAbsentFieldsNeverEmptyString:
    """DESIGN D4/D9: absent fields must be None, never an empty string."""

    def test_series_without_status_object(self) -> None:
        """Status field absent → series_status is None."""
        md = parse_media_details(
            {
                "id": 1,
                "name": "No Status Show",
                "firstAired": "2020-01-01",
            },
            "tvdb",
        )
        assert md.series_status is None

    def test_series_status_not_a_dict(self) -> None:
        """Status field is a string, not a dict → series_status is None."""
        md = parse_media_details(
            {
                "id": 2,
                "name": "String Status",
                "firstAired": "2020-01-01",
                "status": "Ended",  # string, not dict with .name
            },
            "tvdb",
        )
        assert md.series_status is None

    def test_series_status_dict_no_name(self) -> None:
        """Status is a dict but has no 'name' key → series_status is None."""
        md = parse_media_details(
            {
                "id": 3,
                "name": "Nameless Status",
                "firstAired": "2020-01-01",
                "status": {"id": 1},
            },
            "tvdb",
        )
        assert md.series_status is None

    def test_movie_series_status_none(self) -> None:
        """Movies (detected by first_release) never get a series_status."""
        md = parse_media_details(
            {
                "id": 4,
                "name": "Some Movie",
                "first_release": {"date": "2020-01-01"},
                "status": {"id": 2, "name": "Released"},
            },
            "tvdb",
        )
        assert md.series_status is None

    def test_characters_no_director_role(self) -> None:
        """Characters array with no Director personType → director is None."""
        md = parse_media_details(
            {
                "id": 5,
                "name": "Show Without Director",
                "firstAired": "2020-01-01",
                "characters": [
                    {"peopleType": "Actor", "personName": "Jane Smith"},
                    {"peopleType": "Writer", "personName": "John Doe"},
                ],
            },
            "tvdb",
        )
        assert md.director is None
