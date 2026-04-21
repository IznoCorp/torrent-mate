"""Tests for sorter/run.py — assert_temp_empty gate function."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def staging(tmp_path: Path) -> Path:
    """Create a staging directory with 097-TEMP inside."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    return staging_dir


@pytest.fixture
def gate_settings() -> MagicMock:
    """Provide a minimal Settings mock with ingest_dir_name."""
    s = MagicMock()
    s.ingest_dir_name = "097-TEMP"
    s.ingest_dir.side_effect = lambda staging_dir: staging_dir / "097-TEMP"
    return s


class TestAssertTempEmpty:
    """Tests for the assert_temp_empty gate function."""

    def test_gate_passes_when_empty(self, gate_settings: MagicMock, staging: Path) -> None:
        """Empty ingest dir returns empty list (gate passes)."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        remaining = assert_temp_empty(gate_settings, staging_dir=staging)
        assert remaining == []

    def test_gate_returns_names_when_files_remain(self, gate_settings: MagicMock, staging: Path) -> None:
        """Non-empty ingest dir returns list of remaining item names."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / "leftover.mkv").write_text("video")
        (ingest / "another_dir").mkdir()

        remaining = assert_temp_empty(gate_settings, staging_dir=staging)
        assert sorted(remaining) == ["another_dir", "leftover.mkv"]

    def test_gate_ignores_hidden_files(self, gate_settings: MagicMock, staging: Path) -> None:
        """Hidden files (.gitkeep, .DS_Store) are ignored by the gate."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / ".gitkeep").write_text("")
        (ingest / ".DS_Store").write_bytes(b"\x00\x00")

        remaining = assert_temp_empty(gate_settings, staging_dir=staging)
        assert remaining == []

    def test_gate_mixed_hidden_and_visible(self, gate_settings: MagicMock, staging: Path) -> None:
        """Only visible items are returned, hidden ones are ignored."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / ".DS_Store").write_bytes(b"\x00")
        (ingest / ".gitkeep").write_text("")
        (ingest / "unsorted_movie").mkdir()

        remaining = assert_temp_empty(gate_settings, staging_dir=staging)
        assert remaining == ["unsorted_movie"]

    def test_gate_passes_when_dir_missing(self, gate_settings: MagicMock, staging: Path) -> None:
        """Gate passes (empty list) when ingest dir does not exist."""
        from personalscraper.sorter.run import assert_temp_empty

        # 097-TEMP not created — it shouldn't exist
        remaining = assert_temp_empty(gate_settings, staging_dir=staging)
        assert remaining == []


class TestSortFastSkip:
    """Tests for sort fast-skip when 097-TEMP is empty."""

    def test_fast_skip_empty_temp(self, gate_settings: MagicMock, staging: Path) -> None:
        """Sort returns empty report immediately when 097-TEMP is empty."""
        from personalscraper.sorter.run import run_sort

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        report = run_sort(gate_settings, staging_dir=staging)
        assert report.name == "sort"
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0

    def test_no_fast_skip_with_items(self, gate_settings: MagicMock, staging: Path) -> None:
        """Sort processes items when 097-TEMP has content."""
        from personalscraper.sorter.run import run_sort

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / "movie.mkv").write_text("video")
        report = run_sort(gate_settings, staging_dir=staging)
        # At least one item was processed (moved or skipped)
        assert report.success_count + report.skip_count + report.error_count > 0
