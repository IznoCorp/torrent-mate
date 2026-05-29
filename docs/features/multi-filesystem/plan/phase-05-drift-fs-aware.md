# Phase 5 — Make indexer tier-1 drift FS-aware (HIGHER RISK — defer-able)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop exFAT and ext4 perpetual re-hashing by making `drift.py::reconcile_file`
read `tier1_uses_ctime` and `mtime_granularity_ns` from the dest disk's
`FilesystemCapability`. The NTFS and APFS paths (ctime=True, granularity=1) are
byte-identical to the current code. This is the only higher-risk phase.

**NTFS invariant:** `ntfs_macfuse` capability has `tier1_uses_ctime=True` and
`mtime_granularity_ns=1`. The tier-1 tuple for NTFS is therefore
`(size, clamped_mtime_ns, ctime_ns)` — identical to the current unconditional
implementation. The new branches are only exercised for exFAT/ext4.

**Defer option:** If no disk currently uses a non-NTFS filesystem, this phase
ships inert — the `ntfs_macfuse` default ensures zero runtime change. The
`reconcile_file` signature change is additive (default parameter). All new
branches are covered by tests before they ever run on real hardware.

**Architecture:** `reconcile_file` gains a `capability: FilesystemCapability =
NTFS_MACFUSE` parameter. Two conditional blocks control (a) ctime inclusion and
(b) mtime rounding. `_verify_dir_mtime_reliable` is consulted only when
`capability.dir_mtime_reliable_default is None`.

**Tech Stack:** `personalscraper.indexer._fs_capability`, `os.stat_result`.

---

## Gate (prerequisites from Phase 4)

Phase 4 produced:

- `DiskConfig.fs_type` optional override.
- `Dispatcher._disk_capabilities` dict using override-beats-autodetect.
- Capability-aware `db_path` validator.

Verify:

```bash
python -c "from personalscraper.conf.models.disks import DiskConfig; d=DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs'); print(d.fs_type)"
# expected: apfs

make check
# expected: exit 0
```

---

## Files

| Action | Path                                   |
| ------ | -------------------------------------- |
| Modify | `personalscraper/indexer/drift.py`     |
| Create | `tests/indexer/test_drift_fs_aware.py` |

---

## Task 1 — Write the FS-aware drift tests FIRST (TDD anchor)

The tests are written against the **current** `reconcile_file` signature to
establish what must not change (NTFS path), then extended to cover the new
capability-gated branches.

**Files:**

- Create: `tests/indexer/test_drift_fs_aware.py`

- [ ] **Step 1.1: Read `drift.py::reconcile_file` lines 132–280**

Key observations:

- `t1_current = (current_stat.st_size, clamped_mtime_ns, current_stat.st_ctime_ns)` (line 193)
- `t1_stored = (stored.size_bytes, stored.mtime_ns, stored.ctime_ns or 0)` (line 194)
- The function is called from scanner code; the capability will be threaded from
  `Dispatcher._disk_capabilities` keyed on `disk_id`.

- [ ] **Step 1.2: Create `tests/indexer/test_drift_fs_aware.py`**

```python
"""FS-aware drift tests — capability-gated tier-1 comparison.

Tests that:
- NTFS path (tier1_uses_ctime=True, granularity=1) is byte-identical to current.
- exFAT path (tier1_uses_ctime=False, granularity=2s) produces no spurious
  tier1_drift when mtime and ctime are within granularity noise.
- HFS+ path (tier1_uses_ctime=True, granularity=1s) rounds mtime before compare.
"""

import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.indexer._fs_capability import APFS, EXFAT, HFSPLUS, NTFS_MACFUSE, capability_for
from personalscraper.indexer.drift import reconcile_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stat(size: int, mtime_ns: int, ctime_ns: int) -> os.stat_result:
    """Build a fake os.stat_result with controllable size, mtime_ns, ctime_ns."""
    stat = MagicMock(spec=os.stat_result)
    stat.st_size = size
    stat.st_mtime_ns = mtime_ns
    stat.st_ctime_ns = ctime_ns
    return stat


def _make_db_with_file(
    conn: sqlite3.Connection,
    *,
    size: int,
    mtime_ns: int,
    ctime_ns: int | None,
    xxh3_partial: str = "aabbcc",
) -> tuple[int, int]:
    """Insert minimal disk/path/media_file rows and return (path_id, file_id)."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS disk (id INTEGER PRIMARY KEY, mount_path TEXT, label TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS path (id INTEGER PRIMARY KEY, rel_path TEXT, disk_id INTEGER)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS media_file (
            id INTEGER PRIMARY KEY,
            path_id INTEGER,
            filename TEXT,
            size_bytes INTEGER,
            mtime_ns INTEGER,
            ctime_ns INTEGER,
            xxh3_partial TEXT,
            scan_generation INTEGER DEFAULT 0,
            miss_strikes INTEGER DEFAULT 0,
            deleted_at TEXT
        )
        """
    )
    conn.execute("INSERT INTO disk VALUES (1, '/Volumes/Disk1', 'Disk1')")
    conn.execute("INSERT INTO path VALUES (1, 'Movies', 1)")
    conn.execute(
        "INSERT INTO media_file VALUES (1, 1, 'movie.mkv', ?, ?, ?, ?, 0, 0, NULL)",
        (size, mtime_ns, ctime_ns, xxh3_partial),
    )
    conn.commit()
    return 1, 1


# ---------------------------------------------------------------------------
# NTFS path — must be byte-identical to current unconditional behaviour
# ---------------------------------------------------------------------------


class TestNtfsPathUnchanged:
    """NTFS (tier1_uses_ctime=True, granularity=1) — unchanged vs current."""

    def test_ntfs_unchanged_when_size_mtime_ctime_match(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(":memory:")
        now_ns = time.time_ns()
        mtime_ns = now_ns - 10_000_000_000  # 10s ago
        ctime_ns = now_ns - 5_000_000_000

        path_id, _ = _make_db_with_file(conn, size=1000, mtime_ns=mtime_ns, ctime_ns=ctime_ns)
        stat = _make_stat(1000, mtime_ns, ctime_ns)

        result = reconcile_file(
            conn,
            disk_id=1,
            path_id=path_id,
            filename="movie.mkv",
            current_stat=stat,
            current_oshash_or_empty="",
            scan_started_at_ns=now_ns,
            racy_window_ns=5_000_000_000,
            capability=NTFS_MACFUSE,
        )
        assert result == "unchanged"

    def test_ntfs_ctime_change_triggers_tier1_drift(self, tmp_path: Path) -> None:
        """On NTFS, a ctime change with same content → tier1_drift."""
        conn = sqlite3.connect(":memory:")
        now_ns = time.time_ns()
        mtime_ns = now_ns - 20_000_000_000
        old_ctime = now_ns - 15_000_000_000
        new_ctime = now_ns - 5_000_000_000  # ctime changed

        path_id, _ = _make_db_with_file(
            conn, size=500, mtime_ns=mtime_ns, ctime_ns=old_ctime, xxh3_partial="deadbeef"
        )
        stat = _make_stat(500, mtime_ns, new_ctime)

        (tmp_path / "movie.mkv").write_bytes(b"x" * 500)

        with patch(
            "personalscraper.indexer.drift.xxh3_partial", return_value="deadbeef"
        ):
            result = reconcile_file(
                conn,
                disk_id=1,
                path_id=path_id,
                filename="movie.mkv",
                current_stat=stat,
                current_oshash_or_empty="",
                scan_started_at_ns=now_ns,
                racy_window_ns=1_000_000_000,
                capability=NTFS_MACFUSE,
            )
        assert result == "tier1_drift"


# ---------------------------------------------------------------------------
# exFAT path — no ctime, 2s mtime granularity
# ---------------------------------------------------------------------------


class TestExfatNoCtimeNoSpuriousDrift:
    """AC-06: exFAT disables ctime and uses 2s mtime granularity."""

    def test_exfat_no_spurious_drift_within_2s_granularity(self) -> None:
        """Two mtimes within the same 2s bucket must not cause tier1_drift."""
        conn = sqlite3.connect(":memory:")
        now_ns = time.time_ns()
        # Stored mtime: exact second boundary
        stored_mtime = 1_700_000_000 * 1_000_000_000
        # Live mtime: 1.5 seconds later — within the 2s exFAT bucket
        live_mtime = stored_mtime + 1_500_000_000

        path_id, _ = _make_db_with_file(
            conn, size=1000, mtime_ns=stored_mtime, ctime_ns=None
        )
        # exFAT has no ctime — use 0 to simulate
        stat = _make_stat(1000, live_mtime, 0)

        result = reconcile_file(
            conn,
            disk_id=1,
            path_id=path_id,
            filename="movie.mkv",
            current_stat=stat,
            current_oshash_or_empty="",
            scan_started_at_ns=now_ns,
            racy_window_ns=1_000_000_000,
            capability=EXFAT,
        )
        assert result == "unchanged", (
            "exFAT: mtime within 2s granularity bucket must not trigger drift"
        )

    def test_exfat_drift_beyond_granularity_escalates(self) -> None:
        """A 3-second mtime shift on exFAT (beyond 2s bucket) → escalates."""
        conn = sqlite3.connect(":memory:")
        now_ns = time.time_ns()
        stored_mtime = 1_700_000_000 * 1_000_000_000
        live_mtime = stored_mtime + 3_000_000_000  # 3s — crosses bucket boundary

        path_id, _ = _make_db_with_file(
            conn, size=1000, mtime_ns=stored_mtime, ctime_ns=None, xxh3_partial="aabbcc"
        )
        stat = _make_stat(1000, live_mtime, 0)

        with patch("personalscraper.indexer.drift.xxh3_partial", return_value="aabbcc"):
            result = reconcile_file(
                conn,
                disk_id=1,
                path_id=path_id,
                filename="movie.mkv",
                current_stat=stat,
                current_oshash_or_empty="",
                scan_started_at_ns=now_ns,
                racy_window_ns=1_000_000_000,
                capability=EXFAT,
            )
        # Content unchanged → tier1_drift (cosmetic mtime changed)
        assert result == "tier1_drift"


# ---------------------------------------------------------------------------
# HFS+ path — 1s mtime granularity
# ---------------------------------------------------------------------------


class TestHfsplusMtimeGranularity:
    """HFS+ uses 1s mtime granularity — sub-second jitter must not cause drift."""

    def test_hfsplus_sub_second_jitter_no_drift(self) -> None:
        conn = sqlite3.connect(":memory:")
        now_ns = time.time_ns()
        stored_mtime = 1_700_000_000 * 1_000_000_000
        # Sub-second jitter: 0.3s within the same second bucket
        live_mtime = stored_mtime + 300_000_000

        path_id, _ = _make_db_with_file(
            conn, size=2000, mtime_ns=stored_mtime, ctime_ns=stored_mtime
        )
        stat = _make_stat(2000, live_mtime, stored_mtime)

        result = reconcile_file(
            conn,
            disk_id=1,
            path_id=path_id,
            filename="movie.mkv",
            current_stat=stat,
            current_oshash_or_empty="",
            scan_started_at_ns=now_ns,
            racy_window_ns=1_000_000_000,
            capability=HFSPLUS,
        )
        assert result == "unchanged", (
            "HFS+: sub-second mtime jitter must not trigger drift"
        )
```

- [ ] **Step 1.3: Run the tests — they MUST FAIL (reconcile_file has no capability param yet)**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/test_drift_fs_aware.py -v 2>&1 | head -30
# expected: TypeError / FAILED — capability param does not exist yet
# This confirms the tests are wired to the right function.
```

- [ ] **Step 1.4: Commit the failing tests**

```bash
git add tests/indexer/test_drift_fs_aware.py
git commit -m "test(multi-filesystem): add FS-aware drift tests (failing — TDD anchor for reconcile_file)"
```

---

## Task 2 — Update `reconcile_file` in `drift.py`

**Files:**

- Modify: `personalscraper/indexer/drift.py`

- [ ] **Step 2.1: Add the import at the top of `drift.py`**

```python
from personalscraper.indexer._fs_capability import FilesystemCapability, NTFS_MACFUSE
```

- [ ] **Step 2.2: Update the `reconcile_file` signature**

Add `capability: FilesystemCapability = NTFS_MACFUSE` as the last parameter:

```python
def reconcile_file(
    conn: sqlite3.Connection,
    disk_id: int,
    path_id: int,
    filename: str,
    current_stat: os.stat_result,
    current_oshash_or_empty: str,
    scan_started_at_ns: int,
    racy_window_ns: int,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> ReconcileResult:
    """Classify a live file against its stored index row.

    (existing docstring — add to Args section:)

        capability: Filesystem capability for the disk being scanned.
            Defaults to ``NTFS_MACFUSE`` — byte-identical to the former
            unconditional tier-1 comparison.  Controls ctime inclusion and
            mtime granularity rounding.
    """
```

- [ ] **Step 2.3: Replace the tier-1 tuple construction (lines 188–194) with capability-aware logic**

Replace:

```python
# Clamp raw mtime before comparing (DESIGN §17.1 — future/pre-epoch guard).
now_ns = time.time_ns()
clamped_mtime_ns = clamp_mtime_ns(current_stat.st_mtime_ns, now_ns)

# Build tier-1 tuple using the (possibly clamped) mtime and raw ctime.
t1_current: tuple[int, int, int] = (current_stat.st_size, clamped_mtime_ns, current_stat.st_ctime_ns)
t1_stored: tuple[int, int, int] = (stored.size_bytes, stored.mtime_ns, stored.ctime_ns or 0)
```

With:

```python
# Clamp raw mtime before comparing (DESIGN §17.1 — future/pre-epoch guard).
now_ns = time.time_ns()
clamped_mtime_ns = clamp_mtime_ns(current_stat.st_mtime_ns, now_ns)

# Apply mtime granularity rounding for filesystems with coarse timestamps
# (HFS+ 1s, exFAT 2s).  granularity=1 (NTFS, APFS, ext4) is a no-op.
gran = capability.mtime_granularity_ns
if gran > 1:
    # Round both sides to the nearest granularity bucket (floor division).
    clamped_mtime_ns = (clamped_mtime_ns // gran) * gran
    stored_mtime_rounded = (stored.mtime_ns // gran) * gran
else:
    stored_mtime_rounded = stored.mtime_ns

# Build tier-1 tuple; optionally include ctime.
# For exFAT (tier1_uses_ctime=False) ctime is absent / unreliable — drop it.
# The stored side already tolerates NULL ctime (stored.ctime_ns or 0) so only
# the live side needs the conditional.
if capability.tier1_uses_ctime:
    t1_current: tuple[int, ...] = (current_stat.st_size, clamped_mtime_ns, current_stat.st_ctime_ns)
    t1_stored: tuple[int, ...] = (stored.size_bytes, stored_mtime_rounded, stored.ctime_ns or 0)
else:
    # exFAT / no-ctime FS: compare only (size, mtime-bucket).
    t1_current = (current_stat.st_size, clamped_mtime_ns)
    t1_stored = (stored.size_bytes, stored_mtime_rounded)
```

- [ ] **Step 2.4: Handle `dir_mtime_reliable_default` in the scanner call site (optional guard)**

In `scanner/_walker.py` or the scan orchestrator, wherever
`_verify_dir_mtime_reliable` is called, add a guard:

```python
# Use capability's default when available; otherwise run the runtime probe.
if capability.dir_mtime_reliable_default is not None:
    dir_mtime_reliable = capability.dir_mtime_reliable_default
else:
    dir_mtime_reliable = _verify_dir_mtime_reliable(disk_path)
```

This is an optional improvement in this phase; the default parameter on
`reconcile_file` already ensures the NTFS path is unchanged.

- [ ] **Step 2.5: Run the FS-aware drift tests (must now pass)**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/test_drift_fs_aware.py -v
# expected: all tests PASS
```

- [ ] **Step 2.6: Run the full drift test suite to confirm no regression**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/test_drift.py tests/indexer/test_drift_e2e.py -v
# expected: all tests PASS
```

- [ ] **Step 2.7: Commit the drift changes**

```bash
git add personalscraper/indexer/drift.py
git commit -m "feat(multi-filesystem): reconcile_file is FS-aware — exFAT no-ctime, HFS+ 1s mtime granularity"
```

---

## Task 3 — Thread capability through scanner call sites

**Files:**

- Modify: `personalscraper/indexer/scanner/_walker.py` (or scan orchestrator that calls `reconcile_file`)

- [ ] **Step 3.1: Find all call sites of `reconcile_file`**

```bash
rg "reconcile_file" -g '*.py' personalscraper/
# expected: shows call sites in scanner code
```

- [ ] **Step 3.2: Thread the disk's capability to each call site**

Each call site gains `capability=disk_capability` where `disk_capability` is
resolved from `Dispatcher._disk_capabilities[disk_id]` (or equivalently, from
`capability_for(disk.fs_type or probe_fs_type(disk.path))`). The default
`NTFS_MACFUSE` parameter means existing call sites without an explicit argument
are unaffected — add the argument only where the disk capability is available
in scope.

- [ ] **Step 3.3: Run the full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/ -v
# expected: all tests PASS
```

- [ ] **Step 3.4: Commit**

```bash
git add -u
git commit -m "refactor(multi-filesystem): thread FilesystemCapability through reconcile_file call sites"
```

---

## Task 4 — Phase gate + milestone commit

- [ ] **Step 4.1: Branch coverage check on new drift branches**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/test_drift_fs_aware.py --cov=personalscraper/indexer/drift --cov-report=term-missing -v
# expected: ≥90% branch coverage on new branches in drift.py
```

- [ ] **Step 4.2: Full quality gate**

```bash
make lint && make test && make check
# expected: exit 0, all green
```

- [ ] **Step 4.3: Milestone commit**

```bash
git add -u
git commit -m "chore(multi-filesystem): phase 5 gate — drift FS-aware, NTFS path unchanged, exFAT/HFS+ covered"
```

---

## Acceptance criteria for this phase

```bash
# AC-06: exFAT capability disables ctime and sets 2s granularity
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('exfat'); print(c.tier1_uses_ctime, c.mtime_granularity_ns)"
# expected: False 2000000000

# AC-14: full gate
make check
# expected: exit 0

# AC-17: smoke
python -c "import personalscraper; print('ok')"
# expected: ok
```
