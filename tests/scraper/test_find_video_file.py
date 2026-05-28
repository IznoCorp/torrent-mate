"""Tests for `_find_video_file` canonical-video selection.

Verifies the mtime-first / size-tiebreak contract: when a movie directory
holds several video files (e.g. two staged sources merged under the same
TMDB id), the most recently modified file is chosen as the canonical video,
with file size acting as the tie-breaker on identical modification times.
Also covers recursion, the empty case, and the hidden-file skip.
"""

import os
from pathlib import Path

from personalscraper.scraper._shared import _find_video_file


def _make_video(path: Path, size: int, mtime: float) -> Path:
    """Create a video file with a controlled size and modification time.

    Args:
        path: Destination path for the file.
        size: Number of bytes to write.
        mtime: Modification (and access) time to stamp via os.utime.

    Returns:
        The created file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)
    os.utime(path, (mtime, mtime))
    return path


class TestFindVideoFile:
    """Tests for `_find_video_file` selection semantics."""

    def test_newer_mtime_wins_same_size(self, tmp_path: Path) -> None:
        """Two candidates, different mtimes, same size → newest mtime wins."""
        older = _make_video(tmp_path / "old.mkv", size=100, mtime=1000.0)
        newer = _make_video(tmp_path / "new.mkv", size=100, mtime=2000.0)

        result = _find_video_file(tmp_path)

        assert result == newer
        assert result != older

    def test_larger_size_wins_on_equal_mtime(self, tmp_path: Path) -> None:
        """Two candidates, same mtime, different sizes → larger file wins."""
        smaller = _make_video(tmp_path / "small.mkv", size=100, mtime=1500.0)
        larger = _make_video(tmp_path / "large.mkv", size=500, mtime=1500.0)

        result = _find_video_file(tmp_path)

        assert result == larger
        assert result != smaller

    def test_single_candidate_returned_as_is(self, tmp_path: Path) -> None:
        """A single video candidate is returned unchanged."""
        only = _make_video(tmp_path / "only.mkv", size=42, mtime=1234.0)

        assert _find_video_file(tmp_path) == only

    def test_no_candidates_returns_none(self, tmp_path: Path) -> None:
        """A directory with no video files returns None."""
        (tmp_path / "readme.txt").write_text("not a video")
        (tmp_path / "poster.jpg").write_bytes(b"\0" * 10)

        assert _find_video_file(tmp_path) is None

    def test_recurses_into_subdirectory(self, tmp_path: Path) -> None:
        """A candidate nested in a `Saison 01/` sub-dir is discovered."""
        nested = _make_video(tmp_path / "Saison 01" / "episode.mkv", size=100, mtime=1000.0)

        assert _find_video_file(tmp_path) == nested

    def test_hidden_file_is_ignored(self, tmp_path: Path) -> None:
        """A hidden `.foo.mkv` is skipped even if newest and largest."""
        visible = _make_video(tmp_path / "feature.mkv", size=100, mtime=1000.0)
        # Hidden file is both newer and larger — must still be ignored.
        _make_video(tmp_path / ".foo.mkv", size=999, mtime=9999.0)

        assert _find_video_file(tmp_path) == visible
