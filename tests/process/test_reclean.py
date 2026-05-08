"""Tests for process/reclean.py — is_title_polluted and reclean_folders."""

from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.process.reclean import (
    _format_clean_name,
    _propagate_rename_to_disks,
    is_title_polluted,
    reclean_folders,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS


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


def test_reclean_removes_colon_from_folder_name(tmp_path: Path) -> None:
    """Reclean should sanitize folder names — colons must be stripped.

    When NameCleaner.clean() preserves a colon that is part of the title
    (e.g. "Mission: Impossible"), _format_clean_name returns a name with
    a colon. sanitize_filename() must be applied to strip it.
    """
    category_dir = tmp_path / "001-MOVIES"
    category_dir.mkdir()

    # Folder whose title portion retains a colon after guessit parsing.
    # NameCleaner.clean() yields "Mission: Impossible", so _format_clean_name
    # produces "Mission: Impossible (2024)" — sanitize_filename must strip the colon.
    dirty = category_dir / "Mission: Impossible 2024 1080p BluRay"
    dirty.mkdir()
    (dirty / "video.mkv").write_bytes(b"\x00" * 1000)

    reclean_folders(category_dir, dry_run=False)

    # The colon should be gone from every resulting folder name
    result_dirs = [d.name for d in category_dir.iterdir() if d.is_dir()]
    for name in result_dirs:
        assert ":" not in name, f"Colon found in folder name: {name}"


# ---------------------------------------------------------------------------
# Helper: build a multi-disk Config for propagation tests.
# ---------------------------------------------------------------------------


def _make_config_with_disks(tmp_path: Path, disk_paths: list[Path]) -> Config:
    """Build a Config with the given disk paths (id = disk-N).

    Args:
        tmp_path: pytest tmp_path for default sub-paths.
        disk_paths: One mount-point Path per disk.

    Returns:
        A Config instance configured with one ``movies`` category mapped to
        ``001-MOVIES`` on every disk.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[DiskConfig(id=f"disk_{i}", path=p, categories=["movies"]) for i, p in enumerate(disk_paths)],
        categories={"movies": CategoryConfig(folder_name="001-MOVIES")},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


class TestFormatCleanName:
    """Tests for the small _format_clean_name helper."""

    def test_with_year(self) -> None:
        """Year is appended in parentheses."""
        assert _format_clean_name("Foo", 2024) == "Foo (2024)"

    def test_without_year(self) -> None:
        """No year → bare title returned."""
        assert _format_clean_name("Foo", None) == "Foo"


class TestPropagateRenameToDisks:
    """Direct tests for _propagate_rename_to_disks covering all branches."""

    def test_disk_not_mounted_skipped(self, tmp_path: Path) -> None:
        """Unmounted disk (path missing) is silently skipped."""
        ghost = tmp_path / "ghost"  # never created
        config = _make_config_with_disks(tmp_path, [ghost])
        touched = _propagate_rename_to_disks(config, "old", "new", dry_run=True)
        assert touched == []

    def test_disk_iterdir_oserror_logged(self, tmp_path: Path) -> None:
        """OSError on disk.iterdir is caught and the disk is skipped."""
        disk = tmp_path / "disk"
        disk.mkdir()
        config = _make_config_with_disks(tmp_path, [disk])

        original_iterdir = Path.iterdir

        def selective_iterdir(self):
            if self == disk:
                raise OSError("permission denied")
            return original_iterdir(self)

        with patch.object(Path, "iterdir", selective_iterdir):
            touched = _propagate_rename_to_disks(config, "old", "new", dry_run=False)
        assert touched == []

    def test_target_exists_skipped_with_warning(self, tmp_path: Path) -> None:
        """When dst already exists, propagation skips and records 'skipped'."""
        disk = tmp_path / "disk"
        cat = disk / "001-MOVIES"
        cat.mkdir(parents=True)
        (cat / "old").mkdir()
        (cat / "new").mkdir()  # target already exists

        config = _make_config_with_disks(tmp_path, [disk])
        touched = _propagate_rename_to_disks(config, "old", "new", dry_run=False)

        assert any("skipped" in t for t in touched)
        # Source still exists since we did not rename
        assert (cat / "old").is_dir()

    def test_dry_run_logs_without_renaming(self, tmp_path: Path) -> None:
        """dry_run=True records intent but does not rename."""
        disk = tmp_path / "disk"
        cat = disk / "001-MOVIES"
        cat.mkdir(parents=True)
        (cat / "old").mkdir()

        config = _make_config_with_disks(tmp_path, [disk])
        touched = _propagate_rename_to_disks(config, "old", "new", dry_run=True)

        assert (cat / "old").is_dir()
        assert not (cat / "new").exists()
        assert any("dry-run" in t for t in touched)

    def test_actual_rename(self, tmp_path: Path) -> None:
        """dry_run=False successfully renames the folder."""
        disk = tmp_path / "disk"
        cat = disk / "001-MOVIES"
        cat.mkdir(parents=True)
        (cat / "old").mkdir()

        config = _make_config_with_disks(tmp_path, [disk])
        touched = _propagate_rename_to_disks(config, "old", "new", dry_run=False)

        assert not (cat / "old").exists()
        assert (cat / "new").is_dir()
        assert any(t == "disk_0:001-MOVIES" for t in touched)

    def test_rename_oserror_recorded(self, tmp_path: Path) -> None:
        """OSError from rename is caught, captured in touched details."""
        disk = tmp_path / "disk"
        cat = disk / "001-MOVIES"
        cat.mkdir(parents=True)
        (cat / "old").mkdir()

        config = _make_config_with_disks(tmp_path, [disk])

        with patch.object(Path, "rename", side_effect=OSError("perm denied")):
            touched = _propagate_rename_to_disks(config, "old", "new", dry_run=False)

        assert any("failed" in t for t in touched)

    def test_no_matching_folder(self, tmp_path: Path) -> None:
        """If old_name does not exist on disk, nothing is touched."""
        disk = tmp_path / "disk"
        cat = disk / "001-MOVIES"
        cat.mkdir(parents=True)
        # No 'old' subdir

        config = _make_config_with_disks(tmp_path, [disk])
        touched = _propagate_rename_to_disks(config, "old", "new", dry_run=False)
        assert touched == []


class TestRecleanFoldersBranches:
    """Cover the remaining branches of reclean_folders."""

    def test_clean_name_equals_existing_skips(self, tmp_path: Path) -> None:
        """When the cleaned name matches the current folder name, it is skipped.

        Forces the path where ``is_title_polluted`` returns True but the
        cleaner produces the exact same string, so no rename is performed.
        """
        category_dir = tmp_path / "001-MOVIES"
        category_dir.mkdir()
        polluted_name = "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted = category_dir / polluted_name
        polluted.mkdir()

        # Patch the cleaner so the clean_name comes back identical to the source.
        with patch(
            "personalscraper.process.reclean.sanitize_filename",
            return_value=polluted_name,
        ):
            report = reclean_folders(category_dir)

        assert report.skip_count == 1
        assert report.success_count == 0
        assert polluted.exists()

    def test_dry_run_with_config_propagates(self, tmp_path: Path) -> None:
        """dry_run=True and a config: propagation runs in dry mode."""
        # Staging
        staging = tmp_path / "staging" / "001-MOVIES"
        staging.mkdir(parents=True)
        polluted_name = "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        (staging / polluted_name).mkdir()

        # Disk where the same polluted folder also exists
        disk = tmp_path / "disk"
        disk_cat = disk / "001-MOVIES"
        disk_cat.mkdir(parents=True)
        (disk_cat / polluted_name).mkdir()

        config = _make_config_with_disks(tmp_path, [disk])
        report = reclean_folders(staging, dry_run=True, config=config)

        # Staging not renamed, disk not renamed (dry-run)
        assert (staging / polluted_name).exists()
        assert (disk_cat / polluted_name).exists()
        # disk-propagate detail line is appended
        assert any("disk-propagate" in d for d in report.details)

    def test_rename_with_config_propagates(self, tmp_path: Path) -> None:
        """Real rename with a config: propagation also renames on disks."""
        staging = tmp_path / "staging" / "001-MOVIES"
        staging.mkdir(parents=True)
        polluted_name = "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        (staging / polluted_name).mkdir()
        (staging / polluted_name / "f.mkv").write_text("x")

        disk = tmp_path / "disk"
        disk_cat = disk / "001-MOVIES"
        disk_cat.mkdir(parents=True)
        (disk_cat / polluted_name).mkdir()

        config = _make_config_with_disks(tmp_path, [disk])
        report = reclean_folders(staging, dry_run=False, config=config)

        assert report.success_count == 1
        # Source gone, target exists on both staging and disk
        assert not (staging / polluted_name).exists()
        assert not (disk_cat / polluted_name).exists()
        new_name = "Movie Title (2024)"
        assert (staging / new_name).is_dir()
        assert (disk_cat / new_name).is_dir()
        assert report.renames.get(new_name) == polluted_name
        assert any("disk-propagate" in d for d in report.details)

    def test_merge_failed_warning_recorded(self, tmp_path: Path) -> None:
        """When _merge_dirs reports failures, they appear as warnings."""
        category = tmp_path / "001-MOVIES"
        category.mkdir()
        polluted_name = "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted = category / polluted_name
        polluted.mkdir()
        (polluted / "video.mkv").write_text("x")
        clean_name = "Movie Title (2024)"
        (category / clean_name).mkdir()  # target exists -> merge path

        # Patch _merge_dirs to report 1 moved + 2 failed.
        with patch(
            "personalscraper.scraper.scraper._merge_dirs",
            return_value=(1, 2),
        ):
            report = reclean_folders(category, dry_run=False)

        assert report.success_count == 1
        assert any("2 item(s) failed during merge" in w for w in report.warnings)

    def test_oserror_during_rename_recorded(self, tmp_path: Path) -> None:
        """OSError raised by Path.rename is recorded as an error."""
        category = tmp_path / "001-MOVIES"
        category.mkdir()
        polluted_name = "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted = category / polluted_name
        polluted.mkdir()

        with patch.object(Path, "rename", side_effect=OSError("rename denied")):
            report = reclean_folders(category, dry_run=False)

        assert report.error_count == 1
        assert any(polluted_name in w for w in report.warnings)

    def test_unexpected_exception_recorded(self, tmp_path: Path) -> None:
        """Non-OSError exceptions are captured under 'unexpected error'."""
        category = tmp_path / "001-MOVIES"
        category.mkdir()
        polluted_name = "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted = category / polluted_name
        polluted.mkdir()

        with patch.object(Path, "rename", side_effect=RuntimeError("boom")):
            report = reclean_folders(category, dry_run=False)

        assert report.error_count == 1
        assert any("unexpected error" in w for w in report.warnings)
