"""Golden-fixture tests for TMDB media-sheet fields (DESIGN D4/D9).

Asserts that ``parse_media_details`` extracts the four new optional fields
(director, series_status, episode_count, trailer_url) correctly from both
movie and TV golden samples, and that absent fields are ``None`` — never an
empty string.

Golden fixtures:
- ``movie_details.json`` — Fight Club (550), live-captured 2026-08-04 with
  ``append_to_response=videos,images,keywords,external_ids,credits``.
- ``tv_details.json`` — Breaking Bad (1396), live-captured 2026-08-04 with
  ``append_to_response=videos,images,keywords,external_ids,aggregate_credits``.
"""

from __future__ import annotations

import json
from pathlib import Path

from personalscraper.api.metadata._tmdb_parsers import parse_media_details

FIXTURE_DIR = Path(__file__).parents[4] / "docs" / "reference" / "_samples" / "tmdb"


def _load(name: str) -> dict:
    """Load a golden fixture by basename."""
    path = FIXTURE_DIR / name
    assert path.exists(), f"Fixture not found: {path}"
    with open(path) as f:
        return json.load(f)


class TestTMDBMovieMediaSheet:
    """TMDB movie details — media-sheet field extraction."""

    def test_director_from_credits_crew(self) -> None:
        """Director is extracted from credits.crew (job == "Director")."""
        raw = _load("movie_details.json")
        md = parse_media_details(raw, "tmdb")
        # Fight Club → David Fincher
        assert md.director == "David Fincher"
        assert isinstance(md.director, str)
        assert md.director != ""

    def test_series_status_none_for_movie(self) -> None:
        """Movies never have a series_status (DESIGN D4/D9: absent, not empty)."""
        raw = _load("movie_details.json")
        md = parse_media_details(raw, "tmdb")
        assert md.series_status is None

    def test_episode_count_none_for_movie(self) -> None:
        """Movies never have an episode_count."""
        raw = _load("movie_details.json")
        md = parse_media_details(raw, "tmdb")
        assert md.episode_count is None

    def test_trailer_url_youtube(self) -> None:
        """Trailer URL is built from the first YouTube Trailer video."""
        raw = _load("movie_details.json")
        md = parse_media_details(raw, "tmdb")
        # Fight Club has a YouTube trailer.
        assert md.trailer_url is not None
        assert md.trailer_url.startswith("https://www.youtube.com/watch?v=")
        assert "tZpXdiB_pg0" in md.trailer_url


class TestTMDBTVMediaSheet:
    """TMDB TV details — media-sheet field extraction."""

    def test_series_status_from_status_field(self) -> None:
        """series_status comes from raw['status']; Breaking Bad is Ended."""
        raw = _load("tv_details.json")
        md = parse_media_details(raw, "tmdb")
        assert md.series_status == "Ended"
        assert isinstance(md.series_status, str)
        assert md.series_status != ""

    def test_director_from_created_by(self) -> None:
        """For TV, director comes from created_by[0]['name']."""
        raw = _load("tv_details.json")
        md = parse_media_details(raw, "tmdb")
        assert md.director == "Vince Gilligan"
        assert isinstance(md.director, str)
        assert md.director != ""

    def test_episode_count_from_number_of_episodes(self) -> None:
        """episode_count comes from raw['number_of_episodes']."""
        raw = _load("tv_details.json")
        md = parse_media_details(raw, "tmdb")
        assert md.episode_count == 62
        assert isinstance(md.episode_count, int)

    def test_trailer_url_youtube(self) -> None:
        """Trailer URL is built from the first YouTube Trailer video."""
        raw = _load("tv_details.json")
        md = parse_media_details(raw, "tmdb")
        assert md.trailer_url is not None
        assert md.trailer_url.startswith("https://www.youtube.com/watch?v=")


class TestAbsentFieldsNeverEmptyString:
    """DESIGN D4/D9: absent fields must be None, never an empty string."""

    def test_movie_without_credits_director_none(self) -> None:
        """A movie response without a 'credits' key → director is None."""
        md = parse_media_details(
            {
                "id": 1,
                "title": "No Credits Movie",
                "release_date": "2020-01-01",
            },
            "tmdb",
        )
        assert md.director is None

    def test_movie_with_credits_but_no_director(self) -> None:
        """credits.crew exists but no Director job → director is None."""
        md = parse_media_details(
            {
                "id": 2,
                "title": "No Director",
                "release_date": "2020-01-01",
                "credits": {
                    "crew": [
                        {"job": "Producer", "name": "Jane Smith"},
                        {"job": "Writer", "name": "John Doe"},
                    ]
                },
            },
            "tmdb",
        )
        assert md.director is None

    def test_tv_without_created_by_director_none(self) -> None:
        """A TV response without 'created_by' → director is None."""
        md = parse_media_details(
            {
                "id": 3,
                "name": "No Creator Show",
                "first_air_date": "2020-01-01",
            },
            "tmdb",
        )
        assert md.director is None

    def test_movie_without_video_results_trailer_none(self) -> None:
        """videos.results without any Trailer → trailer_url is None."""
        md = parse_media_details(
            {
                "id": 4,
                "title": "Trailerless",
                "release_date": "2020-01-01",
                "videos": {
                    "results": [
                        {"type": "Teaser", "site": "YouTube", "key": "abc123"},
                    ]
                },
            },
            "tmdb",
        )
        assert md.trailer_url is None
