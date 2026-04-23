"""Tests for ensure_staging_tree bootstrap function."""

from pathlib import Path
from unittest.mock import patch

from personalscraper.conf.models import Config
from personalscraper.conf.staging import ensure_staging_tree, folder_name

_STAGING_DIRS = [
    {"id": 1, "name": "movies", "file_type": "movie"},
    {"id": 2, "name": "tvshows", "file_type": "tvshow"},
    {"id": 3, "name": "ebooks", "file_type": "ebook"},
    {"id": 4, "name": "audio", "file_type": "audio"},
    {"id": 5, "name": "apps", "file_type": "app"},
    {"id": 6, "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres", "file_type": "other"},
]


def _make_config(staging_dir: Path) -> Config:
    """Build a minimal Config pointing at the given staging_dir.

    Args:
        staging_dir: The path to use as staging_dir.

    Returns:
        Validated Config with 8 staging entries.
    """
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(staging_dir.parent / "torrents"),
                "staging_dir": str(staging_dir),
                "data_dir": str(staging_dir.parent / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(staging_dir.parent / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": _STAGING_DIRS,
        }
    )


class TestEnsureStagingTree:
    """ensure_staging_tree -- creates missing dirs and returns created paths."""

    def test_full_absent_tree_creates_all_dirs(self, tmp_path: Path) -> None:
        """When staging_dir does not exist at all, root + all 8 subdirs are created."""
        staging = tmp_path / "staging"
        config = _make_config(staging)

        created = ensure_staging_tree(config)

        assert staging.is_dir(), "staging_dir root must be created"
        # root (1) + 8 subdirs = 9 paths
        assert len(created) == 9
        for entry in config.staging_dirs:
            assert (staging / folder_name(entry)).is_dir()

    def test_full_present_tree_is_noop(self, tmp_path: Path) -> None:
        """When all dirs exist, returns empty list (no-op)."""
        staging = tmp_path / "staging"
        config = _make_config(staging)
        staging.mkdir()
        for entry in config.staging_dirs:
            (staging / folder_name(entry)).mkdir()

        created = ensure_staging_tree(config)

        assert created == []

    def test_partial_tree_creates_only_missing(self, tmp_path: Path) -> None:
        """When some dirs exist, only missing ones are created."""
        staging = tmp_path / "staging"
        config = _make_config(staging)
        staging.mkdir()
        # Create only the first 3 subdirs
        for entry in config.staging_dirs[:3]:
            (staging / folder_name(entry)).mkdir()

        created = ensure_staging_tree(config)

        # Remaining 5 subdirs (root already exists, not counted)
        assert len(created) == 5
        for entry in config.staging_dirs:
            assert (staging / folder_name(entry)).is_dir()

    def test_idempotence(self, tmp_path: Path) -> None:
        """Second call on a complete tree is a no-op."""
        staging = tmp_path / "staging"
        config = _make_config(staging)

        ensure_staging_tree(config)
        created_second = ensure_staging_tree(config)

        assert created_second == []

    def test_warning_emitted_when_created(self, tmp_path: Path) -> None:
        """A structlog warning is emitted when directories are created."""
        staging = tmp_path / "staging"
        config = _make_config(staging)

        with patch("personalscraper.conf.staging._log") as mock_log:
            ensure_staging_tree(config)
            mock_log.warning.assert_called_once()

    def test_no_warning_when_nothing_created(self, tmp_path: Path) -> None:
        """No warning logged when the tree is already complete."""
        staging = tmp_path / "staging"
        config = _make_config(staging)
        staging.mkdir()
        for entry in config.staging_dirs:
            (staging / folder_name(entry)).mkdir()

        with patch("personalscraper.conf.staging._log") as mock_log:
            ensure_staging_tree(config)
            mock_log.warning.assert_not_called()
