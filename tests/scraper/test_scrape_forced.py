"""Regression tests for the operator-forced scrape entry points.

These lock in the fix for the *resolve-but-never-dispatch loop* (product-intent
mission, 2026-07-13): a manual scrape resolution used to run a PARTIAL write
(NFO + artwork only), leaving the movie folder + video — and TV episodes —
unrenamed, so the pipeline's ``verify`` step blocked dispatch (poster-name
mismatch for movies; "unrenamed episodes / no episode NFO" for TV). The fix
routes the resolve through the SAME canonical write as the automatic scrape via
``Scraper.scrape_movie_forced`` / ``Scraper.scrape_tvshow_forced`` (a forced
provider match). These tests prove the forced entries produce a COMPLETE result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.orchestrator import Scraper


@pytest.fixture
def scraper(mock_registry: Any) -> Scraper:
    """A registry-backed Scraper with no config (classification is skipped)."""
    settings = MagicMock()
    settings.tmdb_api_key = "fake-key"
    settings.tvdb_api_key = "fake-key"
    with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
        return Scraper(settings, NamingPatterns(), event_bus=EventBus(), registry=mock_registry)


_MOVIE_DATA: dict[str, Any] = {
    "id": 603,
    "title": "The Matrix",
    "original_title": "The Matrix",
    "overview": "A hacker learns the truth.",
    "vote_average": 8.2,
    "vote_count": 20000,
    "genres": [{"name": "Action"}],
    "release_date": "1999-03-31",
    "credits": {"cast": [], "crew": []},
    "images": {"posters": [], "backdrops": []},
    "external_ids": {"imdb_id": "tt0133093"},
    "release_dates": {"results": []},
    "production_countries": [],
    "production_companies": [],
}


class TestScrapeMovieForced:
    """``Scraper.scrape_movie_forced`` — a resolve must produce a COMPLETE result."""

    def test_renames_folder_and_video_and_writes_canonical_nfo(self, scraper: Scraper, tmp_path: Path) -> None:
        """Raw folder + raw video → canonical ``Title (Year)/`` with ``Title.ext`` + ``Title.nfo``.

        This is the exact gap the operator hit: the resolve identified the item
        but left the video with its raw release name (so ``verify`` blocked
        dispatch on a poster/video mismatch). The forced scrape must rename BOTH
        the folder and the video to the canonical form.
        """
        movie_dir = tmp_path / "the.matrix.1999 (1999)"
        movie_dir.mkdir()
        raw_video = movie_dir / "the.matrix.1999.1080p.BluRay.x264-GROUP.mkv"
        raw_video.write_text("video")

        with (
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=_MOVIE_DATA),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie_forced(movie_dir, 603)

        assert result.action == "scraped", result.error
        canonical = tmp_path / "The Matrix (1999)"
        assert canonical.is_dir(), "folder was NOT renamed to the canonical 'Title (Year)'"
        assert (canonical / "The Matrix.mkv").exists(), "video was NOT renamed to the canonical 'Title.ext'"
        assert (canonical / "The Matrix.nfo").exists(), "canonical NFO missing"
        # The raw release-named video must be gone — the precise stuck-item symptom.
        assert not (canonical / "the.matrix.1999.1080p.BluRay.x264-GROUP.mkv").exists()

    def test_case_only_rename_keeps_video(self, scraper: Scraper, tmp_path: Path) -> None:
        """A folder differing from the canonical name ONLY by case keeps its video.

        Regression (prod incident, Flow → FLOW): on macOS's case-insensitive
        filesystem the canonical path ALIASES the current folder, and the old
        code took the merge-with-existing branch — merging the folder into
        itself, unlinking the video (the only copy) and rmdir'ing the folder;
        the item ended up an empty shell holding just the NFO. The rename must
        take the case-safe two-step path and keep every file.
        """
        movie_dir = tmp_path / "the matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "the.matrix.1999.1080p.WEB.x264-GRP.mkv").write_text("precious")

        with (
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=_MOVIE_DATA),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie_forced(movie_dir, 603)

        assert result.action == "scraped", result.error
        canonical = tmp_path / "The Matrix (1999)"
        assert canonical.is_dir()
        assert (canonical / "The Matrix.mkv").exists(), "video LOST during a case-only folder rename"
        assert (canonical / "The Matrix.nfo").exists(), "canonical NFO missing"

    def test_renames_video_even_when_folder_already_canonical(self, scraper: Scraper, tmp_path: Path) -> None:
        """Aymeric/Ferrari shape: folder already ``Title (Year)`` but the video is raw.

        The folder does not move, but the video MUST still be renamed to the
        canonical ``Title.ext`` — otherwise ``verify`` blocks dispatch.
        """
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The.Matrix.1999.FRENCH.1080p.WEBrip.x265-TyHD.mkv").write_text("video")

        with (
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=_MOVIE_DATA),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie_forced(movie_dir, 603)

        assert result.action == "scraped", result.error
        assert (movie_dir / "The Matrix.mkv").exists(), "video was NOT renamed to canonical 'Title.ext'"
        assert not (movie_dir / "The.Matrix.1999.FRENCH.1080p.WEBrip.x265-TyHD.mkv").exists()

    def test_provider_failure_returns_error_result(self, scraper: Scraper, tmp_path: Path) -> None:
        """A provider fetch failure surfaces as ``action='error'`` (fail-soft, no raise)."""
        movie_dir = tmp_path / "Broken (2020)"
        movie_dir.mkdir()

        with patch.object(scraper._registry.get("tmdb"), "get_movie", side_effect=RuntimeError("TMDB down")):
            result = scraper.scrape_movie_forced(movie_dir, 999)

        assert result.action == "error"
        assert "TMDB down" in (result.error or "")


class TestScrapeTvshowForced:
    """``Scraper.scrape_tvshow_forced`` — a resolve must rename episodes + write NFOs."""

    def test_renames_loose_episode_into_season_dir(self, scraper: Scraper, tmp_path: Path) -> None:
        """Top Chef shape: a loose raw-named episode is swept into ``Saison NN/`` + renamed.

        The exact TV gap the operator hit: after resolving, the episode kept its
        raw release name and stayed loose at the show root, so ``verify`` blocked
        dispatch on "unrenamed episodes / no Saison NN". The forced scrape must
        rename the episode into its season directory.
        """
        show_dir = tmp_path / "Top.Chef.Le.Concours.Parallele (2026)"
        show_dir.mkdir()
        raw_ep = show_dir / "Top.Chef.Le.Concours.Parallele.S17E10.FRENCH.1080p.WEB.H264-laRoulade.mkv"
        raw_ep.write_bytes(b"\x00")

        show_data = {
            "id": 475278,
            "name": "Top Chef Le Concours Parallele",
            "original_name": "Top Chef Le Concours Parallele",
            "overview": "Cooking.",
            "genres": [{"name": "Reality"}],
            "first_air_date": "2026-01-01",
            "external_ids": {"imdb_id": "", "tvdb_id": 475278},
            "images": {"posters": [], "backdrops": []},
            "seasons": [],
        }
        # Drive the forced lookup's provider fetch + the episode map. The episode
        # map is mocked (its own fetch is unit-tested elsewhere); the real
        # ``_match_seasons`` performs the rename we assert on.
        episode_map = {(17, 10): {"title": "La Roulade", "still_path": ""}}

        with (
            patch(
                "personalscraper.scraper.tv_service_write.fetch_show_data",
                return_value=(show_data, None),
            ),
            patch.object(scraper, "_build_episode_map", return_value=episode_map),
            patch.object(scraper, "_xref_enrichment", return_value=None),
            patch.object(scraper._artwork, "download_tvshow_artwork", return_value=[]),
        ):
            result = scraper.scrape_tvshow_forced(show_dir, "tvdb", 475278)

        assert result.action == "scraped", result.error
        canonical = tmp_path / "Top Chef Le Concours Parallele (2026)"
        assert canonical.is_dir(), "show folder was NOT renamed to canonical 'Show (Year)'"
        season_dir = canonical / "Saison 17"
        assert season_dir.is_dir(), "episode was NOT swept into a 'Saison NN/' directory"
        moved = list(season_dir.glob("*.mkv"))
        assert moved, "episode file was NOT moved into the season directory"
        assert not raw_ep.exists(), "raw release-named episode still loose at the show root"
        assert (canonical / "tvshow.nfo").exists(), "tvshow.nfo missing"

    def test_provider_failure_returns_error_result(self, scraper: Scraper, tmp_path: Path) -> None:
        """A provider fetch failure surfaces as ``action='error'`` (fail-soft, no raise)."""
        show_dir = tmp_path / "Broken Show (2020)"
        show_dir.mkdir()

        with patch(
            "personalscraper.scraper.tv_service_write.fetch_show_data",
            side_effect=RuntimeError("TVDB down"),
        ):
            result = scraper.scrape_tvshow_forced(show_dir, "tvdb", 999)

        assert result.action == "error"
        assert "TVDB down" in (result.error or "")
