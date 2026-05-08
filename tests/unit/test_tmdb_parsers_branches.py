"""Branch-coverage targeted tests for _tmdb_parsers.

Focuses on the conditional branches and defensive guards that the
golden-sample tests don't reach: malformed dates, non-dict season
entries, non-int season numbers, unknown site/type fallbacks, and
malformed external_ids blocks.
"""

from __future__ import annotations

from personalscraper.api.metadata._tmdb_parsers import (
    parse_artwork,
    parse_media_details,
    parse_search_result,
    parse_video,
)


class TestParseSearchResultMalformedDate:
    """SearchResult year parsing fallbacks."""

    def test_malformed_release_date_year_none(self) -> None:
        """Non-numeric date prefix → year=None (covers ValueError handler)."""
        r = parse_search_result(
            {"id": 1, "title": "X", "release_date": "abcd-01-02"},
            "tmdb",
        )
        assert r.year is None

    def test_no_release_date(self) -> None:
        """Missing release_date → year=None."""
        r = parse_search_result({"id": 1, "title": "X"}, "tmdb")
        assert r.year is None


class TestParseMediaDetailsBranches:
    """parse_media_details defensive guards."""

    def test_malformed_movie_release_date(self) -> None:
        """Movie with non-numeric release_date → year=None."""
        md = parse_media_details({"id": 1, "title": "X", "release_date": "abcd"}, "tmdb")
        assert md.year is None

    def test_seasons_non_dict_skipped(self) -> None:
        """Non-dict season entries are skipped."""
        md = parse_media_details(
            {
                "id": 1,
                "name": "X",
                "seasons": [
                    "not-a-dict",
                    {"season_number": "non-int"},  # int guard
                    {"season_number": 1, "episode_count": 5},
                ],
            },
            "tmdb",
        )
        # Only the well-formed integer-season-number entry should produce SeasonInfo
        assert len(md.seasons) == 1
        assert md.seasons[0].season_number == 1

    def test_external_ids_block_string_filter(self) -> None:
        """Non-string external_ids values are silently dropped."""
        md = parse_media_details(
            {
                "id": 1,
                "title": "X",
                "external_ids": {
                    "tvdb_id": 12345,  # int — should be skipped
                    "imdb_id": "tt0000001",  # string — should land in dict
                    "wikidata_id": None,
                },
            },
            "tmdb",
        )
        assert md.external_ids.get("imdb") == "tt0000001"
        assert "tvdb" not in md.external_ids

    def test_external_ids_not_a_dict(self) -> None:
        """Non-dict external_ids block is ignored."""
        md = parse_media_details({"id": 1, "title": "X", "external_ids": "garbage"}, "tmdb")
        # Only top-level imdb_id (absent) is consulted; nothing should leak in.
        assert md.external_ids == {}

    def test_origin_country_non_list(self) -> None:
        """origin_country that is not a list yields empty origin_countries."""
        md = parse_media_details({"id": 1, "name": "X", "origin_country": "US"}, "tmdb")
        # "US" is a str, not a list → branch falls through → empty
        assert md.origin_countries == []


class TestParseVideoFallbacks:
    """parse_video unknown-site / unknown-type fallbacks."""

    def test_unknown_site_falls_back_to_youtube(self) -> None:
        """An unrecognised site is normalised to ``youtube``."""
        v = parse_video({"id": "1", "site": "Dailymotion", "key": "abc", "type": "trailer"})
        assert v.site == "youtube"

    def test_unknown_type_falls_back_to_trailer(self) -> None:
        """An unrecognised video ``type`` becomes ``trailer``."""
        v = parse_video({"id": "1", "site": "YouTube", "key": "abc", "type": "Behind The Scenes"})
        assert v.type == "trailer"


class TestParseArtworkSeasonPosterBranch:
    """parse_artwork must propagate ``season`` only on poster type."""

    def test_logos_no_season_attribute(self) -> None:
        """Logos do not carry the season number even when one is provided."""
        items = parse_artwork(
            {"logos": [{"file_path": "/l.png", "iso_639_1": "en", "vote_average": 1.0}]},
            season=2,
        )
        assert len(items) == 1
        # Only posters get the season tag; logos remain untagged.
        assert items[0].season is None
