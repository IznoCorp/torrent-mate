"""Tests for the disk scanner module."""

from pathlib import Path

from personalscraper.dispatch.disk_scanner import (
    DiskConfig,
    DiskStatus,
    choose_disk,
)

# ---------------------------------------------------------------------------
# choose_disk
# ---------------------------------------------------------------------------

class TestChooseDisk:
    """Tests for choose_disk selection logic."""

    def _disk(self, name: str, free: float, cats: list[str]) -> DiskStatus:
        """Helper to create a DiskStatus."""
        return DiskStatus(
            config=DiskConfig(name=name, path=Path(f"/Volumes/{name}"), categories=cats),
            free_space_gb=free,
            is_mounted=True,
        )

    def test_picks_most_free_space(self) -> None:
        """Should pick the disk with the most free space."""
        disks = [
            self._disk("Disk1", 100, ["films"]),
            self._disk("Disk3", 200, ["films"]),
        ]
        result = choose_disk(disks, "films", min_free_gb=10)
        assert result is not None
        assert result.config.name == "Disk3"

    def test_filters_by_category(self) -> None:
        """Should only consider disks with matching category."""
        disks = [
            self._disk("Disk1", 500, ["films"]),
            self._disk("Disk2", 1000, ["series", "series animes"]),
        ]
        result = choose_disk(disks, "films", min_free_gb=10)
        assert result is not None
        assert result.config.name == "Disk1"

    def test_filters_by_space_threshold(self) -> None:
        """Should reject disks below min_free_gb threshold."""
        disks = [
            self._disk("Disk1", 5, ["films"]),
        ]
        result = choose_disk(disks, "films", min_free_gb=10)
        assert result is None

    def test_item_size_threshold(self) -> None:
        """Should use max(min_free_gb, item_size * 1.5) as threshold."""
        disks = [
            self._disk("Disk1", 20, ["films"]),
        ]
        # item_size=15, threshold=22.5 → 20 GB not enough
        result = choose_disk(disks, "films", min_free_gb=10, item_size_gb=15)
        assert result is None

    def test_unmounted_excluded(self) -> None:
        """Should skip unmounted disks."""
        disks = [
            DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1"), ["films"]),
                free_space_gb=500,
                is_mounted=False,
            ),
        ]
        result = choose_disk(disks, "films", min_free_gb=10)
        assert result is None

    def test_no_eligible_disk(self) -> None:
        """Should return None when no disk qualifies."""
        result = choose_disk([], "films", min_free_gb=10)
        assert result is None

    def test_series_animes_only_disk2(self) -> None:
        """'series animes' should only be dispatchable to Disk2."""
        disks = [
            self._disk("Disk1", 500, ["films", "series"]),
            self._disk("Disk2", 200, ["series", "series animes"]),
        ]
        result = choose_disk(disks, "series animes", min_free_gb=10)
        assert result is not None
        assert result.config.name == "Disk2"


# ---------------------------------------------------------------------------
# allow_create_category fallback
# ---------------------------------------------------------------------------


class TestChooseDiskCreateCategory:
    """Tests for allow_create_category fallback logic."""

    @staticmethod
    def _disk(name: str, free_gb: float, cats: list[str]) -> DiskStatus:
        return DiskStatus(
            config=DiskConfig(name, Path(f"/Volumes/{name}/medias"), cats),
            free_space_gb=free_gb,
            is_mounted=True,
        )

    def test_default_false_same_behavior(self) -> None:
        """Default (False) has same behavior as before — no fallback."""
        disks = [self._disk("Disk1", 500, ["films"])]
        result = choose_disk(disks, "spectacles", min_free_gb=10)
        assert result is None

    def test_create_category_finds_disk_with_space(self) -> None:
        """With allow_create_category=True, falls back to any disk with space."""
        disks = [
            self._disk("Disk1", 100, ["films"]),
            self._disk("Disk2", 500, ["series"]),
        ]
        # "spectacles" not on any disk — fallback picks most free
        result = choose_disk(
            disks, "spectacles", min_free_gb=10, allow_create_category=True,
        )
        assert result is not None
        assert result.config.name == "Disk2"

    def test_create_category_prefers_existing(self) -> None:
        """Category exists on a disk → uses that disk (pass 1), not fallback."""
        disks = [
            self._disk("Disk1", 200, ["films", "spectacles"]),
            self._disk("Disk2", 500, ["series"]),
        ]
        result = choose_disk(
            disks, "spectacles", min_free_gb=10, allow_create_category=True,
        )
        assert result is not None
        assert result.config.name == "Disk1"

    def test_create_category_full_disk_fallback(self) -> None:
        """Category exists but disk is full → fall back to another disk."""
        disks = [
            self._disk("Disk1", 5, ["spectacles"]),  # has category but full
            self._disk("Disk2", 500, ["series"]),
        ]
        result = choose_disk(
            disks, "spectacles", min_free_gb=10, allow_create_category=True,
        )
        assert result is not None
        assert result.config.name == "Disk2"

    def test_create_category_all_full_returns_none(self) -> None:
        """All disks full → returns None even with allow_create_category."""
        disks = [
            self._disk("Disk1", 5, ["films"]),
            self._disk("Disk2", 3, ["series"]),
        ]
        result = choose_disk(
            disks, "spectacles", min_free_gb=10, allow_create_category=True,
        )
        assert result is None
