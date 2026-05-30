"""FS-aware Merkle CONSUMER tests (Phase 8 cycle-4 regression).

Phase 8 made the SCANNER store a *bucketed* Merkle root (full-scan finalize +
quick/incremental short-circuit, both via
:func:`~personalscraper.indexer.scanner._walker._build_disk_fingerprints`), but
left the two OTHER merkle-root consumers computing a RAW root:

- :func:`~personalscraper.indexer.reconcile.detect_merkle_drift` — the live
  consistency probe behind ``library-doctor``'s ``merkle_drift`` check.
- :func:`~personalscraper.indexer.repair._refresh_disk_merkle` — the post-cascade
  rewrite behind ``library-repair``'s ``soft_delete_subtree``.

On an auto-detected coarse FS (exFAT 2 s, HFS+ 1 s) a RAW recomputation can never
reproduce the bucketed stored root, so:

- the doctor emits a FALSE merkle-drift warning after EVERY clean scan, and
- the repair path writes a RAW root that defeats the next scan's short-circuit.

These tests pin both consumers as FS-aware.  The SACRED invariant
(``round_mtime_ns(m, NTFS_MACFUSE)`` is the identity) means the NTFS path stays
byte-identical to the legacy raw behaviour — pinned here too.

The bucketed stored root is seeded by a REAL full scan under an exFAT probe (the
same ``_seed_full_scan_exfat`` shape used by ``test_merkle_fs_aware.py``), so the
tests prove each consumer reproduces the value the scanner actually stored —
never a hand-faked root.
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
from personalscraper.indexer.merkle import compute_merkle_root
from personalscraper.indexer.reconcile import detect_merkle_drift
from personalscraper.indexer.repair import _refresh_disk_merkle
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

# A clean, past mtime that is an exact multiple of the 2 s exFAT bucket so the
# within-bucket jitter applied below is deterministic.
_ALIGNED_BASE_NS = 1_700_000_000_000_000_000
_ONE_SECOND_NS = 1_000_000_000


# ---------------------------------------------------------------------------
# Helpers (mirror test_merkle_fs_aware.py)
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


def _insert_disk(
    conn: sqlite3.Connection,
    mount_path: str,
    *,
    label: str | None = None,
    merkle_root: str | None = None,
) -> DiskRow:
    """Insert a minimal disk row and return the :class:`DiskRow` with its PK.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute path of the fake mount point.
        label: Stable disk label (== ``DiskConfig.id``). Defaults to the last
            path component of *mount_path*.
        merkle_root: Optional pre-seeded Merkle root.

    Returns:
        :class:`DiskRow` with the SQLite-assigned PK.
    """
    resolved_label = label if label is not None else mount_path.rstrip("/").split("/")[-1]
    uuid = f"test-uuid-{resolved_label}"
    cur = conn.execute(
        """
        INSERT INTO disk (uuid, label, mount_path, is_mounted, merkle_root, unreachable_strikes)
        VALUES (?, ?, ?, 1, ?, 0)
        """,
        (uuid, resolved_label, mount_path, merkle_root),
    )
    disk_id = cur.lastrowid
    assert disk_id is not None
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    return row


def _full_scan(conn: sqlite3.Connection, disk: DiskRow, info: MountInfo) -> DiskRow:
    """Run a full scan of *disk* under the *info* mount probe; return the reloaded row.

    The full-scan finalize stores the disk's first-ever ``merkle_root`` computed
    from fingerprints bucketed by the capability *info* resolves to.

    Args:
        conn: Open SQLite connection.
        disk: The disk row to scan.
        info: The :class:`MountInfo` the probe should return for the mount.

    Returns:
        The freshly-reloaded :class:`DiskRow` carrying the stored root.
    """
    with patch(_PROBE_PATCH, return_value=info):
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())
    fresh = disk_repo.get_by_id(conn, disk.id)
    assert fresh is not None
    assert fresh.merkle_root is not None, "full scan must store a merkle_root"
    return fresh


def _seed_full_scan_exfat(
    conn: sqlite3.Connection,
    mount: str,
    *,
    label: str | None = None,
    n_files: int = 4,
) -> DiskRow:
    """Full-scan a disk holding *n_files* videos under an exFAT capability.

    Each video lives in its OWN subdirectory so it maps to a DISTINCT ``path``
    row.  All on-disk mtimes are pinned to the 2 s-aligned base so a later
    within-bucket jitter is deterministic.

    Args:
        conn: Open SQLite connection.
        mount: Fake mount-point path (already created on the fake FS).
        label: Stable disk label to assign (== ``DiskConfig.id``).
        n_files: Number of video files to create.

    Returns:
        The freshly-reloaded :class:`DiskRow` carrying the stored exFAT root.
    """
    for i in range(n_files):
        subdir = f"{mount}/show{i}"
        Path(subdir).mkdir(parents=True, exist_ok=True)
        fp = f"{subdir}/film{i}.mkv"
        Path(fp).write_bytes(b"V" * 4096)
        os.utime(fp, ns=(_ALIGNED_BASE_NS, _ALIGNED_BASE_NS))

    disk = _insert_disk(conn, mount, label=label)
    exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())
    return _full_scan(conn, disk, exfat_info)


def _seed_full_scan_ntfs(
    conn: sqlite3.Connection,
    mount: str,
    *,
    label: str | None = None,
    n_files: int = 3,
) -> DiskRow:
    """Full-scan a disk holding *n_files* videos under an NTFS-via-macFUSE capability.

    Files carry genuine (non-aligned) on-disk mtimes — a worst case for the
    "NTFS bucketing is the identity" invariant.

    Args:
        conn: Open SQLite connection.
        mount: Fake mount-point path (already created on the fake FS).
        label: Stable disk label to assign (== ``DiskConfig.id``).
        n_files: Number of video files to create.

    Returns:
        The freshly-reloaded :class:`DiskRow` carrying the stored NTFS root.
    """
    for i in range(n_files):
        fp = f"{mount}/film{i}.mkv"
        Path(fp).write_bytes(bytes([70 + i]) * (5000 + i))

    disk = _insert_disk(conn, mount, label=label)
    ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())
    return _full_scan(conn, disk, ntfs_info)


def _raw_root_from_db(conn: sqlite3.Connection, disk_id: int) -> str:
    """Recompute the Merkle root from RAW (unbucketed) DB mtimes for *disk_id*.

    This reproduces the pre-Phase-8 consumer behaviour (no
    :func:`~personalscraper.indexer.fingerprint.round_mtime_ns`) so a test can
    assert byte-identity on NTFS and divergence on a coarse FS.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the disk whose files to read.

    Returns:
        The raw-mtime Merkle root hex string.
    """
    from personalscraper.indexer.merkle import FileFingerprint  # noqa: PLC0415

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
        (disk_id,),
    ).fetchall()
    conn.row_factory = None
    return compute_merkle_root(
        [
            FileFingerprint(path_id=r["path_id"], size=r["size_bytes"], mtime_ns=r["mtime_ns"], oshash=r["oshash"])
            for r in rows
        ]
    )


# ---------------------------------------------------------------------------
# FIX-A — detect_merkle_drift: no FALSE drift on a coarse FS
# ---------------------------------------------------------------------------


class TestDetectMerkleDriftCoarseFs:
    """``detect_merkle_drift`` must reproduce the scanner's bucketed root."""

    def test_no_false_drift_on_exfat_with_override(self, fs: "FakeFilesystem") -> None:
        """ExFAT disk, clean scan, override threaded → detector reports NO drift.

        Without the FS-aware fix the detector would recompute a RAW root that
        cannot equal the exFAT-bucketed STORED root, so this disk would be
        flagged as drifted (the false-warning regression). The override map is
        keyed on the STABLE disk label (== ``DiskConfig.id``).
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatDoctor"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_exfat(conn, mount, label="disk_exfat", n_files=4)

        # Jitter on-disk mtimes within the 2 s bucket: the detector is DB-only so
        # this must not matter — it only proves the gate never reads FS jitter.
        for child in Path(mount).rglob("*.mkv"):
            st = child.stat()
            os.utime(child, ns=(st.st_mtime_ns + _ONE_SECOND_NS, st.st_mtime_ns + _ONE_SECOND_NS))

        drifted = detect_merkle_drift(conn, fs_type_overrides={"disk_exfat": "exfat"})
        assert fresh.id not in drifted, "an exFAT disk with a clean bucketed stored root must NOT be flagged as drifted"
        assert drifted == [], "no disk should drift after a clean scan"

    def test_raw_recompute_would_false_drift_without_fix(self, fs: "FakeFilesystem") -> None:
        """Counter-proof: a RAW recompute (the pre-fix path) DOES mismatch on exFAT.

        Pins exactly what the fix repairs. The stored exFAT-bucketed root must
        NOT equal a root recomputed from raw DB mtimes — proving the bug was real
        and that bucketing (the fix) is what makes the detector agree.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatRawProof"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Use base+jitter mtimes so raw != bucket: file mtimes are NOT on the 2 s
        # boundary, so flooring to the bucket changes the value.
        for i in range(3):
            subdir = f"{mount}/show{i}"
            Path(subdir).mkdir(parents=True, exist_ok=True)
            fp = f"{subdir}/film{i}.mkv"
            Path(fp).write_bytes(b"V" * 4096)
            os.utime(fp, ns=(_ALIGNED_BASE_NS + _ONE_SECOND_NS, _ALIGNED_BASE_NS + _ONE_SECOND_NS))
        disk = _insert_disk(conn, mount, label="disk_raw")
        exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())
        fresh = _full_scan(conn, disk, exfat_info)

        raw_root = _raw_root_from_db(conn, fresh.id)
        assert raw_root != fresh.merkle_root, (
            "sanity: the raw-mtime root must differ from the exFAT-bucketed stored root "
            "(this is the false-drift the FS-aware detector fixes)"
        )
        # The FS-aware detector must NOT flag it despite the raw mismatch.
        drifted = detect_merkle_drift(conn, fs_type_overrides={"disk_raw": "exfat"})
        assert fresh.id not in drifted

    def test_ntfs_control_no_drift(self, fs: "FakeFilesystem") -> None:
        """NTFS control: a clean NTFS disk drifts under NEITHER raw nor bucketed.

        NTFS granularity is 1 (identity), so the detector behaves exactly as the
        legacy raw path — the control proving the fix is inert on NTFS.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NtfsControl"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_ntfs(conn, mount, label="disk_ntfs", n_files=3)

        # No override → auto-detect. The probe is patched off here, so an
        # unprobeable mount falls back to the NTFS-safe "unknown" superset
        # (granularity 1), matching the granularity-1 stored root.
        drifted = detect_merkle_drift(conn)
        assert fresh.id not in drifted, "a clean NTFS disk must never drift"

    def test_ntfs_detector_root_byte_identical_to_raw(self, fs: "FakeFilesystem") -> None:
        """On NTFS the bucketed detector root equals the raw DB root (identity)."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NtfsIdentity"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_ntfs(conn, mount, label="disk_ntfs_id", n_files=3)

        bucketed_root = compute_merkle_root(_build_disk_fingerprints(conn, fresh.id, NTFS_MACFUSE))
        raw_root = _raw_root_from_db(conn, fresh.id)
        assert bucketed_root == raw_root, "NTFS bucketing must be the identity transform"
        assert bucketed_root == fresh.merkle_root, "and must equal the stored NTFS full-scan root"


# ---------------------------------------------------------------------------
# FIX-B — _refresh_disk_merkle: writes a root the next scan can reproduce
# ---------------------------------------------------------------------------


class TestRefreshDiskMerkleCoarseFs:
    """``_refresh_disk_merkle`` must write the SAME root the scanner would."""

    def test_refresh_matches_next_scan_on_exfat(self, fs: "FakeFilesystem") -> None:
        """Refresh an exFAT disk → stored root equals the scanner's bucketed root.

        The repair cascade auto-detects the capability (override map not reachable
        through the ``drain`` processor protocol). The probe returns exFAT, so the
        written root MUST equal ``_build_disk_fingerprints(conn, id, EXFAT)`` →
        ``compute_merkle_root`` — i.e. the next quick/incremental scan
        short-circuits instead of re-walking or bulk-change-freezing.

        Without the fix, ``_refresh_disk_merkle`` would write a RAW root that the
        bucketed next-scan recomputation can never reproduce.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatRepair"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_exfat(conn, mount, label="disk_exfat_repair", n_files=4)

        # Tamper the stored root so the refresh has visible work to do.
        disk_repo.update_merkle_root(conn, fresh.id, "deadbeefdeadbeef")

        exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())
        with patch(_PROBE_PATCH, return_value=exfat_info):
            written = _refresh_disk_merkle(conn, fresh.id)

        # What the next scan's short-circuit will recompute (bucketed with exFAT).
        next_scan_root = compute_merkle_root(_build_disk_fingerprints(conn, fresh.id, EXFAT))
        assert written == next_scan_root, "the refreshed root must equal the scanner's exFAT-bucketed root"

        stored = disk_repo.get_by_id(conn, fresh.id)
        assert stored is not None
        assert stored.merkle_root == next_scan_root, "the persisted disk.merkle_root must match the next scan"

        # The detector must now see this disk as clean (closes the loop).
        drifted = detect_merkle_drift(conn, fs_type_overrides={"disk_exfat_repair": "exfat"})
        assert fresh.id not in drifted

    def test_refresh_byte_identical_to_raw_on_ntfs(self, fs: "FakeFilesystem") -> None:
        """NTFS: the refreshed root equals the raw-mtime root (identity, inert fix)."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NtfsRepair"
        Path(mount).mkdir(parents=True, exist_ok=True)
        fresh = _seed_full_scan_ntfs(conn, mount, label="disk_ntfs_repair", n_files=3)

        disk_repo.update_merkle_root(conn, fresh.id, "deadbeefdeadbeef")

        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())
        with patch(_PROBE_PATCH, return_value=ntfs_info):
            written = _refresh_disk_merkle(conn, fresh.id)

        raw_root = _raw_root_from_db(conn, fresh.id)
        assert written == raw_root, "on NTFS the refreshed root must be byte-identical to the raw-mtime root"

    def test_refresh_noop_when_merkle_null(self, fs: "FakeFilesystem") -> None:
        """A disk with no prior merkle is left untouched (legacy no-op preserved)."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NeverScanned"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk = _insert_disk(conn, mount, label="disk_null", merkle_root=None)

        with patch(_PROBE_PATCH, return_value=None):
            result = _refresh_disk_merkle(conn, disk.id)
        assert result is None, "a NULL-merkle disk must remain a no-op"
        stored = disk_repo.get_by_id(conn, disk.id)
        assert stored is not None and stored.merkle_root is None
