"""``validate_library`` sees a disk's existing media whatever its ``categories``.

A disk frozen to ``["audiobooks"]`` takes no new media, yet still holds films and
series; its ``categories`` gate dispatch eligibility, not what exists.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.verify.library_checks import validate_library
from tests._frozen_disk import FROZEN_DISK_ID, frozen_disk_config, seed_frozen_library


class TestValidateFrozenDisk:
    """library-validate walks the frozen disk's film and series folders."""

    def test_the_frozen_disks_media_are_validated(self, tmp_path: Path) -> None:
        """The defect: the frozen disk's film and series were never reported."""
        library = seed_frozen_library(tmp_path)
        result = validate_library(frozen_disk_config(tmp_path))

        by_path = {item.path: item for item in result.items}
        assert str(library.movie_dir) in by_path
        assert str(library.show_dir) in by_path
        assert by_path[str(library.movie_dir)].disk == FROZEN_DISK_ID
        assert by_path[str(library.movie_dir)].media_type == "movie"
        assert by_path[str(library.show_dir)].media_type == "tvshow"

    def test_the_disk_filter_still_scopes_to_the_frozen_disk(self, tmp_path: Path) -> None:
        """``--disk`` keeps selecting the frozen disk, and only its media."""
        library = seed_frozen_library(tmp_path)
        result = validate_library(frozen_disk_config(tmp_path), disk_filter=FROZEN_DISK_ID)

        assert {item.path for item in result.items} == {str(library.movie_dir), str(library.show_dir)}

    def test_the_category_filter_still_applies(self, tmp_path: Path) -> None:
        """``--category`` narrows the frozen disk's walk to that category."""
        library = seed_frozen_library(tmp_path)
        result = validate_library(frozen_disk_config(tmp_path), category_filter="tv_shows")

        assert {item.path for item in result.items} == {str(library.show_dir)}
