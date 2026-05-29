"""Integration tests for FS-aware incremental / quick tier-1 comparison (Phase 5).

These tests run the *real* incremental and quick scanner code paths against a
small in-memory DB plus pyfakefs-backed files, injecting a per-disk
:class:`~personalscraper.indexer._fs_capability.FilesystemCapability` either:

- directly, via the ``capability=`` argument of
  :func:`~personalscraper.indexer.scanner._modes.incremental._scan_disk_incremental`
  (focused tier-1 assertions), or
- end-to-end, by monkeypatching ``personalscraper.indexer._fs_probe.probe_mount``
  (the single real call site, reached via the lazy import inside
  :func:`~personalscraper.indexer._fs_capability.resolve_capability`) so the
  orchestrator resolves and threads the capability itself (proves the wiring).

The core proof obligations:

- **exFAT within the 2 s bucket**: a stale stored mtime that differs from the
  on-disk mtime by < 2 s normalises equal → tier-1 *match* → cheap
  generation-only update, no OSHash recompute, no repair.
- **exFAT beyond the 2 s bucket**: a stale stored mtime > 2 s away → tier-1
  *mismatch* → OSHash recomputed (content unchanged → ``tier1_drift_only``).
- **HFS+ sub-second jitter**: < 1 s stored/on-disk mtime difference normalises
  equal → no drift.
- **NTFS regression**: a changed stored ctime → tier-1 *mismatch* (ctime
  participates on NTFS), exactly the legacy behaviour.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer._fs_capability import EXFAT, HFSPLUS, NTFS_MACFUSE
from personalscraper.indexer._fs_probe import MountInfo
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo, file_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.scanner._db_writes import _compute_oshash as _real_compute_oshash
from personalscraper.indexer.scanner._modes.incremental import _scan_disk_incremental
from personalscraper.indexer.scanner._modes.quick import _run_paranoia_branch
from personalscraper.indexer.schema import DiskRow

pytestmark = pytest.mark.multifs

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"
_OSHASH_PATCH = "personalscraper.indexer.scanner._modes.incremental._compute_oshash"
_PROBE_PATCH = "personalscraper.indexer._fs_probe.probe_mount"

_ONE_SECOND_NS = 1_000_000_000
_THREE_SECONDS_NS = 3_000_000_000
_HALF_SECOND_NS = 500_000_000

# A fixed, well-in-the-past mtime aligned to BOTH the 1 s (HFS+) and 2 s (exFAT)
# bucket boundaries: 1.7e18 ns is an exact multiple of 2_000_000_000.  Pinning
# the on-disk mtime here makes the within-/beyond-bucket deltas deterministic
# (a relative shift can otherwise straddle an absolute bucket boundary).  It is
# also in the past, so ``_safe_mtime_ns`` never clamps it.
_ALIGNED_BASE_NS = 1_700_000_000_000_000_000


# ---------------------------------------------------------------------------
# Helpers (mirroring tests/indexer/test_scanner.py conventions)
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


def _seed_one_video(conn: sqlite3.Connection, mount: str, filename: str = "film.mkv") -> tuple[DiskRow, int, int]:
    """Full-scan a disk holding one video file; return (disk, file_id, on_disk_mtime_ns).

    After this, the ``media_file`` row carries the file's real on-disk tier-1
    fingerprint and a valid OSHash, ready for a stale-mtime mutation.

    Args:
        conn: Open SQLite connection.
        mount: Fake mount-point path (already created on the fake FS).
        filename: Video filename to create under *mount*.

    Returns:
        Tuple ``(disk_row, file_id, on_disk_mtime_ns)`` where ``on_disk_mtime_ns``
        equals :data:`_ALIGNED_BASE_NS` (pinned via ``os.utime`` before the scan).
    """
    file_path = f"{mount}/{filename}"
    Path(file_path).write_bytes(b"V" * 4096)
    # Pin the on-disk mtime to a clean, past, bucket-aligned boundary so the
    # within-/beyond-bucket deltas applied by each test are deterministic.
    os.utime(file_path, ns=(_ALIGNED_BASE_NS, _ALIGNED_BASE_NS))

    disk = _insert_disk(conn, mount)
    with patch(_GUARD_PATCH, return_value=None):
        scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

    row = file_repo.find_by_path_and_filename(
        conn,
        _root_path_id(conn, disk.id),
        filename,
    )
    assert row is not None, "media_file row must exist after full scan"
    assert row.oshash is not None, "oshash must be populated by the full scan"
    assert row.mtime_ns == _ALIGNED_BASE_NS, f"stored mtime should match the pinned on-disk value; got {row.mtime_ns}"
    return disk, row.id, row.mtime_ns


def _root_path_id(conn: sqlite3.Connection, disk_id: int) -> int:
    """Return the ``path.id`` of the disk-root (rel_path = "") for *disk_id*."""
    conn.row_factory = sqlite3.Row
    pid = conn.execute(
        "SELECT id FROM path WHERE disk_id = ? AND rel_path = '' LIMIT 1",
        (disk_id,),
    ).fetchone()
    conn.row_factory = None
    assert pid is not None, "root path row must exist after full scan"
    return int(pid["id"])


def _set_stored_tier1(
    conn: sqlite3.Connection,
    file_id: int,
    *,
    mtime_ns: int | None = None,
    ctime_ns: int | None = None,
) -> None:
    """Backdate / mutate the *stored* tier-1 fields of a ``media_file`` row.

    Used to create a controlled stored-vs-on-disk delta so the next incremental
    compare exercises a specific normalisation branch.

    Args:
        conn: Open SQLite connection.
        file_id: ``media_file.id`` to mutate.
        mtime_ns: New stored ``mtime_ns`` (skipped when ``None``).
        ctime_ns: New stored ``ctime_ns`` (skipped when ``None``).
    """
    if mtime_ns is not None:
        conn.execute("UPDATE media_file SET mtime_ns = ? WHERE id = ?", (mtime_ns, file_id))
    if ctime_ns is not None:
        conn.execute("UPDATE media_file SET ctime_ns = ? WHERE id = ?", (ctime_ns, file_id))


def _scan_generation(conn: sqlite3.Connection, file_id: int) -> int:
    """Return the current ``scan_generation`` of a ``media_file`` row."""
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT scan_generation FROM media_file WHERE id = ?", (file_id,)).fetchone()
    conn.row_factory = None
    assert r is not None
    return int(r["scan_generation"])


def _stored_oshash(conn: sqlite3.Connection, file_id: int) -> str | None:
    """Return the currently stored ``oshash`` for *file_id* (or ``None``)."""
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT oshash FROM media_file WHERE id = ?", (file_id,)).fetchone()
    conn.row_factory = None
    assert r is not None
    return r["oshash"]


def _has_repair(conn: sqlite3.Connection, file_id: int) -> bool:
    """Return whether a ``repair_queue`` row exists for *file_id*."""
    conn.row_factory = sqlite3.Row
    r = conn.execute(
        "SELECT id FROM repair_queue WHERE scope = 'file' AND scope_id = ?",
        (file_id,),
    ).fetchone()
    conn.row_factory = None
    return r is not None


def _run_incremental(conn: sqlite3.Connection, disk: DiskRow, mount: str, capability: object) -> None:
    """Drive ``_scan_disk_incremental`` directly with an explicit *capability*.

    ``dir_mtime_reliable=False`` forces a full per-file walk so the changed file
    is always visited; ``merkle_root`` is reset to ``None`` (Merkle miss without
    tripping the bulk-change guard, which only fires when a stored root exists).

    Args:
        conn: Open SQLite connection.
        disk: Disk row to scan.
        mount: Mount-point path.
        capability: The :class:`FilesystemCapability` to thread to the compare.
    """
    disk_repo.update_merkle_root(conn, disk.id, None)
    fresh = disk_repo.get_by_id(conn, disk.id)
    assert fresh is not None
    _scan_disk_incremental(
        conn,
        fresh,
        mount,
        [0],
        [0],
        2,
        [0],
        False,  # dir_mtime_reliable
        capability=capability,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# exFAT — within the 2 s bucket (no spurious drift)
# ---------------------------------------------------------------------------


class TestExfatWithinBucket:
    """exFAT: stored mtime < 2 s from on-disk + zeroed ctime → treated unchanged."""

    def test_within_two_seconds_no_recompute_no_repair(self, fs: "FakeFilesystem") -> None:
        """A 1 s stored/on-disk mtime gap on exFAT is absorbed by the 2 s bucket.

        The stored ctime is also zeroed to prove exFAT drops ctime: despite the
        ctime difference, no tier-1 mismatch fires, so ``_compute_oshash`` is
        never invoked and no repair is enqueued — only the generation is bumped.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatWithin"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        # Shift stored mtime +1 s (same 2 s bucket as the aligned base) and
        # clobber stored ctime.  on_disk == base, stored == base+1s → both floor
        # to base on exFAT → tier-1 match.
        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _ONE_SECOND_NS, ctime_ns=0)

        with patch(_OSHASH_PATCH) as mock_oshash:
            _run_incremental(conn, disk, mount, EXFAT)

        assert mock_oshash.call_count == 0, "exFAT within-bucket must NOT recompute OSHash"
        assert not _has_repair(conn, file_id), "no repair expected for within-bucket exFAT mtime jitter"
        assert _scan_generation(conn, file_id) == 2, "generation must be bumped on the cheap-skip path"


# ---------------------------------------------------------------------------
# exFAT — beyond the 2 s bucket (real tier-1 mismatch, content unchanged)
# ---------------------------------------------------------------------------


class TestExfatBeyondBucket:
    """exFAT: stored mtime > 2 s from on-disk → tier-1 mismatch → OSHash recompute."""

    def test_beyond_two_seconds_recomputes_oshash_no_repair(self, fs: "FakeFilesystem") -> None:
        """A 3 s stored/on-disk mtime gap crosses the exFAT bucket → mismatch.

        The mismatch forces an OSHash recompute; since the bytes are unchanged
        the recomputed hash matches the stored value (``tier1_drift_only`` path),
        so no repair is enqueued but the OSHash *was* recomputed.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatBeyond"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        # Shift stored mtime +3 s → different 2 s bucket (base+2s) than the
        # on-disk base → tier-1 mismatch.
        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _THREE_SECONDS_NS)

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            _run_incremental(conn, disk, mount, EXFAT)

        assert mock_oshash.call_count >= 1, "exFAT beyond-bucket must recompute OSHash"
        assert not _has_repair(conn, file_id), "content unchanged → tier1_drift_only, no repair"


# ---------------------------------------------------------------------------
# exFAT — DOCUMENTED LIMITATION: same-size, within-bucket, content-changed is
# invisible to incremental tier-1 (FIX-3). This is the asymmetric coarse-FS
# blind spot the reviewer flagged sev-9 — it must stay PINNED, not "fixed".
# ---------------------------------------------------------------------------


class TestExfatMissedDriftLimitation:
    """PINNED documented limitation — DO NOT "fix" this accidentally.

    On a coarse-granularity filesystem (exFAT, 2 s mtime bucket), an in-place
    content edit that (a) keeps the byte count identical AND (b) lands within
    the same 2 s mtime bucket as the stored value is **invisible** to the
    incremental tier-1 compare: ``normalize_tier1`` floors the mtime, drops
    ctime, and sees an unchanged ``(size, mtime_bucket)`` tuple → cheap-skip
    taken → ``_compute_oshash`` is never invoked → the changed bytes are never
    re-hashed. The full / Merkle scan is the backstop for this window.

    This is a deliberate, accepted trade-off of the coarse-FS tier-1 path, NOT
    a bug. The companion unit test ``test_size_difference_trips_even_within_same_bucket``
    pins the other half: any size delta DOES trip tier-1, so the blind spot is
    narrowed to same-size + within-bucket + content-changed only.
    """

    def test_same_size_within_bucket_content_change_is_missed(self, fs: "FakeFilesystem") -> None:
        """ExFAT incremental tier-1 misses a same-size, within-bucket content edit.

        Uses the REAL ``_compute_oshash`` (not mocked) so the assertion is about
        the genuine code path: because tier-1 matches, the OSHash is never
        recomputed, the stored hash still points at the ORIGINAL content, and no
        repair is enqueued — only the generation is bumped. This is the
        documented coarse-FS limitation; the full/merkle scan is the backstop.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatMissedDrift"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)
        original_oshash = _stored_oshash(conn, file_id)
        assert original_oshash is not None

        # Rewrite the file to DIFFERENT content of the SAME length (4096 bytes):
        # the OSHash (size + head/tail hash) genuinely changes, but the size is
        # identical so tier-1 size is unchanged.
        film = f"{mount}/film.mkv"
        Path(film).write_bytes(b"W" * 4096)
        # Pin the on-disk mtime +1 s — same 2 s exFAT bucket as the stored value,
        # so the bucketed mtime is also unchanged.
        os.utime(film, ns=(on_disk_mtime + _ONE_SECOND_NS, on_disk_mtime + _ONE_SECOND_NS))

        # Wrap the REAL hash function so we can assert it was NEVER called.
        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            _run_incremental(conn, disk, mount, EXFAT)

        assert mock_oshash.call_count == 0, (
            "DOCUMENTED LIMITATION: exFAT same-size + within-bucket content change "
            "is invisible to incremental tier-1 (cheap-skip taken, no recompute). "
            "If this now recomputes, the limitation changed — update the docstring, "
            "do not silently flip the assertion."
        )
        assert _stored_oshash(conn, file_id) == original_oshash, (
            "the stored OSHash must still point at the ORIGINAL content (never re-hashed)"
        )
        assert not _has_repair(conn, file_id), "no repair for an undetected within-bucket same-size edit"
        assert _scan_generation(conn, file_id) == 2, "generation must still be bumped on the cheap-skip path"


# ---------------------------------------------------------------------------
# exFAT — real drift (beyond bucket + content change) → repair enqueue (FIX-6)
# ---------------------------------------------------------------------------


class TestExfatRealDriftEnqueuesRepair:
    """Coarse FS still enqueues a repair when a real, detectable drift occurs."""

    def test_beyond_bucket_content_change_enqueues_content_drift_repair(self, fs: "FakeFilesystem") -> None:
        """exFAT: beyond-2 s mtime mismatch + real content change → repair enqueue.

        Complements the missed-drift limitation: when the mtime moves into a
        DIFFERENT 2 s bucket (so tier-1 mismatches) AND the bytes actually
        changed, the recomputed OSHash differs from the stored value, no rename
        candidate matches, and ``enqueue_repair(reason='content_drift')`` fires.
        Proves the repair path still works on a coarse filesystem.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatRealDrift"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)
        original_oshash = _stored_oshash(conn, file_id)
        assert original_oshash is not None

        # Real content change AND a mtime shift into a different 2 s bucket
        # (+3 s) so tier-1 genuinely mismatches on exFAT.
        film = f"{mount}/film.mkv"
        Path(film).write_bytes(b"W" * 8192)
        os.utime(film, ns=(on_disk_mtime + _THREE_SECONDS_NS, on_disk_mtime + _THREE_SECONDS_NS))

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            _run_incremental(conn, disk, mount, EXFAT)

        assert mock_oshash.call_count >= 1, "beyond-bucket mismatch must recompute the OSHash"
        assert _stored_oshash(conn, file_id) != original_oshash, "the new content's OSHash must be persisted"
        assert _has_repair(conn, file_id), "a real content drift on exFAT must enqueue a content_drift repair"


# ---------------------------------------------------------------------------
# HFS+ — sub-second jitter (no drift)
# ---------------------------------------------------------------------------


class TestHfsplusSubSecond:
    """HFS+: stored mtime < 1 s from on-disk (same ctime) → treated unchanged."""

    def test_subsecond_jitter_no_recompute(self, fs: "FakeFilesystem") -> None:
        """A 0.5 s stored/on-disk mtime gap on HFS+ stays within the 1 s bucket.

        ctime is left untouched (HFS+ keeps ctime), so the only difference is the
        sub-second mtime jitter, which the 1 s granularity absorbs → no OSHash
        recompute, no repair.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/HfsplusJitter"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        # Shift stored mtime +0.5 s (same 1 s bucket as the aligned base).  HFS+
        # keeps ctime, so pin the stored ctime to the live on-disk value (the
        # seed scan bumps the fake-FS ctime away from what it stored): then the
        # ONLY remaining difference is the sub-second mtime jitter we are testing.
        live_ctime = os.stat(f"{mount}/film.mkv").st_ctime_ns
        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _HALF_SECOND_NS, ctime_ns=live_ctime)

        with patch(_OSHASH_PATCH) as mock_oshash:
            _run_incremental(conn, disk, mount, HFSPLUS)

        assert mock_oshash.call_count == 0, "HFS+ sub-second jitter must NOT recompute OSHash"
        assert not _has_repair(conn, file_id), "no repair expected for HFS+ sub-second mtime jitter"
        assert _scan_generation(conn, file_id) == 2


# ---------------------------------------------------------------------------
# NTFS — regression: ctime change is a real tier-1 mismatch
# ---------------------------------------------------------------------------


class TestNtfsRegression:
    """NTFS: ctime participates in tier-1 → a stored ctime change forces a mismatch."""

    def test_ctime_change_triggers_mismatch_recompute(self, fs: "FakeFilesystem") -> None:
        """Changing only the stored ctime on NTFS produces a tier-1 mismatch.

        This pins the legacy behaviour: NTFS keeps ctime in the tier-1 tuple, so
        even with identical size + mtime, a differing ctime forces an OSHash
        recompute (content unchanged → ``tier1_drift_only``, no repair).
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NtfsCtime"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, _on_disk_mtime = _seed_one_video(conn, mount)

        # Keep size + mtime as stored; mutate ONLY the stored ctime to a clearly
        # different value so the tier-1 tuples diverge on NTFS.
        _set_stored_tier1(conn, file_id, ctime_ns=1)

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            _run_incremental(conn, disk, mount, NTFS_MACFUSE)

        assert mock_oshash.call_count >= 1, "NTFS ctime change must force an OSHash recompute (legacy behaviour)"
        assert not _has_repair(conn, file_id), "content unchanged → tier1_drift_only, no repair"


# ---------------------------------------------------------------------------
# End-to-end: orchestrator resolves + threads the capability via probe_mount
# ---------------------------------------------------------------------------


class TestOrchestratorThreadsCapability:
    """Prove ``scan()`` resolves the per-disk capability and threads it down."""

    def test_exfat_probe_makes_incremental_fs_aware(self, fs: "FakeFilesystem") -> None:
        """With ``probe_mount`` returning exFAT, a within-bucket gap is unchanged.

        Drives the *full* :func:`scan` entry point in incremental mode and
        monkeypatches the orchestrator's ``probe_mount`` to report exFAT for the
        disk.  A 1 s stored-vs-on-disk mtime gap (within the 2 s exFAT bucket)
        must therefore NOT trigger an OSHash recompute — confirming the
        capability flowed from the orchestrator all the way to the compare site.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExfatE2E"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _ONE_SECOND_NS, ctime_ns=0)
        disk_repo.update_merkle_root(conn, disk.id, None)
        fresh = disk_repo.get_by_id(conn, disk.id)
        assert fresh is not None

        exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())

        with patch(_OSHASH_PATCH) as mock_oshash:
            with patch(_PROBE_PATCH, return_value=exfat_info):
                with patch(_GUARD_PATCH, return_value=None):
                    with patch(
                        "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                        return_value=False,
                    ):
                        result = scan([fresh], ScanMode.incremental, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert mock_oshash.call_count == 0, (
            "orchestrator must thread the exFAT capability so the within-bucket gap is a no-op"
        )

    def test_ntfs_probe_keeps_ctime_sensitivity(self, fs: "FakeFilesystem") -> None:
        """With ``probe_mount`` returning NTFS, a stored ctime change still drifts.

        Mirror of the exFAT E2E test for the NTFS regression: the orchestrator
        resolves NTFS, ctime participates, so a stored ctime mutation forces an
        OSHash recompute end-to-end.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NtfsE2E"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, _on_disk_mtime = _seed_one_video(conn, mount)

        _set_stored_tier1(conn, file_id, ctime_ns=1)
        disk_repo.update_merkle_root(conn, disk.id, None)
        fresh = disk_repo.get_by_id(conn, disk.id)
        assert fresh is not None

        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            with patch(_PROBE_PATCH, return_value=ntfs_info):
                with patch(_GUARD_PATCH, return_value=None):
                    with patch(
                        "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                        return_value=False,
                    ):
                        result = scan([fresh], ScanMode.incremental, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert mock_oshash.call_count >= 1, "NTFS ctime change must still force a recompute end-to-end"


# ---------------------------------------------------------------------------
# Consistency (Phase 5 Task 5): the DiskConfig.fs_type override reaches the
# scanner — a disk that PROBES NTFS but is OVERRIDDEN to exFAT must scan with
# exFAT semantics (one shared resolver for transfer + scan).
# ---------------------------------------------------------------------------


class TestScannerHonorsFsTypeOverride:
    """``scan(fs_type_overrides=...)`` must beat the auto-detected probe result."""

    def test_override_exfat_beats_ntfs_probe_no_spurious_drift(self, fs: "FakeFilesystem") -> None:
        """Probe → NTFS, override → exFAT: a within-2 s mtime gap must NOT drift.

        Proves the operator override threads from ``scan()`` all the way to the
        per-file tier-1 compare via the SHARED ``resolve_capability`` resolver.
        Under the (ignored) NTFS probe, the zeroed stored ctime would force a
        tier-1 mismatch + OSHash recompute; under the exFAT override, ctime is
        dropped and the 1 s mtime gap is absorbed by the 2 s bucket → no
        recompute. ``probe_mount`` returning NTFS makes the override the only
        thing that can produce exFAT semantics.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/OverrideExfat"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        # +1 s mtime (same 2 s exFAT bucket) and a clobbered ctime: on NTFS this
        # is a drift; on exFAT it is a no-op.
        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _ONE_SECOND_NS, ctime_ns=0)
        disk_repo.update_merkle_root(conn, disk.id, None)
        fresh = disk_repo.get_by_id(conn, disk.id)
        assert fresh is not None

        # Probe reports NTFS; the override map says exFAT for this exact mount.
        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())

        with patch(_OSHASH_PATCH) as mock_oshash:
            with patch(_PROBE_PATCH, return_value=ntfs_info):
                with patch(_GUARD_PATCH, return_value=None):
                    with patch(
                        "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                        return_value=False,
                    ):
                        result = scan(
                            [fresh],
                            ScanMode.incremental,
                            generation=2,
                            conn=conn,
                            # Keyed on the STABLE DiskRow.label (== DiskConfig.id),
                            # not the mount path — matches the orchestrator lookup.
                            fs_type_overrides={fresh.label: "exfat"},
                            event_bus=EventBus(),
                        )

        assert result.status == "ok"
        assert mock_oshash.call_count == 0, (
            "override must reach the scanner: exFAT semantics absorb the within-bucket gap "
            "despite the NTFS probe result"
        )

    def test_no_override_falls_back_to_ntfs_probe_drift(self, fs: "FakeFilesystem") -> None:
        """Same fixture, but WITHOUT the override → NTFS probe wins → ctime drift.

        The control case for ``test_override_exfat_beats_ntfs_probe...``: with an
        empty override map the probe-detected NTFS capability governs, ctime
        participates, and the zeroed stored ctime forces an OSHash recompute.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NoOverrideNtfs"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _ONE_SECOND_NS, ctime_ns=0)
        disk_repo.update_merkle_root(conn, disk.id, None)
        fresh = disk_repo.get_by_id(conn, disk.id)
        assert fresh is not None

        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            with patch(_PROBE_PATCH, return_value=ntfs_info):
                with patch(_GUARD_PATCH, return_value=None):
                    with patch(
                        "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                        return_value=False,
                    ):
                        result = scan(
                            [fresh],
                            ScanMode.incremental,
                            generation=2,
                            conn=conn,
                            event_bus=EventBus(),
                        )

        assert result.status == "ok"
        assert mock_oshash.call_count >= 1, (
            "without the override the NTFS probe governs: the zeroed ctime forces a recompute"
        )


# ---------------------------------------------------------------------------
# FIX-7: per-disk override map across TWO disks — each disk resolves its OWN
# capability (override applied per-disk via the orchestrator, not globally).
# ---------------------------------------------------------------------------


class TestPerDiskOverrideMapTwoDisks:
    """``fs_type_overrides`` is resolved per-disk: one overridden, one auto-detected."""

    def test_override_one_disk_other_autodetected(self, fs: "FakeFilesystem") -> None:
        """Two disks, one ``exfat`` override + one auto-detect → distinct capabilities.

        Both mounts PROBE as NTFS. The override map contains ONLY the first
        disk (→ exfat). After a single ``scan()`` over both disks:

        - Disk A (overridden exfat): a +1 s mtime gap + zeroed ctime is a no-op
          (exFAT drops ctime, buckets the mtime) → NO OSHash recompute for A.
        - Disk B (auto-detected NTFS): the same zeroed-ctime mutation IS a
          tier-1 mismatch (NTFS keeps ctime) → OSHash recompute for B.

        Asserting per-mount via the wrapped ``_compute_oshash`` call args proves
        the orchestrator resolved each disk's capability INDEPENDENTLY — the
        override is applied per-disk, not globally.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount_a = "/mnt/TwoDiskExfat"  # overridden → exfat
        mount_b = "/mnt/TwoDiskNtfs"  # auto-detected → ntfs
        Path(mount_a).mkdir(parents=True, exist_ok=True)
        Path(mount_b).mkdir(parents=True, exist_ok=True)

        disk_a, file_a, mtime_a = _seed_one_video(conn, mount_a)
        disk_b, file_b, _mtime_b = _seed_one_video(conn, mount_b)

        # Same mutation on both: +1 s mtime (within the exFAT 2 s bucket) and a
        # zeroed ctime. On exFAT this is a no-op; on NTFS the ctime change drifts.
        _set_stored_tier1(conn, file_a, mtime_ns=mtime_a + _ONE_SECOND_NS, ctime_ns=0)
        _set_stored_tier1(conn, file_b, ctime_ns=0)

        for d in (disk_a, disk_b):
            disk_repo.update_merkle_root(conn, d.id, None)
        fresh_a = disk_repo.get_by_id(conn, disk_a.id)
        fresh_b = disk_repo.get_by_id(conn, disk_b.id)
        assert fresh_a is not None and fresh_b is not None

        # Both mounts probe as NTFS; only disk A is overridden to exfat.
        def _probe(path: str) -> MountInfo:
            return MountInfo(mount_point=path, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            with patch(_PROBE_PATCH, side_effect=_probe):
                with patch(_GUARD_PATCH, return_value=None):
                    with patch(
                        "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                        return_value=False,
                    ):
                        result = scan(
                            [fresh_a, fresh_b],
                            ScanMode.incremental,
                            generation=2,
                            conn=conn,
                            # Keyed on the STABLE DiskRow.label (== DiskConfig.id):
                            # only disk A is overridden, by its label.
                            fs_type_overrides={fresh_a.label: "exfat"},
                            event_bus=EventBus(),
                        )

        assert result.status == "ok"

        # Partition the recompute calls by which mount's file was hashed.
        hashed_paths = [c.args[0] for c in mock_oshash.call_args_list]
        a_recomputes = [p for p in hashed_paths if p.startswith(mount_a + "/")]
        b_recomputes = [p for p in hashed_paths if p.startswith(mount_b + "/")]

        assert a_recomputes == [], "disk A (override → exfat) must absorb the within-bucket gap: no OSHash recompute"
        assert len(b_recomputes) >= 1, (
            "disk B (auto-detected → ntfs) keeps ctime: the zeroed ctime forces an OSHash recompute"
        )


# ---------------------------------------------------------------------------
# Phase 8 Task 3: the override map keys on the STABLE DiskRow.label
# (== DiskConfig.id), NOT the mutable DiskRow.mount_path. A remount that
# rewrites mount_path (so DiskRow.mount_path != str(DiskConfig.path)) must STILL
# apply the operator override on the scan side. The map is built via the REAL
# CLI key-builder (build_fs_type_overrides), so a regression that re-keyed on
# the mount path would make this test fail.
# ---------------------------------------------------------------------------


class TestOverrideSurvivesMountPathDivergence:
    """A remounted disk (mount_path != config path) still gets its override."""

    def test_override_applies_when_mount_path_diverges_from_config_path(self, fs: "FakeFilesystem") -> None:
        """Override survives a mount_path that no longer equals the config path.

        Simulates a remount: the ``DiskRow.mount_path`` is the NEW location while
        the ``DiskConfig.path`` still records the ORIGINAL one. They differ, but
        ``DiskConfig.id == DiskRow.label`` is unchanged. The override map is built
        by the production :func:`build_fs_type_overrides` (keyed on ``id``), so the
        orchestrator's ``ctx.fs_type_overrides.get(disk.label)`` lookup still hits.

        The proof: probe reports NTFS, override says exFAT. Under NTFS the zeroed
        stored ctime + within-bucket mtime would force an OSHash recompute; under
        the exFAT override it is absorbed. ``_compute_oshash`` is never called ⇒
        the exFAT override reached the scanner DESPITE mount_path != config path.

        A regression that keyed the map on ``str(DiskConfig.path)`` (the old code)
        would build ``{config_path: "exfat"}`` while the orchestrator looked up
        ``mount_path`` — a miss — so the NTFS probe would win and the recompute
        would fire, failing this test.
        """
        from personalscraper.conf.models.disks import DiskConfig  # noqa: PLC0415
        from personalscraper.indexer.commands._bootstrap import build_fs_type_overrides  # noqa: PLC0415

        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        # The disk's CURRENT mount (where the files actually live after remount).
        # The basename becomes the DiskRow.label, which doubles as the
        # DiskConfig.id below — so it must satisfy the ``^[a-z][a-z0-9_]*$`` id
        # pattern (lowercase).
        mount = "/mnt/remounted_new"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        # Same within-bucket mtime + zeroed ctime mutation as the sibling tests:
        # a drift under NTFS, a no-op under exFAT.
        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _ONE_SECOND_NS, ctime_ns=0)
        disk_repo.update_merkle_root(conn, disk.id, None)
        fresh = disk_repo.get_by_id(conn, disk.id)
        assert fresh is not None

        # The config still records the ORIGINAL (pre-remount) path. Its ``id``
        # matches the DiskRow.label (set by bootstrap from DiskConfig.id), but its
        # ``path`` deliberately DIFFERS from the current mount_path.
        original_config_path = Path("/mnt/OriginalBeforeRemount")
        assert str(original_config_path) != fresh.mount_path, "fixture must exercise a path divergence"
        disk_cfg = DiskConfig(id=fresh.label, path=original_config_path, fs_type="exfat", categories=["movies"])

        # Build the override map with the PRODUCTION key-builder, not a hand-seeded
        # literal — so the test exercises the real CLI→scan key contract.
        overrides = build_fs_type_overrides([disk_cfg])
        assert overrides == {fresh.label: "exfat"}, "key-builder must key on the stable DiskConfig.id"

        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            with patch(_PROBE_PATCH, return_value=ntfs_info):
                with patch(_GUARD_PATCH, return_value=None):
                    with patch(
                        "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                        return_value=False,
                    ):
                        result = scan(
                            [fresh],
                            ScanMode.incremental,
                            generation=2,
                            conn=conn,
                            fs_type_overrides=overrides,
                            event_bus=EventBus(),
                        )

        assert result.status == "ok"
        assert mock_oshash.call_count == 0, (
            "override keyed on DiskConfig.id must still reach the scanner even though "
            "mount_path != str(DiskConfig.path): exFAT semantics absorb the within-bucket gap"
        )


# ---------------------------------------------------------------------------
# Phase 8 Task 5: full → incremental no-op handoff on a COARSE FS. After a real
# full scan on an exFAT disk stores a (FS-aware, Task 1) merkle_root, an
# incremental with ZERO on-disk changes and the merkle_root LEFT INTACT must
# short-circuit: no walk, no OSHash recompute, no repair, merkle_root unchanged.
# This pins the idempotent-flooring guarantee now that the merkle gate is
# FS-aware — a regression that bucketed the full-scan store differently from the
# incremental recompute would force a spurious re-hash on the first incremental.
# ---------------------------------------------------------------------------


class TestFullToIncrementalNoOpHandoffCoarseFs:
    """A no-change incremental after a full exFAT scan is a pure no-op."""

    def test_incremental_after_full_exfat_is_noop_merkle_intact(self, fs: "FakeFilesystem") -> None:
        """Full → incremental with no changes on exFAT: merkle hit, no recompute.

        Both scans run under the exFAT override (keyed on the stable DiskRow.label)
        so the full-scan merkle_root store and the incremental recompute bucket with
        the SAME capability. With unchanged content and the stored root left intact,
        the incremental must take the Merkle short-circuit (``files_visited == 0``,
        the disk counted as skipped), invoke ``_compute_oshash`` zero times, enqueue
        no repair, and leave ``merkle_root`` byte-identical.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/exfat_noop"  # basename → DiskRow.label "exfat_noop"
        Path(mount).mkdir(parents=True, exist_ok=True)
        film = f"{mount}/film.mkv"
        Path(film).write_bytes(b"V" * 4096)
        os.utime(film, ns=(_ALIGNED_BASE_NS, _ALIGNED_BASE_NS))

        disk = _insert_disk(conn, mount)
        overrides = {disk.label: "exfat"}

        # Full scan under the exFAT override: stores the FS-aware merkle_root.
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, fs_type_overrides=overrides, event_bus=EventBus())

        after_full = disk_repo.get_by_id(conn, disk.id)
        assert after_full is not None
        assert after_full.merkle_root is not None, "full exFAT scan must store a merkle_root"
        stored_root = after_full.merkle_root

        # Incremental, ZERO on-disk changes, merkle_root deliberately LEFT INTACT.
        exfat_info = MountInfo(mount_point=mount, fs_type="exfat", raw_fs_type="exfat", flags=frozenset())

        with patch(_OSHASH_PATCH, wraps=_real_compute_oshash) as mock_oshash:
            with patch(_PROBE_PATCH, return_value=exfat_info):
                with patch(_GUARD_PATCH, return_value=None):
                    with patch(
                        "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                        return_value=True,
                    ):
                        result = scan(
                            [after_full],
                            ScanMode.incremental,
                            generation=2,
                            conn=conn,
                            fs_type_overrides=overrides,
                            event_bus=EventBus(),
                        )

        assert result.status == "ok"
        assert result.files_visited == 0, "merkle short-circuit must skip the walk entirely"
        assert result.disks_skipped == 1, "the unchanged disk must be counted as a Merkle-hit skip"
        assert mock_oshash.call_count == 0, "no OSHash recompute on an unchanged merkle-hit disk"

        n_repairs = conn.execute("SELECT COUNT(*) FROM repair_queue").fetchone()[0]
        assert n_repairs == 0, "a pure no-op incremental must enqueue no repair"

        after_incr = disk_repo.get_by_id(conn, disk.id)
        assert after_incr is not None
        assert after_incr.merkle_root == stored_root, "merkle_root must be byte-identical after the no-op incremental"


# ---------------------------------------------------------------------------
# FIX-4: quick-mode paranoia branch is FS-aware (coarse capability). This is the
# ONLY FS-aware compare site in quick mode and was untested with a coarse cap.
# ---------------------------------------------------------------------------


def _seed_paranoia_outbox_event(conn: sqlite3.Connection, rel_path: str) -> None:
    """Insert a scan_run + recent ``outbox.*`` scan_event referencing *rel_path*.

    The paranoia branch only inspects paths surfaced by recent outbox events, so
    a row is needed for :func:`_run_paranoia_branch` to re-stat the file.

    Args:
        conn: Open SQLite connection.
        rel_path: Disk-relative path stored in the event ``payload_json``.
    """
    scan_run_id = conn.execute(
        "INSERT INTO scan_run (generation, mode, started_at, status) VALUES (2, 'quick', ?, 'running')",
        (int(time.time()),),
    ).lastrowid
    conn.execute(
        "INSERT INTO scan_event (scan_id, ts, event, payload_json) VALUES (?, ?, 'outbox.move', ?)",
        (scan_run_id, int(time.time()), f'{{"rel_path": "{rel_path}"}}'),
    )


class TestQuickParanoiaCoarseFs:
    """The quick-mode paranoia compare buckets mtime via the per-disk capability.

    ``_run_paranoia_branch`` re-stats outbox-referenced paths and flags a tier-1
    mismatch (``indexer.scan.paranoia_recheck``). On a coarse filesystem (exFAT,
    2 s bucket) it must NOT flag within-bucket mtime jitter at the SAME size, but
    MUST flag a stored mtime that is more than one bucket away. This is the only
    FS-aware compare site in quick mode and was previously untested with a
    coarse capability.
    """

    def test_within_bucket_same_size_no_recheck(self, fs: "FakeFilesystem", caplog: pytest.LogCaptureFixture) -> None:
        """exFAT: within-2 s stored/on-disk mtime jitter (same size) → NO recheck."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ParanoiaExfatWithin"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        # On-disk mtime stays at the aligned base; stored mtime is +1 s (same 2 s
        # exFAT bucket). Same size → no real change for a coarse FS.
        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _ONE_SECOND_NS)
        _seed_paranoia_outbox_event(conn, "film.mkv")

        with caplog.at_level(logging.INFO):
            _run_paranoia_branch(conn, disk, mount, 86400, EXFAT)

        msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert not any("indexer.scan.paranoia_recheck" in m for m in msgs), (
            f"exFAT within-bucket same-size jitter must NOT trigger a paranoia recheck; got: {msgs}"
        )

    def test_beyond_bucket_same_size_recheck_logged(
        self, fs: "FakeFilesystem", caplog: pytest.LogCaptureFixture
    ) -> None:
        """exFAT: stored mtime > 2 s away (same size) → paranoia_recheck logged."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ParanoiaExfatBeyond"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk, file_id, on_disk_mtime = _seed_one_video(conn, mount)

        # Stored mtime +3 s → a different 2 s bucket than the on-disk base, even
        # at the same size: the coarse-FS compare still flags this.
        _set_stored_tier1(conn, file_id, mtime_ns=on_disk_mtime + _THREE_SECONDS_NS)
        _seed_paranoia_outbox_event(conn, "film.mkv")

        with caplog.at_level(logging.INFO):
            _run_paranoia_branch(conn, disk, mount, 86400, EXFAT)

        msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert any("indexer.scan.paranoia_recheck" in m for m in msgs), (
            f"a beyond-bucket stored mtime must trigger a paranoia recheck on exFAT; got: {msgs}"
        )
