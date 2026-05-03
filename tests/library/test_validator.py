"""Tests for personalscraper.library.validator — library validation."""

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
