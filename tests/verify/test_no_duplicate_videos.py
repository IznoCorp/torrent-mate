"""Tests for the movie-only no_duplicate_videos check.

A movie folder is flat: it must hold at most one feature video at its root.
More than one root-level video signals that the same-TMDB merge dedup contract
was violated and an orphan video was left behind. The check is non-recursive,
so videos inside sub-dirs (e.g. ``Extras/``) are ignored. TV shows are exempt
and are not covered here.
"""

from pathlib import Path

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import MediaChecker


@pytest.fixture
def checker(test_config: Config) -> MediaChecker:
    """Create a MediaChecker with default patterns and a synthetic V15 Config."""
    return MediaChecker(NamingPatterns(), test_config)


def _make_movie_dir(tmp_path: Path, title: str = "Gourou", year: int = 2026) -> Path:
    """Create a movie directory with a single root-level video file."""
    d = tmp_path / f"{title} ({year})"
    d.mkdir()
    (d / f"{title}.mkv").write_bytes(b"\x00" * 1024)
    return d


def test_single_root_video_passes(checker: MediaChecker, tmp_path: Path) -> None:
    """One video at the root → check passes with no message."""
    movie_dir = _make_movie_dir(tmp_path)

    result = checker._check_no_duplicate_videos(movie_dir)

    assert result.passed is True
    assert result.message == ""


def test_two_root_videos_fails(checker: MediaChecker, tmp_path: Path) -> None:
    """Two videos at the root → check fails, message lists both filenames."""
    movie_dir = _make_movie_dir(tmp_path)
    (movie_dir / "orphan.mkv").write_bytes(b"\x00" * 1024)

    result = checker._check_no_duplicate_videos(movie_dir)

    assert result.passed is False
    assert "Multiple video files at root" in result.message
    assert "Gourou.mkv" in result.message
    assert "orphan.mkv" in result.message


def test_flat_trailer_exempt_passes(checker: MediaChecker, tmp_path: Path) -> None:
    """Root feature video plus a flat ``-trailer`` video → passes (trailer exempt).

    Movies place their trailer FLAT at the root as ``{media_name}-trailer.{ext}``
    (Plex convention). That trailer must not count as a duplicate feature video.
    """
    movie_dir = _make_movie_dir(tmp_path, title="Film", year=2020)
    (movie_dir / "Film (2020)-trailer.mp4").write_bytes(b"\x00" * 1024)

    result = checker._check_no_duplicate_videos(movie_dir)

    assert result.passed is True
    assert result.message == ""


def test_orphan_video_still_fails(checker: MediaChecker, tmp_path: Path) -> None:
    """Root feature video plus a non-trailer orphan video → still fails (regression intact)."""
    movie_dir = _make_movie_dir(tmp_path, title="Film", year=2020)
    (movie_dir / "orphan.mkv").write_bytes(b"\x00" * 1024)

    result = checker._check_no_duplicate_videos(movie_dir)

    assert result.passed is False
    assert "Multiple video files at root" in result.message
    assert "orphan.mkv" in result.message


def test_video_in_subdir_ignored(checker: MediaChecker, tmp_path: Path) -> None:
    """One root video plus one in an Extras/ sub-dir → passes (non-recursive)."""
    movie_dir = _make_movie_dir(tmp_path)
    extras = movie_dir / "Extras"
    extras.mkdir()
    (extras / "behind-the-scenes.mkv").write_bytes(b"\x00" * 1024)

    result = checker._check_no_duplicate_videos(movie_dir)

    assert result.passed is True
    assert result.message == ""
