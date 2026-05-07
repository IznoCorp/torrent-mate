"""Tests for TVDB response parsers — driven by Phase 6 golden samples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.metadata._base import (
    EpisodeInfo,
    SearchResult,
    SeasonDetails,
)
from personalscraper.api.metadata._tvdb_parsers import (
    map_language,
    parse_artwork,
    parse_artworks,
    parse_episode,
    parse_media_details,
    parse_search_result,
    parse_season_details,
    parse_video,
    unwrap,
)

SAMPLES = Path("docs/reference/_samples/tvdb")


def _load(name: str) -> Any:
    """Load a golden sample JSON file from the samples directory."""
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


class TestUnwrap:
    """TVDB envelope unwrapping."""

    def test_unwrap_success(self) -> None:
        """Strips status/data envelope on success."""
        data = _load("login.json")
        result = unwrap(data)
        assert "token" in result

    def test_unwrap_search_data_is_list(self) -> None:
        """Search results unwrap to a list."""
        data = _load("search_series.json")
        result = unwrap(data)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_unwrap_failure_raises_api_error(self) -> None:
        """Failure status raises ApiError."""
        with pytest.raises(ApiError):
            unwrap({"status": "failure", "message": "InvalidAPIKey: apikey invalid"})


class TestMapLanguage:
    """Language code mapping."""

    def test_fr_to_fra(self) -> None:
        """2-char fr → 3-char fra."""
        assert map_language("fr") == "fra"

    def test_en_to_eng(self) -> None:
        """2-char en → 3-char eng."""
        assert map_language("en") == "eng"

    def test_unknown_fallback(self) -> None:
        """Unknown code falls back to eng."""
        assert map_language("xx") == "eng"


class TestParseSearchResult:
    """Search result parsing from golden samples."""

    def test_series_search(self) -> None:
        """TVDB series search → SearchResult."""
        data = _load("search_series.json")
        items = unwrap(data)
        assert isinstance(items, list)
        r = parse_search_result(items[0], "tvdb")
        assert isinstance(r, SearchResult)
        assert r.provider == "tvdb"
        assert r.provider_id == "81189"
        assert r.title == "Breaking Bad"
        assert r.media_type == "tv"
        assert r.year == 2008
        assert r.poster_url.startswith("https://artworks.thetvdb.com/")

    def test_movie_search(self) -> None:
        """TVDB movie search → SearchResult."""
        data = _load("search_movie.json")
        items = unwrap(data)
        assert isinstance(items, list)
        r = parse_search_result(items[0], "tvdb")
        assert r.media_type == "movie"

    def test_empty_search(self) -> None:
        """Empty search returns empty list."""
        data = _load("search_empty.json")
        items = unwrap(data)
        assert items == []


class TestParseArtwork:
    """Artwork type mapping."""

    def test_poster_type(self) -> None:
        """Type ID 2 (Poster) → ArtworkItem(type='poster')."""
        item = parse_artwork({"type": 2, "image": "https://example.com/poster.jpg"})
        assert item is not None
        assert item.type == "poster"

    def test_backdrop_type(self) -> None:
        """Type ID 3 (Background) → ArtworkItem(type='backdrop')."""
        item = parse_artwork({"type": 3, "image": "https://example.com/bg.jpg"})
        assert item is not None
        assert item.type == "backdrop"

    def test_clearlogo_type(self) -> None:
        """Type ID 23 (ClearLogo) → ArtworkItem(type='landscape')."""
        item = parse_artwork({"type": 23, "image": "https://example.com/logo.png"})
        assert item is not None
        assert item.type == "landscape"

    def test_season_poster(self) -> None:
        """Poster with season → season_poster."""
        item = parse_artwork({"type": 2, "image": "https://example.com/s1.jpg"}, season=1)
        assert item is not None
        assert item.type == "season_poster"
        assert item.season == 1

    def test_banner_ignored(self) -> None:
        """Type ID 1 (Banner) → None (skip)."""
        assert parse_artwork({"type": 1, "image": "https://example.com/banner.jpg"}) is None

    def test_parse_artworks_filters(self) -> None:
        """parse_artworks skips irrelevant types."""
        raws = [
            {"type": 2, "image": "https://example.com/p.jpg"},
            {"type": 1, "image": "https://example.com/b.jpg"},  # Banner → skip
            {"type": 3, "image": "https://example.com/bg.jpg"},
        ]
        result = parse_artworks(raws)
        assert len(result) == 2


class TestParseMediaDetails:
    """MediaDetails from golden samples."""

    def test_series_extended(self) -> None:
        """Breaking Bad extended → MediaDetails."""
        data = _load("series_extended.json")
        raw = unwrap(data)
        assert isinstance(raw, dict)
        md = parse_media_details(raw, "tvdb")
        assert md.provider == "tvdb"
        assert md.title == "Breaking Bad"
        assert md.year == 2008
        assert md.runtime_minutes == 48
        assert md.rating is None  # score is popularity rank
        assert "imdb" in md.external_ids
        assert md.external_ids["imdb"] == "tt0903747"

    def test_movie_extended(self) -> None:
        """Movie extended → MediaDetails with first_release object."""
        data = _load("movie_extended.json")
        raw = unwrap(data)
        assert isinstance(raw, dict)
        md = parse_media_details(raw, "tvdb")
        assert md.provider == "tvdb"
        assert md.runtime_minutes == 100
        assert md.rating is None

    def test_series_extended_phase27_fields(self) -> None:
        """Phase 27: seasons + genre_ids + origin_countries + primary_backdrop_url."""
        data = _load("series_extended.json")
        raw = unwrap(data)
        assert isinstance(raw, dict)
        md = parse_media_details(raw, "tvdb")
        # Genres come as {id, name} dicts on TVDB; both lists are filled.
        if raw.get("genres"):
            assert len(md.genre_ids) <= len(md.genres)  # only int IDs make it
            assert all(isinstance(gid, int) for gid in md.genre_ids)
        # Seasons summary (lightweight per-season catalog)
        if raw.get("seasons"):
            assert all(s.season_number >= 0 for s in md.seasons)
            assert all(isinstance(s.episode_count, int) for s in md.seasons)
        # primary_backdrop_url is the first backdrop ArtworkItem.url, when any
        backdrops = [a for a in md.images if a.type == "backdrop"]
        if backdrops:
            assert md.primary_backdrop_url == backdrops[0].url
        # origin_countries normalised to 2-char ISO codes when known
        if raw.get("originalCountry") or raw.get("country"):
            assert all(len(c) == 2 for c in md.origin_countries)


class TestParseSearchResultPhase27Tvdb:
    """Phase 27: TVDB search result original_title from translations."""

    def test_translations_eng_becomes_original_title(self) -> None:
        """When ``translations`` contains an English entry, surface it as original."""
        result = parse_search_result(
            {
                "tvdb_id": "123",
                "name": "Le Mystère",
                "type": "series",
                "translations": [{"language": "fra", "name": "Le Mystère"}, {"language": "eng", "name": "The Mystery"}],
            },
            "tvdb",
        )
        assert result.original_title == "The Mystery"

    def test_no_eng_translation_empty_original(self) -> None:
        """Absent English translation → empty original_title (not None)."""
        result = parse_search_result(
            {
                "tvdb_id": "1",
                "name": "Show",
                "type": "series",
                "translations": [{"language": "fra", "name": "Émission"}],
            },
            "tvdb",
        )
        assert result.original_title == ""


class TestParseArtworkPhase27Tvdb:
    """Phase 27: TVDB ArtworkItem.vote_average from ``score`` field."""

    def test_score_propagates_to_vote_average(self) -> None:
        """TVDB's ``score`` ends up in vote_average (same selector contract)."""
        item = parse_artwork({"type": 2, "image": "http://example.com/p.jpg", "score": 12.5})
        assert item is not None
        assert item.vote_average == 12.5

    def test_score_invalid_falls_back_to_zero(self) -> None:
        """Non-numeric ``score`` does not crash; vote_average defaults to 0.0."""
        item = parse_artwork({"type": 2, "image": "http://x", "score": "n/a"})
        assert item is not None
        assert item.vote_average == 0.0


class TestParseEpisodePhase27Tvdb:
    """Phase 27: TVDB EpisodeInfo.season_number + still_url."""

    def test_episode_carries_season_number(self) -> None:
        """``seasonNumber`` from TVDB raw response is preserved."""
        ep = parse_episode({"number": 5, "seasonNumber": 3, "name": "T"})
        assert ep.season_number == 3

    def test_episode_still_url_from_image(self) -> None:
        """TVDB ``image`` field becomes ``still_url`` (already absolute URL)."""
        ep = parse_episode({"number": 1, "image": "https://artworks.thetvdb.com/x.jpg", "name": "T"})
        assert ep.still_url == "https://artworks.thetvdb.com/x.jpg"


class TestParseEpisode:
    """Episode parsing."""

    def test_episode_from_golden(self) -> None:
        """First Breaking Bad episode."""
        data = _load("episodes_default.json")
        raw = unwrap(data)
        assert isinstance(raw, dict)
        ep = parse_episode(raw["episodes"][0])
        assert isinstance(ep, EpisodeInfo)
        assert ep.episode_number == 1
        assert ep.title == "Pilot"
        assert ep.runtime_minutes == 58
        assert ep.air_date == "2008-01-20"

    def test_episode_null_runtime(self) -> None:
        """Null runtime → None."""
        ep = parse_episode({"number": 1, "runtime": None, "name": "", "aired": ""})
        assert ep.runtime_minutes is None


class TestParseSeasonDetails:
    """SeasonDetails from golden samples."""

    def test_season_details(self) -> None:
        """Breaking Bad S1 → SeasonDetails."""
        data = _load("episodes_default.json")
        raw = unwrap(data)
        assert isinstance(raw, dict)
        sd = parse_season_details(raw, "tvdb", "81189", 1)
        assert isinstance(sd, SeasonDetails)
        assert sd.provider == "tvdb"
        assert sd.tv_id == "81189"
        assert sd.season_number == 1
        assert len(sd.episodes) == 7
        assert sd.episodes[0].episode_number == 1


class TestParseVideo:
    """Video/trailer parsing."""

    def test_extract_youtube_key(self) -> None:
        """Extracts YouTube key from URL."""
        v = parse_video({"id": 1, "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        assert v is not None
        assert v.key == "dQw4w9WgXcQ"

    def test_empty_url_returns_none(self) -> None:
        """No URL → None."""
        assert parse_video({"id": 1, "url": ""}) is None
