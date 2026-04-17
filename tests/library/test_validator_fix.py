"""Tests for library-validate --fix functionality."""

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.library.validator import validate_library


def _make_config(path: Path, name: str, categories: list[str]):
    """Create a mock DiskConfig."""
    config = MagicMock()
    config.path = path
    config.name = name
    config.categories = categories
    return config


class TestFixEmptyDirs:
    """Tests for --fix removing empty subdirectories."""

    def test_fix_dry_run_preserves(self, tmp_path: Path) -> None:
        """Dry-run should report but not delete empty dirs."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(
            '<movie><title>Test</title><year>2024</year>'
            '<uniqueid type="tmdb">1</uniqueid>'
            '<uniqueid type="imdb">tt0000001</uniqueid>'
            '<genre>Action</genre>'
            '<fileinfo><streamdetails>'
            '<video><codec>h264</codec><width>1920</width><height>1080</height></video>'
            '<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>'
            '</streamdetails></fileinfo></movie>'
        )
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config], fix=True, apply=False)

        assert empty.exists()  # Not deleted in dry-run
        fixed_items = [i for i in result.items if i.fixes_applied]
        assert len(fixed_items) >= 1

    def test_fix_apply_deletes(self, tmp_path: Path) -> None:
        """Apply should delete empty subdirectories."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(
            '<movie><title>Test</title><year>2024</year>'
            '<uniqueid type="tmdb">1</uniqueid>'
            '<uniqueid type="imdb">tt0000001</uniqueid>'
            '<genre>Action</genre>'
            '<fileinfo><streamdetails>'
            '<video><codec>h264</codec><width>1920</width><height>1080</height></video>'
            '<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>'
            '</streamdetails></fileinfo></movie>'
        )
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config], fix=True, apply=True)

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

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config], fix=True, apply=True)

        assert result.issues_count >= 1
