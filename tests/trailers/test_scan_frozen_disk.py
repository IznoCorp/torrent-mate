"""The trailer purge / heal scan sees a disk's existing media whatever its ``categories``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.trailers.cli import _discover_fs_orphan_trailers, _normalize_path
from tests._frozen_disk import FROZEN_DISK_ID, frozen_disk_config, seed_frozen_library
from tests._media_files import write_placeholder_media

_PATCH_LIVE = "personalscraper.trailers.cli._live_item_dirs"


def _scan(tmp_path: Path, live: set[str]) -> tuple[list[Path], list]:
    """Run the scan over the frozen-disk library with *live* as the index truth."""
    with patch(_PATCH_LIVE, return_value=live):
        return _discover_fs_orphan_trailers(
            frozen_disk_config(tmp_path), MagicMock(), disk=None, seasons_enabled=True, min_size=1
        )


class TestScanFrozenDisk:
    """Orphans and gaps are found on the disk frozen to audiobooks."""

    def test_an_orphan_trailer_is_a_purge_candidate(self, tmp_path: Path) -> None:
        """The defect: a media folder without media on the frozen disk was never purged."""
        library = seed_frozen_library(tmp_path)
        gone = tmp_path / FROZEN_DISK_ID / "films" / "Gone Film (2018)"
        trailer = gone / "Gone Film (2018)-trailer.mp4"
        trailer.parent.mkdir(parents=True)
        write_placeholder_media(trailer, 2 * 1024 * 1024)
        live = {_normalize_path(library.movie_dir), _normalize_path(library.show_dir)}

        orphans, gaps = _scan(tmp_path, live)

        assert trailer in orphans
        assert gaps == []

    def test_a_present_unindexed_media_is_a_heal_target(self, tmp_path: Path) -> None:
        """Present media missing from the index on the frozen disk is healed, not purged."""
        library = seed_frozen_library(tmp_path)
        trailer = library.movie_dir / "Frozen Film (2020)-trailer.mp4"
        write_placeholder_media(trailer, 2 * 1024 * 1024)

        orphans, gaps = _scan(tmp_path, {_normalize_path(library.show_dir)})

        assert trailer not in orphans
        assert [(g.disk_cfg.id, g.category_id, g.kind, g.media_dir) for g in gaps] == [
            (FROZEN_DISK_ID, "movies", "movie", library.movie_dir)
        ]

    def test_an_indexed_media_keeps_its_trailer(self, tmp_path: Path) -> None:
        """An indexed item on the frozen disk is neither an orphan nor a gap."""
        library = seed_frozen_library(tmp_path)
        trailer = library.movie_dir / "Frozen Film (2020)-trailer.mp4"
        write_placeholder_media(trailer, 2 * 1024 * 1024)
        live = {_normalize_path(library.movie_dir), _normalize_path(library.show_dir)}

        orphans, gaps = _scan(tmp_path, live)

        assert trailer not in orphans
        assert gaps == []
