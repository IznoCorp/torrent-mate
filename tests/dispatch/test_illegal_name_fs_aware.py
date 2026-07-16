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
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
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
            patch("personalscraper.dispatch._item.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
            patch("personalscraper.dispatch._item.disk_id_for_path", return_value=None),
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
            patch("personalscraper.dispatch._item.get_disk_status") as mock_status,
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
            patch("personalscraper.dispatch._item.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
            patch("personalscraper.dispatch._item.disk_id_for_path", return_value=None),
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
            patch("personalscraper.dispatch._item.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
        ):
            mock_status.return_value = _disk_status("drive_a", tmp_path / "drive_a", ["tv_shows"])
            result = dispatch_tvshow(d, show_dir, "tv_shows")

        assert result.action == "skipped"
        assert "NTFS" in (result.reason or "")
        mock_move.assert_not_called()


class TestSkipReasonPrecedence:
    """AC-05 skip-reason precedence: disk-full beats illegal-name when BOTH hold.

    The phase-8 gate move relocated the illegal-name gate to run AFTER the
    destination disk is chosen — and therefore AFTER the disk-full check in the
    ``existing`` (replace / merge) branch.  When an item is BOTH disk-full AND
    illegally named on an NTFS dest, the disk-full check returns first, so the
    *disk-full* reason wins.  The action is ``skipped`` either way (no
    transfer-safety change), but pinning the precedence locks the user-facing
    reason so a future reorder cannot silently flip it.
    """

    def test_movie_replace_disk_full_beats_illegal_name(
        self, test_config, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        """Colon-named movie on a FULL NTFS dest → skipped with the DISK-FULL reason."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        # Materialise the existing dest so _resolve_existing_on_filesystem
        # validates it and the replace branch is taken.
        dest_dir = tmp_path / "drive_a" / "Films" / "Movie S01E01: Pilot"
        dest_dir.mkdir(parents=True)
        (dest_dir / "Movie.mkv").write_bytes(b"old")
        idx.add(
            IndexEntry(
                name="Movie S01E01: Pilot",
                disk="drive_a",
                category="movies",
                path=str(dest_dir),
                media_type="movie",
            )
        )

        d = Dispatcher(test_config, mock_settings, idx, event_bus=EventBus())
        # NTFS dest → the colon WOULD be illegal, but disk-full must win first.
        d._disk_capabilities["drive_a"] = NTFS_MACFUSE

        movie_dir = tmp_path / "Movie S01E01: Pilot"
        movie_dir.mkdir()
        (movie_dir / "Movie S01E01: Pilot.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch("personalscraper.dispatch._item.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
        ):
            mock_status.return_value = DiskStatus(
                config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["movies"]),
                free_space_gb=0.1,  # Way below threshold → disk-full.
                is_mounted=True,
            )
            result = dispatch_movie(d, movie_dir, "movies")

        assert result.action == "skipped"
        # Disk-full wins: the reason is the disk-full message, NOT the NTFS one.
        assert "full" in (result.reason or "").lower()
        assert "NTFS" not in (result.reason or "")
        mock_move.assert_not_called()

    def test_tvshow_merge_disk_full_beats_illegal_name(
        self, test_config, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        """Colon-named show on a FULL NTFS dest → skipped with the DISK-FULL reason."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        dest_dir = tmp_path / "drive_a" / "Series" / "Show S01E01: Pilot"
        dest_dir.mkdir(parents=True)
        (dest_dir / "S01E01.mkv").write_bytes(b"old")
        idx.add(
            IndexEntry(
                name="Show S01E01: Pilot",
                disk="drive_a",
                category="tv_shows",
                path=str(dest_dir),
                media_type="tvshow",
            )
        )

        d = Dispatcher(test_config, mock_settings, idx, event_bus=EventBus())
        d._disk_capabilities["drive_a"] = NTFS_MACFUSE

        show_dir = tmp_path / "Show S01E01: Pilot"
        show_dir.mkdir()
        (show_dir / "Show S01E01: Pilot.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch("personalscraper.dispatch._item.get_disk_status") as mock_status,
            patch.object(d, "_move_new", return_value=True) as mock_move,
        ):
            mock_status.return_value = DiskStatus(
                config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["tv_shows"]),
                free_space_gb=0.1,
                is_mounted=True,
            )
            result = dispatch_tvshow(d, show_dir, "tv_shows")

        assert result.action == "skipped"
        assert "full" in (result.reason or "").lower()
        assert "NTFS" not in (result.reason or "")
        mock_move.assert_not_called()
