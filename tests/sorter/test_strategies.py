"""Tests for personalscraper.sorter.strategies — sorting strategies."""

from pathlib import Path

import pytest

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, folder_name, staging_path
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType
from personalscraper.sorter.strategies import DefaultStrategy, MovieStrategy, TVShowStrategy

_STAGING_DIRS = [
    {"id": 1, "name": "movies", "file_type": "movie"},
    {"id": 2, "name": "tvshows", "file_type": "tvshow"},
    {"id": 3, "name": "ebooks", "file_type": "ebook"},
    {"id": 4, "name": "audio", "file_type": "audio"},
    {"id": 5, "name": "apps", "file_type": "app"},
    {"id": 6, "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres", "file_type": "other"},
]


@pytest.fixture
def config(tmp_path) -> Config:
    """Provide a Config with staging_dirs pointing at tmp_path."""
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": _STAGING_DIRS,
        }
    )


@pytest.fixture
def cleaner() -> NameCleaner:
    """Provide a NameCleaner instance for strategy tests."""
    return NameCleaner()


@pytest.fixture
def staging(config, tmp_path) -> Path:
    """Create staging subdirs on disk matching config."""
    staging_root = config.paths.staging_dir
    staging_root.mkdir(parents=True, exist_ok=True)
    for entry in config.staging_dirs:
        (staging_root / folder_name(entry)).mkdir(parents=True, exist_ok=True)
    return staging_root


class TestMovieStrategy:
    """MovieStrategy — places movies in {movies_dir}/Title (Year)/."""

    def test_new_movie_creates_folder(self, staging, cleaner, config):
        """New movie name with year → destination under the movies staging dir."""
        strategy = MovieStrategy()
        dest = strategy.get_destination("Movie.Title.2024.1080p.BluRay.x264-GROUP", staging, cleaner, config)
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        assert dest.parent == movies_dir
        assert "Movie Title" in dest.name
        assert "(2024)" in dest.name

    def test_new_movie_without_year(self, staging, cleaner, config):
        """Movie without year in name still lands under movies dir."""
        strategy = MovieStrategy()
        dest = strategy.get_destination("Some.Movie.1080p.BluRay", staging, cleaner, config)
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        assert dest.parent == movies_dir

    def test_existing_movie_fuzzy_match(self, staging, cleaner, config):
        """Existing movie folder matched fuzzily → destination equals existing folder."""
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        existing = movies_dir / "The Matrix (1999)"
        existing.mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("The.Matrix.1999.Remaster.1080p.BluRay", staging, cleaner, config)
        assert dest == existing

    def test_different_year_no_match(self, staging, cleaner, config):
        """Same title but different year → treated as a different movie."""
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        existing = movies_dir / "The Matrix (1999)"
        existing.mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("The.Matrix.Reloaded.2003.1080p", staging, cleaner, config)
        assert dest != existing

    def test_custom_config_different_folder_name(self, tmp_path, cleaner):
        """Custom id=10,name='mega' → dir is 010-MEGA."""
        custom_dirs = [
            {"id": 10, "name": "mega", "file_type": "movie"},
            {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
        ]
        config = Config.model_validate(
            {
                "paths": {
                    "torrent_complete_dir": str(tmp_path / "torrents"),
                    "staging_dir": str(tmp_path / "staging"),
                    "data_dir": str(tmp_path / ".data"),
                },
                "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
                "staging_dirs": custom_dirs,
            }
        )
        staging_root = config.paths.staging_dir
        staging_root.mkdir(parents=True)
        (staging_root / "010-MEGA").mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("Inception.2010.1080p", staging_root, cleaner, config)
        assert dest.parent == staging_root / "010-MEGA"


class TestTVShowStrategy:
    """TVShowStrategy — places TV shows in {tvshows_dir}/Show Name/."""

    def test_new_show_creates_folder(self, staging, cleaner, config):
        """New TV show → destination under the tvshows staging dir."""
        strategy = TVShowStrategy()
        dest = strategy.get_destination("Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX", staging, cleaner, config)
        tvshows_dir = staging_path(config, find_by_file_type(config, FileType.TVSHOW))
        assert dest.parent == tvshows_dir
        assert "Shrinking" in dest.name

    def test_show_folder_has_no_year(self, staging, cleaner, config):
        """TV show folder name should not include a movie-style year marker."""
        strategy = TVShowStrategy()
        dest = strategy.get_destination("The.Boys.S05E01.MULTi.1080p", staging, cleaner, config)
        assert "(" not in dest.name or "S05" in dest.name

    def test_existing_show_fuzzy_match(self, staging, cleaner, config):
        """Existing show folder matched fuzzily → destination equals existing folder."""
        tvshows_dir = staging_path(config, find_by_file_type(config, FileType.TVSHOW))
        existing = tvshows_dir / "Shrinking"
        existing.mkdir()
        strategy = TVShowStrategy()
        dest = strategy.get_destination("Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX", staging, cleaner, config)
        assert dest == existing

    def test_episode_file_matches_show_folder(self, staging, cleaner, config):
        """Episode file matches an existing show folder despite extra quality tags."""
        tvshows_dir = staging_path(config, find_by_file_type(config, FileType.TVSHOW))
        existing = tvshows_dir / "The Boys"
        existing.mkdir()
        strategy = TVShowStrategy()
        dest = strategy.get_destination(
            "The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP-R3MiX", staging, cleaner, config
        )
        assert dest == existing


class TestDefaultStrategy:
    """DefaultStrategy — places items in type-specific directories."""

    @pytest.mark.parametrize(
        "file_type,expected_name",
        [
            (FileType.EBOOK, "003-EBOOKS"),
            (FileType.AUDIO, "004-AUDIO"),
            (FileType.APP, "005-APPS"),
            (FileType.OTHER, "098-AUTRES"),
        ],
    )
    def test_type_directory_mapping(self, staging, cleaner, config, file_type, expected_name):
        """Each FileType resolves to its canonical staging directory name."""
        strategy = DefaultStrategy(file_type)
        dest = strategy.get_destination("file.ext", staging, cleaner, config)
        assert dest == config.paths.staging_dir / expected_name
