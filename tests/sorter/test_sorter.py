"""Tests for personalscraper.sorter.sorter — main sorting orchestrator."""

import shutil

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import folder_name
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
def staging(config, tmp_path):
    """Create a staging directory with type subdirectories derived from config."""
    staging_root = config.paths.staging_dir
    staging_root.mkdir(parents=True, exist_ok=True)
    for entry in config.staging_dirs:
        (staging_root / folder_name(entry)).mkdir(parents=True, exist_ok=True)
    return staging_root


# --- process() ---


class TestProcess:
    """Sorter.process() — batch sorting of staging root items."""

    def test_skips_sorted_directories(self, staging, config):
        """Does not process the sorting destination directories themselves."""
        sorter = Sorter(config=config, dry_run=True)
        results = sorter.process(staging)
        assert len(results) == 0

    def test_skips_hidden_files(self, staging, config):
        """Skips dotfiles like .DS_Store."""
        (staging / ".DS_Store").touch()
        sorter = Sorter(config=config, dry_run=True)
        results = sorter.process(staging)
        assert len(results) == 0

    def test_processes_movie_file(self, staging, config):
        """Processes a standalone movie file."""
        (staging / "Movie.Title.2024.1080p.mkv").touch()
        sorter = Sorter(config=config, dry_run=True)
        results = sorter.process(staging)
        assert len(results) == 1
        assert results[0].media_type == "movie"
        assert results[0].status == "dry-run"

    def test_processes_tvshow_directory(self, staging, config):
        """Processes a TV show directory."""
        show_dir = staging / "Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX"
        show_dir.mkdir()
        (show_dir / "episode.mkv").touch()
        sorter = Sorter(config=config, dry_run=True)
        results = sorter.process(staging)
        assert len(results) == 1
        assert results[0].media_type == "tvshow"

    def test_processes_multiple_items(self, staging, config):
        """Processes all items at root level."""
        (staging / "Movie.2024.mkv").touch()
        (staging / "book.epub").touch()
        (staging / "track.mp3").touch()
        sorter = Sorter(config=config, dry_run=True)
        results = sorter.process(staging)
        assert len(results) == 3

    def test_returns_sort_results(self, staging, config):
        """Returns proper SortResult objects with metadata."""
        (staging / "The.Boys.S05E01.MULTi.1080p.mkv").touch()
        sorter = Sorter(config=config, dry_run=True)
        results = sorter.process(staging)
        r = results[0]
        assert r.media_type == "tvshow"
        assert "The Boys" in r.title
        assert r.season == 5
        assert r.episode == 1


# --- sort_item() dry-run ---


class TestSortItemDryRun:
    """Sorter.sort_item() in dry-run mode — no actual moves."""

    def test_dry_run_does_not_move(self, staging, config):
        """Dry-run mode does not actually move files."""
        movie = staging / "Movie.2024.mkv"
        movie.touch()
        sorter = Sorter(config=config, dry_run=True)
        result = sorter.sort_item(movie, staging)
        assert result.status == "dry-run"
        assert movie.exists()  # File should still be at original location

    def test_dry_run_movie_destination(self, staging, config):
        """Dry-run correctly computes movie destination."""
        movie = staging / "Movie.Title.2024.1080p.mkv"
        movie.touch()
        sorter = Sorter(config=config, dry_run=True)
        result = sorter.sort_item(movie, staging)
        assert "001-MOVIES" in str(result.destination)
        assert result.year == 2024

    def test_dry_run_tvshow_destination(self, staging, config):
        """Dry-run correctly computes TV show destination."""
        episode = staging / "Show.S01E04.1080p.mkv"
        episode.touch()
        sorter = Sorter(config=config, dry_run=True)
        result = sorter.sort_item(episode, staging)
        assert "002-TVSHOWS" in str(result.destination)
        assert result.season == 1
        assert result.episode == 4

    def test_dry_run_ebook_destination(self, staging, config):
        """Dry-run correctly routes ebooks."""
        (staging / "book.epub").touch()
        sorter = Sorter(config=config, dry_run=True)
        result = sorter.sort_item(staging / "book.epub", staging)
        assert "003-EBOOKS" in str(result.destination)

    def test_dry_run_audio_destination(self, staging, config):
        """Dry-run correctly routes audio."""
        (staging / "track.mp3").touch()
        sorter = Sorter(config=config, dry_run=True)
        result = sorter.sort_item(staging / "track.mp3", staging)
        assert "004-AUDIO" in str(result.destination)


# --- sort_item() actual moves ---


class TestSortItemMove:
    """Sorter.sort_item() with actual file moves."""

    def test_move_movie_file(self, staging, config):
        """Moves a movie file into {movies_dir}/Title (Year)/."""
        movie = staging / "Movie.Title.2024.1080p.mkv"
        movie.write_text("fake video content")
        sorter = Sorter(config=config, dry_run=False)
        result = sorter.sort_item(movie, staging)
        assert result.status == "moved"
        assert not movie.exists()
        assert result.destination.exists()

    def test_move_movie_directory(self, staging, config):
        """Moves a movie directory into {movies_dir}/."""
        movie_dir = staging / "Movie.Title.2024.1080p"
        movie_dir.mkdir()
        (movie_dir / "movie.mkv").write_text("content")
        (movie_dir / "movie.nfo").write_text("nfo")
        sorter = Sorter(config=config, dry_run=False)
        result = sorter.sort_item(movie_dir, staging)
        assert result.status == "moved"
        assert not movie_dir.exists()
        assert result.destination.exists()

    def test_move_tvshow_file(self, staging, config):
        """Moves a TV show file into {tvshows_dir}/Show Name/."""
        episode = staging / "Show.S01E04.1080p.mkv"
        episode.write_text("fake episode")
        sorter = Sorter(config=config, dry_run=False)
        result = sorter.sort_item(episode, staging)
        assert result.status == "moved"
        assert not episode.exists()
        assert result.destination.exists()
        assert "002-TVSHOWS" in str(result.destination)

    def test_move_ebook(self, staging, config):
        """Moves an ebook into {ebooks_dir}/."""
        ebook = staging / "book.epub"
        ebook.write_text("ebook content")
        sorter = Sorter(config=config, dry_run=False)
        result = sorter.sort_item(ebook, staging)
        assert result.status == "moved"
        assert "003-EBOOKS" in str(result.destination)

    def test_skip_existing_destination(self, staging, config):
        """Skips item if destination already exists."""
        episode = staging / "Show.S01E04.1080p.mkv"
        episode.write_text("content")
        # Pre-create the destination
        show_dir = staging / "002-TVSHOWS" / "Show"
        show_dir.mkdir(parents=True)
        dest = show_dir / "Show.S01E04.1080p.mkv"
        dest.write_text("existing")
        sorter = Sorter(config=config, dry_run=False)
        result = sorter.sort_item(episode, staging)
        assert result.status == "skipped"
        assert episode.exists()  # Original not moved


# --- Error handling ---


class TestErrorHandling:
    """Sorter error handling — never crashes on individual items."""

    def test_error_on_permission_denied(self, staging, config, monkeypatch):
        """Returns error SortResult on permission denied."""
        bad_file = staging / "restricted.mkv"
        bad_file.touch()
        # Simulate permission error by monkeypatching shutil.move
        import personalscraper.sorter.sorter as sorter_mod

        monkeypatch.setattr(
            sorter_mod.shutil, "move", lambda *a, **kw: (_ for _ in ()).throw(PermissionError("denied"))
        )
        sorter = Sorter(config=config, dry_run=False)
        result = sorter.sort_item(bad_file, staging)
        assert result.status == "error"
        assert result.message is not None
        assert "denied" in result.message

    def test_errors_dont_stop_processing(self, staging, config, monkeypatch):
        """Errors on one item don't prevent processing others."""
        (staging / "Movie.2024.mkv").write_text("ok")
        (staging / "bad.mkv").write_text("will fail")

        original_move = shutil.move
        call_count = {"n": 0}

        def flaky_move(src, dst, **kw):
            call_count["n"] += 1
            if "bad" in str(src):
                raise OSError("disk error")
            return original_move(src, dst)

        import personalscraper.sorter.sorter as sorter_mod

        monkeypatch.setattr(sorter_mod.shutil, "move", flaky_move)
        sorter = Sorter(config=config, dry_run=False)
        results = sorter.process(staging)
        statuses = {r.status for r in results}
        assert "error" in statuses
        assert "moved" in statuses
