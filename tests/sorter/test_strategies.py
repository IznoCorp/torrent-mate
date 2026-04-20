"""Tests for personalscraper.sorter.strategies — sorting strategies."""

import pytest

from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType
from personalscraper.sorter.strategies import (
    TYPE_DIR_MAP,
    DefaultStrategy,
    MovieStrategy,
    TVShowStrategy,
)


@pytest.fixture
def cleaner():
    """Provide a NameCleaner instance."""
    return NameCleaner()


@pytest.fixture
def staging(tmp_path):
    """Create a staging directory with type subdirectories."""
    for dir_name in TYPE_DIR_MAP.values():
        (tmp_path / dir_name).mkdir()
    return tmp_path


# --- MovieStrategy ---


class TestMovieStrategy:
    """MovieStrategy — places movies in 001-MOVIES/Title (Year)/."""

    def test_new_movie_creates_folder(self, staging, cleaner):
        """New movie gets a 'Title (Year)' folder."""
        strategy = MovieStrategy()
        dest = strategy.get_destination("Movie.Title.2024.1080p.BluRay.x264-GROUP", staging, cleaner)
        assert dest.parent == staging / "001-MOVIES"
        assert "Movie Title" in dest.name
        assert "(2024)" in dest.name

    def test_new_movie_without_year(self, staging, cleaner):
        """Movie without year gets a 'Title' folder."""
        strategy = MovieStrategy()
        dest = strategy.get_destination("Some.Movie.1080p.BluRay", staging, cleaner)
        assert dest.parent == staging / "001-MOVIES"

    def test_existing_movie_fuzzy_match(self, staging, cleaner):
        """Matches existing movie folder via fuzzy matching."""
        existing = staging / "001-MOVIES" / "The Matrix (1999)"
        existing.mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("The.Matrix.1999.Remaster.1080p.BluRay", staging, cleaner)
        assert dest == existing

    def test_different_year_no_match(self, staging, cleaner):
        """Different year does not match existing folder."""
        existing = staging / "001-MOVIES" / "The Matrix (1999)"
        existing.mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("The.Matrix.Reloaded.2003.1080p", staging, cleaner)
        # Should not match the 1999 folder
        assert dest != existing


# --- TVShowStrategy ---


class TestTVShowStrategy:
    """TVShowStrategy — places TV shows in 002-TVSHOWS/Show Name/."""

    def test_new_show_creates_folder(self, staging, cleaner):
        """New show gets a folder without year."""
        strategy = TVShowStrategy()
        dest = strategy.get_destination("Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX", staging, cleaner)
        assert dest.parent == staging / "002-TVSHOWS"
        assert "Shrinking" in dest.name

    def test_show_folder_has_no_year(self, staging, cleaner):
        """V2 creates show folders WITHOUT year (V3 adds it)."""
        strategy = TVShowStrategy()
        dest = strategy.get_destination("The.Boys.S05E01.MULTi.1080p", staging, cleaner)
        # Should not contain a year in parentheses
        assert "(" not in dest.name or "S05" in dest.name

    def test_existing_show_fuzzy_match(self, staging, cleaner):
        """Merges into existing show folder via fuzzy matching."""
        existing = staging / "002-TVSHOWS" / "Shrinking"
        existing.mkdir()
        strategy = TVShowStrategy()
        dest = strategy.get_destination("Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX", staging, cleaner)
        assert dest == existing

    def test_episode_file_matches_show_folder(self, staging, cleaner):
        """Single episode file matches existing show folder."""
        existing = staging / "002-TVSHOWS" / "The Boys"
        existing.mkdir()
        strategy = TVShowStrategy()
        dest = strategy.get_destination("The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP-R3MiX", staging, cleaner)
        assert dest == existing


# --- DefaultStrategy ---


class TestDefaultStrategy:
    """DefaultStrategy — places items in type-specific directories."""

    @pytest.mark.parametrize(
        "file_type,expected_dir",
        [
            (FileType.EBOOK, "003-EBOOKS"),
            (FileType.AUDIO, "004-AUDIO"),
            (FileType.APP, "005-APPS"),
            (FileType.OTHER, "098-AUTRES"),
        ],
    )
    def test_type_directory_mapping(self, staging, cleaner, file_type, expected_dir):
        """Each type maps to its correct directory."""
        strategy = DefaultStrategy(file_type)
        dest = strategy.get_destination("file.ext", staging, cleaner)
        assert dest == staging / expected_dir


# --- TYPE_DIR_MAP ---


class TestTypeDirMap:
    """TYPE_DIR_MAP constant validation."""

    def test_all_types_mapped(self):
        """All FileType values have a directory mapping."""
        for ft in FileType:
            assert ft in TYPE_DIR_MAP
