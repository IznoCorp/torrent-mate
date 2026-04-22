"""Tests for the disk scanner module.

V15 P6.2: DiskConfig is now a Pydantic model from conf.models (field ``id``
instead of ``name``). DISK_CATEGORIES removed. Tests updated accordingly.
"""

from pathlib import Path

from personalscraper.conf.models import DiskConfig
from personalscraper.dispatch.disk_scanner import (
    DiskStatus,
    choose_disk,
    get_disk_configs,
    get_disk_status,
)

# ---------------------------------------------------------------------------
# get_disk_configs
# ---------------------------------------------------------------------------


class TestGetDiskConfigs:
    """Tests for get_disk_configs(config) — now returns config.disks."""

    def test_returns_config_disks(self, test_config) -> None:
        """Should return the same DiskConfig objects as config.disks."""
        result = get_disk_configs(test_config)
        assert result == list(test_config.disks)

    def test_count_matches_disks(self, test_config) -> None:
        """Number of returned configs matches number of disks in config."""
        result = get_disk_configs(test_config)
        assert len(result) == len(test_config.disks)

    def test_returns_pydantic_disk_configs(self, test_config) -> None:
        """Returned objects are Pydantic DiskConfig instances."""
        result = get_disk_configs(test_config)
        for dc in result:
            assert isinstance(dc, DiskConfig)
            assert hasattr(dc, "id")
            assert hasattr(dc, "path")
            assert hasattr(dc, "categories")


# ---------------------------------------------------------------------------
# get_disk_status
# ---------------------------------------------------------------------------


class TestGetDiskStatus:
    """Tests for get_disk_status — unchanged, uses Pydantic DiskConfig."""

    def test_unmounted_disk_returns_false(self, tmp_path: Path) -> None:
        """Non-existent path → is_mounted=False, free_space_gb=0."""
        dc = DiskConfig(id="disk_a", path=tmp_path / "nonexistent", categories=["movies"])
        status = get_disk_status(dc)
        assert status.is_mounted is False
        assert status.free_space_gb == 0.0

    def test_mounted_disk_returns_true(self, tmp_path: Path) -> None:
        """Existing path → is_mounted=True, free_space_gb > 0."""
        dc = DiskConfig(id="disk_a", path=tmp_path, categories=["movies"])
        status = get_disk_status(dc)
        assert status.is_mounted is True
        assert status.free_space_gb > 0.0

    def test_returns_disk_status_instance(self, tmp_path: Path) -> None:
        """get_disk_status returns a DiskStatus dataclass."""
        dc = DiskConfig(id="disk_a", path=tmp_path, categories=["movies"])
        status = get_disk_status(dc)
        assert isinstance(status, DiskStatus)
        assert status.config is dc


# ---------------------------------------------------------------------------
# choose_disk (V14 compat shim — kept for dispatcher.py transition)
# ---------------------------------------------------------------------------


class TestChooseDisk:
    """Tests for choose_disk selection logic (V14 compat shim).

    Uses Pydantic DiskConfig (``id`` field) as returned by get_disk_configs.
    """

    def _disk(self, disk_id: str, free: float, cats: list[str]) -> DiskStatus:
        """Helper to create a DiskStatus with a Pydantic DiskConfig."""
        return DiskStatus(
            config=DiskConfig(id=disk_id, path=Path(f"/Volumes/{disk_id}"), categories=cats),
            free_space_gb=free,
            is_mounted=True,
        )

    def test_picks_most_free_space(self) -> None:
        """Should pick the disk with the most free space."""
        disks = [
            self._disk("disk_1", 100, ["movies"]),
            self._disk("disk_3", 200, ["movies"]),
        ]
        result = choose_disk(disks, "movies", min_free_gb=10)
        assert result is not None
        assert result.config.id == "disk_3"

    def test_filters_by_category(self) -> None:
        """Should only consider disks with matching category."""
        disks = [
            self._disk("disk_1", 500, ["movies"]),
            self._disk("disk_2", 1000, ["tv_shows", "anime"]),
        ]
        result = choose_disk(disks, "movies", min_free_gb=10)
        assert result is not None
        assert result.config.id == "disk_1"

    def test_filters_by_space_threshold(self) -> None:
        """Should reject disks below min_free_gb threshold."""
        disks = [
            self._disk("disk_1", 5, ["movies"]),
        ]
        result = choose_disk(disks, "movies", min_free_gb=10)
        assert result is None

    def test_item_size_threshold(self) -> None:
        """Should use max(min_free_gb, item_size * 1.5) as threshold."""
        disks = [
            self._disk("disk_1", 20, ["movies"]),
        ]
        # item_size=15, threshold=22.5 → 20 GB not enough
        result = choose_disk(disks, "movies", min_free_gb=10, item_size_gb=15)
        assert result is None

    def test_unmounted_excluded(self) -> None:
        """Should skip unmounted disks."""
        disks = [
            DiskStatus(
                config=DiskConfig(id="disk_1", path=Path("/Volumes/Disk1"), categories=["movies"]),
                free_space_gb=500,
                is_mounted=False,
            ),
        ]
        result = choose_disk(disks, "movies", min_free_gb=10)
        assert result is None

    def test_no_eligible_disk(self) -> None:
        """Should return None when no disk qualifies."""
        result = choose_disk([], "movies", min_free_gb=10)
        assert result is None

    def test_anime_only_specific_disk(self) -> None:
        """'anime' category should only be dispatchable to disk accepting it."""
        disks = [
            self._disk("disk_1", 500, ["movies", "tv_shows"]),
            self._disk("disk_2", 200, ["tv_shows", "anime"]),
        ]
        result = choose_disk(disks, "anime", min_free_gb=10)
        assert result is not None
        assert result.config.id == "disk_2"


# ---------------------------------------------------------------------------
# allow_create_category fallback
# ---------------------------------------------------------------------------


class TestChooseDiskCreateCategory:
    """Tests for allow_create_category fallback logic."""

    @staticmethod
    def _disk(disk_id: str, free_gb: float, cats: list[str]) -> DiskStatus:
        return DiskStatus(
            config=DiskConfig(id=disk_id, path=Path(f"/Volumes/{disk_id}/medias"), categories=cats),
            free_space_gb=free_gb,
            is_mounted=True,
        )

    def test_default_false_same_behavior(self) -> None:
        """Default (False) has same behavior as before — no fallback."""
        disks = [self._disk("disk_1", 500, ["movies"])]
        result = choose_disk(disks, "standup", min_free_gb=10)
        assert result is None

    def test_create_category_finds_disk_with_space(self) -> None:
        """With allow_create_category=True, falls back to any disk with space."""
        disks = [
            self._disk("disk_1", 100, ["movies"]),
            self._disk("disk_2", 500, ["tv_shows"]),
        ]
        # "standup" not on any disk — fallback picks most free
        result = choose_disk(
            disks,
            "standup",
            min_free_gb=10,
            allow_create_category=True,
        )
        assert result is not None
        assert result.config.id == "disk_2"

    def test_create_category_prefers_existing(self) -> None:
        """Category exists on a disk → uses that disk (pass 1), not fallback."""
        disks = [
            self._disk("disk_1", 200, ["movies", "standup"]),
            self._disk("disk_2", 500, ["tv_shows"]),
        ]
        result = choose_disk(
            disks,
            "standup",
            min_free_gb=10,
            allow_create_category=True,
        )
        assert result is not None
        assert result.config.id == "disk_1"

    def test_create_category_full_disk_fallback(self) -> None:
        """Category exists but disk is full → fall back to another disk."""
        disks = [
            self._disk("disk_1", 5, ["standup"]),  # has category but full
            self._disk("disk_2", 500, ["tv_shows"]),
        ]
        result = choose_disk(
            disks,
            "standup",
            min_free_gb=10,
            allow_create_category=True,
        )
        assert result is not None
        assert result.config.id == "disk_2"

    def test_create_category_all_full_returns_none(self) -> None:
        """All disks full → returns None even with allow_create_category."""
        disks = [
            self._disk("disk_1", 5, ["movies"]),
            self._disk("disk_2", 3, ["tv_shows"]),
        ]
        result = choose_disk(
            disks,
            "standup",
            min_free_gb=10,
            allow_create_category=True,
        )
        assert result is None
