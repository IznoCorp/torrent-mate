# Phase 5 — Make indexer tier-1 drift FS-aware (HIGHER RISK — hot scan path)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

> **RE-SCOPED 2026-05-29.** The original plan targeted `drift.py::reconcile_file`,
> which a grep proved is **dead/test-only code** (zero production callers — only
> `tests/indexer/test_drift.py`, `test_drift_e2e.py`, `tests/e2e/test_indexer_racy_mtime.py`).
> The **live** tier-1 drift comparison is in `scanner/_modes/incremental.py` and
> `scanner/_modes/quick.py`. The full scan (`_walker.py` via `fingerprint_tier1`)
> only **stores** raw fingerprints and never compares — it needs no change _in
> this phase_. This re-scoped plan targets the real paths. `reconcile_file` is
> left untouched (dead code; flagged for tech-debt-2 removal, out of scope here).
>
> **Phase-8 follow-up (2026-05-29):** the Merkle/dir-mtime _gating_ layer in
> `_walker.py` (`_build_disk_fingerprints` / `_sample_fresh_fingerprints`) was
> later made FS-aware too — it buckets mtime via the disk capability so the
> Merkle short-circuit, the bulk-change freeze, and the dir-mtime skip are all
> coarse-FS-safe. See `phase-08-retro-fixes.md` Task 1. The full-scan raw
> _storage_ path is still unchanged.

**Goal:** Stop exFAT/ext4 perpetual re-hashing by making the live tier-1
comparison FS-aware. Introduce one centralized, pure `normalize_tier1` helper
that reads `tier1_uses_ctime` and `mtime_granularity_ns` from the dest disk's
`FilesystemCapability`, and call it at both live comparison sites. Thread the
per-disk capability through the scanner mirroring the existing
`dir_mtime_reliable` plumbing.

**NTFS invariant (the safety anchor):** `ntfs_macfuse` has
`tier1_uses_ctime=True` and `mtime_granularity_ns=1`. Therefore
`normalize_tier1(size, mtime_ns, ctime_ns, NTFS_MACFUSE) == (size, mtime_ns, ctime_ns)`
— byte-identical to the current inline tuples. The new branches (ctime drop,
mtime rounding) are **only** exercised for exFAT/HFS+. The default parameter
`capability=NTFS_MACFUSE` means any call site not yet threaded is unchanged.
APFS/ext4 also have `granularity=1`/`ctime=True` → identical.

**Why higher risk:** this touches the hottest indexer code (every file, every
incremental/quick scan). The risk is bounded by (a) the NTFS-identical helper,
(b) the full existing drift suite as a regression net, (c) unit tests pinning
the NTFS no-op.

**Architecture:**

- `fingerprint.py` gains `round_mtime_ns(mtime_ns, capability)` and
  `normalize_tier1(size, mtime_ns, ctime_ns, capability)` — pure, no I/O.
- `incremental.py` replaces its inline `t1_stored`/`t1_current` tuples with
  `normalize_tier1(...)` on both sides, using the disk's capability.
- `quick.py` rounds both mtimes via `round_mtime_ns` before the size/mtime
  compare (quick mode never reads ctime — only mtime granularity applies).
- `_scan_orchestrator._scan_one_disk` resolves the per-disk capability via
  `probe_mount(disk.mount_path)` and passes it to `_scan_disk_incremental` /
  `_scan_disk_quick` (mirroring how `dir_mtime_reliable` is passed). It also
  computes an effective per-disk `dir_mtime_reliable` honouring
  `capability.dir_mtime_reliable_default` when not `None`.
- `_scan_disk_full` / the full-scan raw-storage path in `_walker.py` are **not**
  changed in this phase (full scan stores raw, never compares). _(Phase-8 later
  made `_walker.py`'s Merkle/dir-mtime fingerprint helpers FS-aware — see the
  re-scope note above.)_

**Capability source (one shared resolver — delivered, not deferred):** the
scanner and the transfer layer both resolve through the **same**
`resolve_capability(path, fs_type_override)` (Task 5 below), so the
`DiskConfig.fs_type` operator override is authoritative across scan _and_
transfer — they can never diverge. When no override is given the type is
auto-detected via `probe_mount`; an unrecognised token / unmounted path falls
back to `unknown` == `ntfs_macfuse` (conservative: full ctime + exact mtime →
never skips a real change). (An earlier draft of this plan called threading the
override into the scanner "out of scope here"; that was superseded by Task 5,
which delivered it.)

**Tech Stack:** `personalscraper.indexer._fs_capability`, `personalscraper.indexer._fs_probe`, `os.stat_result`.

---

## Gate (prerequisites from Phase 4)

Verify:

```bash
python -c "from personalscraper.conf.models.disks import DiskConfig; print(DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs').fs_type)"
# expected: apfs

make check
# expected: exit 0
```

---

## Files

| Action | Path                                                    |
| ------ | ------------------------------------------------------- |
| Modify | `personalscraper/indexer/fingerprint.py`                |
| Modify | `personalscraper/indexer/scanner/_modes/incremental.py` |
| Modify | `personalscraper/indexer/scanner/_modes/quick.py`       |
| Modify | `personalscraper/indexer/scanner/_scan_orchestrator.py` |
| Create | `tests/indexer/test_tier1_fs_aware.py`                  |
| Create | `tests/indexer/test_scan_fs_aware.py`                   |

(`drift.py::reconcile_file` is deliberately NOT in scope — dead code.)

---

## Task 1 — Add the centralized FS-aware tier-1 helpers (TDD)

**Files:**

- Modify: `personalscraper/indexer/fingerprint.py`
- Create: `tests/indexer/test_tier1_fs_aware.py`

- [ ] **Step 1.1: Write the failing unit tests first** in `tests/indexer/test_tier1_fs_aware.py`.

Cover, using the real capability singletons (`NTFS_MACFUSE`, `APFS`, `HFSPLUS`, `EXFAT`, `EXT4` from `_fs_capability`):

- **NTFS byte-identical**: `normalize_tier1(s, m, c, NTFS_MACFUSE) == (s, m, c)` for several `(s, m, c)`.
- **APFS / ext4 identical**: same as NTFS (gran=1, ctime=True) → 3-tuple, mtime unrounded.
- **exFAT**: `normalize_tier1(s, m, c, EXFAT)` drops ctime → `(s, round_mtime_ns(m, EXFAT))`; two mtimes within the same 2 s bucket normalize equal; a 3 s apart pair normalize unequal.
- **HFS+**: keeps ctime, rounds mtime to 1 s; sub-second jitter normalizes equal.
- **round_mtime_ns**: gran=1 → identity; gran=2e9 → floor to 2 s bucket.

These MUST fail initially (functions don't exist yet) — confirms wiring.

- [ ] **Step 1.2: Implement the helpers** in `fingerprint.py`:

```python
from personalscraper.indexer._fs_capability import FilesystemCapability, NTFS_MACFUSE


def round_mtime_ns(mtime_ns: int, capability: FilesystemCapability) -> int:
    """Floor an mtime to the capability's granularity bucket.

    Args:
        mtime_ns: Raw ``st_mtime_ns``.
        capability: Filesystem capability (provides ``mtime_granularity_ns``).

    Returns:
        ``mtime_ns`` unchanged when granularity is 1 (NTFS/APFS/ext4); otherwise
        floored to the nearest ``mtime_granularity_ns`` bucket (HFS+ 1 s, exFAT 2 s).
    """
    gran = capability.mtime_granularity_ns
    return (mtime_ns // gran) * gran if gran > 1 else mtime_ns


def normalize_tier1(
    size: int, mtime_ns: int, ctime_ns: int, capability: FilesystemCapability
) -> tuple[int, ...]:
    """Capability-aware tier-1 fingerprint used for drift comparison.

    For ``ntfs_macfuse`` (and APFS/ext4: granularity=1, ctime=True) this returns
    ``(size, mtime_ns, ctime_ns)`` — byte-identical to the legacy inline tuples,
    so the NTFS scan path is unchanged. exFAT drops ctime (unreliable) and rounds
    mtime to 2 s; HFS+ rounds mtime to 1 s.

    Args:
        size: ``st_size``.
        mtime_ns: Raw ``st_mtime_ns``.
        ctime_ns: Raw ``st_ctime_ns`` (caller passes ``stored.ctime_ns or 0``).
        capability: Filesystem capability for the disk being scanned.

    Returns:
        A 3-tuple ``(size, mtime_bucket, ctime_ns)`` when the FS has reliable
        ctime, else a 2-tuple ``(size, mtime_bucket)``.
    """
    m = round_mtime_ns(mtime_ns, capability)
    if capability.tier1_uses_ctime:
        return (size, m, ctime_ns)
    return (size, m)
```

Leave `fingerprint_tier1` (raw 3-tuple) unchanged — it is used by the full scan
for storage; comparison normalises both stored and current at compare time.

- [ ] **Step 1.3: Run the unit tests (must pass) and commit.**

```bash
pytest tests/indexer/test_tier1_fs_aware.py -v
git add personalscraper/indexer/fingerprint.py tests/indexer/test_tier1_fs_aware.py
git commit -m "feat(multi-filesystem): add normalize_tier1/round_mtime_ns FS-aware tier-1 helpers (NTFS identical)"
```

---

## Task 2 — Resolve + thread per-disk capability through the scanner

**Files:**

- Modify: `personalscraper/indexer/scanner/_scan_orchestrator.py`

- [ ] **Step 2.1:** In `_scan_one_disk`, after the mount/circuit guards (the `disk: DiskRow` is in scope), resolve the disk capability and an effective dir-mtime flag:

```python
from personalscraper.indexer._fs_capability import capability_for
from personalscraper.indexer._fs_probe import probe_mount

_info = probe_mount(disk.mount_path)
disk_capability = capability_for(_info.fs_type if _info is not None else "unknown")

# Capability may hard-wire dir-mtime reliability; else use the session probe.
if disk_capability.dir_mtime_reliable_default is not None:
    effective_dir_mtime_reliable = disk_capability.dir_mtime_reliable_default
else:
    effective_dir_mtime_reliable = ctx.dir_mtime_reliable
```

For NTFS: `dir_mtime_reliable_default is None` → `effective == ctx.dir_mtime_reliable` (the session probe) → unchanged.

- [ ] **Step 2.2:** Pass `disk_capability` and `effective_dir_mtime_reliable` into the `_scan_disk_incremental` and `_scan_disk_quick` dispatch calls (replace the `ctx.dir_mtime_reliable` argument with `effective_dir_mtime_reliable`, and append `disk_capability`). Do **not** change the `_scan_disk_full` call (full scan needs neither).

- [ ] **Step 2.3:** Add `capability: FilesystemCapability = NTFS_MACFUSE` as the last parameter of `_scan_disk_incremental`, `_walk_dir_incremental`, `_scan_disk_quick` (and any quick walker), forwarding it down to the comparison site exactly as `dir_mtime_reliable` is forwarded. The default keeps any un-threaded caller NTFS-identical.

---

## Task 3 — Apply `normalize_tier1` at the two live comparison sites

**Files:**

- Modify: `personalscraper/indexer/scanner/_modes/incremental.py`
- Modify: `personalscraper/indexer/scanner/_modes/quick.py`

- [ ] **Step 3.1: incremental.py** — replace (≈ lines 446-447):

```python
t1_stored = (existing.size_bytes, existing.mtime_ns, existing.ctime_ns or 0)
t1_current = (st.st_size, mtime_ns_val, ctime_ns_val or 0)
```

with:

```python
t1_stored = normalize_tier1(existing.size_bytes, existing.mtime_ns, existing.ctime_ns or 0, capability)
t1_current = normalize_tier1(st.st_size, mtime_ns_val, ctime_ns_val or 0, capability)
```

Storage of tier-1 fields (the `UPDATE ... SET size_bytes/mtime_ns/ctime_ns`
statements) stays raw — only the comparison is normalised. Add the
`from personalscraper.indexer.fingerprint import normalize_tier1` import.

- [ ] **Step 3.2: quick.py** — quick mode selects only `size_bytes, mtime_ns`
      (no ctime). Replace (≈ line 142):

```python
if st.st_size != stored_size or st.st_mtime_ns != stored_mtime_ns:
```

with granularity-aware mtime comparison:

```python
if (
    st.st_size != stored_size
    or round_mtime_ns(st.st_mtime_ns, capability) != round_mtime_ns(stored_mtime_ns, capability)
):
```

Add the `from personalscraper.indexer.fingerprint import round_mtime_ns` import.
(NTFS gran=1 → identity → unchanged.)

- [ ] **Step 3.3: Run the full existing drift + scanner suites — MUST stay green** (the NTFS regression net):

```bash
pytest tests/indexer/test_drift.py tests/indexer/test_drift_e2e.py tests/indexer/test_scanner.py -v
```

- [ ] **Step 3.4: Commit.**

```bash
git add personalscraper/indexer/scanner/_modes/incremental.py personalscraper/indexer/scanner/_modes/quick.py personalscraper/indexer/scanner/_scan_orchestrator.py
git commit -m "feat(multi-filesystem): incremental+quick tier-1 compare is FS-aware via normalize_tier1; per-disk capability threaded"
```

---

## Task 4 — Integration tests: real scan, FS-aware, NTFS unchanged

**Files:**

- Create: `tests/indexer/test_scan_fs_aware.py`

- [ ] **Step 4.1:** Write integration tests that seed a small DB + temp files and
      run the **incremental** mode (and a **quick**-mode test) through the real
      scanner with an injected capability:

- **exFAT no spurious drift:** seed a file row; on rescan present the same file
  with an mtime shifted < 2 s and a changed/zeroed ctime; with the disk probed
  as exFAT (monkeypatch `_scan_orchestrator.probe_mount` to return an exFAT
  `MountInfo`), assert the file is treated as unchanged (generation bumped, no
  repair enqueued, no OSHash recompute).
- **exFAT drift beyond bucket:** mtime shifted > 2 s with unchanged content →
  tier-1 mismatch path taken (OSHash recompute confirms content unchanged).
- **HFS+ sub-second jitter:** mtime shifted < 1 s → unchanged.
- **NTFS regression:** same fixtures with the disk probed as NTFS → identical to
  current behaviour (ctime change → tier-1 mismatch).

Prefer driving `_scan_disk_incremental` / `_scan_disk_quick` directly with an
explicit `capability=` argument where that keeps the test focused; use the
`probe_mount` monkeypatch path for at least one end-to-end assertion that the
orchestrator resolves and threads the capability.

- [ ] **Step 4.2: Run + commit.**

```bash
pytest tests/indexer/test_scan_fs_aware.py -v
git add tests/indexer/test_scan_fs_aware.py
git commit -m "test(multi-filesystem): integration tests for FS-aware incremental/quick scan (exFAT/HFS+/NTFS)"
```

---

## Task 5 — Consistency: honor `DiskConfig.fs_type` override in the scanner (one resolver everywhere)

**Why:** Phase 4 made the **transfer** path (Dispatcher) honor the
`DiskConfig.fs_type` operator override, but the scanner (Task 2 above) resolves
capability via `probe_mount` auto-detect only. That is an inconsistency — one
knob, two behaviours. The override MUST be authoritative across the whole
pipeline (transfer **and** scan), via a single shared resolver so the two
layers can never diverge.

**Files:**

- Modify: `personalscraper/indexer/_fs_capability.py`
- Modify: `personalscraper/dispatch/dispatcher.py`
- Modify: `personalscraper/indexer/scanner/_scan_orchestrator.py`
- Modify: `personalscraper/indexer/scanner/__init__.py`
- Modify: `personalscraper/indexer/commands/scan.py`
- Create/extend tests covering both layers.

- [ ] **Step 5.1: Add the single shared resolver** in `_fs_capability.py`:

```python
def resolve_capability(path: str, fs_type_override: str | None = None) -> FilesystemCapability:
    """Resolve a disk's capability: explicit override beats FsProbe auto-detect.

    Single source of truth for BOTH the dispatch (transfer) layer and the
    indexer scanner, so ``DiskConfig.fs_type`` is honoured uniformly.

    Args:
        path: Disk mount/scan-root path to probe when no override is given.
        fs_type_override: Canonical fs-type string from ``DiskConfig.fs_type``;
            when not ``None`` it wins and the probe is skipped entirely.

    Returns:
        The resolved capability (override → auto-detect → NTFS-safe ``unknown``).
    """
    if fs_type_override is not None:
        return capability_for(fs_type_override)
    from personalscraper.indexer._fs_probe import probe_mount  # local: avoid import cost at module load
    info = probe_mount(path)
    return capability_for(info.fs_type if info is not None else "unknown")
```

- [ ] **Step 5.2: Dispatcher delegates to it.** Replace the body of
      `_resolve_disk_capability(disk)` with `return resolve_capability(str(disk.path), disk.fs_type)`.
      Behaviour is identical (Phase 4 tests must still pass) — this removes the
      duplicate resolution logic.

- [ ] **Step 5.3: Scanner honors the override.** Add `fs_type_overrides: dict[str, str]`
      to `_DiskWalkContext` (run-wide; default empty dict). In `_scan_one_disk`,
      replace the Task-2 `probe_mount(...)` call with:

```python
disk_capability = resolve_capability(
    disk.mount_path, ctx.fs_type_overrides.get(disk.mount_path)
)
```

- [ ] **Step 5.4: Plumb the map from `scan()`.** Add a keyword-only
      `fs_type_overrides: dict[str, str] | None = None` parameter to `scan()`; pass
      `fs_type_overrides or {}` into the `_DiskWalkContext` build. Default `None`
      preserves current behaviour for every other caller/test.

- [ ] **Step 5.5: Build the map in the CLI command.** In
      `personalscraper/indexer/commands/scan.py`, where `scan(...)` is invoked (it
      already has `cfg`), build and pass:

```python
fs_type_overrides={str(d.path): d.fs_type for d in cfg.disks if d.fs_type is not None}
```

(`DiskRow.mount_path == str(DiskConfig.path)`, so the keys match the scanner's lookup.)

- [ ] **Step 5.6: Tests.**
  - Unit `resolve_capability`: override beats probe; `None` → probe; unprobeable → `unknown`; an override of `"exfat"` on a path that probes NTFS returns `EXFAT`.
  - Dispatcher: existing Phase 4 override test still green (delegation preserves behaviour).
  - Scanner end-to-end: a disk whose `probe_mount` returns **NTFS** but with `fs_type_overrides={mount_path: "exfat"}` must scan with EXFAT semantics (mtime within 2 s → no spurious drift) — proving the override reaches the scanner.

- [ ] **Step 5.7: Commit.**

```bash
git add personalscraper/indexer/_fs_capability.py personalscraper/dispatch/dispatcher.py personalscraper/indexer/scanner/_scan_orchestrator.py personalscraper/indexer/scanner/__init__.py personalscraper/indexer/commands/scan.py tests/
git commit -m "feat(multi-filesystem): unify capability resolution — scanner honors DiskConfig.fs_type override (one resolver, transfer+scan consistent)"
```

---

## Task 6 — Phase gate (milestone commit reserved for orchestrator)

- [ ] **Step 6.1: Branch coverage on new helpers + branches.**

```bash
pytest tests/indexer/test_tier1_fs_aware.py tests/indexer/test_scan_fs_aware.py --cov=personalscraper/indexer/fingerprint --cov-report=term-missing
```

- [ ] **Step 6.2: Full quality gate.**

```bash
make lint && make test && make check
# expected: exit 0
```

- [ ] **Step 6.3:** Do NOT make the milestone commit — the orchestrator owns it.
      Leave the tree clean after the Task 5 commit.

---

## Acceptance criteria for this phase

```bash
# AC-06: exFAT capability disables ctime and sets 2s granularity (table, unchanged)
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('exfat'); print(c.tier1_uses_ctime, c.mtime_granularity_ns)"
# expected: False 2000000000

# AC-NEW-1: NTFS normalize_tier1 is byte-identical to the legacy tuple
python -c "from personalscraper.indexer.fingerprint import normalize_tier1; from personalscraper.indexer._fs_capability import NTFS_MACFUSE; print(normalize_tier1(10, 123, 456, NTFS_MACFUSE) == (10, 123, 456))"
# expected: True

# AC-NEW-2: exFAT drops ctime + buckets mtime
python -c "from personalscraper.indexer.fingerprint import normalize_tier1; from personalscraper.indexer._fs_capability import EXFAT; print(normalize_tier1(10, 1_700_000_001_000_000_000, 999, EXFAT))"
# expected: (10, 1700000000000000000)

# AC-NEW-3: shared resolver — override beats auto-detect (one resolver for transfer + scan)
python -c "from personalscraper.indexer._fs_capability import resolve_capability, EXFAT; print(resolve_capability('/Volumes/Disk1', 'exfat') is EXFAT)"
# expected: True

# AC-14: full gate
make check
# expected: exit 0

# AC-17: smoke
python -c "import personalscraper; print('ok')"
# expected: ok
```
