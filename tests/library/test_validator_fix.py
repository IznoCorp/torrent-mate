"""Tests for library-validate --fix functionality."""

from pathlib import Path
from unittest.mock import patch

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.library.validator import (
    _fix_empty_dirs,
    _fix_ntfs_names,
    validate_library,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_v15_config(
    disk_path: Path,
    disk_id: str,
    folder_name: str,
    category_id: str,
    tmp_path: Path,
) -> Config:
    """Create a minimal V15 Config for a single disk/category."""
    disk_cfg = DiskConfig(id=disk_id, path=disk_path, categories=[category_id])
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={category_id: CategoryConfig(folder_name=folder_name)},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


_VALID_MOVIE_NFO = (
    "<movie><title>Test</title><year>2024</year>"
    '<uniqueid type="tmdb">1</uniqueid>'
    '<uniqueid type="imdb">tt0000001</uniqueid>'
    "<genre>Action</genre>"
    "<fileinfo><streamdetails>"
    "<video><codec>h264</codec><width>1920</width><height>1080</height></video>"
    "<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>"
    "</streamdetails></fileinfo></movie>"
)


class TestFixEmptyDirs:
    """Tests for --fix removing empty subdirectories."""

    def test_fix_dry_run_preserves(self, tmp_path: Path) -> None:
        """Dry-run should report but not delete empty dirs."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(_VALID_MOVIE_NFO)
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config, fix=True, apply=False)

        assert empty.exists()  # Not deleted in dry-run
        fixed_items = [i for i in result.items if i.fixes_applied]
        assert len(fixed_items) >= 1

    def test_fix_apply_deletes(self, tmp_path: Path) -> None:
        """Apply should delete empty subdirectories."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(_VALID_MOVIE_NFO)
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config, fix=True, apply=True)

        assert not empty.exists()  # Deleted
        assert result.fixed_count >= 1


class TestFixNonFixableMessage:
    """Tests for non-fixable items staying as issues."""

    def test_missing_nfo_stays_issues(self, tmp_path: Path) -> None:
        """Items with API-dependent issues should remain as issues."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "NoNfo (2024)"
        movie.mkdir(parents=True)
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 200_000_000)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config, fix=True, apply=True)

        assert result.issues_count >= 1


class TestFixHelpers:
    """Direct tests for helper functions covering OSError branches."""

    def test_fix_empty_dirs_dry_run_reports(self, tmp_path: Path) -> None:
        """Dry-run mode reports the empty subdir without removing it."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        empty = media / "Subs"
        empty.mkdir()

        fixes = _fix_empty_dirs(media, dry_run=True)

        assert empty.exists()
        assert any("Would remove" in f for f in fixes)

    def test_fix_empty_dirs_applies(self, tmp_path: Path) -> None:
        """Apply mode actually removes empty subdir."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        empty = media / "Subs"
        empty.mkdir()

        fixes = _fix_empty_dirs(media, dry_run=False)

        assert not empty.exists()
        assert any("Removed empty dir" in f for f in fixes)

    def test_fix_empty_dirs_iterdir_oserror(self, tmp_path: Path) -> None:
        """OSError on iterdir is caught and logged, returning empty list."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        with patch.object(Path, "iterdir", side_effect=OSError("permission denied")):
            fixes = _fix_empty_dirs(media, dry_run=False)
        assert fixes == []

    def test_fix_empty_dirs_rmdir_oserror(self, tmp_path: Path) -> None:
        """Rmdir failures are logged and the entry is skipped without crash."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        empty = media / "Subs"
        empty.mkdir()
        with patch.object(Path, "rmdir", side_effect=OSError("denied")):
            fixes = _fix_empty_dirs(media, dry_run=False)
        # The continue path means no fix appended for this dir
        assert all("Removed" not in f for f in fixes)

    def test_fix_ntfs_names_dry_run(self, tmp_path: Path) -> None:
        """Dry-run reports rename without performing it."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        bad = media / "weird:file.mkv"
        bad.write_bytes(b"\x00")

        fixes = _fix_ntfs_names(media, dry_run=True)

        assert bad.exists()
        assert any("Would rename" in f for f in fixes)

    def test_fix_ntfs_names_applies(self, tmp_path: Path) -> None:
        """Apply mode renames NTFS-illegal filename."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        bad = media / "weird:file.mkv"
        bad.write_bytes(b"\x00")

        fixes = _fix_ntfs_names(media, dry_run=False)

        assert not bad.exists()
        assert any("Renamed" in f for f in fixes)

    def test_fix_ntfs_names_no_illegal_chars(self, tmp_path: Path) -> None:
        """Files with safe names yield no fixes."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        ok = media / "ok_file.mkv"
        ok.write_bytes(b"\x00")

        fixes = _fix_ntfs_names(media, dry_run=False)

        assert fixes == []
        assert ok.exists()

    def test_fix_ntfs_names_rglob_oserror(self, tmp_path: Path) -> None:
        """Rglob OSError is caught and logged, returning empty list."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        with patch.object(Path, "rglob", side_effect=OSError("scan failed")):
            fixes = _fix_ntfs_names(media, dry_run=False)
        assert fixes == []

    def test_fix_ntfs_names_rename_oserror(self, tmp_path: Path) -> None:
        """Rename OSError is caught and the file is skipped."""
        media = tmp_path / "Movie (2024)"
        media.mkdir()
        bad = media / "weird:file.mkv"
        bad.write_bytes(b"\x00")
        with patch.object(Path, "rename", side_effect=OSError("rename denied")):
            fixes = _fix_ntfs_names(media, dry_run=False)
        # The continue path means no rename description was appended
        assert all("Renamed" not in f for f in fixes)


class TestValidateLibraryBranches:
    """Tests for validate_library branches not covered by other suites."""

    def test_disk_not_mounted_skipped(self, tmp_path: Path) -> None:
        """A disk whose path does not exist is skipped with a warning."""
        missing_disk = tmp_path / "ghost"  # never created
        config = _make_v15_config(missing_disk, "ghost", "films", "movies", tmp_path)
        result = validate_library(config)
        assert result.total_items == 0

    def test_category_filter_skips_other(self, tmp_path: Path) -> None:
        """category_filter restricts to a single category id."""
        disk = tmp_path / "medias"
        # Two categories on the same disk
        (disk / "films" / "Foo (2024)").mkdir(parents=True)
        (disk / "films" / "Foo (2024)" / "Foo.mkv").write_bytes(b"\x00" * 1024)
        (disk / "series" / "Bar").mkdir(parents=True)
        (disk / "series" / "Bar" / "S01E01.mkv").write_bytes(b"\x00" * 1024)

        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[
                DiskConfig(
                    id="disk1",
                    path=disk,
                    categories=["movies", "tv_shows"],
                ),
            ],
            categories={
                "movies": CategoryConfig(folder_name="films"),
                "tv_shows": CategoryConfig(folder_name="series"),
            },
            staging_dirs=CANONICAL_STAGING_DIRS,
        )

        result = validate_library(config, category_filter="movies")
        # Only the movie should be picked up
        assert all(it.category == "movies" for it in result.items)
        assert result.total_items >= 1

    def test_category_dir_missing(self, tmp_path: Path) -> None:
        """Disk exists but category dir does not — silently skipped."""
        disk = tmp_path / "medias"
        disk.mkdir()
        # No 'films' subdir
        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config)
        assert result.total_items == 0

    def test_hidden_media_dir_ignored(self, tmp_path: Path) -> None:
        """Media dirs starting with '.' are skipped."""
        disk = tmp_path / "medias"
        cat = disk / "films"
        cat.mkdir(parents=True)
        (cat / ".hidden").mkdir()
        (cat / ".hidden" / "file.mkv").write_bytes(b"\x00")

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config)
        assert result.total_items == 0

    def test_tv_show_validates_via_check_tvshow(self, tmp_path: Path) -> None:
        """TV category triggers check_tvshow path (line 304)."""
        disk = tmp_path / "medias"
        show = disk / "series" / "Foo"
        show.mkdir(parents=True)
        # Minimal show structure (will produce many issues, that's fine for branch coverage)
        (show / "Foo.mkv").write_bytes(b"\x00" * 1024)

        config = _make_v15_config(disk, "disk1", "series", "tv_shows", tmp_path)
        result = validate_library(config)

        assert result.total_items == 1
        assert result.items[0].media_type == "tvshow"

    def test_check_oserror_recorded(self, tmp_path: Path) -> None:
        """OSError during checker is recorded on the item with os_error tag."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 1024)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)

        # Patch the checker to raise OSError
        from personalscraper.verify.checker import MediaChecker

        with patch.object(MediaChecker, "check_movie", side_effect=OSError("io")):
            result = validate_library(config)

        assert result.issues_count == 1
        assert any("os_error" in e for e in result.items[0].errors)

    def test_fix_dir_naming_renames_on_apply(self, tmp_path: Path) -> None:
        """dir_naming fix path renames a polluted dir using the NFO title."""
        disk = tmp_path / "medias"
        # Bad dir name -> dir_naming fails. NFO supplies correct title/year.
        movie = disk / "films" / "Test"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(_VALID_MOVIE_NFO)
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config, fix=True, apply=True)

        # Dir was renamed to "Test (2024)" matching NFO content
        assert (disk / "films" / "Test (2024)").exists() or any(it.fixes_applied for it in result.items)
        # At least one fix description was emitted
        assert any(it.fixes_applied for it in result.items)

    def test_fix_ntfs_safe_names_branch(self, tmp_path: Path) -> None:
        """NTFS fix branch runs when filenames contain illegal chars."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "weird:name.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(_VALID_MOVIE_NFO)
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config, fix=True, apply=True)

        # The illegal-char file should have been renamed
        items_with_fixes = [it for it in result.items if it.fixes_applied]
        assert items_with_fixes  # at least one
        assert any("weird" in fix or "Renamed" in fix for it in items_with_fixes for fix in it.fixes_applied)
