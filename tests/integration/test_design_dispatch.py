"""Design-contract tests for the dispatch + verify subsystem.

Pin points for ``docs/reference/storage.md`` (codename: ``dispatch``) and
``docs/reference/pipeline-internals.md`` (codename: ``pipeline``).
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from personalscraper.conf import ids as CID
from personalscraper.conf.models.categories import CategoryConfig, GenreMapping
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.resolver import pick_disk_for
from personalscraper.dispatch._movie import replace
from personalscraper.dispatch._tv import purge_episode_conflicts
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_config(
    tmp_path: Path,
    *,
    disks: list[DiskConfig],
) -> Config:
    """Build a minimal Config for dispatch contract tests."""
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "tc",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=disks,
        categories={CID.MOVIES: CategoryConfig(folder_name="Films")},
        custom_categories=[],
        genre_mapping=GenreMapping(
            default_movies_category=CID.MOVIES,
            default_tv_category=CID.TV_SHOWS,
        ),
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


class TestMovieReplaceContract:
    """Movie replace semantics — DESIGN storage.md §Move Rules (dispatch)."""

    def test_replace_swaps_destination_atomically(self, tmp_path: Path) -> None:
        """Movie replace performs a transfer + atomic swap.

        Design: docs/reference/storage.md#move-rules-dispatch
        Contract: For a movie whose destination folder already exists on
        the target disk, ``replace`` transfers ``source`` into a temporary
        sibling and atomically swaps it for the existing destination.
        After a successful call the destination contains the source's
        files and the source path is gone — last-writer-wins as the move
        rule prescribes.
        """
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "movie.mkv").write_bytes(b"new")
        (dest / "movie.mkv").write_bytes(b"old")

        ok = replace(source, dest)

        assert ok is True
        assert dest.exists()
        assert (dest / "movie.mkv").read_bytes() == b"new"
        assert not source.exists()

    def test_replace_rolls_back_when_rsync_transfer_fails(self, tmp_path: Path) -> None:
        """Rsync failure leaves source + destination untouched.

        Design: docs/reference/storage.md#move-rules-dispatch
        Contract: When Phase 1 (rsync transfer) fails, ``replace`` returns
        ``False`` and rolls back: the original destination keeps its
        content, the source is NOT consumed, and no ``.new.tmp`` /
        ``.old.tmp`` sibling is left behind. This is the load-bearing
        invariant for the "atomic swap" claim — a partial swap that
        leaves either side in an inconsistent state would silently lose
        data on the next dispatch run.
        """
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "movie.mkv").write_bytes(b"new")
        (dest / "movie.mkv").write_bytes(b"old")

        # Force rsync to fail. ``_transfer.rsync`` is the only critical
        # I/O in Phase 1; making it return False simulates a transfer
        # error (out of disk, broken pipe, etc.) without needing to
        # actually run rsync.
        with patch("personalscraper.dispatch._movie._transfer.rsync", return_value=False):
            ok = replace(source, dest)

        assert ok is False, "replace must report failure when rsync fails"
        # Original destination preserved untouched.
        assert (dest / "movie.mkv").read_bytes() == b"old"
        # Source preserved (not consumed by Phase 3 cleanup).
        assert (source / "movie.mkv").read_bytes() == b"new"
        # No staging siblings leaked.
        assert not (dest.parent / f"{dest.name}.new.tmp").exists()
        assert not (dest.parent / f"{dest.name}.old.tmp").exists()

    def test_replace_restores_original_when_swap_fails_mid_way(self, tmp_path: Path) -> None:
        """Mid-swap failure restores the original destination from backup.

        Design: docs/reference/storage.md#move-rules-dispatch
        Contract: If Phase 2 fails AFTER the original ``dest`` was
        renamed to ``dest.old.tmp`` but BEFORE ``dest.new.tmp`` was
        renamed to ``dest``, ``replace`` rolls the backup back to
        ``dest`` so the on-disk view is identical to the pre-call
        state. Without this rollback, a swap failure would leave the
        media library missing the title entirely until a manual
        recovery — exactly the silent-data-loss mode the atomic-swap
        contract exists to prevent.
        """
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "movie.mkv").write_bytes(b"new")
        (dest / "movie.mkv").write_bytes(b"old")

        real_rename = os.rename
        rename_count = 0

        def fake_rename(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
            """Allow first rename (dest → dest.old.tmp), fail the second.

            This recreates the exact mid-swap state Phase 2's rollback
            block is designed to recover from.
            """
            nonlocal rename_count
            rename_count += 1
            if rename_count == 2:
                raise OSError(28, "simulated swap failure")  # ENOSPC
            real_rename(src, dst)

        # rsync writes a real .new.tmp so the second rename has something
        # to act on; only os.rename is patched.
        with patch("personalscraper.dispatch._movie.os.rename", side_effect=fake_rename):
            ok = replace(source, dest)

        assert ok is False, "replace must report failure when the swap fails"
        # Pre-call view restored: dest exists with original content.
        assert dest.exists()
        assert (dest / "movie.mkv").read_bytes() == b"old"
        # No staging siblings leaked after rollback — both .old.tmp (backup)
        # and .new.tmp (successful Phase 1 transfer) must be cleaned up.
        assert not (dest.parent / f"{dest.name}.old.tmp").exists()
        assert not (dest.parent / f"{dest.name}.new.tmp").exists()


class TestTvShowMergeContract:
    """TV-show merge semantics — DESIGN storage.md §Move Rules (dispatch)."""

    def test_purge_resolves_episode_conflicts_on_season_episode_key(self, tmp_path: Path) -> None:
        """Existing episode files matching the (season, episode) key are purged.

        Design: docs/reference/storage.md#move-rules-dispatch
        Contract: TV-show merge keys episode files on the (season,
        episode) tuple, NOT the full filename. When the source carries
        a re-titled re-scrape of the same episode (e.g. EN
        ``S04E06 - YOU LOOK HORRIBLE.mkv`` vs FR ``S04E06 - T'AS UNE
        SALE GUEULE.mkv``), the existing destination copy must be moved
        out of the way before the rsync merge, otherwise both
        differently-named files would coexist on disk. Episodes that
        the source does not provide remain untouched (preserves
        existing content per the merge — not replace — rule).
        """
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        backup = tmp_path / ".merge_backup"

        # Source carries a French re-scrape of S04E06 only.
        (source / "Saison 04").mkdir(parents=True)
        (source / "Saison 04" / "S04E06 - T'AS UNE SALE GUEULE.mkv").write_bytes(b"fr")

        # Destination has the English original of S04E06 plus E07 (untouched).
        (dest / "Saison 04").mkdir(parents=True)
        (dest / "Saison 04" / "S04E06 - YOU LOOK HORRIBLE.mkv").write_bytes(b"en")
        (dest / "Saison 04" / "S04E07 - HONEST DAY.mkv").write_bytes(b"keep")

        purge_episode_conflicts(source, dest, backup)

        # E06 (different filename, same key) was moved aside.
        assert not (dest / "Saison 04" / "S04E06 - YOU LOOK HORRIBLE.mkv").exists()
        # E07 (no source counterpart) is preserved on the destination.
        assert (dest / "Saison 04" / "S04E07 - HONEST DAY.mkv").exists()


class TestNewMediaDiskSelectionContract:
    """New-media disk selection — DESIGN storage.md §Move Rules (dispatch)."""

    def test_pick_disk_for_returns_most_free_eligible(self, tmp_path: Path) -> None:
        """New media targets the eligible disk with the most free space.

        Design: docs/reference/storage.md#move-rules-dispatch
        Contract: For a media item whose folder does not already exist
        on any storage disk, dispatch resolves the target via
        ``pick_disk_for`` which (a) filters disks accepting the
        category and meeting ``threshold = max(min_free_gb,
        item_size_gb * 1.5)``, and (b) returns the eligible disk with
        the highest free space. Disks below threshold (including
        unmounted disks reported as 0.0) are excluded.
        """
        disk_small = DiskConfig(
            id="disk_small",
            path=tmp_path / "disk_small",
            categories=[CID.MOVIES],
        )
        disk_full = DiskConfig(
            id="disk_full",
            path=tmp_path / "disk_full",
            categories=[CID.MOVIES],
        )
        disk_large = DiskConfig(
            id="disk_large",
            path=tmp_path / "disk_large",
            categories=[CID.MOVIES],
        )
        disk_offline = DiskConfig(
            id="disk_offline",
            path=tmp_path / "disk_offline",
            categories=[CID.MOVIES],
        )
        config = _make_config(
            tmp_path,
            disks=[disk_small, disk_full, disk_large, disk_offline],
        )

        # disk_small has just-enough; disk_large has more; disk_full is
        # below threshold; disk_offline reports 0.0 (treated as unmounted).
        free_space_by_id = {
            "disk_small": 200.0,
            "disk_full": 50.0,
            "disk_large": 800.0,
            "disk_offline": 0.0,
        }
        # threshold = max(100, 4*1.5) = 100 → eligible: small + large.
        chosen = pick_disk_for(config, CID.MOVIES, free_space_by_id, 100.0, 4.0)

        assert chosen is not None
        assert chosen.id == "disk_large"

    def test_pick_disk_for_returns_none_when_no_disk_eligible(self, tmp_path: Path) -> None:
        """No eligible disk → ``None``; caller skips the dispatch.

        Design: docs/reference/storage.md#move-rules-dispatch
        Contract: When no disk has enough free space (or none accept
        the category), ``pick_disk_for`` returns ``None`` and the
        dispatch step records a ``skipped`` outcome rather than picking
        an under-threshold disk.
        """
        disk = DiskConfig(
            id="disk_a",
            path=tmp_path / "disk_a",
            categories=[CID.MOVIES],
        )
        config = _make_config(tmp_path, disks=[disk])

        # 30 GB free, 100 GB threshold, 4 GB item → no eligible disk.
        chosen = pick_disk_for(config, CID.MOVIES, {"disk_a": 30.0}, 100.0, 4.0)

        assert chosen is None
