"""Tests for ``_local_show_seasons`` — the seasons a show folder's video files really carry.

The set feeds the season request of every scrape, rescrape and repair, and the TVDB
candidate disambiguation: a false season costs a provider call per provider and a
``show_season_empty`` warning, and a missing one lets a real season look like a phantom.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.scraper.existing_validator_drift import _local_show_seasons


def _show_with(tmp_path: Path, *relative_files: str) -> Path:
    """Create a show folder holding the given empty files.

    Args:
        tmp_path: Pytest temporary directory the show folder is created in.
        *relative_files: File paths relative to the show folder (subfolders are created).

    Returns:
        The show folder.
    """
    show = tmp_path / "Show (2025)"
    show.mkdir()
    for relative in relative_files:
        path = show / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    return show


class TestSamplesAreNotEpisodes:
    """A scene sample clip never contributes a season."""

    def test_sample_folder_is_skipped(self, tmp_path: Path) -> None:
        """A clip under ``Sample/`` carries a season of its own that is not the show's."""
        show = _show_with(tmp_path, "Show.S01E01.mkv", "Show.S05.pack/Sample/Show.S05E01.sample.mkv")

        assert _local_show_seasons(show) == {1}

    def test_sample_file_is_skipped(self, tmp_path: Path) -> None:
        """A ``-sample`` clip next to the real episodes is not an episode."""
        show = _show_with(tmp_path, "Show.S01E01.mkv", "Show.S05E01-sample.mkv")

        assert _local_show_seasons(show) == {1}

    def test_a_sample_folder_above_the_show_does_not_hide_its_episodes(self, tmp_path: Path) -> None:
        """Only the path below the show folder says whether a file is a sample."""
        show = tmp_path / "Sample" / "Show (2025)"
        show.mkdir(parents=True)
        (show / "Show.S02E01.mkv").touch()

        assert _local_show_seasons(show) == {2}


class TestResolutionIsNotAnEpisodeMarker:
    """``1920x1080`` is a frame size, not season 20 episode 108."""

    @pytest.mark.parametrize("resolution", ["1920x1080", "1280x720", "3840x2160", "720x480"])
    def test_resolution_token_is_not_read_as_a_season(self, tmp_path: Path, resolution: str) -> None:
        """A name carrying only a resolution has no season at all."""
        show = _show_with(tmp_path, f"Show.{resolution}.x264.mkv")

        assert _local_show_seasons(show) == set()

    def test_real_marker_beside_a_resolution_is_kept(self, tmp_path: Path) -> None:
        """``2x05`` stays an episode marker when the name also carries a resolution."""
        show = _show_with(tmp_path, "Show.2x05.1920x1080.mkv")

        assert _local_show_seasons(show) == {2}

    def test_sxxexx_beside_a_resolution_is_kept(self, tmp_path: Path) -> None:
        """The ``SxxEyy`` form is untouched by the resolution rule."""
        show = _show_with(tmp_path, "Show.S03E04.1920x1080.mkv")

        assert _local_show_seasons(show) == {3}
