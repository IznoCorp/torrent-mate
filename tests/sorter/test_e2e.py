"""End-to-end tests for V2 sort — realistic staging directory scenarios."""

from pathlib import Path

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import folder_name
from personalscraper.sorter.run import run_sort
from personalscraper.sorter.sorter import Sorter
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture
def config(tmp_path) -> Config:
    """Provide a Config with CANONICAL_STAGING_DIRS pointing at tmp_path."""
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": [s.model_dump() for s in CANONICAL_STAGING_DIRS],
        }
    )


@pytest.fixture
def staging(config, tmp_path) -> Path:
    """Create a realistic staging directory with type subdirectories derived from config.

    Uses the staging_dir from config so that run_sort resolves paths correctly.
    """
    staging_root = config.paths.staging_dir
    staging_root.mkdir(parents=True, exist_ok=True)
    for entry in config.staging_dirs:
        (staging_root / folder_name(entry)).mkdir(parents=True, exist_ok=True)
    return staging_root


@pytest.fixture
def staging_settings(staging):
    """Provide a minimal Settings mock pointing to the staging tmp directory."""
    from unittest.mock import MagicMock

    s = MagicMock()
    s.ingest_dir_name = "097-TEMP"
    s.ingest_dir.side_effect = lambda staging_dir: staging_dir / "097-TEMP"
    return s


def _create_movie_dir(staging: Path, name: str) -> Path:
    """Create a movie directory with typical files."""
    d = staging / name
    d.mkdir()
    (d / "movie.mkv").write_text("video")
    (d / "movie.nfo").write_text("nfo")
    (d / "poster.jpg").write_text("image")
    return d


def _create_episode_file(staging: Path, name: str) -> Path:
    """Create a standalone episode file."""
    f = staging / name
    f.write_text("episode video")
    return f


# --- End-to-end with Sorter ---


class TestE2ESorter:
    """End-to-end tests using Sorter.process() directly."""

    def test_movie_dir_sorted_correctly(self, staging, config):
        """Movie directory goes into {movies_dir}/Title (Year)/."""
        _create_movie_dir(staging, "Movie.Title.2024.1080p.BluRay.x264-GROUP")
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        assert len(results) == 1
        r = results[0]
        assert r.status == "moved"
        assert r.media_type == "movie"
        assert "001-MOVIES" in str(r.destination)
        assert "Movie Title" in r.title
        assert r.year == 2024

    def test_tvshow_episode_sorted_correctly(self, staging, config):
        """TV show episode file goes into {tvshows_dir}/Show Name/."""
        _create_episode_file(staging, "The.Boys.S05E01.MULTi.1080p.mkv")
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        assert len(results) == 1
        r = results[0]
        assert r.status == "moved"
        assert r.media_type == "tvshow"
        assert "002-TVSHOWS" in str(r.destination)
        assert r.season == 5
        assert r.episode == 1

    def test_tvshow_season_pack_sorted(self, staging, config):
        """Season pack directory goes into {tvshows_dir}/Show Name/."""
        pack = staging / "Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX"
        pack.mkdir()
        (pack / "ep1.mkv").write_text("video")
        (pack / "ep2.mkv").write_text("video")
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        assert len(results) == 1
        assert results[0].media_type == "tvshow"
        assert "002-TVSHOWS" in str(results[0].destination)

    def test_ebook_sorted_correctly(self, staging, config):
        """Ebook goes into {ebooks_dir}/."""
        (staging / "book.epub").write_text("ebook")
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        assert results[0].media_type == "ebook"
        assert "003-EBOOKS" in str(results[0].destination)

    def test_audio_sorted_correctly(self, staging, config):
        """Audio goes into {audio_dir}/."""
        (staging / "audiobook.mp3").write_text("audio")
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        assert results[0].media_type == "audio"
        assert "004-AUDIO" in str(results[0].destination)

    def test_mixed_items_sorted(self, staging, config):
        """Multiple items of different types are all sorted correctly."""
        _create_movie_dir(staging, "Movie.2024.1080p")
        _create_episode_file(staging, "Show.S01E01.mkv")
        (staging / "book.epub").write_text("ebook")
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        types = {r.media_type for r in results}
        assert "movie" in types
        assert "tvshow" in types
        assert "ebook" in types
        assert all(r.status == "moved" for r in results)

    def test_existing_show_folder_merge(self, staging, config):
        """New episode merges into existing show folder."""
        existing = staging / "002-TVSHOWS" / "The Boys"
        existing.mkdir(parents=True)
        (existing / "S05E01.mkv").write_text("ep1")
        _create_episode_file(staging, "The.Boys.S05E02.MULTi.1080p.mkv")
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        r = results[0]
        assert r.status == "moved"
        # Should go into existing "The Boys" folder, not create a new one
        assert "The Boys" in str(r.destination)

    def test_dry_run_full_pipeline(self, staging, config):
        """Dry-run processes all items without moving anything."""
        _create_movie_dir(staging, "Movie.2024.1080p")
        _create_episode_file(staging, "Show.S01E01.mkv")
        sorter = Sorter(config=config, dry_run=True)
        results = sorter.process(staging)
        assert all(r.status == "dry-run" for r in results)
        # Original items should still exist
        assert (staging / "Movie.2024.1080p").exists()
        assert (staging / "Show.S01E01.mkv").exists()


# --- End-to-end with run_sort + StepReport ---


class TestE2ERunSort:
    """End-to-end tests using run_sort() which returns StepReport."""

    def test_run_sort_returns_step_report(self, staging_settings, staging, config):
        """run_sort returns a properly populated StepReport."""
        temp = staging / "097-TEMP"
        temp.mkdir(exist_ok=True)
        _create_movie_dir(temp, "Movie.2024.1080p")
        _create_episode_file(temp, "Show.S01E01.mkv")
        report = run_sort(staging_settings, staging_dir=staging, config=config, dry_run=False)
        assert report.name == "sort"
        assert report.success_count == 2
        assert report.error_count == 0

    def test_run_sort_dry_run(self, staging_settings, staging, config):
        """run_sort dry-run counts items in details."""
        temp = staging / "097-TEMP"
        temp.mkdir(exist_ok=True)
        _create_movie_dir(temp, "Movie.2024.1080p")
        report = run_sort(staging_settings, staging_dir=staging, config=config, dry_run=True)
        assert report.success_count == 1
        assert any("[DRY-RUN]" in d for d in report.details)

    def test_run_sort_empty_staging(self, staging_settings, staging, config):
        """run_sort on empty staging returns zero counts."""
        (staging / "097-TEMP").mkdir(exist_ok=True)
        report = run_sort(staging_settings, staging_dir=staging, config=config, dry_run=False)
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0
