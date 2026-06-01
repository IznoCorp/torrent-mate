"""Tests for personalscraper.verify.library_checks — library validation."""

from pathlib import Path

import pytest

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.verify.library_checks import ValidationItem, validate_library
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


# Minimal valid NFO with genres for category check to pass
_VALID_MOVIE_NFO = (
    "<movie>"
    "<title>Test</title><year>2024</year>"
    '<uniqueid type="tmdb">1</uniqueid>'
    '<uniqueid type="imdb">tt0000001</uniqueid>'
    "<genre>Action</genre>"
    "<fileinfo><streamdetails>"
    "<video><codec>h264</codec><width>1920</width><height>1080</height></video>"
    "<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>"
    "</streamdetails></fileinfo>"
    "</movie>"
)


class TestValidateLibrary:
    """Tests for validate_library function."""

    def test_valid_movie(self, tmp_path: Path) -> None:
        """Complete movie with full NFO should be marked valid."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        # 200 MB to pass not_sample check
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(_VALID_MOVIE_NFO)
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config)

        assert result.total_items == 1
        assert result.valid_count == 1
        assert result.items[0].status == "valid"

    def test_missing_nfo_has_issues(self, tmp_path: Path) -> None:
        """Movie without NFO should have issues."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "NoNfo (2024)"
        movie.mkdir(parents=True)
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 200_000_000)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = validate_library(config)

        assert result.issues_count == 1
        assert "nfo_present" in result.items[0].errors

    def test_disk_filter(self, tmp_path: Path) -> None:
        """Disk filter should limit validation."""
        d1 = tmp_path / "d1" / "medias"
        d2 = tmp_path / "d2" / "medias"
        (d1 / "films" / "A (2024)").mkdir(parents=True)
        (d2 / "films" / "B (2024)").mkdir(parents=True)
        (d1 / "films" / "A (2024)" / "A.mkv").write_bytes(b"\x00" * 200_000_000)
        (d2 / "films" / "B (2024)" / "B.mkv").write_bytes(b"\x00" * 200_000_000)

        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[
                DiskConfig(id="disk1", path=d1, categories=["movies"]),
                DiskConfig(id="disk2", path=d2, categories=["movies"]),
            ],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        result = validate_library(config, disk_filter="disk1")

        assert result.total_items == 1


class TestValidateFromIndexEdgeCases:
    """Branch coverage for validate_from_index."""

    def _conn(self):  # noqa: ANN202
        """Build an in-memory DB with the migration chain applied."""
        import sqlite3

        from personalscraper.indexer.db import apply_migrations

        migrations = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"
        c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        c.execute("PRAGMA foreign_keys=ON")
        apply_migrations(c, migrations)
        return c

    def test_artwork_json_invalid_treated_as_empty(self) -> None:
        """Malformed artwork_json triggers TypeError/ValueError branch and is empty.

        The DB enforces json_valid via virtual columns, so we feed the broken
        payload through a mocked connection that returns hand-built rows.
        """
        from unittest.mock import MagicMock

        from personalscraper.verify.library_checks import validate_from_index

        # Build one row with an obviously malformed artwork_json blob.
        row = {
            "id": 1,
            "kind": "movie",
            "title": "Foo",
            "year": 2024,
            "category_id": "movies",
            "nfo_status": "valid",
            "artwork_json": "{not-json}",
            "disk_label": "Disk1",
            "dispatch_path": "/Volumes/Disk1/films/Foo (2024)",
        }

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [row]
        conn.execute.return_value = cursor

        result = validate_from_index(conn)

        assert result.total_items == 1
        # artwork={} after decode error → poster missing → poster_present error
        assert "poster_present" in result.items[0].errors

    def test_artwork_json_empty_string_skips_block(self) -> None:
        """artwork_raw being empty/None skips the parse branch entirely."""
        from unittest.mock import MagicMock

        from personalscraper.verify.library_checks import validate_from_index

        row = {
            "id": 1,
            "kind": "movie",
            "title": "Foo",
            "year": 2024,
            "category_id": "movies",
            "nfo_status": "valid",
            "artwork_json": None,
            "disk_label": "Disk1",
            "dispatch_path": "/Volumes/Disk1/films/Foo (2024)",
        }
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [row]
        conn.execute.return_value = cursor

        result = validate_from_index(conn)
        assert result.total_items == 1
        # No artwork errors when the column is NULL
        assert "poster_present" not in result.items[0].errors


class TestValidationItem:
    """Tests for ValidationItem model."""

    def test_valid_item(self) -> None:
        """Item with all checks passed."""
        item = ValidationItem(
            path="/tmp/Movie (2024)",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="Movie",
            year=2024,
            status="valid",
            errors=[],
            warnings=[],
            fixes_applied=[],
        )
        assert item.status == "valid"

    def test_item_with_issues(self) -> None:
        """Item with errors should have 'issues' status."""
        item = ValidationItem(
            path="/tmp/Movie",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="Movie",
            year=None,
            status="issues",
            errors=["nfo_missing", "bad_dir_naming"],
            warnings=["no_landscape"],
            fixes_applied=[],
        )
        assert item.status == "issues"
        assert len(item.errors) == 2


class TestValidationItemInvariant:
    """Tests for ValidationItem.__post_init__ enforcement."""

    def test_valid_status_accepted(self) -> None:
        """Valid status values should be accepted."""
        for status in ("valid", "fixed", "issues"):
            item = ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status=status,
                errors=["err"] if status == "issues" else [],
                fixes_applied=["fix"] if status == "fixed" else [],
            )
            assert item.status == status

    def test_invalid_status_raises(self) -> None:
        """Unknown status should raise ValueError."""
        with pytest.raises(ValueError, match="status"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="blocked",
            )

    def test_fixed_without_fixes_raises(self) -> None:
        """status='fixed' with empty fixes_applied should raise."""
        with pytest.raises(ValueError, match="fixes_applied"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="fixed",
                fixes_applied=[],
            )

    def test_valid_with_errors_raises(self) -> None:
        """status='valid' with errors should raise."""
        with pytest.raises(ValueError, match="valid"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="valid",
                errors=["nfo_present"],
            )

    def test_issues_without_errors_or_warnings_raises(self) -> None:
        """status='issues' with no errors and no warnings should raise."""
        with pytest.raises(ValueError, match="issues"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="issues",
                errors=[],
                warnings=[],
            )

    def test_issues_with_only_warnings_accepted(self) -> None:
        """status='issues' with only warnings should be accepted."""
        item = ValidationItem(
            path="/tmp/X",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="X",
            year=2024,
            status="issues",
            errors=[],
            warnings=["no_landscape"],
        )
        assert item.status == "issues"
