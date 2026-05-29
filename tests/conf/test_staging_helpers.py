"""Tests for personalscraper.conf.staging helper functions."""

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.conf.models.staging import StagingDirConfig
from personalscraper.conf.staging import find_by_file_type, find_ingest_dir, folder_name, staging_path
from personalscraper.core.media_types import FileType


def _make_config(staging_dirs: list[dict]) -> Config:
    """Build a minimal Config for staging helper tests.

    Args:
        staging_dirs: List of staging dir dicts to include.

    Returns:
        Validated Config instance with one disk and the given staging_dirs.
    """
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": "/tmp/torrents",
                "staging_dir": "/tmp/staging",
                "data_dir": "/tmp/.data",
            },
            "disks": [{"id": "disk_a", "path": "/tmp/disk_a", "categories": ["movies"]}],
            "staging_dirs": staging_dirs,
        }
    )


_DEFAULT_DIRS = [
    {"id": 1, "name": "movies", "file_type": "movie"},
    {"id": 2, "name": "tvshows", "file_type": "tvshow"},
    {"id": 3, "name": "ebooks", "file_type": "ebook"},
    {"id": 4, "name": "audio", "file_type": "audio"},
    {"id": 5, "name": "apps", "file_type": "app"},
    {"id": 6, "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres", "file_type": "other"},
]


class TestFolderName:
    """Tests for conf.staging.folder_name helper."""

    def test_standard_movie(self):
        """id=1, name='movies' produces '001-MOVIES'."""
        entry = StagingDirConfig(id=1, name="movies", file_type="movie")
        assert folder_name(entry) == "001-MOVIES"

    def test_tvshows(self):
        """id=2, name='tvshows' produces '002-TVSHOWS'."""
        entry = StagingDirConfig(id=2, name="tvshows", file_type="tvshow")
        assert folder_name(entry) == "002-TVSHOWS"

    def test_temp_ingest(self):
        """id=97, name='temp' (role=ingest) produces '097-TEMP'."""
        entry = StagingDirConfig(id=97, name="temp", role="ingest")
        assert folder_name(entry) == "097-TEMP"

    def test_custom_id_10(self):
        """id=10, name='mega' produces '010-MEGA'."""
        entry = StagingDirConfig(id=10, name="mega", file_type="movie")
        assert folder_name(entry) == "010-MEGA"

    def test_kebab_name_uppercased(self):
        """Kebab name 'tv-shows' produces '002-TV-SHOWS' (hyphens preserved)."""
        entry = StagingDirConfig(id=2, name="tv-shows", file_type="tvshow")
        assert folder_name(entry) == "002-TV-SHOWS"


class TestStagingPath:
    """Tests for conf.staging.staging_path helper."""

    def test_path_combines_staging_dir_and_folder_name(self):
        """staging_path returns staging_dir / folder_name(entry)."""
        config = _make_config(_DEFAULT_DIRS)
        entry = config.staging_dirs[0]  # movies
        path = staging_path(config, entry)
        assert path == config.paths.staging_dir / "001-MOVIES"


class TestFindByFileType:
    """Tests for conf.staging.find_by_file_type helper."""

    def test_finds_movie(self):
        """Returns the entry with file_type='movie' for FileType.MOVIE."""
        config = _make_config(_DEFAULT_DIRS)
        entry = find_by_file_type(config, FileType.MOVIE)
        assert entry.name == "movies"

    def test_finds_tvshow(self):
        """Returns the entry with file_type='tvshow' for FileType.TVSHOW."""
        config = _make_config(_DEFAULT_DIRS)
        entry = find_by_file_type(config, FileType.TVSHOW)
        assert entry.name == "tvshows"

    def test_missing_type_raises_key_error(self):
        """Raises KeyError when no entry matches the requested FileType."""
        config = _make_config([{"id": 97, "name": "temp", "file_type": None, "role": "ingest"}])
        with pytest.raises(KeyError, match="movie"):
            find_by_file_type(config, FileType.MOVIE)


class TestFindIngestDir:
    """Tests for conf.staging.find_ingest_dir helper."""

    def test_finds_ingest_entry(self):
        """Returns the entry with role='ingest' and correct folder name."""
        config = _make_config(_DEFAULT_DIRS)
        entry = find_ingest_dir(config)
        assert entry.role == "ingest"
        assert folder_name(entry) == "097-TEMP"
