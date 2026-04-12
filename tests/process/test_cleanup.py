"""Tests for process/cleanup.py — recursive empty directory removal."""

import pytest

from personalscraper.process.cleanup import cleanup_empty_dirs


@pytest.fixture
def category_dir(tmp_path):
    """Create a category directory for cleanup tests."""
    d = tmp_path / "001-MOVIES"
    d.mkdir()
    return d


class TestCleanupEmptyDirs:
    """Tests for cleanup_empty_dirs() recursive removal."""

    def test_nested_empty_dirs_removed(self, category_dir):
        """Nested empty directories are all removed bottom-up."""
        # Create: root/A/B/C (all empty)
        c = category_dir / "A" / "B" / "C"
        c.mkdir(parents=True)

        report = cleanup_empty_dirs(category_dir)

        assert report.success_count == 3
        assert not (category_dir / "A").exists()

    def test_dir_with_files_not_removed(self, category_dir):
        """Directory containing files is not removed."""
        movie = category_dir / "The Matrix (1999)"
        movie.mkdir()
        (movie / "movie.mkv").write_text("video")

        report = cleanup_empty_dirs(category_dir)

        assert report.success_count == 0
        assert movie.exists()

    def test_ds_store_only_treated_as_empty(self, category_dir):
        """Directory with only .DS_Store is treated as empty."""
        folder = category_dir / "empty_with_ds"
        folder.mkdir()
        (folder / ".DS_Store").write_bytes(b"\x00")

        report = cleanup_empty_dirs(category_dir)

        assert report.success_count == 1
        assert not folder.exists()

    def test_category_root_never_removed(self, category_dir):
        """The category root directory is never removed even if empty."""
        report = cleanup_empty_dirs(category_dir)

        assert report.success_count == 0
        assert category_dir.exists()

    def test_dry_run_no_removal(self, category_dir):
        """Dry-run counts but does not remove."""
        empty = category_dir / "empty_folder"
        empty.mkdir()

        report = cleanup_empty_dirs(category_dir, dry_run=True)

        assert report.success_count == 1
        assert empty.exists()
        assert any("[DRY-RUN]" in d for d in report.details)

    def test_mixed_empty_and_nonempty(self, category_dir):
        """Only empty dirs are removed, non-empty are kept."""
        # Non-empty
        movie = category_dir / "Movie (2024)"
        movie.mkdir()
        (movie / "movie.mkv").write_text("video")

        # Empty
        empty = category_dir / "empty_folder"
        empty.mkdir()

        report = cleanup_empty_dirs(category_dir)

        assert report.success_count == 1
        assert not empty.exists()
        assert movie.exists()

    def test_nonexistent_dir_returns_empty_report(self, tmp_path):
        """Non-existent directory returns empty report."""
        report = cleanup_empty_dirs(tmp_path / "nonexistent")
        assert report.success_count == 0
