"""E2E: the maintenance commands see a disk's existing media whatever its ``categories``.

A library of two disks, the second frozen to ``["audiobooks"]`` yet holding a
film and a series, run through each command's CLI (read-only / dry-run).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from personalscraper.trailers.cli import _normalize_path
from tests._frozen_disk import frozen_disk_config, seed_frozen_library
from tests._media_files import write_placeholder_media
from tests.commands._e2e_helpers import assert_no_python_traceback, make_synthetic_db, run_cli

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_LIVE = "personalscraper.trailers.cli._live_item_dirs"


def _config_with_db(tmp_path: Path):
    """The frozen-disk config with a migrated index and an existing data dir."""
    config = frozen_disk_config(tmp_path)
    (tmp_path / ".data").mkdir(exist_ok=True)
    db_path = make_synthetic_db(tmp_path)
    return config.model_copy(update={"indexer": config.indexer.model_copy(update={"db_path": db_path})})


def test_library_validate_reports_the_frozen_disks_media(tmp_path: Path) -> None:
    """``library-validate`` lists the frozen disk's film and series."""
    library = seed_frozen_library(tmp_path)
    config = _config_with_db(tmp_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=config):
        result = run_cli(["library-validate", "--disk", "medias2"])

    assert result.exit_code == 0, result.output
    assert_no_python_traceback(result)
    data = json.loads((tmp_path / ".data" / "library_validation.json").read_text())
    assert {item["path"] for item in data["items"]} == {str(library.movie_dir), str(library.show_dir)}


def test_library_clean_dry_run_reaches_the_frozen_disks_media(tmp_path: Path) -> None:
    """``library-clean --dry-run`` names the junk on the frozen disk and deletes nothing."""
    library = seed_frozen_library(tmp_path)
    config = _config_with_db(tmp_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=config):
        result = run_cli(["library-clean", "--dry-run", "--only", "junk", "--disk", "medias2"])

    assert result.exit_code == 0, result.output
    assert_no_python_traceback(result)
    assert (library.movie_dir / ".DS_Store").exists()
    assert (library.show_dir / ".DS_Store").exists()
    assert "Would delete 2 items" in " ".join(result.output.split())  # one junk file per media folder


def test_trailers_purge_dry_run_sees_the_frozen_disks_orphan_and_gap(tmp_path: Path) -> None:
    """``trailers purge --dry-run`` lists the frozen disk's orphan trailer and unindexed media."""
    library = seed_frozen_library(tmp_path)
    orphan = tmp_path / "medias2" / "films" / "Gone Film (2018)" / "Gone Film (2018)-trailer.mp4"
    orphan.parent.mkdir(parents=True)
    write_placeholder_media(orphan, 2 * 1024 * 1024)
    kept = library.show_dir / "Frozen Show (2019)-trailer.mp4"
    write_placeholder_media(kept, 2 * 1024 * 1024)
    config = _config_with_db(tmp_path)
    (tmp_path / "staging").mkdir(exist_ok=True)

    with (
        patch(_PATCH_LOAD_CONFIG, return_value=config),
        patch(_PATCH_LIVE, return_value={_normalize_path(library.show_dir)}),
    ):
        result = run_cli(["trailers", "purge", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert_no_python_traceback(result)
    assert kept.exists() and orphan.exists()
    output = " ".join(result.output.split())
    assert "Would purge 1 orphan trailer(s)" in output
    assert "Gone Film (2018)-trailer.mp4" in output
    assert "Would re-index 1 present media dir(s)" in output
