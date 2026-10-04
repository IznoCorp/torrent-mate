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
        """For TV, director AND creator come from created_by[0]['name']."""
        raw = _load("tv_details.json")
        md = parse_media_details(raw, "tmdb")
        assert md.director == "Vince Gilligan"
        assert isinstance(md.director, str)
        assert md.director != ""
        # Creator is also populated for TV (operator arbitration 2026-08-04).
        assert md.creator == "Vince Gilligan"
        assert isinstance(md.creator, str)

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
        """A TV response without 'created_by' → director AND creator are None."""
        md = parse_media_details(
            {
                "id": 3,
                "name": "No Creator Show",
                "first_air_date": "2020-01-01",
            },
            "tmdb",
        )
        assert md.director is None
        assert md.creator is None

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


class TestTMDBCast:
    """The cast: name, role and portrait, in the provider's ``order``."""

    def test_movie_cast_from_credits(self) -> None:
        """A movie's cast comes from credits.cast, portrait at the profile size."""
        md = parse_media_details(_load("movie_details.json"), "tmdb")
        assert len(md.cast) == 76
        first = md.cast[0]
        assert first.name == "Edward Norton"
        assert first.role == "Narrator"
        assert first.portrait_url == "https://image.tmdb.org/t/p/w185/8nytsqL59SFJTVYVrN72k6qkGgJ.jpg"
        assert [member.name for member in md.cast[1:3]] == ["Brad Pitt", "Helena Bonham Carter"]

    def test_movie_cast_member_without_profile_has_no_portrait(self) -> None:
        """A member with no profile_path keeps portrait_url None, never an empty string."""
        md = parse_media_details(_load("movie_details.json"), "tmdb")
        without = [member for member in md.cast if member.portrait_url is None]
        assert len(without) == 20
        assert all(member.portrait_url != "" for member in md.cast)

    def test_tv_cast_from_aggregate_credits_in_order(self) -> None:
        """A show's cast comes from aggregate_credits, sorted by ``order``, role from roles[0]."""
        raw = _load("tv_details.json")
        md = parse_media_details(raw, "tmdb")
        assert len(md.cast) == 348
        assert (md.cast[0].name, md.cast[0].role) == ("Bryan Cranston", "Walter White")
        assert md.cast[0].portrait_url == "https://image.tmdb.org/t/p/w185/npIIZJGSrcJIJ6yHdmbqO6Jzo5I.jpg"
        by_order = sorted(raw["aggregate_credits"]["cast"], key=lambda person: person["order"])
        assert [member.name for member in md.cast[:12]] == [person["name"] for person in by_order[:12]]

    def test_cast_sorted_by_order_not_payload_position(self) -> None:
        """The payload's position does not decide; ``order`` does."""
        md = parse_media_details(
            {
                "id": 5,
                "title": "Shuffled",
                "credits": {
                    "cast": [
                        {"name": "Second", "character": "B", "order": 1},
                        {"name": "First", "character": "A", "order": 0, "profile_path": "/a.jpg"},
                    ]
                },
            },
            "tmdb",
        )
        assert [(member.name, member.role) for member in md.cast] == [("First", "A"), ("Second", "B")]
        assert md.cast[0].portrait_url == "https://image.tmdb.org/t/p/w185/a.jpg"
        assert md.cast[1].portrait_url is None

    def test_cast_skips_nameless_members_and_keeps_empty_role(self) -> None:
        """A member with no name is dropped; a missing character is an empty role."""
        md = parse_media_details(
            {
                "id": 6,
                "name": "Show",
                "aggregate_credits": {
                    "cast": [
                        {"name": "", "roles": [{"character": "Ghost"}], "order": 0},
                        {"name": "Kept", "roles": [], "order": 1},
                    ]
                },
            },
            "tmdb",
        )
        assert [(member.name, member.role) for member in md.cast] == [("Kept", "")]

    def test_no_credits_is_an_empty_cast(self) -> None:
        """A response without credits gives an empty cast."""
        md = parse_media_details(_load("movie_details_minimal.json"), "tmdb")
        assert md.cast == []


class TestTMDBTrailerNameAndLanguage:
    """The picked trailer's name and language, beside its key."""

    def test_movie_trailer_name_and_language(self) -> None:
        """Fight Club's first YouTube trailer is the French subtitled one."""
        md = parse_media_details(_load("movie_details.json"), "tmdb")
        assert md.trailer_url == "https://www.youtube.com/watch?v=tZpXdiB_pg0"
        assert md.trailer_name == "Fight Club – Bande Annonce VOST"
        assert md.trailer_language == "fr"

    def test_tv_trailer_name_and_language(self) -> None:
        """Breaking Bad's first YouTube trailer."""
        md = parse_media_details(_load("tv_details.json"), "tmdb")
        assert md.trailer_name == "Breaking Bad - Serie Netflix - Bande Annonce VF - 2008"
        assert md.trailer_language == "fr"

    def test_no_trailer_no_name_nor_language(self) -> None:
        """No trailer picked: name and language stay None."""
        md = parse_media_details({"id": 7, "title": "Trailerless"}, "tmdb")
        assert md.trailer_name is None
        assert md.trailer_language is None

    def test_trailer_without_name_or_language_is_none_not_empty(self) -> None:
        """A picked trailer with no name/language leaves them None."""
        md = parse_media_details(
            {
                "id": 8,
                "title": "Bare",
                "videos": {"results": [{"type": "Trailer", "site": "YouTube", "key": "k", "name": "", "iso_639_1": None}]},
            },
            "tmdb",
        )
        assert md.trailer_url == "https://www.youtube.com/watch?v=k"
        assert md.trailer_name is None
        assert md.trailer_language is None
