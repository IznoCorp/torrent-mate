"""Tests for TMDB response parsers — driven by Phase 4 golden samples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from personalscraper.api.metadata._base import SearchResult, Video
from personalscraper.api.metadata._tmdb_parsers import (
    _build_image_url,
    parse_artwork,
    parse_episode,
    parse_keywords,
    parse_media_details,
    parse_search_result,
    parse_season_details,
    parse_video,
)

SAMPLES = Path("docs/reference/_samples/tmdb")


def _load(name: str) -> Any:
    """Load a golden sample JSON file from the samples directory."""
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


class TestBuildImageUrl:
    """_build_image_url helper."""

    def test_valid_path(self) -> None:
        """Builds full URL from path and size."""
        assert _build_image_url("/abc.jpg", "w500") == "https://image.tmdb.org/t/p/w500/abc.jpg"

    def test_none_path(self) -> None:
        """Returns empty string for None path."""
        assert _build_image_url(None, "w500") == ""

    def test_empty_path(self) -> None:
        """Returns empty string for empty path."""
        assert _build_image_url("", "w500") == ""


class TestParseSearchResult:
    """Search result parsing from golden samples."""

    def test_movie_search(self) -> None:
        """Parses search_movie.json result."""
        data = _load("search_movie.json")
        r = parse_search_result(data["results"][0], "tmdb")
        assert isinstance(r, SearchResult)
        assert r.provider == "tmdb"
        assert r.provider_id == "550"
        assert r.title == "Fight Club"
        assert r.media_type == "movie"
        assert r.year == 1999
        assert r.poster_url.startswith("https://image.tmdb.org/t/p/w500/")

    def test_tv_search(self) -> None:
        """Parses search_tv.json result with TV-specific fields."""
        data = _load("search_tv.json")
        r = parse_search_result(data["results"][0], "tmdb")
        assert r.media_type == "tv"
        assert r.title != ""
        assert r.year is not None


class TestParseArtwork:
    """Image array merging from golden movie_details."""

    def test_merges_three_arrays(self) -> None:
        """Merges backdrops, posters, logos into single list."""
        data = _load("movie_details.json")
        images = parse_artwork(data.get("images", {}))
        types = {a.type for a in images}
        assert "backdrop" in types
        assert "poster" in types
        assert "landscape" in types

    def test_backdrop_has_correct_url(self) -> None:
        """Backdrop URLs use w1280 size."""
        data = _load("movie_details.json")
        images = parse_artwork(data.get("images", {}))
        backdrops = [a for a in images if a.type == "backdrop"]
        assert len(backdrops) > 0
        assert "/w1280/" in backdrops[0].url

    def test_poster_has_correct_url(self) -> None:
        """Poster URLs use w780 size."""
        data = _load("movie_details.json")
        images = parse_artwork(data.get("images", {}))
        posters = [a for a in images if a.type == "poster"]
        assert len(posters) > 0
        assert "/w780/" in posters[0].url

    def test_season_poster_type(self) -> None:
        """When season is provided, poster type becomes season_poster."""
        data = _load("movie_details.json")
        images = parse_artwork(data.get("images", {}), season=1)
        posters = [a for a in images if a.type == "season_poster"]
        assert len(posters) > 0
        assert posters[0].season == 1

    def test_empty_images(self) -> None:
        """Empty images dict returns empty list."""
        assert parse_artwork({}) == []


class TestParseMediaDetails:
    """MediaDetails parsing from golden samples."""

    def test_movie_details(self) -> None:
        """Parses movie_details.json into MediaDetails."""
        data = _load("movie_details.json")
        md = parse_media_details(data, "tmdb")
        assert md.provider == "tmdb"
        assert md.provider_id == "550"
        assert md.title == "Fight Club"
        assert md.original_title == "Fight Club"
        assert md.year == 1999
        assert md.runtime_minutes == 139
        assert len(md.genres) > 0
        assert "Drame" in md.genres
        assert md.rating is not None and md.rating > 0
        assert len(md.images) > 0
        assert "imdb" in md.external_ids

    def test_tv_details(self) -> None:
        """Parses tv_details.json — episode_run_time may be empty for TV."""
        data = _load("tv_details.json")
        md = parse_media_details(data, "tmdb")
        assert md.title == "Breaking Bad"
        assert md.runtime_minutes is None

    def test_movie_details_minimal(self) -> None:
        """Parses movie_details_minimal.json (no append_to_response)."""
        data = _load("movie_details_minimal.json")
        md = parse_media_details(data, "tmdb")
        assert md.provider_id == "550"
        assert md.title
        assert md.images == []

    def test_movie_details_genre_ids_origin_production_backdrop(self) -> None:
        """Phase 27 fields: genre_ids, origin_countries, production_countries, primary_backdrop_url."""
        data = _load("movie_details.json")
        md = parse_media_details(data, "tmdb")
        # Genre IDs surface alongside genre names — same length, all int.
        assert len(md.genre_ids) == len(md.genres)
        assert all(isinstance(gid, int) for gid in md.genre_ids)
        # production_countries from production_countries[*].iso_3166_1
        assert isinstance(md.production_countries, list)
        assert all(isinstance(c, str) and len(c) == 2 for c in md.production_countries)
        # backdrop fallback URL is non-empty when raw has backdrop_path
        if data.get("backdrop_path"):
            assert md.primary_backdrop_url.startswith("https://image.tmdb.org/t/p/")
            assert md.primary_backdrop_url.endswith(data["backdrop_path"])
        # Movies have no seasons.
        assert md.seasons == []

    def test_tv_details_seasons_origin_country(self) -> None:
        """Phase 27: TV responses populate seasons + origin_countries."""
        data = _load("tv_details.json")
        md = parse_media_details(data, "tmdb")
        # If the golden has a seasons[] block, SeasonInfo must be populated
        # for each integer season_number entry (not via .get() shape).
        if data.get("seasons"):
            assert len(md.seasons) >= 1
            assert all(s.season_number >= 0 for s in md.seasons)
            assert all(isinstance(s.episode_count, int) for s in md.seasons)
        # origin_country for TV is a list[str] at top-level.
        if data.get("origin_country"):
            assert md.origin_countries == data["origin_country"]


class TestParseSearchResultPhase27:
    """Phase 27: SearchResult.original_title for localised matching."""

    def test_search_movie_includes_original_title(self) -> None:
        """``original_title`` is populated from the TMDB response."""
        result = parse_search_result(
            {"id": 1954, "title": "L'Effet papillon", "original_title": "The Butterfly Effect"},
            "tmdb",
        )
        assert result.original_title == "The Butterfly Effect"

    def test_search_tv_includes_original_name(self) -> None:
        """For TV results TMDB uses ``original_name`` — surfaced as original_title."""
        result = parse_search_result(
            {"id": 100, "name": "La Casa de Papel", "original_name": "Money Heist"},
            "tmdb",
        )
        assert result.original_title == "Money Heist"

    def test_search_no_original_title_defaults_empty(self) -> None:
        """Absent original_title becomes empty string, not None."""
        result = parse_search_result({"id": 1, "title": "X"}, "tmdb")
        assert result.original_title == ""


class TestParseArtworkPhase27:
    """Phase 27: ArtworkItem.vote_average for tie-breaker selection."""

    def test_vote_average_propagates(self) -> None:
        """Each image's ``vote_average`` is preserved on the typed item."""
        items = parse_artwork(
            {
                "posters": [
                    {"file_path": "/a.jpg", "iso_639_1": "fr", "vote_average": 7.2},
                    {"file_path": "/b.jpg", "iso_639_1": "en", "vote_average": 0},
                ],
                "backdrops": [
                    {"file_path": "/x.jpg", "iso_639_1": None, "vote_average": 5.5},
                ],
            }
        )
        # Just sanity check that nonzero vote_averages survive parsing.
        nonzero = [i.vote_average for i in items if i.vote_average > 0]
        assert 7.2 in nonzero
        assert 5.5 in nonzero
        # Zero vote also OK (typed default).
        assert any(i.vote_average == 0.0 for i in items)


class TestParseEpisodePhase27:
    """Phase 27: EpisodeInfo.season_number + still_url."""

    def test_episode_carries_season_number(self) -> None:
        """``season_number`` from raw response is preserved."""
        ep = parse_episode({"episode_number": 5, "season_number": 3, "name": "T"})
        assert ep.season_number == 3

    def test_episode_still_url_built_from_path(self) -> None:
        """``still_path`` becomes a CDN-prefixed ``still_url``."""
        ep = parse_episode({"episode_number": 1, "still_path": "/abc.jpg", "name": "T"})
        assert ep.still_url == "https://image.tmdb.org/t/p/w300/abc.jpg"

    def test_episode_no_still_path_empty_url(self) -> None:
        """No still_path means empty still_url, never a malformed URL."""
        ep = parse_episode({"episode_number": 1, "name": "T"})
        assert ep.still_url == ""


class TestParseVideo:
    """Video parsing from golden samples."""

    def test_video_parsing(self) -> None:
        """Parses movie_videos.json results."""
        data = _load("movie_videos.json")
        v = parse_video(data["results"][0])
        assert isinstance(v, Video)
        assert v.id != ""
        assert v.key != ""
        assert v.site in ("youtube", "vimeo")
        assert v.type in ("trailer", "teaser", "clip")
        assert isinstance(v.official, bool)


class TestParseEpisode:
    """Episode parsing from golden season_details."""

    def test_episode_parsing(self) -> None:
        """Parses season_details.json first episode."""
        data = _load("season_details.json")
        ep = parse_episode(data["episodes"][0])
        assert ep.episode_number == 1
        assert ep.title != ""
        assert ep.runtime_minutes == 59

    def test_episode_runtime_null_handled(self) -> None:
        """Episode with null runtime returns None for runtime_minutes."""
        ep = parse_episode({"episode_number": 1, "runtime": None, "name": "Test", "air_date": ""})
        assert ep.runtime_minutes is None


class TestParseKeywords:
    """Keywords parsing — movie vs TV envelope."""

    def test_movie_keywords(self) -> None:
        """Movie keywords uses 'keywords' envelope."""
        data = _load("movie_keywords.json")
        keywords = parse_keywords(data, "movie")
        assert len(keywords) > 0
        assert all(isinstance(k, str) for k in keywords)

    def test_tv_keywords(self) -> None:
        """TV keywords uses 'results' envelope (TMDB inconsistency)."""
        data = _load("tv_keywords.json")
        keywords = parse_keywords(data, "tv")
        assert len(keywords) == 30
        assert all(isinstance(k, str) for k in keywords)


class TestParseSeasonDetails:
    """SeasonDetails parsing from golden samples."""

    def test_season_details(self) -> None:
        """Parses season_details.json into SeasonDetails."""
        data = _load("season_details.json")
        data["_tv_id"] = "1396"
        sd = parse_season_details(data, "tmdb")
        assert sd.provider == "tmdb"
        assert sd.tv_id == "1396"
        assert sd.season_number == 1
        assert len(sd.episodes) == 7
        assert sd.episodes[0].episode_number == 1
