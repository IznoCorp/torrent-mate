"""Tests for `_find_video_file` canonical-video selection.

Verifies the mtime-first / size-tiebreak contract: when a movie directory
holds several video files (e.g. two staged sources merged under the same
TMDB id), the most recently modified file is chosen as the canonical video,
with file size acting as the tie-breaker on identical modification times.
Also covers recursion, the empty case, the hidden-file skip, the flat-trailer
exclusion, the ``Trailers/`` sub-dir skip, and the ``OSError`` stat fallback.
"""

import os
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest

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

    def test_flat_trailer_not_selected_even_when_newest(self, tmp_path: Path) -> None:
        """A flat `{name}-trailer.{ext}` is excluded even when it is the newest video.

        Reproduces the phase-30 bug: a trailer downloaded after the feature has
        the latest mtime and would otherwise be picked as the canonical feature
        video. ``is_trailer_filename`` must keep it out of the candidate set.
        """
        feature = _make_video(tmp_path / "Feature.mkv", size=100, mtime=1000.0)
        # Trailer is strictly newer (and larger) — would win on mtime if not excluded.
        _make_video(tmp_path / "Feature (2020)-trailer.mkv", size=999, mtime=9999.0)

        result = _find_video_file(tmp_path)

        assert result == feature

    def test_trailers_subdir_video_is_ignored(self, tmp_path: Path) -> None:
        """A video inside a `Trailers/` sub-dir is never selected (D3).

        The root feature is older and smaller, yet the `Trailers/` candidate is
        excluded by the `"Trailers" not in f.parts` skip, so the feature wins.
        """
        feature = _make_video(tmp_path / "feature.mkv", size=100, mtime=1000.0)
        # Trailers/ entry is newer and larger — must still be ignored.
        _make_video(tmp_path / "Trailers" / "teaser.mkv", size=999, mtime=9999.0)

        assert _find_video_file(tmp_path) == feature

    def test_oserror_on_stat_falls_back_to_first_candidate(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A `stat()` failure in the selection key falls back to `candidates[0]` (D2).

        Both `is_file()` (in the comprehension) and the `(st_mtime, st_size)`
        sort key call `Path.stat()`. We patch `Path.stat` with a per-path
        call-counting side_effect: the FIRST call per path returns the real
        stat (so `is_file()` admits the candidate), and every SUBSEQUENT call
        raises `OSError` (so the sort key raises). `_find_video_file` must then
        log `video_stat_failed` and return the first candidate rather than crash.
        """
        only = _make_video(tmp_path / "feature.mkv", size=42, mtime=1234.0)

        real_stat = Path.stat
        calls: Counter[str] = Counter()

        def _flaky_stat(self: Path, *args: object, **kwargs: object) -> os.stat_result:
            key = str(self)
            calls[key] += 1
            if calls[key] == 1:
                # First touch (is_file in the comprehension) succeeds.
                return real_stat(self, *args, **kwargs)  # type: ignore[arg-type]
            # Selection-key stat() — fail so the `except OSError` branch runs.
            raise OSError("ENXIO simulated stat failure")

        with caplog.at_level("WARNING"):
            with patch("pathlib.Path.stat", _flaky_stat):
                result = _find_video_file(tmp_path)

        assert result == only
        assert "video_stat_failed" in caplog.text


class TestFindVideoFileSampleExclusion:
    """Regression (DEV #1): sample clips must never be picked as the feature."""

    def test_sample_subdir_video_is_ignored(self, tmp_path: Path) -> None:
        """A larger, newer ``Sample/`` clip must NOT beat the real feature.

        Reproduces the bug: the sample sits in a ``Sample/`` subdir and is both
        newer and larger, so without the exclusion it would win on mtime/size.
        """
        feature = _make_video(tmp_path / "movie.2026.mkv", size=4096, mtime=1000.0)
        # Sample is newer AND larger — would win if not excluded.
        _make_video(tmp_path / "Sample" / "movie.2026-sample.mkv", size=999_999, mtime=9999.0)

        assert _find_video_file(tmp_path) == feature

    def test_flat_sample_named_file_is_ignored(self, tmp_path: Path) -> None:
        """A flat ``*-sample.mkv`` (no Sample/ dir) is excluded too."""
        feature = _make_video(tmp_path / "movie.2026.mkv", size=4096, mtime=1000.0)
        _make_video(tmp_path / "movie.2026-sample.mkv", size=999_999, mtime=9999.0)

        assert _find_video_file(tmp_path) == feature

    def test_only_sample_yields_none(self, tmp_path: Path) -> None:
        """A directory holding nothing but a sample yields no feature video."""
        _make_video(tmp_path / "Sample" / "x-sample.mkv", size=1024, mtime=1.0)

        assert _find_video_file(tmp_path) is None
