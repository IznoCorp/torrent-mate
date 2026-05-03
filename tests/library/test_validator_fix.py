"""Tests for library-validate --fix functionality."""

from pathlib import Path

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.library.validator import validate_library
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
