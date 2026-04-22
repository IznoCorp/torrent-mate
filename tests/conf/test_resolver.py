"""Unit tests for personalscraper.conf.resolver.

Tests cover:
- folder_for: explicit category, absent category (default_label fallback),
  custom_category, many-to-one folder names.
- pick_disk_for: no candidates, single eligible, single ineligible,
  multiple candidates (returns max free), threshold boundary, unmounted disk
  (0.0), V14 threshold formula specifically.
"""

from pathlib import Path

from personalscraper.conf import ids as CID
from personalscraper.conf.models import (
    CategoryConfig,
    Config,
    DiskConfig,
    GenreMapping,
    PathConfig,
)
from personalscraper.conf.resolver import folder_for, pick_disk_for
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# ---------------------------------------------------------------------------
# Helpers / minimal config factory
# ---------------------------------------------------------------------------


def _make_config(
    tmp_path: Path,
    *,
    disks: list[DiskConfig],
    categories: dict[str, CategoryConfig] | None = None,
    custom_categories: list[str] | None = None,
    genre_mapping: GenreMapping | None = None,
) -> Config:
    """Build a minimal Config for resolver tests."""
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "tc",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=disks,
        categories=categories or {},
        custom_categories=custom_categories or [],
        genre_mapping=genre_mapping
        or GenreMapping(
            default_movies_category=CID.MOVIES,
            default_tv_category=CID.TV_SHOWS,
        ),
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


# ---------------------------------------------------------------------------
# folder_for tests
# ---------------------------------------------------------------------------


class TestFolderFor:
    """Tests for resolver.folder_for."""

    def test_explicit_category_config(self, tmp_path: Path) -> None:
        """Returns disk.path / folder_name when category has explicit config."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(
            tmp_path,
            disks=[disk],
            categories={CID.MOVIES: CategoryConfig(folder_name="Films")},
        )

        result = folder_for(config, disk, CID.MOVIES)

        assert result == tmp_path / "drive_a" / "Films"

    def test_absent_category_uses_default_label_fallback(self, tmp_path: Path) -> None:
        """Falls back to default_label when no explicit CategoryConfig exists.

        default_label("tv_shows") == "tv shows" (underscores → spaces).
        """
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.TV_SHOWS],
        )
        # No entry for tv_shows in categories dict → uses default_label
        config = _make_config(tmp_path, disks=[disk])

        result = folder_for(config, disk, CID.TV_SHOWS)

        assert result == tmp_path / "drive_a" / "tv shows"

    def test_custom_category(self, tmp_path: Path) -> None:
        """Works for user-defined custom category IDs."""
        disk = DiskConfig(
            id="drive_x",
            path=tmp_path / "drive_x",
            categories=["concerts"],
        )
        config = _make_config(
            tmp_path,
            disks=[disk],
            categories={"concerts": CategoryConfig(folder_name="Concerts")},
            custom_categories=["concerts"],
        )

        result = folder_for(config, disk, "concerts")

        assert result == tmp_path / "drive_x" / "Concerts"

    def test_many_to_one_folder_name(self, tmp_path: Path) -> None:
        """Two category IDs mapping to the same folder_name produce same path."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.TV_SHOWS_ANIMATION, CID.ANIME],
        )
        # Both IDs map to the same physical folder "Animations"
        config = _make_config(
            tmp_path,
            disks=[disk],
            categories={
                CID.TV_SHOWS_ANIMATION: CategoryConfig(folder_name="Animations"),
                CID.ANIME: CategoryConfig(folder_name="Animations"),
            },
        )

        path_animation = folder_for(config, disk, CID.TV_SHOWS_ANIMATION)
        path_anime = folder_for(config, disk, CID.ANIME)

        assert path_animation == path_anime
        assert path_animation == tmp_path / "drive_a" / "Animations"

    def test_returns_path_not_directory(self, tmp_path: Path) -> None:
        """folder_for returns a Path — does not create the directory."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(
            tmp_path,
            disks=[disk],
            categories={CID.MOVIES: CategoryConfig(folder_name="movies")},
        )

        result = folder_for(config, disk, CID.MOVIES)

        # Path is computed but the directory is NOT created automatically
        assert not result.exists()
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# pick_disk_for tests
# ---------------------------------------------------------------------------


class TestPickDiskFor:
    """Tests for resolver.pick_disk_for."""

    def _disks(self, tmp_path: Path) -> tuple[DiskConfig, DiskConfig, DiskConfig]:
        """Return three disks all accepting CID.MOVIES for convenience."""
        da = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES, CID.TV_SHOWS],
        )
        db = DiskConfig(
            id="drive_b",
            path=tmp_path / "drive_b",
            categories=[CID.MOVIES],
        )
        dc = DiskConfig(
            id="drive_c",
            path=tmp_path / "drive_c",
            categories=[CID.TV_SHOWS],
        )
        return da, db, dc

    def test_no_candidates_accepting_category(self, tmp_path: Path) -> None:
        """Returns None when no disk accepts the requested category."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.TV_SHOWS],  # does NOT accept MOVIES
        )
        config = _make_config(tmp_path, disks=[disk])
        free = {"drive_a": 500.0}

        result = pick_disk_for(config, CID.MOVIES, free, 100.0, 4.0)

        assert result is None

    def test_single_candidate_with_enough_space(self, tmp_path: Path) -> None:
        """Returns the single eligible disk when it has sufficient free space."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        free = {"drive_a": 200.0}

        # threshold = max(100.0, 4.0 * 1.5) = max(100.0, 6.0) = 100.0
        result = pick_disk_for(config, CID.MOVIES, free, 100.0, 4.0)

        assert result is not None
        assert result.id == "drive_a"

    def test_single_candidate_insufficient_space(self, tmp_path: Path) -> None:
        """Returns None when the only candidate lacks sufficient free space."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        free = {"drive_a": 50.0}

        # threshold = max(100.0, 4.0 * 1.5) = 100.0 — drive_a has 50.0 < 100.0
        result = pick_disk_for(config, CID.MOVIES, free, 100.0, 4.0)

        assert result is None

    def test_multiple_candidates_returns_max_free(self, tmp_path: Path) -> None:
        """Returns the disk with the most free space among eligible candidates."""
        da, db, _dc = self._disks(tmp_path)
        config = _make_config(tmp_path, disks=[da, db, _dc])
        free = {"drive_a": 150.0, "drive_b": 300.0, "drive_c": 500.0}

        # Both drive_a and drive_b accept MOVIES; drive_b has more free space
        result = pick_disk_for(config, CID.MOVIES, free, 100.0, 4.0)

        assert result is not None
        assert result.id == "drive_b"

    def test_threshold_boundary_exact_equals_eligible(self, tmp_path: Path) -> None:
        """A disk with free space exactly equal to threshold is eligible."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        # threshold = max(100.0, 4.0 * 1.5) = 100.0
        # Exact equality → eligible
        free = {"drive_a": 100.0}

        result = pick_disk_for(config, CID.MOVIES, free, 100.0, 4.0)

        assert result is not None
        assert result.id == "drive_a"

    def test_threshold_boundary_just_below_not_eligible(self, tmp_path: Path) -> None:
        """A disk with free space just below threshold is NOT eligible."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        free = {"drive_a": 99.99}  # threshold = 100.0 — just below

        result = pick_disk_for(config, CID.MOVIES, free, 100.0, 4.0)

        assert result is None

    def test_unmounted_disk_treated_as_zero(self, tmp_path: Path) -> None:
        """A disk with free_space=0.0 (unmounted) is never eligible."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        # 0.0 simulates unmounted disk — caller sets this by convention
        free = {"drive_a": 0.0}

        result = pick_disk_for(config, CID.MOVIES, free, 1.0, 0.1)

        assert result is None

    def test_missing_key_defaults_to_zero(self, tmp_path: Path) -> None:
        """A disk absent from free_space_by_id defaults to 0.0 (unreachable)."""
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        # drive_a key is absent — should default to 0.0
        free: dict[str, float] = {}

        result = pick_disk_for(config, CID.MOVIES, free, 1.0, 0.1)

        assert result is None

    def test_v14_threshold_formula_item_size_dominates(self, tmp_path: Path) -> None:
        """Verifies V14 formula: threshold = max(min_free_gb, item_size_gb * 1.5).

        When item_size_gb * 1.5 > min_free_gb, the item size drives the threshold.
        """
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        # item_size_gb = 8.0 → item_size_gb * 1.5 = 12.0 > min_free_gb = 5.0
        # threshold = 12.0
        free_just_below = {"drive_a": 11.99}
        free_at_threshold = {"drive_a": 12.0}

        assert pick_disk_for(config, CID.MOVIES, free_just_below, 5.0, 8.0) is None
        result = pick_disk_for(config, CID.MOVIES, free_at_threshold, 5.0, 8.0)
        assert result is not None
        assert result.id == "drive_a"

    def test_v14_threshold_formula_min_free_dominates(self, tmp_path: Path) -> None:
        """Verifies V14 formula: threshold = max(min_free_gb, item_size_gb * 1.5).

        When min_free_gb > item_size_gb * 1.5, the min_free_gb drives the threshold.
        """
        disk = DiskConfig(
            id="drive_a",
            path=tmp_path / "drive_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])
        # min_free_gb = 100.0 > item_size_gb * 1.5 = 0.3
        # threshold = 100.0
        free_just_below = {"drive_a": 99.99}
        free_at_threshold = {"drive_a": 100.0}

        assert pick_disk_for(config, CID.MOVIES, free_just_below, 100.0, 0.2) is None
        result = pick_disk_for(config, CID.MOVIES, free_at_threshold, 100.0, 0.2)
        assert result is not None
        assert result.id == "drive_a"

    def test_only_accepting_disks_are_considered(self, tmp_path: Path) -> None:
        """Disks that do not accept the category are ignored even with lots of space."""
        da, _db, dc = self._disks(tmp_path)
        # drive_a accepts MOVIES (+ TV_SHOWS), drive_c accepts only TV_SHOWS
        config = _make_config(tmp_path, disks=[da, dc])
        # drive_c has 1000 GB free but doesn't accept MOVIES — should not win
        free = {"drive_a": 150.0, "drive_c": 1000.0}

        result = pick_disk_for(config, CID.MOVIES, free, 100.0, 4.0)

        assert result is not None
        assert result.id == "drive_a"
