"""Tests for the dispatch orchestrator.

Tests dispatch logic with mocked rsync, disk statuses, and index.
Covers movie replace, TV show merge, new item placement, dry-run,
and insufficient space handling.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.verify.verifier import VerifyResult


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock Settings."""
    s = MagicMock()
    s.disk1_dir = "/Volumes/Disk1/medias"
    s.disk2_dir = "/Volumes/Disk2/medias"
    s.disk3_dir = "/Volumes/Disk3/medias"
    s.disk4_dir = "/Volumes/Disk4/medias"
    s.min_free_space_disk_gb = 100.0
    return s


# ---------------------------------------------------------------------------
# Dispatcher initialization
# ---------------------------------------------------------------------------

class TestDispatcherInit:
    """Tests for Dispatcher initialization."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_init_with_rsync(self, mock_which: MagicMock, mock_settings: MagicMock) -> None:
        """Should initialize when rsync is available."""
        idx = MediaIndex()
        d = Dispatcher(mock_settings, idx)
        assert d is not None

    @patch("shutil.which", return_value=None)
    def test_init_without_rsync(self, mock_which: MagicMock, mock_settings: MagicMock) -> None:
        """Should raise DispatchError when rsync is missing."""
        from personalscraper.dispatch.dispatcher import DispatchError
        idx = MediaIndex()
        with pytest.raises(DispatchError, match="rsync"):
            Dispatcher(mock_settings, idx)


# ---------------------------------------------------------------------------
# Movie dispatch
# ---------------------------------------------------------------------------

class TestDispatchMovie:
    """Tests for dispatch_movie."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_new_movie_dry_run(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Dry run should report action without moving."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "Matrix.mkv").write_bytes(b"\x00" * 1024)

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["films"]),
                free_space_gb=500,
                is_mounted=True,
            )

            result = d.dispatch_movie(movie_dir, "films")

        assert result.action == "moved"
        assert movie_dir.exists()  # Not moved in dry run

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_no_space_skips(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should skip when no disk has enough space."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["films"]),
                free_space_gb=0.5,  # Not enough
                is_mounted=True,
            )

            result = d.dispatch_movie(movie_dir, "films")

        assert result.action == "skipped"
        assert "space" in (result.reason or "").lower()


# ---------------------------------------------------------------------------
# TV show dispatch
# ---------------------------------------------------------------------------

class TestDispatchTvshow:
    """Tests for dispatch_tvshow."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_new_tvshow_dry_run(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Dry run for new show should report action."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["series"]),
                free_space_gb=500,
                is_mounted=True,
            )

            result = d.dispatch_tvshow(show_dir, "series")

        assert result.action == "moved"


# ---------------------------------------------------------------------------
# Process verified items
# ---------------------------------------------------------------------------

class TestProcess:
    """Tests for process() method."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_process_verified_items(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should dispatch each verified item."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()

        verified = [
            VerifyResult(
                media_path=movie_dir, media_type="movie",
                category="films", status="valid",
            ),
        ]

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["films"]),
                free_space_gb=500,
                is_mounted=True,
            )

            results = d.process(verified=verified)

        assert len(results) == 1
        assert results[0].action in ("moved", "replaced")

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_skip_no_category(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should skip items without a category."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        verified = [
            VerifyResult(
                media_path=tmp_path, media_type="movie",
                category=None, status="blocked",
            ),
        ]

        results = d.process(verified=verified)
        assert len(results) == 1
        assert results[0].action == "skipped"

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_process_requires_one_mode(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should raise ValueError with both or neither args."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        with pytest.raises(ValueError):
            d.process(verified=[], staging_dir=tmp_path)

        with pytest.raises(ValueError):
            d.process()


# ---------------------------------------------------------------------------
# Verify transfer
# ---------------------------------------------------------------------------

class TestVerifyTransfer:
    """Tests for _verify_transfer."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_matching_files(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should return True when all files match."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        content = b"\x00" * 1024
        (src / "file.mkv").write_bytes(content)
        (dst / "file.mkv").write_bytes(content)

        assert d._verify_transfer(src, dst) is True

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_missing_file_fails(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should return False when dest file is missing."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)

        assert d._verify_transfer(src, dst) is False
