"""Tests for personalscraper.library.validator — library validation."""

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


# Minimal valid NFO with genres for category check to pass
_VALID_MOVIE_NFO = (
    '<movie>'
    '<title>Test</title><year>2024</year>'
    '<uniqueid type="tmdb">1</uniqueid>'
    '<uniqueid type="imdb">tt0000001</uniqueid>'
    '<genre>Action</genre>'
    '<fileinfo><streamdetails>'
    '<video><codec>h264</codec><width>1920</width><height>1080</height></video>'
    '<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>'
    '</streamdetails></fileinfo>'
    '</movie>'
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

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config])

        assert result.total_items == 1
        assert result.valid_count == 1
        assert result.items[0].status == "valid"

    def test_missing_nfo_blocked(self, tmp_path: Path) -> None:
        """Movie without NFO should be blocked."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "NoNfo (2024)"
        movie.mkdir(parents=True)
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 200_000_000)

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config])

        assert result.blocked_count == 1
        assert "nfo_present" in result.items[0].errors

    def test_disk_filter(self, tmp_path: Path) -> None:
        """Disk filter should limit validation."""
        d1 = tmp_path / "d1" / "medias"
        d2 = tmp_path / "d2" / "medias"
        (d1 / "films" / "A (2024)").mkdir(parents=True)
        (d2 / "films" / "B (2024)").mkdir(parents=True)
        (d1 / "films" / "A (2024)" / "A.mkv").write_bytes(b"\x00" * 200_000_000)
        (d2 / "films" / "B (2024)" / "B.mkv").write_bytes(b"\x00" * 200_000_000)

        configs = [
            _make_config(d1, "Disk1", ["films"]),
            _make_config(d2, "Disk2", ["films"]),
        ]
        result = validate_library(configs, disk_filter="Disk1")

        assert result.total_items == 1
