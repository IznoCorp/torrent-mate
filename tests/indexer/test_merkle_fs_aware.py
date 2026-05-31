"""FS-aware Merkle gating tests (Phase 8 Task 1).

These tests pin the three gating short-circuits that decide — *before* any walk
happens — whether the scanner touches a disk:

- the **Merkle root** short-circuit (DB-recomputed root vs stored
  ``disk.merkle_root``),
- the **Merkle delta** bulk-change freeze guard (DB-vs-FS sample), and
- the full-scan **root store** that the FIRST incremental/quick scan reads back.

Before Phase 8 these gates compared RAW ``mtime_ns`` while the per-file compare
was FS-aware, so on a coarse filesystem (exFAT 2 s, HFS+ 1 s) sub-bucket jitter
defeated the short-circuit AND could spuriously trip the bulk-change FREEZE of a
healthy disk. The fix buckets the mtime via
:func:`~personalscraper.indexer.fingerprint.round_mtime_ns` at the
fingerprint-build sites so root + delta + dir-mtime are consistently FS-aware.

The SACRED invariant: ``round_mtime_ns(m, NTFS_MACFUSE)`` is the identity
(granularity 1), so every gate must produce byte-identical results to the legacy
raw-mtime behaviour for NTFS/APFS/ext4. The first test pins exactly that.

NOTE (deliberate): unlike the pre-Phase-8 coarse-FS tests, these tests do **not**
reset ``merkle_root=None``. The whole point is to seed a VALID stored root and
prove the gating layer behaves correctly with the root left intact.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer._fs_capability import EXFAT, NTFS_MACFUSE
from personalscraper.indexer._fs_probe import MountInfo
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.fingerprint import round_mtime_ns
from personalscraper.indexer.merkle import (
    FileFingerprint,
    compute_merkle_delta,
    compute_merkle_root,
)
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.scanner._walker import _build_disk_fingerprints
from personalscraper.indexer.schema import DiskRow

pytestmark = pytest.mark.multifs

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"
_PROBE_PATCH = "personalscraper.indexer._fs_probe.probe_mount"
_OSHASH_INCR_PATCH = "personalscraper.indexer.scanner._modes.incremental._compute_oshash"
_DIR_MTIME_PATCH = "personalscraper.indexer.scanner._verify_dir_mtime_reliable"

# A clean, past mtime that is an exact multiple of the 2 s exFAT bucket
# (1.7e18 ns) so the within-bucket jitter applied below is deterministic.
_ALIGNED_BASE_NS = 1_700_000_000_000_000_000
_ONE_SECOND_NS = 1_000_000_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn_real() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full migration chain.

    Must be invoked while the real filesystem is active (``fs.pause()``), since
    :func:`apply_migrations` reads SQL files from disk.

    Returns:
        Open connection with FK enforcement and all migrations applied.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, mount_path: str, merkle_root: str | None = None) -> DiskRow:
    """Insert a minimal disk row and return the :class:`DiskRow` with its PK.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute path of the fake mount point.
        merkle_root: Optional pre-seeded Merkle root.

    Returns:
        :class:`DiskRow` with the SQLite-assigned PK.
    """
    uuid = f"test-uuid-{mount_path}"
    label = mount_path.rstrip("/").split("/")[-1]
    cur = conn.execute(
        """
        INSERT INTO disk (uuid, label, mount_path, is_mounted, merkle_root, unreachable_strikes)
        VALUES (?, ?, ?, 1, ?, 0)
        """,
        (uuid, label, mount_path, merkle_root),
    )
    disk_id = cur.lastrowid
    assert disk_id is not None
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    return row


def _seed_full_scan_exfat(conn: sqlite3.Connection, mount: str, n_files: int = 4) -> DiskRow:
    """Full-scan a disk holding *n_files* videos under an exFAT capability.

    The full scan's finalize path stores the disk's first-ever ``merkle_root``;
    with the exFAT override threaded, that root is computed from exFAT-bucketed
    fingerprints. All on-disk mtimes are pinned to the 2 s-aligned base so a
    later within-bucket jitter is deterministic.

    Args:
        conn: Open SQLite connection.
        mount: Fake mount-point path (already created on the fake FS).
        n_files: Number of video files to create.

    Returns:
        The freshly-reloaded :class:`DiskRow` carrying the stored exFAT root.
    """
    # Each video lives in its OWN subdirectory so it maps to a DISTINCT
    # ``path`` row (and therefore a distinct ``path_id``).  The schema's
    # ``path`` row refers to a *directory*, so co-locating files in the root
    # would collapse them onto one ``path_id`` and defeat the per-path_id
    # delta lookup (DEV #11).  Subdirs give the delta guard the realistic
    # one-file-per-path shape it is designed for.
    for i in range(n_files):
        subdir = f"{mount}/show{i}"
        Path(subdir).mkdir(parents=True, exist_ok=True)
        fp = f"{subdir}/film{i}.mkv"
        Path(fp).write_bytes(b"V" * 4096)
        os.utime(fp, ns=(_ALIGNED_BASE_NS, _ALIGNED_BASE_NS))

    disk = _insert_disk(conn, mount)
    exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())
    with patch(_PROBE_PATCH, return_value=exfat_info):
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

    fresh = disk_repo.get_by_id(conn, disk.id)
    assert fresh is not None
    assert fresh.merkle_root is not None, "full scan must store a merkle_root"
    return fresh


def _jitter_disk_mtimes(mount: str, delta_ns: int) -> None:
    """Shift every ``*.mkv`` mtime under *mount* (recursively) by *delta_ns*."""
    for child in Path(mount).rglob("*.mkv"):
        st = child.stat()
        os.utime(child, ns=(st.st_mtime_ns + delta_ns, st.st_mtime_ns + delta_ns))


# ---------------------------------------------------------------------------
# 1. NTFS merkle-root byte-identical pin (the sacred invariant)
# ---------------------------------------------------------------------------


class TestNtfsMerkleRootByteIdentical:
    """``round_mtime_ns(m, NTFS_MACFUSE)`` is the identity → roots are byte-equal."""

    def test_round_mtime_ns_ntfs_is_identity(self) -> None:
        """NTFS granularity is 1, so bucketing returns the value unchanged."""
        for m in (0, 1, 999, 1_700_000_000_123_456_789, 2**40 + 7):
            assert round_mtime_ns(m, NTFS_MACFUSE) == m

    def test_ntfs_built_fingerprints_root_equals_raw_root(self, fs: "FakeFilesystem") -> None:
        """A root from NTFS-bucketed DB rows equals the root from RAW mtimes.

        This is the byte-identical anchor: ``_build_disk_fingerprints(...,
        NTFS_MACFUSE)`` must yield fingerprints whose ``compute_merkle_root`` is
        identical to one built from the unrounded ``mtime_ns`` straight off the
        DB rows. Any divergence here means the NTFS path was perturbed.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NtfsPin"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Seed via a real full scan so the media_file rows carry genuine
        # (non-aligned) on-disk mtimes — a worst case for "identity".
        for i in range(3):
            fp = f"{mount}/film{i}.mkv"
            Path(fp).write_bytes(bytes([70 + i]) * (5000 + i))
        disk = _insert_disk(conn, mount)
        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())
        with patch(_PROBE_PATCH, return_value=ntfs_info):
            with patch(_GUARD_PATCH, return_value=None):
                scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # NTFS-bucketed fingerprints (the new code path).
        ntfs_fps = _build_disk_fingerprints(conn, disk.id, NTFS_MACFUSE)
        assert ntfs_fps, "the full scan must have produced fingerprinted rows"

        # RAW fingerprints read straight off the DB with no rounding (the legacy
        # behaviour pre-Phase-8).
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT mf.path_id, mf.size_bytes, mf.mtime_ns, mf.oshash
            FROM media_file mf
            JOIN path p ON mf.path_id = p.id
            WHERE p.disk_id = ?
              AND mf.deleted_at IS NULL
              AND mf.oshash IS NOT NULL
            """,
            (disk.id,),
        ).fetchall()
        conn.row_factory = None
        raw_fps = [
            FileFingerprint(path_id=r["path_id"], size=r["size_bytes"], mtime_ns=r["mtime_ns"], oshash=r["oshash"])
            for r in rows
        ]

        assert compute_merkle_root(ntfs_fps) == compute_merkle_root(raw_fps), (
            "NTFS bucketing must be the identity transform — the merkle root must be byte-identical to the raw root"
        )

    def test_stored_ntfs_full_scan_root_equals_raw_root(self, fs: "FakeFilesystem") -> None:
        """The full-scan root STORED on the disk row equals the raw-mtime root.

        Pins the full-scan finalize store (Phase 8 §full-scan): the value
        persisted to ``disk.merkle_root`` under an NTFS capability must equal a
        root recomputed from the raw DB mtimes — i.e. the first incremental will
        see no spurious one-version mismatch on NTFS.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NtfsStorePin"
        Path(mount).mkdir(parents=True, exist_ok=True)
        for i in range(2):
            Path(f"{mount}/film{i}.mkv").write_bytes(bytes([80 + i]) * (6000 + i))
        disk = _insert_disk(conn, mount)
        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())
        with patch(_PROBE_PATCH, return_value=ntfs_info):
            with patch(_GUARD_PATCH, return_value=None):
                scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        stored = disk_repo.get_by_id(conn, disk.id)
        assert stored is not None and stored.merkle_root is not None

        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT mf.path_id, mf.size_bytes, mf.mtime_ns, mf.oshash
            FROM media_file mf
            JOIN path p ON mf.path_id = p.id
            WHERE p.disk_id = ?
              AND mf.deleted_at IS NULL
              AND mf.oshash IS NOT NULL
            """,
            (disk.id,),
        ).fetchall()
        conn.row_factory = None
        raw_root = compute_merkle_root(
            [
                FileFingerprint(path_id=r["path_id"], size=r["size_bytes"], mtime_ns=r["mtime_ns"], oshash=r["oshash"])
                for r in rows
            ]
        )
        assert stored.merkle_root == raw_root, "the stored NTFS full-scan root must be byte-identical to the raw root"


# ---------------------------------------------------------------------------
# 2. Coarse-FS merkle stability — full→incremental handoff short-circuits
# ---------------------------------------------------------------------------


class TestCoarseFsMerkleStability:
    """exFAT: a valid stored root survives the full→incremental handoff.

    Seeds a VALID ``merkle_root`` via a full scan on an exFAT disk (root stored
    bucketed), then runs an incremental with the root LEFT INTACT and no DB
    content change. The DB-recomputed root must equal the stored root (both
    bucketed with exFAT) so the Merkle short-circuit HITS — no walk, no
    ``DiskBulkChangeDetected``, no OSHash recompute. Pre-Phase-8 the full scan
    stored a RAW root and the incremental recomputed a (still raw, but the
    handoff was untested) root; the real coarse-FS hazard — a stored root that
    cannot be reproduced after Phase 8 — is what this pins.
    """

    def test_incremental_short_circuits_on_intact_exfat_root(self, fs: "FakeFilesystem") -> None:
        """Stored exFAT root + unchanged DB → incremental Merkle short-circuit hits."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatStable"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_exfat(conn, mount, n_files=4)

        # Jitter the on-disk mtimes within the 2 s bucket. The Merkle
        # short-circuit is DB-only, so this must not matter; we apply it to prove
        # the gate does not read sub-bucket FS jitter into a miss.
        _jitter_disk_mtimes(mount, _ONE_SECOND_NS)

        exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())
        with patch(_OSHASH_INCR_PATCH) as mock_oshash:
            with patch(_PROBE_PATCH, return_value=exfat_info):
                with patch(_GUARD_PATCH, return_value=None):
                    result = scan(
                        [fresh],
                        ScanMode.incremental,
                        generation=2,
                        conn=conn,
                        event_bus=EventBus(),
                    )

        assert result.status == "ok"
        assert result.disks_skipped == 1, "the intact exFAT root must trigger the Merkle short-circuit (disk skipped)"
        assert mock_oshash.call_count == 0, "a short-circuited disk must never recompute OSHash"

    def test_db_recomputed_exfat_root_matches_stored(self, fs: "FakeFilesystem") -> None:
        """The exFAT root recomputed from the DB equals the stored full-scan root.

        This is the direct proof of the full→incremental handoff: both sides
        bucket with exFAT, so ``_build_disk_fingerprints(..., EXFAT)`` →
        ``compute_merkle_root`` reproduces exactly the value the full scan stored.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatHandoff"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_exfat(conn, mount, n_files=3)

        recomputed = compute_merkle_root(_build_disk_fingerprints(conn, fresh.id, EXFAT))
        assert recomputed == fresh.merkle_root, (
            "the exFAT-bucketed DB root must reproduce the stored full-scan root (no one-version mismatch)"
        )


# ---------------------------------------------------------------------------
# 3. Bulk-change freeze guard — sub-bucket jitter must NOT freeze a healthy disk
# ---------------------------------------------------------------------------


class TestBulkChangeFreezeGuard:
    """exFAT: >50% sub-bucket mtime jitter, content unchanged → no freeze.

    The freeze guard runs only on a Merkle MISS. With every file carrying
    sub-2 s on-disk mtime jitter (but identical content), a RAW delta would count
    100% of files as changed and trip ``DiskBulkChangeDetected``. Because both
    the DB and the fresh FS sample are bucketed with the SAME exFAT capability,
    the bucketed delta is 0.0 → the guard stays well below threshold → no freeze.
    """

    def test_subbucket_jitter_does_not_trip_delta_freeze(self, fs: "FakeFilesystem") -> None:
        """Bucketed delta of all-jittered-but-unchanged files is below threshold."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatFreeze"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_exfat(conn, mount, n_files=6)

        # Jitter EVERY file's on-disk mtime by +1 s — within the 2 s exFAT bucket,
        # so content is unchanged and the bucketed delta must be 0.0.
        _jitter_disk_mtimes(mount, _ONE_SECOND_NS)

        # Direct delta check: DB (bucketed) vs fresh FS sample (bucketed).
        from personalscraper.indexer.scanner._walker import _sample_fresh_fingerprints  # noqa: PLC0415

        db_fps = _build_disk_fingerprints(conn, fresh.id, EXFAT)
        fresh_fps = _sample_fresh_fingerprints(conn, fresh.id, mount, EXFAT)
        bucketed_delta = compute_merkle_delta(db_fps, fresh_fps)
        assert bucketed_delta == 0.0, "all-within-bucket jitter must produce a zero bucketed delta"

        # Counter-check: the RAW delta (no bucketing) would have been 100% and
        # tripped the freeze — proving the bucketing is what saves the disk.
        raw_db_fps = _build_disk_fingerprints(conn, fresh.id, NTFS_MACFUSE)
        raw_fresh_fps = _sample_fresh_fingerprints(conn, fresh.id, mount, NTFS_MACFUSE)
        raw_delta = compute_merkle_delta(raw_db_fps, raw_fresh_fps)
        assert raw_delta == 1.0, "sanity: without bucketing every file looks changed (the pre-Phase-8 freeze hazard)"

    def test_incremental_misses_root_but_does_not_freeze(self, fs: "FakeFilesystem") -> None:
        """A forced Merkle MISS on exFAT runs the guard but does NOT freeze.

        Tampering the stored ``merkle_root`` forces a miss so the bulk-change
        guard runs. With sub-bucket on-disk jitter and unchanged content the
        bucketed delta is 0.0, so the walk proceeds normally and
        ``DiskBulkChangeDetected`` is never raised (the scan finishes ``ok``).
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatMissNoFreeze"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_exfat(conn, mount, n_files=6)

        # Force a Merkle MISS while keeping a non-NULL stored root (so the guard
        # is armed): overwrite with a syntactically valid but wrong hash.
        disk_repo.update_merkle_root(conn, fresh.id, "deadbeefdeadbeef")
        missed = disk_repo.get_by_id(conn, fresh.id)
        assert missed is not None

        # Sub-bucket jitter on every file, content unchanged.
        _jitter_disk_mtimes(mount, _ONE_SECOND_NS)

        exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())
        with patch(_PROBE_PATCH, return_value=exfat_info):
            with patch(_GUARD_PATCH, return_value=None):
                with patch(_DIR_MTIME_PATCH, return_value=False):
                    result = scan(
                        [missed],
                        ScanMode.incremental,
                        generation=2,
                        conn=conn,
                        event_bus=EventBus(),
                    )

        assert result.status == "ok", (
            "a healthy disk with sub-bucket jitter must NOT freeze (no DiskBulkChangeDetected)"
        )
