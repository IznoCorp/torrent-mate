"""Tests for sorter/run.py — assert_temp_empty gate function."""

import pytest

from personalscraper.config import Settings


@pytest.fixture
def gate_settings(tmp_path, monkeypatch):
    """Provide Settings with ingest_dir pointing to a temp 097-TEMP/."""
    staging = tmp_path / "staging"
    staging.mkdir()
    complete = tmp_path / "complete"
    complete.mkdir()
    monkeypatch.setenv("STAGING_DIR", str(staging))
    monkeypatch.setenv("TORRENT_COMPLETE_DIR", str(complete))
    return Settings(_env_file=None)


class TestAssertTempEmpty:
    """Tests for the assert_temp_empty gate function."""

    def test_gate_passes_when_empty(self, gate_settings):
        """Empty ingest dir returns empty list (gate passes)."""
        from personalscraper.sorter.run import assert_temp_empty

        gate_settings.ingest_dir.mkdir(parents=True, exist_ok=True)
        remaining = assert_temp_empty(gate_settings)
        assert remaining == []

    def test_gate_returns_names_when_files_remain(self, gate_settings):
        """Non-empty ingest dir returns list of remaining item names."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = gate_settings.ingest_dir
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / "leftover.mkv").write_text("video")
        (ingest / "another_dir").mkdir()

        remaining = assert_temp_empty(gate_settings)
        assert sorted(remaining) == ["another_dir", "leftover.mkv"]

    def test_gate_ignores_hidden_files(self, gate_settings):
        """Hidden files (.gitkeep, .DS_Store) are ignored by the gate."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = gate_settings.ingest_dir
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / ".gitkeep").write_text("")
        (ingest / ".DS_Store").write_bytes(b"\x00\x00")

        remaining = assert_temp_empty(gate_settings)
        assert remaining == []

    def test_gate_mixed_hidden_and_visible(self, gate_settings):
        """Only visible items are returned, hidden ones are ignored."""
        from personalscraper.sorter.run import assert_temp_empty

        ingest = gate_settings.ingest_dir
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / ".DS_Store").write_bytes(b"\x00")
        (ingest / ".gitkeep").write_text("")
        (ingest / "unsorted_movie").mkdir()

        remaining = assert_temp_empty(gate_settings)
        assert remaining == ["unsorted_movie"]

    def test_gate_passes_when_dir_missing(self, gate_settings):
        """Gate passes (empty list) when ingest dir does not exist."""
        from personalscraper.sorter.run import assert_temp_empty

        # Don't create ingest_dir — it shouldn't exist
        remaining = assert_temp_empty(gate_settings)
        assert remaining == []


class TestSortFastSkip:
    """Tests for sort fast-skip when 097-TEMP is empty."""

    def test_fast_skip_empty_temp(self, gate_settings):
        """Sort returns empty report immediately when 097-TEMP is empty."""
        from personalscraper.sorter.run import run_sort

        gate_settings.ingest_dir.mkdir(parents=True, exist_ok=True)
        report = run_sort(gate_settings)
        assert report.name == "sort"
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0

    def test_no_fast_skip_with_items(self, gate_settings):
        """Sort processes items when 097-TEMP has content."""
        from personalscraper.sorter.run import run_sort

        gate_settings.ingest_dir.mkdir(parents=True, exist_ok=True)
        (gate_settings.ingest_dir / "movie.mkv").write_text("video")
        report = run_sort(gate_settings)
        # At least one item was processed (moved or skipped)
        assert report.success_count + report.skip_count + report.error_count > 0
