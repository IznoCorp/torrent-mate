"""Unit tests for TrailerFinder — TMDB-first / YouTube-fallback discovery.

All external dependencies (TMDBClient, YoutubeSearch, TrailersCache) are mocked.
"""

from unittest.mock import MagicMock

import pytest

from personalscraper.scraper.tmdb_client import Video
from personalscraper.scraper.trailer_finder import TrailerFinder

_TRAILER_VIDEO = Video(
    id="abc",
    site="YouTube",
    key="TRAILER_KEY",
    type="Trailer",
    official=True,
    size=1080,
    iso_639_1="en",
)
_TEASER_VIDEO = Video(
    id="def",
    site="YouTube",
    key="TEASER_KEY",
    type="Teaser",
    official=True,
    size=720,
    iso_639_1="en",
)
_YT_URL = "https://www.youtube.com/watch?v=TRAILER_KEY"


@pytest.fixture()
def finder(tmp_path):
    """Build a TrailerFinder with mocked TMDBClient and YoutubeSearch."""
    client = MagicMock()
    searcher = MagicMock()
    from personalscraper.scraper.trailers_cache import TrailersCache

    cache = TrailersCache(tmp_path / "tc.json")
    return TrailerFinder(
        tmdb_client=client,
        youtube_search=searcher,
        cache=cache,
        languages=["fr-FR", "en-US"],
    )


class TestTrailerFinder:
    """Tests for TrailerFinder two-tier discovery strategy."""

    def test_returns_tmdb_trailer_url(self, finder):
        """find() returns YouTube URL for first Trailer type from TMDB."""
        finder._tmdb_client.fetch_movie_videos.return_value = [_TRAILER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_tmdb_teaser_used_when_no_trailer(self, finder):
        """find() falls back to Teaser if no Trailer type exists in TMDB results."""
        finder._tmdb_client.fetch_movie_videos.return_value = [_TEASER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == "https://www.youtube.com/watch?v=TEASER_KEY"

    def test_youtube_fallback_on_empty_tmdb(self, finder):
        """find() falls back to YouTube search when TMDB returns no videos."""
        finder._tmdb_client.fetch_movie_videos.return_value = []
        finder._youtube_search.search.return_value = _YT_URL
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_returns_none_when_both_fail(self, finder):
        """find() returns None when TMDB and YouTube both return nothing."""
        finder._tmdb_client.fetch_movie_videos.return_value = []
        finder._youtube_search.search.return_value = None
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url is None

    def test_language_priority_fr_before_en(self, finder):
        """find() queries fr-FR before en-US and returns on first hit."""

        def fetch_side_effect(tmdb_id, language):
            if language == "fr-FR":
                return [_TRAILER_VIDEO]
            return []

        finder._tmdb_client.fetch_movie_videos.side_effect = fetch_side_effect
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        # Only one call (fr-FR) because it already found a result
        assert finder._tmdb_client.fetch_movie_videos.call_count == 1

    def test_tv_show_uses_fetch_tv_videos(self, finder):
        """find() calls fetch_tv_videos for media_type='tv'."""
        finder._tmdb_client.fetch_tv_videos.return_value = [_TRAILER_VIDEO]
        url = finder.find(1399, "tv", title="Game of Thrones", year=2011)
        assert url == _YT_URL
        finder._tmdb_client.fetch_tv_videos.assert_called()

    def test_cache_hit_skips_network(self, finder, tmp_path):
        """find() returns cached URL without calling TMDBClient or YoutubeSearch."""
        # Prime the cache directly
        finder._cache.set_tmdb_videos(550, "movie", "fr-FR", [_TRAILER_VIDEO])
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        finder._tmdb_client.fetch_movie_videos.assert_not_called()

    def test_non_youtube_videos_filtered_out(self, finder):
        """find() ignores non-YouTube videos even when they are Trailers."""
        vimeo_video = Video(
            id="xyz",
            site="Vimeo",
            key="vimeo-id",
            type="Trailer",
            official=True,
            size=1080,
            iso_639_1="en",
        )
        finder._tmdb_client.fetch_movie_videos.return_value = [vimeo_video]
        finder._youtube_search.search.return_value = _YT_URL
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        # Vimeo entry must be ignored; YouTube search fallback should be used.
        assert url == _YT_URL
        finder._youtube_search.search.assert_called_once()

    def test_season_uses_fetch_tv_season_videos(self, finder):
        """find() calls fetch_tv_season_videos when season_number is provided."""
        finder._tmdb_client.fetch_tv_season_videos.return_value = [_TRAILER_VIDEO]
        url = finder.find(1399, "tv", title="Game of Thrones", year=2011, season_number=1)
        assert url == _YT_URL
        finder._tmdb_client.fetch_tv_season_videos.assert_called()
        finder._tmdb_client.fetch_tv_videos.assert_not_called()
