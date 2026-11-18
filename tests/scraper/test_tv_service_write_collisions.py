"""A rename skipped for a collision is reported in ``ScrapeResult.warnings``.

``rename_episodes`` never replaces an existing destination (it logs
``episode_rename_collision`` and leaves both files). The scrape result must say so too:
with a mix of renamed and skipped files the run used to look like a plain success, the
skipped file staying loose with nothing but a log line to tell the operator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.orchestrator import Scraper

_SHOW_TVDB_ID = 420001
_SHOW_DATA: dict[str, Any] = {
    "id": 66732,
    "name": "Fallout",
    "original_name": "Fallout",
    "overview": "",
    "genres": [],
    "first_air_date": "2024-04-10",
    "external_ids": {"imdb_id": "tt12637874", "tvdb_id": _SHOW_TVDB_ID},
    "images": {"posters": [], "backdrops": [], "logos": []},
    "seasons": [{"season_number": 1, "episode_count": 2}],
}


@pytest.fixture
def scraper(mock_registry: Any) -> Scraper:
    """A registry-backed Scraper with no config (classification skipped).

    Args:
        mock_registry: The fake-provider registry of the scraper conftest.

    Returns:
        A :class:`Scraper` wired to that registry.
    """
    settings = MagicMock()
    settings.tmdb_api_key = "fake-key"
    settings.tvdb_api_key = "fake-key"
    with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
        return Scraper(settings, NamingPatterns(), event_bus=EventBus(), registry=mock_registry)


def _scrape(scraper: Scraper, show_dir: Path) -> Any:
    """Run the forced scrape of *show_dir* against a two-episode season 1, offline.

    Args:
        scraper: The scraper under test.
        show_dir: The show folder to scrape.

    Returns:
        The :class:`~personalscraper.scraper._shared.ScrapeResult`.
    """
    episode_map = {
        (1, 1): {"title": "The End", "still_path": ""},
        (1, 2): {"title": "The Target", "still_path": ""},
    }
    with (
        patch(
            "personalscraper.scraper.tv_service_write.fetch_show_data",
            return_value=(_SHOW_DATA, 66732),
        ),
        patch.object(scraper, "_build_episode_map", return_value=episode_map),
        patch.object(scraper, "_xref_enrichment", return_value=None),
        patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
        patch.object(scraper._artwork, "download_tvshow_artwork", return_value=[]),
    ):
        return scraper.scrape_tvshow_forced(show_dir, "tvdb", _SHOW_TVDB_ID)


def _show_with_a_taken_destination(tmp_path: Path) -> Path:
    """Build a show holding a real S01E01, a duplicate S01E01 in a release folder and a new S01E02.

    Args:
        tmp_path: Pytest temporary directory the show folder is created in.

    Returns:
        The show folder (pre-rename).
    """
    show = tmp_path / "Fallout.S01.1080p.WEB.H264-GROUP"
    (show / "Saison 01").mkdir(parents=True)
    (show / "Saison 01" / "S01E01 - The End.mkv").write_text("the real S01E01")
    release = show / "Fallout.S01.REPACK"
    release.mkdir()
    (release / "Fallout.S01E01.REPACK.mkv").write_text("duplicate S01E01")
    (release / "Fallout.S01E02.REPACK.mkv").write_text("new S01E02")
    return show


def test_a_skipped_collision_is_reported_in_the_warnings(scraper: Scraper, tmp_path: Path) -> None:
    """One line names the skipped source and its taken destination, one line sums up."""
    result = _scrape(scraper, _show_with_a_taken_destination(tmp_path))

    assert result.media_path is not None
    renamed = sorted(p.name for p in (result.media_path / "Saison 01").glob("*.mkv"))
    assert renamed == ["S01E01 - The End.mkv", "S01E02 - The Target.mkv"]
    assert (result.media_path / "Saison 01" / "S01E01 - The End.mkv").read_text() == "the real S01E01"
    assert (result.media_path / "Fallout.S01.REPACK" / "Fallout.S01E01.REPACK.mkv").exists()
    assert (
        "Episode not renamed, destination already exists: "
        "Fallout.S01.REPACK/Fallout.S01E01.REPACK.mkv → Saison 01/S01E01 - The End.mkv"
    ) in result.warnings
    assert "1 episode(s) not renamed: destination already exists" in result.warnings


def test_no_collision_adds_no_warning(scraper: Scraper, tmp_path: Path) -> None:
    """A clean scrape keeps an empty warning list."""
    show = tmp_path / "Fallout.S01.1080p.WEB.H264-GROUP"
    show.mkdir()
    (show / "Fallout.S01E01.mkv").write_text("S01E01")
    (show / "Fallout.S01E02.mkv").write_text("S01E02")

    result = _scrape(scraper, show)

    assert result.warnings == []
    assert result.episodes_renamed == 2
