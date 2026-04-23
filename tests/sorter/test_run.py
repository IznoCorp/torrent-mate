"""Tests for sorter/run.py — assert_temp_empty gate function."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.conf.models import Config
from tests.fixtures.config import CANONICAL_STAGING_DIRS


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


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Provide a Config with CANONICAL_STAGING_DIRS for run_sort tests."""
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": [s.model_dump() for s in CANONICAL_STAGING_DIRS],
        }
    )


class TestAssertTempEmpty:
    """Tests for the assert_temp_empty gate function."""

    def test_gate_passes_when_empty(self, gate_settings: MagicMock, staging: Path, config: Config) -> None:
        """Empty ingest dir returns empty list (gate passes)."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        remaining = assert_temp_empty(gate_settings, staging_dir=staging, config=config)
        assert remaining == []

    def test_gate_returns_names_when_files_remain(self, gate_settings: MagicMock, staging: Path, config: Config) -> None:
        """Non-empty ingest dir returns list of remaining item names."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / "leftover.mkv").write_text("video")
        (ingest / "another_dir").mkdir()

        remaining = assert_temp_empty(gate_settings, staging_dir=staging, config=config)
        assert sorted(remaining) == ["another_dir", "leftover.mkv"]

    def test_gate_ignores_hidden_files(self, gate_settings: MagicMock, staging: Path, config: Config) -> None:
        """Hidden files (.gitkeep, .DS_Store) are ignored by the gate."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / ".gitkeep").write_text("")
        (ingest / ".DS_Store").write_bytes(b"\x00\x00")

        remaining = assert_temp_empty(gate_settings, staging_dir=staging, config=config)
        assert remaining == []

    def test_gate_mixed_hidden_and_visible(self, gate_settings: MagicMock, staging: Path, config: Config) -> None:
        """Only visible items are returned, hidden ones are ignored."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / ".DS_Store").write_bytes(b"\x00")
        (ingest / ".gitkeep").write_text("")
        (ingest / "unsorted_movie").mkdir()

        remaining = assert_temp_empty(gate_settings, staging_dir=staging, config=config)
        assert remaining == ["unsorted_movie"]

    def test_gate_passes_when_dir_missing(self, gate_settings: MagicMock, staging: Path, config: Config) -> None:
        """Gate passes (empty list) when ingest dir does not exist."""
        from personalscraper.sorter.run import assert_temp_empty

        # 097-TEMP not created — it shouldn't exist
        remaining = assert_temp_empty(gate_settings, staging_dir=staging, config=config)
        assert remaining == []


class TestSortFastSkip:
    """Tests for sort fast-skip when the ingest dir is empty."""

    def test_fast_skip_empty_temp(self, gate_settings: MagicMock, staging: Path, config: Config) -> None:
        """Sort returns empty report immediately when ingest dir is empty."""
        from personalscraper.sorter.run import run_sort

        ingest = staging / "097-TEMP"
        ingest.mkdir(parents=True, exist_ok=True)
        report = run_sort(gate_settings, staging_dir=staging, config=config)
        assert report.name == "sort"
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0

    def test_no_fast_skip_with_items(self, gate_settings: MagicMock, staging: Path, config: Config) -> None:
        """Sort processes items when ingest dir has content."""
        from personalscraper.conf.staging import folder_name
        from personalscraper.sorter.run import run_sort

        # Create staging subdirs so strategies can resolve destinations
        staging_root = config.paths.staging_dir
        staging_root.mkdir(parents=True, exist_ok=True)
        for entry in config.staging_dirs:
            (staging_root / folder_name(entry)).mkdir(parents=True, exist_ok=True)

        ingest = staging_root / "097-TEMP"
        (ingest / "movie.mkv").write_text("video")
        report = run_sort(gate_settings, staging_dir=staging_root, config=config)
        # At least one item was processed (moved or skipped)
        assert report.success_count + report.skip_count + report.error_count > 0
