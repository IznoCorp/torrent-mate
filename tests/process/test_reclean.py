"""Tests for process/reclean.py — is_title_polluted and reclean_folders."""

import pytest

from personalscraper.process.reclean import is_title_polluted, reclean_folders


class TestIsTitlePolluted:
    """Tests for release token detection in folder names."""

    def test_raw_release_name_detected(self):
        """Full release name with codec, resolution, group → polluted."""
        assert is_title_polluted("Movie.Title.2024.1080p.BluRay.x264-GROUP") is True

    def test_avatar_neostark_detected(self):
        """Real-world case: Avatar with release group → polluted."""
        assert is_title_polluted("Avatar de feu et de cendres 7 1 neostark") is True

    def test_tvshow_release_detected(self):
        """TV show release name with resolution and group → polluted."""
        assert is_title_polluted("The.Boys.S05E01.MULTi.1080p-R3MiX") is True

    def test_clean_title_not_flagged(self):
        """Clean title 'The Matrix' → not polluted."""
        assert is_title_polluted("The Matrix") is False

    def test_scream_7_not_flagged(self):
        """Title with number 'Scream 7' → not polluted (7 is not a resolution)."""
        assert is_title_polluted("Scream 7") is False

    def test_title_with_year_not_flagged(self):
        """Clean 'Title (Year)' format → not polluted."""
        assert is_title_polluted("Shrinking (2023)") is False

    def test_2001_space_odyssey_not_flagged(self):
        """Title starting with year-like number → not polluted."""
        assert is_title_polluted("2001 A Space Odyssey") is False

    def test_jury_duty_not_flagged(self):
        """Simple clean title → not polluted."""
        assert is_title_polluted("Jury Duty") is False


@pytest.fixture
def movies_dir(tmp_path):
    """Create a category directory with some media folders."""
    d = tmp_path / "001-MOVIES"
    d.mkdir()
    return d


class TestRecleanFolders:
    """Tests for reclean_folders() folder re-cleaning."""

    def test_polluted_folder_renamed(self, movies_dir):
        """Folder with release tokens is re-cleaned to 'Title (Year)'."""
        polluted = movies_dir / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "movie.mkv").write_text("video")

        report = reclean_folders(movies_dir)

        assert report.success_count == 1
        assert not polluted.exists()
        # Should be renamed to clean format
        clean = movies_dir / "Movie Title (2024)"
        assert clean.exists()
        assert (clean / "movie.mkv").exists()

    def test_clean_folder_skipped(self, movies_dir):
        """Folder with clean name is skipped."""
        clean = movies_dir / "The Matrix (1999)"
        clean.mkdir()
        (clean / "movie.mkv").write_text("video")

        report = reclean_folders(movies_dir)

        assert report.skip_count == 1
        assert report.success_count == 0
        assert clean.exists()

    def test_target_exists_merges(self, movies_dir):
        """When clean target already exists, polluted folder is merged into it."""
        # Existing clean folder
        existing = movies_dir / "Movie Title (2024)"
        existing.mkdir()
        (existing / "existing.nfo").write_text("nfo")

        # Polluted duplicate
        polluted = movies_dir / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "movie.mkv").write_text("video")

        report = reclean_folders(movies_dir)

        assert report.success_count == 1
        assert not polluted.exists()
        # Both files should be in the clean folder
        assert (existing / "existing.nfo").exists()
        assert (existing / "movie.mkv").exists()

    def test_dry_run_no_rename(self, movies_dir):
        """Dry-run logs but does not rename."""
        polluted = movies_dir / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "movie.mkv").write_text("video")

        report = reclean_folders(movies_dir, dry_run=True)

        assert report.success_count == 1
        assert polluted.exists()  # Not renamed
        assert any("[DRY-RUN]" in d for d in report.details)

    def test_hidden_folders_ignored(self, movies_dir):
        """Hidden folders (.actors, .DS_Store) are not processed."""
        hidden = movies_dir / ".actors"
        hidden.mkdir()

        report = reclean_folders(movies_dir)

        assert report.success_count == 0
        assert report.skip_count == 0

    def test_empty_dir_returns_empty_report(self, tmp_path):
        """Non-existent category dir returns empty report."""
        report = reclean_folders(tmp_path / "nonexistent")

        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0
