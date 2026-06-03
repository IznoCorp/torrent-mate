"""Tests for the sample/archive filename predicates (DEV #1).

Pins :func:`is_sample_filename`, :func:`is_sample_path`, and
:func:`is_archive_filename` against the real "Rafa" scene-release shapes that
triggered the bug, plus the false-positive guard for legitimate titles that
merely contain the word "sample".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.core.media_types import (
    is_archive_filename,
    is_sample_filename,
    is_sample_path,
)


class TestIsSampleFilename:
    """Strict suffix match — only delimited ``-sample``/``.sample`` clips."""

    @pytest.mark.parametrize(
        "name",
        [
            "rafa.s01e01.doc.multi.1080p.web.x264-penrose-sample.mkv",  # real Rafa case
            "rafa.s01e02.1080p.web.h264-edith.sample.mkv",  # real Rafa case (.sample)
            "sample.mkv",  # bare
            "SHOW-SAMPLE.MKV",  # case-insensitive
        ],
    )
    def test_sample_clips_detected(self, name: str) -> None:
        """Delimited ``-sample``/``.sample`` clips (and bare ``sample``) match."""
        assert is_sample_filename(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "Free.Sample.2012.1080p.x264.mkv",  # legit title containing "sample"
            "rafa.s01e01.doc.multi.1080p.web.x264-penrose.mkv",  # the real episode
            "Sample.Movie.2020.1080p.mkv",  # "sample" at start, not a suffix
        ],
    )
    def test_non_samples_not_flagged(self, name: str) -> None:
        """Titles that merely contain "sample" are not flagged."""
        assert is_sample_filename(name) is False


class TestIsSamplePath:
    """``Sample/`` directory component OR sample filename."""

    def test_sample_dir_component(self) -> None:
        """A ``Sample/`` component anywhere in the path matches."""
        assert is_sample_path(Path("Rafa/Rafa.S01E01.DOC/Sample/clip.mkv")) is True

    def test_samples_dir_case_insensitive(self) -> None:
        """``SAMPLES/`` matches case-insensitively."""
        assert is_sample_path(Path("Show/SAMPLES/x.mkv")) is True

    def test_proof_dir(self) -> None:
        """``Proof/`` is treated as a sample location."""
        assert is_sample_path(Path("Show/Proof/x.mkv")) is True

    def test_real_episode_not_flagged(self) -> None:
        """A real organised episode path is not a sample path."""
        assert is_sample_path(Path("Rafa/Saison 01/S01E01 - Capitulo 1.mkv")) is False


class TestIsArchiveFilename:
    """Primary archive extensions + old-style RAR volume parts."""

    @pytest.mark.parametrize("name", ["x.rar", "x.zip", "x.7z", "x.r00", "x.r15", "x.r99", "X.RAR"])
    def test_archives_detected(self, name: str) -> None:
        """Containers and old-style RAR volumes (.r00-.r99) match."""
        assert is_archive_filename(name) is True

    @pytest.mark.parametrize("name", ["x.mkv", "x.nfo", "x.srt", "x.r1", "x.rb"])
    def test_non_archives_not_flagged(self, name: str) -> None:
        """Media/text files and near-miss extensions (.r1, .rb) are not archives."""
        assert is_archive_filename(name) is False
