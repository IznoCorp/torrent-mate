"""Tests for personalscraper.conf.loader.collect_warnings."""

from personalscraper.conf import ids as CID
from personalscraper.conf.loader import collect_warnings
from personalscraper.conf.models import (
    CategoryConfig,
    Config,
    DiskConfig,
    PathConfig,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_config(tmp_path, *, disk_path_exists: bool = True) -> Config:
    """Build a base config with all categories explicitly set.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        disk_path_exists: If True, disk_a path is tmp_path/disk_a (exists after mkdir).
            If False, path points to a nonexistent subdirectory.

    Returns:
        A fully configured Config instance.
    """
    disk_path = tmp_path / "disk_a"
    if disk_path_exists:
        disk_path.mkdir(parents=True, exist_ok=True)

    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "complete",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[
            DiskConfig(
                id="disk_a",
                path=disk_path,
                categories=list(CID.BUILTIN_CATEGORY_IDS),
            )
        ],
        categories={cid: CategoryConfig(folder_name=f"cat_{cid}") for cid in CID.BUILTIN_CATEGORY_IDS},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


# ---------------------------------------------------------------------------
# Warning 1 — dead custom_category
# ---------------------------------------------------------------------------


class TestDeadCustomCategoryWarning:
    """Tests for dead custom_category warning."""

    def test_dead_custom_category_warns(self, tmp_path):
        """Custom category not accepted by any disk must produce a warning."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
            custom_categories=["my_unused_cat"],
            categories={"my_unused_cat": CategoryConfig(folder_name="unused")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        warnings = collect_warnings(cfg)
        assert any("dead custom_category" in w and "my_unused_cat" in w for w in warnings)

    def test_accepted_custom_category_no_warning(self, tmp_path):
        """Custom category accepted by a disk must not produce a dead-category warning."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES, "my_custom"])],
            custom_categories=["my_custom"],
            categories={"my_custom": CategoryConfig(folder_name="Custom Stuff")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        warnings = collect_warnings(cfg)
        assert not any("dead custom_category" in w for w in warnings)


# ---------------------------------------------------------------------------
# Warning 2 — default label used
# ---------------------------------------------------------------------------


class TestDefaultLabelWarning:
    """Tests for default label warning."""

    def test_used_id_without_category_config_warns(self, tmp_path):
        """Category ID used by a disk but missing from categories dict must warn."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
            # No categories dict — MOVIES has no explicit config
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        warnings = collect_warnings(cfg)
        assert any("using default label" in w and CID.MOVIES in w for w in warnings)

    def test_fully_configured_category_no_warning(self, tmp_path):
        """Category ID with explicit config must not produce a default-label warning."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
            categories={CID.MOVIES: CategoryConfig(folder_name="Films")},
            # Also provide config for defaults used by genre_mapping and anime_rule
            # to suppress their warnings — add the remaining ones that get pulled in
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        # MOVIES is configured; only check that MOVIES warning is absent
        warnings = collect_warnings(cfg)
        assert not any("using default label" in w and f"'{CID.MOVIES}'" in w for w in warnings)


# ---------------------------------------------------------------------------
# Warning 3 — disk unmounted
# ---------------------------------------------------------------------------


class TestDiskUnmountedWarning:
    """Tests for disk unmounted/not-present warning."""

    def test_nonexistent_disk_path_warns(self, tmp_path):
        """Disk with path that does not exist must produce an unmounted warning."""
        cfg = _base_config(tmp_path, disk_path_exists=False)
        warnings = collect_warnings(cfg)
        assert any("not mounted/present" in w and "disk_a" in w for w in warnings)

    def test_existing_disk_path_no_warning(self, tmp_path):
        """Disk with existing path must not produce an unmounted warning."""
        cfg = _base_config(tmp_path, disk_path_exists=True)
        warnings = collect_warnings(cfg)
        assert not any("not mounted/present" in w for w in warnings)

    def test_load_config_emits_warnings_via_logger(self, tmp_path, caplog):
        """load_config must emit warnings via logger for each warning found."""
        import logging

        cfg_path = tmp_path / "config.json5"
        # Write config with unmounted disk path
        disk_path = tmp_path / "nonexistent_disk"
        cfg_path.write_text(
            f"""{{
                paths: {{
                    torrent_complete_dir: "{tmp_path / "complete"}",
                    staging_dir: "{tmp_path / "staging"}",
                    data_dir: "{tmp_path / ".data"}",
                }},
                disks: [{{
                    id: "disk_a",
                    path: "{disk_path}",
                    categories: ["movies"],
                }}],
                categories: {{
                    movies: {{ folder_name: "Films" }},
                    tv_shows: {{ folder_name: "TV Shows" }},
                    anime: {{ folder_name: "Anime" }},
                    movies_animation: {{ folder_name: "Movies Animation" }},
                    movies_documentary: {{ folder_name: "Movies Documentary" }},
                    tv_shows_animation: {{ folder_name: "TV Shows Animation" }},
                    tv_shows_documentary: {{ folder_name: "TV Shows Documentary" }},
                    audiobooks: {{ folder_name: "Audiobooks" }},
                    standup: {{ folder_name: "Standup" }},
                    theater: {{ folder_name: "Theater" }},
                    tv_programs: {{ folder_name: "TV Programs" }},
                }},
                staging_dirs: [
                    {{ id: 1, name: "movies", file_type: "movie" }},
                    {{ id: 2, name: "tvshows", file_type: "tvshow" }},
                    {{ id: 3, name: "ebooks", file_type: "ebook" }},
                    {{ id: 4, name: "audio", file_type: "audio" }},
                    {{ id: 5, name: "apps", file_type: "app" }},
                    {{ id: 6, name: "android", file_type: "app" }},
                    {{ id: 97, name: "temp", file_type: null, role: "ingest" }},
                    {{ id: 98, name: "autres", file_type: "other" }},
                ],
            }}""",
            encoding="utf-8",
        )
        from personalscraper.conf.loader import load_config

        with caplog.at_level(logging.WARNING, logger="personalscraper.conf.loader"):
            load_config(cfg_path)

        assert any("not mounted/present" in r.message for r in caplog.records)
