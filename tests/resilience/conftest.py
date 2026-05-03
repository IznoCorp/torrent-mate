"""Shared fixtures for resilience tests.

Provides realistic media directory setups with valid NFOs, artwork,
and category structures for testing crash recovery and idempotence.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.conf.models.config import Config
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture
def staging(tmp_path):
    """Create a realistic staging directory with category subdirectories."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "001-MOVIES").mkdir()
    (staging_dir / "002-TVSHOWS").mkdir()
    (staging_dir / "097-TEMP").mkdir()
    return staging_dir


@pytest.fixture
def resilience_settings(staging):
    """Provide a minimal Settings mock pointing to the staging tmp directory.

    V15 P6.5: Settings no longer carries staging_dir (moved to Config.paths).
    Tests that use this fixture pass staging_dir explicitly to run_* functions.
    The mock retains staging_dir and movies/tvshows dir names for modules that
    still accept them via MagicMock attribute access.
    """
    s = MagicMock()
    s.staging_dir = staging
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    s.ingest_dir_name = "097-TEMP"
    s.ingest_dir.side_effect = lambda staging_dir: staging_dir / "097-TEMP"
    return s


@pytest.fixture
def resilience_config(staging, tmp_path) -> Config:
    """Real Config with CANONICAL_STAGING_DIRS pointing at the staging fixture.

    Args:
        staging: Resilience staging directory fixture.
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Validated Config with staging_dir matching the staging fixture.
    """
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(staging),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": [s.model_dump() for s in CANONICAL_STAGING_DIRS],
        }
    )


def make_valid_movie_dir(movies_dir: Path, title: str = "Movie", year: int = 2024) -> Path:
    """Create a complete movie directory with valid NFO, poster, and video.

    Args:
        movies_dir: Parent category directory ({movies_dir}/).
        title: Movie title.
        year: Movie year.

    Returns:
        Path to the created movie directory.
    """
    d = movies_dir / f"{title} ({year})"
    d.mkdir(exist_ok=True)
    # Video file (small but enough for tests)
    (d / f"{title}.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    # Valid NFO with uniqueid
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid = ET.SubElement(root, "uniqueid")
    uid.set("type", "tmdb")
    uid.text = "12345"
    uid2 = ET.SubElement(root, "uniqueid")
    uid2.set("type", "imdb")
    uid2.text = "tt12345"
    ET.SubElement(root, "genre").text = "Drame"
    fi = ET.SubElement(root, "fileinfo")
    ET.SubElement(ET.SubElement(fi, "streamdetails"), "video")
    ET.ElementTree(root).write(d / f"{title}.nfo", encoding="unicode")
    # Artwork
    (d / f"{title}-poster.jpg").write_bytes(b"\xff\xd8\xff")
    (d / f"{title}-landscape.jpg").write_bytes(b"\xff\xd8\xff")
    return d


def make_valid_tvshow_dir(tvshows_dir: Path, title: str = "Show", year: int = 2024) -> Path:
    """Create a complete TV show directory with valid NFO, poster, and episodes.

    Args:
        tvshows_dir: Parent category directory ({tvshows_dir}/).
        title: Show title.
        year: Show year.

    Returns:
        Path to the created TV show directory.
    """
    d = tvshows_dir / f"{title} ({year})"
    d.mkdir(exist_ok=True)
    # tvshow.nfo with uniqueid
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = title
    uid = ET.SubElement(root, "uniqueid")
    uid.set("type", "tvdb")
    uid.text = "456"
    uid2 = ET.SubElement(root, "uniqueid")
    uid2.set("type", "tmdb")
    uid2.text = "789"
    ET.SubElement(root, "genre").text = "Drame"
    ET.ElementTree(root).write(d / "tvshow.nfo", encoding="unicode")
    # Artwork
    (d / "poster.jpg").write_bytes(b"\xff\xd8\xff")
    (d / "fanart.jpg").write_bytes(b"\xff\xd8\xff")
    # Season with properly named episode
    season = d / "Saison 01"
    season.mkdir()
    (season / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    (season / "S01E01 - Pilot.nfo").write_text("<episodedetails/>")
    return d
