"""Unit tests for the single-owner crash-recovery orphan sweep (P2.4).

Exercises :func:`personalscraper.dispatch.crash_recovery.sweep_orphans` across
every root kind (media-tree, ingest-dir, lockout-file), both dry-run policies,
and the OSError guard branches. Safe: ``tmp_path`` only, no network.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from unittest.mock import patch

from personalscraper.dispatch.crash_recovery import (
    ARTIFACT_TABLE,
    DISPATCH_TMP_PREFIX,
    INGEST_TMP_PREFIX,
    LOCKOUT_STALE_AGE_S,
    MERGE_BACKUP_NAME,
    DryRunPolicy,
    RootKind,
    SweepRoot,
    sweep_orphans,
)


def _media_tree_root(path: Path, dry_run: DryRunPolicy = DryRunPolicy.SKIP) -> SweepRoot:
    """Build a MEDIA_TREE sweep root for *path*."""
    return SweepRoot(path, RootKind.MEDIA_TREE, dry_run)


class TestArtifactTable:
    """The declarative table is the single home for every marker."""

    def test_markers_present_in_table(self) -> None:
        """All recognised marker prefixes appear in the artifact table."""
        markers = {a.marker for a in ARTIFACT_TABLE}
        assert DISPATCH_TMP_PREFIX in markers
        assert INGEST_TMP_PREFIX in markers
        assert MERGE_BACKUP_NAME in markers


class TestMediaTreeSweep:
    """MEDIA_TREE roots: storage disks and the staging root."""

    def test_cleans_tmp_dispatch(self, tmp_path: Path) -> None:
        """``_tmp_dispatch_*`` media dirs are removed."""
        orphan = tmp_path / "movies" / f"{DISPATCH_TMP_PREFIX}Movie (2024)"
        orphan.mkdir(parents=True)
        (orphan / "partial.mkv").write_bytes(b"\x00" * 64)

        cleaned = sweep_orphans([_media_tree_root(tmp_path)], dry_run=False)

        assert cleaned == 1
        assert not orphan.exists()

    def test_cleans_merge_backup(self, tmp_path: Path) -> None:
        """``.merge_backup/`` subdirs inside media dirs are removed."""
        media = tmp_path / "tv_shows" / "Show (2024)"
        backup = media / MERGE_BACKUP_NAME
        backup.mkdir(parents=True)
        (backup / "old.mkv").write_bytes(b"\x00" * 32)

        cleaned = sweep_orphans([_media_tree_root(tmp_path)], dry_run=False)

        assert cleaned == 1
        assert not backup.exists()
        assert media.exists()  # the media dir itself is preserved

    def test_safety_never_touches_non_marker_dirs(self, tmp_path: Path) -> None:
        """A normal media dir with no marker is left completely untouched."""
        keeper = tmp_path / "movies" / "Real Movie (2024)"
        keeper.mkdir(parents=True)
        (keeper / "Real Movie.mkv").write_bytes(b"\x00" * 128)

        cleaned = sweep_orphans([_media_tree_root(tmp_path)], dry_run=False)

        assert cleaned == 0
        assert keeper.exists()
        assert (keeper / "Real Movie.mkv").exists()

    def test_non_dir_items_skipped(self, tmp_path: Path) -> None:
        """Files (not directories) inside a category dir are skipped."""
        category = tmp_path / "movies"
        category.mkdir(parents=True)
        (category / "loose.txt").write_text("not a dir")

        cleaned = sweep_orphans([_media_tree_root(tmp_path)], dry_run=False)
        assert cleaned == 0

    def test_missing_root_is_noop(self, tmp_path: Path) -> None:
        """A non-existent root path yields zero cleaned, no error."""
        cleaned = sweep_orphans([_media_tree_root(tmp_path / "nope")], dry_run=False)
        assert cleaned == 0

    def test_iterdir_oserror_caught(self, tmp_path: Path) -> None:
        """OSError while listing the root is caught and yields zero."""
        (tmp_path / "movies").mkdir()
        with patch.object(Path, "iterdir", side_effect=OSError("io")):
            cleaned = sweep_orphans([_media_tree_root(tmp_path)], dry_run=False)
        assert cleaned == 0

    def test_rmtree_oserror_caught(self, tmp_path: Path) -> None:
        """OSError during removal is caught — orphan survives, no raise."""
        orphan = tmp_path / "movies" / f"{DISPATCH_TMP_PREFIX}Broken"
        orphan.mkdir(parents=True)
        with patch.object(shutil, "rmtree", side_effect=OSError("busy")):
            cleaned = sweep_orphans([_media_tree_root(tmp_path)], dry_run=False)
        assert cleaned == 0
        assert orphan.exists()

    def test_dry_run_report_counts_but_keeps(self, tmp_path: Path) -> None:
        """REPORT policy in dry-run counts the orphan but does not delete it."""
        orphan = tmp_path / "movies" / f"{DISPATCH_TMP_PREFIX}Test"
        orphan.mkdir(parents=True)
        backup_media = tmp_path / "movies" / "Some Movie (2024)"
        (backup_media / MERGE_BACKUP_NAME).mkdir(parents=True)

        cleaned = sweep_orphans(
            [_media_tree_root(tmp_path, DryRunPolicy.REPORT)],
            dry_run=True,
        )

        assert cleaned == 2  # both reported
        assert orphan.exists()
        assert (backup_media / MERGE_BACKUP_NAME).exists()

    def test_dry_run_skip_does_nothing(self, tmp_path: Path) -> None:
        """SKIP policy in dry-run neither counts nor deletes."""
        orphan = tmp_path / "movies" / f"{DISPATCH_TMP_PREFIX}Test"
        orphan.mkdir(parents=True)

        cleaned = sweep_orphans(
            [_media_tree_root(tmp_path, DryRunPolicy.SKIP)],
            dry_run=True,
        )

        assert cleaned == 0
        assert orphan.exists()


class TestIngestDirSweep:
    """INGEST_DIR roots: the ingest staging directory."""

    def test_cleans_ingest_tmp(self, tmp_path: Path) -> None:
        """``.ingest_tmp_*`` dirs are removed."""
        orphan = tmp_path / f"{INGEST_TMP_PREFIX}Movie"
        orphan.mkdir()
        (orphan / "file.mkv").write_bytes(b"\x00" * 16)

        cleaned = sweep_orphans([SweepRoot(tmp_path, RootKind.INGEST_DIR)], dry_run=False)

        assert cleaned == 1
        assert not orphan.exists()

    def test_ignores_non_prefix(self, tmp_path: Path) -> None:
        """Dirs without the ingest prefix are preserved."""
        keeper = tmp_path / "Movie (2024)"
        keeper.mkdir()

        cleaned = sweep_orphans([SweepRoot(tmp_path, RootKind.INGEST_DIR)], dry_run=False)

        assert cleaned == 0
        assert keeper.exists()

    def test_missing_root_is_noop(self, tmp_path: Path) -> None:
        """A non-existent ingest dir yields zero."""
        cleaned = sweep_orphans([SweepRoot(tmp_path / "gone", RootKind.INGEST_DIR)], dry_run=False)
        assert cleaned == 0

    def test_iterdir_oserror_caught(self, tmp_path: Path) -> None:
        """OSError while listing the ingest dir is caught."""
        with patch.object(Path, "iterdir", side_effect=OSError("io")):
            cleaned = sweep_orphans([SweepRoot(tmp_path, RootKind.INGEST_DIR)], dry_run=False)
        assert cleaned == 0


class TestLockoutFileSweep:
    """LOCKOUT_FILE roots: the stale qBit auth-lockout file."""

    def _lockout(self, tmp_path: Path, age_s: float) -> Path:
        """Create a lockout file with the given age in seconds."""
        lockout = tmp_path / "qbit_auth_lockout"
        lockout.write_text("login_failed")
        old = time.time() - age_s
        import os

        os.utime(lockout, (old, old))
        return lockout

    def test_expired_removed(self, tmp_path: Path) -> None:
        """A lockout older than the threshold is unlinked."""
        lockout = self._lockout(tmp_path, LOCKOUT_STALE_AGE_S + 100)

        cleaned = sweep_orphans([SweepRoot(lockout, RootKind.LOCKOUT_FILE)], dry_run=False)

        assert cleaned == 1
        assert not lockout.exists()

    def test_recent_kept(self, tmp_path: Path) -> None:
        """A recent lockout (younger than threshold) is preserved."""
        lockout = self._lockout(tmp_path, 10)

        cleaned = sweep_orphans([SweepRoot(lockout, RootKind.LOCKOUT_FILE)], dry_run=False)

        assert cleaned == 0
        assert lockout.exists()

    def test_missing_is_noop(self, tmp_path: Path) -> None:
        """A non-existent lockout path yields zero."""
        cleaned = sweep_orphans([SweepRoot(tmp_path / "none", RootKind.LOCKOUT_FILE)], dry_run=False)
        assert cleaned == 0

    def test_unlink_oserror_caught(self, tmp_path: Path) -> None:
        """OSError during unlink is caught — lockout survives, no raise."""
        lockout = self._lockout(tmp_path, LOCKOUT_STALE_AGE_S + 100)
        with patch.object(Path, "unlink", side_effect=OSError("read-only")):
            cleaned = sweep_orphans([SweepRoot(lockout, RootKind.LOCKOUT_FILE)], dry_run=False)
        assert cleaned == 0
        assert lockout.exists()

    def test_dry_run_report_counts_but_keeps(self, tmp_path: Path) -> None:
        """REPORT policy in dry-run counts the stale lockout without deleting."""
        lockout = self._lockout(tmp_path, LOCKOUT_STALE_AGE_S + 100)
        cleaned = sweep_orphans(
            [SweepRoot(lockout, RootKind.LOCKOUT_FILE, DryRunPolicy.REPORT)],
            dry_run=True,
        )
        assert cleaned == 1
        assert lockout.exists()

    def test_dry_run_skip_does_nothing(self, tmp_path: Path) -> None:
        """SKIP policy in dry-run neither counts nor deletes."""
        lockout = self._lockout(tmp_path, LOCKOUT_STALE_AGE_S + 100)
        cleaned = sweep_orphans(
            [SweepRoot(lockout, RootKind.LOCKOUT_FILE, DryRunPolicy.SKIP)],
            dry_run=True,
        )
        assert cleaned == 0
        assert lockout.exists()


class TestMultipleRoots:
    """A single sweep call aggregates across disjoint roots."""

    def test_aggregates_count(self, tmp_path: Path) -> None:
        """Cleaned counts sum across a media tree, an ingest dir, and a lockout."""
        disk = tmp_path / "disk"
        (disk / "movies" / f"{DISPATCH_TMP_PREFIX}A").mkdir(parents=True)

        ingest = tmp_path / "ingest"
        (ingest / f"{INGEST_TMP_PREFIX}B").mkdir(parents=True)

        lockout = tmp_path / "lock"
        lockout.write_text("x")
        old = time.time() - (LOCKOUT_STALE_AGE_S + 100)
        import os

        os.utime(lockout, (old, old))

        cleaned = sweep_orphans(
            [
                SweepRoot(disk, RootKind.MEDIA_TREE),
                SweepRoot(ingest, RootKind.INGEST_DIR),
                SweepRoot(lockout, RootKind.LOCKOUT_FILE),
            ],
            dry_run=False,
        )

        assert cleaned == 3
