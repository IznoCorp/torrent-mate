"""Integration tests for the enforce pipeline step.

Catalogue #9 — enforce gate invariants.
"""

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.enforce.structure_validator import validate_structure
from personalscraper.sorter.file_type import FileType


def test_enforce_creates_missing_season_dir(staging_tree: Path, integration_config: Config) -> None:
    """Enforce should move orphan episode files into Saison 01/ subdir.

    Creates a TV show folder with S01 episode files at root level (no
    Saison 01/ subdirectory) and asserts enforce reorganises them.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        integration_config: Fully composed integration Config fixture.
    """
    # Build ShowName/ directly under the tvshows staging dir with orphan episode files.
    tvshows_dir = staging_tree / folder_name(find_by_file_type(integration_config, FileType.TVSHOW))
    show_dir = tvshows_dir / "ShowName"
    show_dir.mkdir(parents=True, exist_ok=True)
    ep1 = show_dir / "ShowName.S01E01.mkv"
    ep2 = show_dir / "ShowName.S01E02.mkv"
    ep1.write_bytes(b"\x00")
    ep2.write_bytes(b"\x00")

    # Run structure validation — this triggers orphan-episode relocation.
    settings = MagicMock()
    validate_structure(settings, integration_config, dry_run=False)

    season_dir = show_dir / "Saison 01"
    assert season_dir.exists(), "Saison 01/ should be created by enforce"
    assert (season_dir / ep1.name).exists(), f"{ep1.name} should be moved into Saison 01/"
    assert (season_dir / ep2.name).exists(), f"{ep2.name} should be moved into Saison 01/"
