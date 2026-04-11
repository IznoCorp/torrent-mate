"""Tests for personalscraper.sorter.file_type — FileType enum and detection."""

from pathlib import Path

import pytest

from personalscraper.sorter.file_type import (
    FileType,
    _has_tvshow_markers,
    detect_dir_type,
    detect_file_type,
)

# --- FileType enum ---


class TestFileType:
    """FileType enum basic properties."""

    def test_all_types_exist(self):
        """All 6 expected types are defined."""
        expected = {"movie", "tvshow", "ebook", "audio", "app", "other"}
        assert {ft.value for ft in FileType} == expected


# --- detect_file_type ---


class TestDetectFileType:
    """Extension-based file type detection."""

    @pytest.mark.parametrize("ext", ["mkv", "mp4", "avi", "mov", "wmv", "flv", "webm", "m4v", "ts"])
    def test_video_without_markers_is_movie(self, ext):
        """Video files without S/E markers are classified as MOVIE."""
        assert detect_file_type(Path(f"Your.Friends.H265-TFA.{ext}")) == FileType.MOVIE

    @pytest.mark.parametrize("name", [
        "Shrinking.S03.MULTi.1080p.mkv",
        "The.Boys.S05E01.MULTi.1080p.mkv",
        "show.1x04.episode.mkv",
        "Show.Saison.3.MULTi.mkv",
        "Show.Season.2.1080p.mkv",
        "show.s01e04.mkv",
    ])
    def test_video_with_markers_is_tvshow(self, name):
        """Video files with season/episode markers are classified as TVSHOW."""
        assert detect_file_type(Path(name)) == FileType.TVSHOW

    @pytest.mark.parametrize("ext", ["pdf", "epub", "mobi", "azw3", "cbz", "cbr"])
    def test_ebook_extensions(self, ext):
        """Ebook extensions are classified as EBOOK."""
        assert detect_file_type(Path(f"book.{ext}")) == FileType.EBOOK

    @pytest.mark.parametrize("ext", ["mp3", "flac", "ogg", "m4a", "m4b", "opus"])
    def test_audio_extensions(self, ext):
        """Audio extensions are classified as AUDIO."""
        assert detect_file_type(Path(f"track.{ext}")) == FileType.AUDIO

    @pytest.mark.parametrize("ext", ["exe", "msi", "dmg", "pkg", "apk"])
    def test_app_extensions(self, ext):
        """App/installer extensions are classified as APP."""
        assert detect_file_type(Path(f"setup.{ext}")) == FileType.APP

    @pytest.mark.parametrize("ext", ["nfo", "txt", "jpg", "png", "srt", "sub"])
    def test_unknown_extensions_are_other(self, ext):
        """Extensions not in any category are classified as OTHER."""
        assert detect_file_type(Path(f"file.{ext}")) == FileType.OTHER

    def test_no_extension_is_other(self):
        """Files without extension are classified as OTHER."""
        assert detect_file_type(Path("README")) == FileType.OTHER

    def test_case_insensitive_extension(self):
        """Extension matching is case-insensitive."""
        assert detect_file_type(Path("movie.MKV")) == FileType.MOVIE
        assert detect_file_type(Path("book.EPUB")) == FileType.EBOOK


# --- _has_tvshow_markers ---


class TestHasTvshowMarkers:
    """TV show pattern detection in filenames."""

    @pytest.mark.parametrize("name,expected", [
        ("Show.S01E04.1080p.mkv", True),
        ("Show.s03.MULTi.mkv", True),
        ("Show.1x04.mkv", True),
        ("Show.Saison.1.mkv", True),
        ("Show.Season.2.mkv", True),
        ("Show.S01-S08.Complete.mkv", True),
        ("Movie.2024.1080p.mkv", False),
        ("Your.Friends.H265.mkv", False),
    ])
    def test_tvshow_marker_detection(self, name, expected):
        """Detects various TV show naming conventions."""
        assert _has_tvshow_markers(name) is expected


# --- detect_dir_type ---


class TestDetectDirType:
    """Directory type detection via name and children."""

    def test_dir_name_with_tvshow_markers(self, tmp_path):
        """Directory name containing S01E04 is TVSHOW without checking children."""
        d = tmp_path / "Shrinking.S03.MULTi.1080p"
        d.mkdir()
        assert detect_dir_type(d) == FileType.TVSHOW

    def test_dir_with_movie_files(self, tmp_path):
        """Directory containing only video files without markers is MOVIE."""
        d = tmp_path / "Some.Movie.2024"
        d.mkdir()
        (d / "movie.mkv").touch()
        (d / "movie.nfo").touch()  # OTHER, ignored in vote
        assert detect_dir_type(d) == FileType.MOVIE

    def test_dir_with_tvshow_files(self, tmp_path):
        """Directory with episode files is TVSHOW."""
        d = tmp_path / "SomeShow"
        d.mkdir()
        (d / "Show.S01E01.mkv").touch()
        (d / "Show.S01E02.mkv").touch()
        assert detect_dir_type(d) == FileType.TVSHOW

    def test_empty_dir_is_other(self, tmp_path):
        """Empty directories are classified as OTHER."""
        d = tmp_path / "empty"
        d.mkdir()
        assert detect_dir_type(d) == FileType.OTHER

    def test_dir_with_only_nfo_is_other(self, tmp_path):
        """Directory with only non-sortable files is OTHER."""
        d = tmp_path / "nfo_only"
        d.mkdir()
        (d / "info.nfo").touch()
        (d / "poster.jpg").touch()
        assert detect_dir_type(d) == FileType.OTHER

    def test_dir_with_audio_files(self, tmp_path):
        """Directory with audio files is AUDIO."""
        d = tmp_path / "audiobook"
        d.mkdir()
        (d / "chapter1.mp3").touch()
        (d / "chapter2.mp3").touch()
        assert detect_dir_type(d) == FileType.AUDIO

    def test_majority_vote_movie_wins(self, tmp_path):
        """Majority vote picks the most common type among children."""
        d = tmp_path / "mixed"
        d.mkdir()
        (d / "movie1.mkv").touch()
        (d / "movie2.mkv").touch()
        (d / "bonus.S01E01.mkv").touch()  # 1 TVSHOW vs 2 MOVIE
        assert detect_dir_type(d) == FileType.MOVIE
