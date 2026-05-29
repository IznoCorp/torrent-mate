"""AC-05 end-to-end: per-FS illegal-name relaxation through the dispatch path.

These tests drive the REAL ``dispatch_movie`` / ``dispatch_tvshow`` entry
points (not ``_transfer.has_ntfs_illegal_names`` directly) to prove the
illegal-name gate now runs AFTER the destination disk is chosen and is driven
by the RESOLVED capability's ``illegal_name_regex``:

- APFS destination (``illegal_name_regex is None``) → a ``:``-titled item is
  NOT skipped; the dispatch proceeds to the move/replace step.
- NTFS destination (``illegal_name_regex`` present) → the same item IS skipped
  with the NTFS-illegal reason and no transfer is attempted.

The actual rsync/move is mocked (``_move_new`` / ``replace`` / ``merge``) so the
assertions are about the SKIP DECISION, not real I/O. The APFS-vs-NTFS
difference is driven solely by ``Dispatcher._disk_capabilities`` — the same
disk, the same colon name, only the resolved capability changes — proving the
behaviour is no longer hardcoded to the NTFS regex.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch._movie import dispatch_movie
from personalscraper.dispatch._tv import dispatch_tvshow
from personalscraper.dispatch.disk_scanner import DiskStatus
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.indexer._fs_capability import APFS, NTFS_MACFUSE

pytestmark = pytest.mark.multifs


@pytest.fixture
def mock_settings() -> MagicMock:
    """Minimal Settings stub for the dispatcher constructor."""
    return MagicMock()


def _disk_status(disk_id: str, root: Path, categories: list[str]) -> DiskStatus:
    """Build a mounted DiskStatus with ample free space for the resolver."""
    return DiskStatus(
        config=DiskConfig(id=disk_id, path=root, categories=categories),
        free_space_gb=500.0,
        is_mounted=True,
    )


class TestMovieIllegalNameFsAware:
    """AC-05 for ``dispatch_movie`` (new-media branch)."""

    def test_colon_movie_not_skipped_on_apfs_dest(self, test_config, mock_settings: MagicMock, tmp_path: Path) -> None:
        """APFS dest (regex None) → colon name proceeds to the move (not skipped)."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        d = Dispatcher(test_config, mock_settings, idx, event_bus=EventBus())
        # Force the resolved capability for the chosen disk to APFS (regex None).
        d._disk_capabilities["drive_a"] = APFS

        movie_dir = tmp_path / "Movie S01E01: Pilot"
        movie_dir.mkdir()
        (movie_dir / "Movie S01E01: Pilot.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch("personalscraper.dispatch._movie.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
            patch("personalscraper.dispatch._movie.disk_id_for_path", return_value=None),
        ):
            mock_status.return_value = _disk_status("drive_a", tmp_path / "drive_a", ["movies"])
            result = dispatch_movie(d, movie_dir, "movies")

        # POSIX dest accepts the colon → not skipped; the move runs.
        assert result.action == "moved"
        mock_move.assert_called_once()

    def test_colon_movie_skipped_on_ntfs_dest(self, test_config, mock_settings: MagicMock, tmp_path: Path) -> None:
        """NTFS dest (regex present) → colon name is skipped, no move attempted."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        d = Dispatcher(test_config, mock_settings, idx, event_bus=EventBus())
        # Force the resolved capability for the chosen disk to NTFS (regex set).
        d._disk_capabilities["drive_a"] = NTFS_MACFUSE

        movie_dir = tmp_path / "Movie S01E01: Pilot"
        movie_dir.mkdir()
        (movie_dir / "Movie S01E01: Pilot.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch("personalscraper.dispatch._movie.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
        ):
            mock_status.return_value = _disk_status("drive_a", tmp_path / "drive_a", ["movies"])
            result = dispatch_movie(d, movie_dir, "movies")

        # NTFS dest rejects the colon → skipped with the illegal-name reason.
        assert result.action == "skipped"
        assert "NTFS" in (result.reason or "")
        mock_move.assert_not_called()


class TestTvIllegalNameFsAware:
    """AC-05 for ``dispatch_tvshow`` (new-media branch)."""

    def test_colon_show_not_skipped_on_apfs_dest(self, test_config, mock_settings: MagicMock, tmp_path: Path) -> None:
        """APFS dest (regex None) → colon name proceeds to the move (not skipped)."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        d = Dispatcher(test_config, mock_settings, idx, event_bus=EventBus())
        d._disk_capabilities["drive_a"] = APFS

        show_dir = tmp_path / "Show S01E01: Pilot"
        show_dir.mkdir()
        (show_dir / "Show S01E01: Pilot.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch("personalscraper.dispatch._tv.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
            patch("personalscraper.dispatch._tv.disk_id_for_path", return_value=None),
        ):
            mock_status.return_value = _disk_status("drive_a", tmp_path / "drive_a", ["tv_shows"])
            result = dispatch_tvshow(d, show_dir, "tv_shows")

        assert result.action == "moved"
        mock_move.assert_called_once()

    def test_colon_show_skipped_on_ntfs_dest(self, test_config, mock_settings: MagicMock, tmp_path: Path) -> None:
        """NTFS dest (regex present) → colon name is skipped, no move attempted."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        d = Dispatcher(test_config, mock_settings, idx, event_bus=EventBus())
        d._disk_capabilities["drive_a"] = NTFS_MACFUSE

        show_dir = tmp_path / "Show S01E01: Pilot"
        show_dir.mkdir()
        (show_dir / "Show S01E01: Pilot.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch("personalscraper.dispatch._tv.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
        ):
            mock_status.return_value = _disk_status("drive_a", tmp_path / "drive_a", ["tv_shows"])
            result = dispatch_tvshow(d, show_dir, "tv_shows")

        assert result.action == "skipped"
        assert "NTFS" in (result.reason or "")
        mock_move.assert_not_called()
