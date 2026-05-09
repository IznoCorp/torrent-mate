"""Branch-coverage targeted tests for _tvdb_parsers.

Focuses on the conditional branches the golden-sample tests don't reach:
malformed years, malformed first_release dates, non-dict season entries,
non-int season numbers, remoteIds source mapping fallbacks, and
youtu.be short-URL key extraction.
"""

from __future__ import annotations

from personalscraper.api.metadata._tvdb_parsers import (
    parse_episode,
    parse_media_details,
    parse_search_result,
    parse_video,
)


class TestParseSearchResultBranches:
    """parse_search_result year fallbacks and translations short-circuit."""

    def test_malformed_year_string(self) -> None:
        """Non-numeric ``year`` value yields year=None (covers exception path)."""
        r = parse_search_result(
            {"tvdb_id": "1", "name": "X", "type": "movie", "year": "n/a"},
            "tvdb",
        )
        assert r.year is None

    def test_translations_not_a_list_ignored(self) -> None:
        """A non-list ``translations`` field is silently ignored."""
        r = parse_search_result(
            {"tvdb_id": "1", "name": "X", "type": "movie", "translations": "garbage"},
            "tvdb",
        )
        assert r.original_title == ""

    def test_translation_entry_not_dict_skipped(self) -> None:
        """Non-dict items inside translations[] are skipped."""
        r = parse_search_result(
            {
                "tvdb_id": "1",
                "name": "X",
                "type": "series",
                "translations": [
                    "not-a-dict",
                    {"language": "fra", "name": "Whatever"},
                ],
            },
            "tvdb",
        )
        # No eng entry → empty original_title
        assert r.original_title == ""


class TestParseMediaDetailsBranches:
    """parse_media_details defensive guards."""

    def test_movie_first_release_malformed_date(self) -> None:
        """Movie with non-numeric first_release.date → year=None."""
        md = parse_media_details(
            {"id": 1, "name": "X", "first_release": {"date": "abcd-01-02"}},
            "tvdb",
        )
        assert md.year is None

    def test_movie_first_release_not_a_dict(self) -> None:
        """``first_release`` not being a dict still flags is_movie but yields year=None."""
        md = parse_media_details(
            {"id": 1, "name": "X", "first_release": "garbage"},
            "tvdb",
        )
        # is_movie path runs but skips date parsing → None
        assert md.year is None

    def test_series_malformed_first_aired(self) -> None:
        """Non-numeric ``firstAired`` for series yields year=None."""
        md = parse_media_details(
            {"id": 1, "name": "X", "firstAired": "abcd"},
            "tvdb",
        )
        assert md.year is None

    def test_seasons_non_dict_skipped(self) -> None:
        """Non-dict items in seasons[] are skipped."""
        md = parse_media_details(
            {
                "id": 1,
                "name": "X",
                "seasons": [
                    "not-a-dict",
                    {"number": "non-int"},  # int guard
                    {"number": 1, "episodeCount": 7},
                ],
            },
            "tvdb",
        )
        assert len(md.seasons) == 1
        assert md.seasons[0].season_number == 1

    def test_remote_ids_unknown_source_skipped(self) -> None:
        """Unknown remoteId.sourceName values are silently dropped."""
        md = parse_media_details(
            {
                "id": 1,
                "name": "X",
                "remoteIds": [
                    "not-a-dict",
                    {"sourceName": "Wikidata", "id": "Q123"},  # unknown
                    {"sourceName": "IMDB", "id": "tt000"},
                    {"sourceName": "TheMovieDB", "id": "999"},
                    {"sourceName": "TVDB", "id": "555"},
                ],
            },
            "tvdb",
        )
        assert md.external_ids["imdb"] == "tt000"
        assert md.external_ids["tmdb"] == "999"
        assert md.external_ids["tvdb"] == "555"
        assert "wikidata" not in md.external_ids


class TestParseVideoYoutuBe:
    """parse_video extracts the ``v`` parameter or the youtu.be short path."""

    def test_youtu_be_short_url(self) -> None:
        """``youtu.be/<key>`` short URLs yield the key after the slash."""
        v = parse_video({"id": "1", "url": "https://youtu.be/dQw4w9WgXcQ?t=10"})
        assert v is not None
        assert v.key == "dQw4w9WgXcQ"

    def test_youtube_url_without_v_param(self) -> None:
        """A youtube.com URL without ``v=`` yields an empty key (filtered out by parse_videos)."""
        v = parse_video({"id": "1", "url": "https://www.youtube.com/embed/abc123"})
        # parse_video itself returns Video; key extraction returns "" (no v=, no youtu.be)
        assert v is not None
        assert v.key == ""

    def test_non_youtube_url(self) -> None:
        """Vimeo or other URLs yield empty key (parse_videos drops them)."""
        v = parse_video({"id": "1", "url": "https://vimeo.com/12345"})
        assert v is not None
        assert v.key == ""


class TestParseEpisodeDefaults:
    """parse_episode handles missing/typed fields without crashing."""

    def test_missing_number_zero_default(self) -> None:
        """Missing ``number`` yields episode_number=0."""
        ep = parse_episode({"name": "X"})
        assert ep.episode_number == 0
