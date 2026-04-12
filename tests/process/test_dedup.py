"""Tests for process/dedup.py — fuzzy duplicate folder merging."""

import pytest

from personalscraper.process.dedup import dedup_folders


@pytest.fixture
def movies_dir(tmp_path):
    """Create a category directory for dedup tests."""
    d = tmp_path / "001-MOVIES"
    d.mkdir()
    return d


class TestDedupFolders:
    """Tests for dedup_folders() duplicate detection and merging."""

    def test_shrinking_duplicate_merged(self, movies_dir):
        """'Shrinking' + 'Shrinking (2023)' are merged (classic dedup case)."""
        # Less complete — no NFO, fewer files
        dup = movies_dir / "Shrinking"
        dup.mkdir()
        (dup / "movie.mkv").write_text("video")

        # More complete — has NFO
        canonical = movies_dir / "Shrinking (2023)"
        canonical.mkdir()
        (canonical / "movie.mkv").write_text("video")
        (canonical / "movie.nfo").write_text("nfo")

        merged = dedup_folders(movies_dir)

        assert merged == 1
        assert not dup.exists()
        assert canonical.exists()
        assert (canonical / "movie.nfo").exists()

    def test_year_mismatch_no_merge(self, movies_dir):
        """'The Matrix (1999)' + 'The Matrix (2003)' — year guard prevents merge."""
        a = movies_dir / "The Matrix (1999)"
        a.mkdir()
        (a / "movie.mkv").write_text("v1")

        b = movies_dir / "The Matrix (2003)"
        b.mkdir()
        (b / "movie.mkv").write_text("v2")

        merged = dedup_folders(movies_dir)

        assert merged == 0
        assert a.exists()
        assert b.exists()

    def test_different_titles_no_merge(self, movies_dir):
        """Completely different titles are not merged."""
        a = movies_dir / "Inception (2010)"
        a.mkdir()
        (a / "movie.mkv").write_text("v1")

        b = movies_dir / "Interstellar (2014)"
        b.mkdir()
        (b / "movie.mkv").write_text("v2")

        merged = dedup_folders(movies_dir)

        assert merged == 0

    def test_dry_run_no_merge(self, movies_dir):
        """Dry-run detects but does not merge."""
        dup = movies_dir / "Shrinking"
        dup.mkdir()
        (dup / "movie.mkv").write_text("video")

        canonical = movies_dir / "Shrinking (2023)"
        canonical.mkdir()
        (canonical / "movie.mkv").write_text("video")

        merged = dedup_folders(movies_dir, dry_run=True)

        assert merged == 1
        # Both folders still exist
        assert dup.exists()
        assert canonical.exists()

    def test_empty_dir_returns_zero(self, tmp_path):
        """Non-existent category dir returns 0."""
        assert dedup_folders(tmp_path / "nonexistent") == 0

    def test_merge_keeps_more_complete(self, movies_dir):
        """The folder with more files is kept as target."""
        # Folder with fewer files
        sparse = movies_dir / "Movie"
        sparse.mkdir()
        (sparse / "movie.mkv").write_text("video")

        # Folder with more files (NFO + poster)
        rich = movies_dir / "Movie (2024)"
        rich.mkdir()
        (rich / "movie.mkv").write_text("video")
        (rich / "movie.nfo").write_text("nfo")
        (rich / "movie-poster.jpg").write_text("poster")

        merged = dedup_folders(movies_dir)

        assert merged == 1
        assert not sparse.exists()
        assert rich.exists()
        # Rich folder should still have all its files
        assert (rich / "movie.nfo").exists()
        assert (rich / "movie-poster.jpg").exists()
