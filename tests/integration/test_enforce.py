"""Integration tests for the enforce pipeline step.

Catalogue #9 — enforce gate invariants.

Note: test_enforce_creates_missing_season_dir is marked xfail/skip because
the production API (structure_validator._validate_tvshow) does not implement
the behavior of moving orphan episode files into Saison NN/ subdirectories.
The function only removes empty non-season subdirs and orphan season posters.
A production seam is required before this test can be activated.
"""

from pathlib import Path

import pytest

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.sorter.file_type import FileType


@pytest.mark.skip(
    reason=(
        "API gap: structure_validator._validate_tvshow does not create missing "
        "season directories or move orphan episode files. The plan assumes "
        "run_enforce() would move ShowName.S01E01.mkv into Saison 01/ but no "
        "such logic exists in enforce/structure_validator.py. "
        "A production seam is required before this test can be activated."
    )
)
def test_enforce_creates_missing_season_dir(staging_tree: Path, integration_config: Config) -> None:
    """Enforce should move orphan episode files into Saison 01/ subdir.

    Creates a TV show folder with S01 episode files at root level (no
    Saison 01/ subdirectory) and asserts enforce reorganises them.

    This test is skipped because the production API does not implement this
    behavior — see module docstring for details.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        integration_config: Fully composed integration Config fixture.
    """
    # Build ShowName/ directly under 002-TVSHOWS/ with orphan episode files.
    tvshows_dir = staging_tree / folder_name(find_by_file_type(integration_config, FileType.TVSHOW))
    show_dir = tvshows_dir / "ShowName"
    show_dir.mkdir(parents=True, exist_ok=True)
    ep1 = show_dir / "ShowName.S01E01.mkv"
    ep2 = show_dir / "ShowName.S01E02.mkv"
    ep1.write_bytes(b"\x00")
    ep2.write_bytes(b"\x00")

    # run_enforce would be called here — but the behavior is not implemented.
    # Season dir that would be expected:
    season_dir = show_dir / "Saison 01"
    assert season_dir.exists(), "Saison 01/ should be created by enforce"
    assert (season_dir / ep1.name).exists(), f"{ep1.name} should be moved into Saison 01/"
    assert (season_dir / ep2.name).exists(), f"{ep2.name} should be moved into Saison 01/"
