# Audit 12 — NTFS / macFUSE Cache Pressure

**Date**: 2026-05-23
**Scope**: I/O paths that read files on the 4 NTFS-via-macFUSE storage disks
**Trigger**: User reports macOS Unified Buffer Cache (UBC) consuming 14–16 GB of RAM during normal pipeline operation.

## TL;DR

Four cumulative causes inflate macOS' UBC during indexer scans and dispatcher moves. **None of the read paths in the codebase ever evict pages from the cache** (`rg "MADV_DONTNEED|F_NOCACHE|MADV_FREE|posix_fadvise" --type py` returns zero hits). The two highest-impact fixes are localised and low-risk:

1. Remove `--checksum` from `rsync` in `dispatch/_transfer.py` (eliminates TB-scale redundant reads).
2. Replace `MADV_SEQUENTIAL` with `F_NOCACHE` on the fingerprint read path (prevents UBC accumulation during cold scans).

## Priority Summary

| Prio | Action | File(s) | Estimated gain |
|------|--------|---------|----------------|
| 🔴 P0 | Drop `--checksum` from rsync | `dispatch/_transfer.py:98,151` | Huge — removes TB-scale redundant reads on every merge |
| 🔴 P0 | Add `disable_cache()` + use `F_NOCACHE` on fingerprint reads | `indexer/_macos_io.py`, `indexer/fingerprint.py` | Big — prevents UBC accumulation during cold scans |
| 🟠 P1 | Remove `sequential_hint` call in mediainfo | `indexer/mediainfo.py:172-176` | Medium — kills the FUSE/UBC double-cache for headers |
| 🟠 P1 | Activate read-rate throttle, drop parallelism 4→2 | `config/indexer.json5`, `config.example/indexer.json5` | Medium — caps instantaneous cache ingest |
| 🟠 P1 | Add `--inplace` and `--omit-dir-times` to rsync | `dispatch/_transfer.py:91-101,144-154` | Medium — halves cache pressure on TV-show merges, avoids NTFS utime warnings |
| 🟢 P2 | Document `sudo purge` and `kern.maxvnodes` tuning | `docs/reference/storage.md` | Small — operational hygiene |
| 🟢 P2 | Optional `rsync && sudo purge` wrapper for >10 GB transfers | `dispatch/_transfer.py` (helper) | Small — defensive, only if symptom persists post P0/P1 |

## Symptoms

- `Activity Monitor` → "Cached Files" climbs to 14–16 GB during indexer scans.
- Memory pressure stays green (the cache is reclaimable), but co-resident processes (Plex, n8n, Home Assistant) suffer noticeable disk slowdowns mid-scan because the FUSE/UBC double-cache competes with their own working set.
- After scan completion the cache does not drop until pressure forces it.

## Root Causes (ranked by impact)

### Cause 1 — `rsync --checksum` in dispatcher (TB-scale waste)

**Files**: `personalscraper/dispatch/_transfer.py:91-101` (`rsync`) and `:144-154` (`rsync_merge`).

```python
cmd = [
    "rsync", "-a",
    "--no-perms", "--no-owner", "--no-group",
    "--partial",
    "--checksum",          # ← reads both source AND dest in full
    "--exclude=.DS_Store",
    "--exclude=._*",
]
```

`--checksum` forces rsync to read **every byte of source and destination** to compute MD5 before deciding what to transfer. For a 50 GB movie merge, that's 100 GB through the NTFS-FUSE layer just for the comparison, then the actual transfer on top. For a TV-show merge across an existing folder of 40 episodes, the cache hit can exceed 500 GB.

The default `size + mtime` heuristic is sufficient for a media library where files never change in place — the only mutations are full-file replacements (movies) or new-episode additions (TV shows), both detectable by size or absence.

### Cause 2 — `MADV_SEQUENTIAL` without `MADV_DONTNEED` on fingerprint path

**Files**: `personalscraper/indexer/_macos_io.py:107-114` (`sequential_hint`), called from `indexer/fingerprint.py:154,214` and `indexer/mediainfo.py:174`.

```python
mm = mmap.mmap(fd, file_size, access=mmap.ACCESS_READ)
try:
    mm.madvise(mmap.MADV_SEQUENTIAL)   # triggers aggressive readahead
finally:
    mm.close()
```

Two compounding problems:

1. **`MADV_SEQUENTIAL` triggers aggressive readahead**: the macOS VM subsystem responds by prefetching 1–4 MiB ahead of the actual read. For a fingerprint operation that only consumes 64 KiB head + 64 KiB tail, the kernel pulls in *megabytes per file*. Multiplied by tens of thousands of video files during a cold scan, this alone accounts for several GiB of cache.

2. **No symmetric eviction call**: nothing in the codebase ever calls `MADV_DONTNEED`, `MADV_FREE`, `F_NOCACHE`, or `posix_fadvise(POSIX_FADV_DONTNEED)`. Pages enter the UBC and stay until memory pressure forces eviction.

The fingerprint use case is **read-once**: the head/tail bytes are hashed, the digest is persisted to the indexer DB, and the file is never re-read in that session. The page cache contributes nothing.

### Cause 3 — Mediainfo also hints the cache without consuming the prefetched data

**File**: `personalscraper/indexer/mediainfo.py:172-176`

```python
_fd = os.open(path, os.O_RDONLY)
try:
    sequential_hint(_fd, offset=0, length=0)
finally:
    os.close(_fd)
```

The hint is issued on a Python-owned fd, then closed. libmediainfo subsequently opens its own fd internally. The prefetched pages may or may not still be hot when libmediainfo starts reading (depends on kernel scheduling and other I/O between the two opens) — but they're always charged to the UBC. The hint trades guaranteed cache pollution against an uncertain prefetch benefit.

For Matroska/WebM files the `_container_fastpath` parser (enzyme) reads only the EBML header at the file start, so even the in-theory benefit doesn't apply for the most common container.

### Cause 4 — 4-way parallelism with unlimited throttle

**File**: `config/indexer.json5:10,12`

```json5
max_workers_total: 4,           // one worker per disk, all four parallel
read_rate_mb_per_sec: null,     // unlimited
```

With 4 disks scanned concurrently and no per-second cap, peak cache ingest exceeds what macOS can evict under steady-state conditions, especially while USB-3 bus contention slows the actual eviction-triggering writes elsewhere on the system.

The throttle infrastructure (`indexer/_throttle.py`) is already wired through `_acquire_read_tokens` calls in `fingerprint.py` and `mediainfo.py` — it's purely a config change to activate it.

## Recommendations

### Phase A — Drop `--checksum` (1 line × 2)

**Patch**:
```diff
--- a/personalscraper/dispatch/_transfer.py
+++ b/personalscraper/dispatch/_transfer.py
@@ -95,7 +95,6 @@ def rsync(source: Path, dest: Path, delete: bool = False) -> bool:
         "--no-owner",
         "--no-group",
         "--partial",
-        "--checksum",
         "--exclude=.DS_Store",
         "--exclude=._*",
     ]
@@ -148,7 +147,6 @@ def rsync_merge(...):
         "--no-owner",
         "--no-group",
         "--partial",
-        "--checksum",
         "--exclude=.DS_Store",
         "--exclude=._*",
         "--backup",
```

**Rationale**: Default `size + mtime` is correct for an immutable media library. If a future invariant check needs full-content verification, expose it as an explicit `personalscraper verify --deep` flag rather than burning cache on every routine move.

**Risk**: low. The only failure mode would be missing a transfer where source and destination have identical size+mtime but different content — impossible in this pipeline since moves are full-file replacements or merges of *new* episodes (distinct filenames).

**Test impact**: any test that asserts `--checksum` appears in the rsync argv (grep `tests/` for `--checksum`) will need updating.

**Companion flag additions (Phase A.2)** — same patch, while editing the rsync argv:

```diff
@@ -95,7 +95,9 @@ def rsync(source: Path, dest: Path, delete: bool = False) -> bool:
         "--no-perms",
         "--no-owner",
         "--no-group",
+        "--no-times",            # NTFS-FUSE doesn't honour utimes() reliably
+        "--omit-dir-times",      # avoid spurious 'failed to set times' warnings
+        "--inplace",             # write directly to destination, halves cache pressure for large files
         "--partial",
         "--exclude=.DS_Store",
```

- `--inplace`: avoids the rsync default of writing to `<file>.tmp` then renaming. The default doubles cache footprint for the duration of the transfer (both temp and final exist briefly). On a media library where partial corruption from interrupted transfers is non-fatal (the source still exists in staging), `--inplace` is the correct choice.
- `--no-times` / `--omit-dir-times`: mount has `noatime`; mtime updates on NTFS-FUSE sometimes warn even when they succeed. Suppressing avoids log noise and a small amount of journal write pressure.

### Phase B — Add `F_NOCACHE` helper and switch the fingerprint path

**New function in `personalscraper/indexer/_macos_io.py`**:

```python
def disable_cache(fd: int) -> None:
    """Disable UBC caching on this fd for read-once operations.

    Issues fcntl(fd, F_NOCACHE, 1) on Darwin. Pages read through this fd
    bypass the unified buffer cache entirely — appropriate for fingerprint
    head/tail reads where the bytes are hashed once and the digest stored
    in the indexer DB.

    Unlike F_RDADVISE (which has an arm64 variadic-ABI issue documented
    above), F_NOCACHE takes a single int argument and works correctly
    through Python's fcntl extension.

    On non-Darwin: no-op.
    """
    if not _IS_DARWIN:
        return
    try:
        import fcntl
        F_NOCACHE = 48
        fcntl.fcntl(fd, F_NOCACHE, 1)
    except (OSError, ValueError):
        return
```

**Replace `sequential_hint` calls in `fingerprint.py`**:

```diff
--- a/personalscraper/indexer/fingerprint.py
+++ b/personalscraper/indexer/fingerprint.py
@@ -25,7 +25,7 @@
-from personalscraper.indexer._macos_io import sequential_hint
+from personalscraper.indexer._macos_io import disable_cache
@@ -151,9 +151,9 @@ def oshash(path: Path) -> str:
     fd: int = os.open(path, os.O_RDONLY)
     try:
-        sequential_hint(fd, offset=0, length=0)
+        disable_cache(fd)
@@ -211,9 +211,9 @@ def xxh3_partial(path: Path, ...):
     fd: int = os.open(path, os.O_RDONLY)
     try:
-        sequential_hint(fd, offset=0, length=0)
+        disable_cache(fd)
```

**Rationale**: head/tail hash reads are pure read-once. `F_NOCACHE` is strictly better than `MADV_SEQUENTIAL` here because it both prevents prefetch *and* keeps pages out of the cache.

**Verify with a one-file experiment first** (see "Validation" below) before rolling out across both call sites.

### Phase C — Remove the hint from `mediainfo.py`

**Patch**:
```diff
--- a/personalscraper/indexer/mediainfo.py
+++ b/personalscraper/indexer/mediainfo.py
@@ -169,12 +169,9 @@ class MediaInfoWrapper:
-        # Advise the OS to read the file sequentially before pymediainfo opens
-        # it internally. [...]
-        _fd = os.open(path, os.O_RDONLY)
-        try:
-            sequential_hint(_fd, offset=0, length=0)
-        finally:
-            os.close(_fd)
+        # No explicit prefetch hint: libmediainfo opens its own fd internally
+        # and reads sequentially, which gets natural kernel readahead. The
+        # previous mmap+MADV_SEQUENTIAL hint on a separate Python fd polluted
+        # the UBC without a reliable prefetch benefit (the two fds don't
+        # coordinate). See audit/12-ntfs-cache-pressure.md §Cause-3.
```

**Rationale**: the hint targets a different fd than the one libmediainfo actually uses, so the benefit is unreliable while the cache cost is guaranteed. Removing it strictly reduces RAM with no expected performance regression.

**Risk**: low. If profiling later shows a measurable slowdown on cold scans of large MKV files, reintroduce the hint specifically for files not handled by the enzyme fastpath.

### Phase D — Activate the throttle and reduce parallelism

**Patch** to `config/indexer.json5` and `config.example/indexer.json5`:

```diff
-      max_workers_total: 4,
-      read_rate_mb_per_sec: null,
+      max_workers_total: 2,
+      read_rate_mb_per_sec: 80,
```

**Rationale**: per `docs/reference/storage.md`, USB-3 sequential throughput is ~100 MB/s per disk. With 4 disks on a shared hub the bus is already the bottleneck — 4-way parallel doesn't double real throughput, but it does quadruple instantaneous cache ingest. 2 workers + 80 MB/s cap aligns the indexer with the physical bus while letting macOS keep up with eviction.

**Risk**: scan duration may increase 20–30 % in wall-clock time. Acceptable trade-off; reversible.

### Phase E — Operational documentation

Add a section to `docs/reference/storage.md` titled "UBC Pressure During Scans":

```markdown
## UBC Pressure During Scans

A full-array indexer scan reads tens of thousands of file headers from
NTFS-via-macFUSE mounts. Even with the cache-bypass mitigations in
`fingerprint.py` and `mediainfo.py`, residual UBC growth is normal.

### Diagnostic commands

    # Distinguish reclaimable cache from real wired/app memory
    vm_stat
    top -l 1 -o mem | head -20
    memory_pressure

    # Identify which NTFS driver is in use
    mount | grep -i ntfs
    kextstat | grep -i ntfs
    brew list | grep -iE 'ntfs|paragon|tuxera|fuse'

If `Activity Monitor` shows the growth under "Cached Files" (yellow), it
is reclaimable and benign. If the growth appears under "Wired" or against
the macFUSE process itself, the driver is leaking and a remount is needed.

### Releasing cache

To force release after a scan completes:

    sudo purge

To bound the vnode cache (defaults to ~260 000 entries on macOS, which is
oversized for a 4-disk media library):

    sudo sysctl -w kern.maxvnodes=100000

`kern.maxvnodes` is volatile — to persist, add to `/etc/sysctl.conf`.
```

### Phase F (optional, P2) — Post-transfer purge wrapper

If P0/P1 mitigations turn out to be insufficient (re-measure after deployment), wrap large rsync transfers with a deferred purge:

```python
# In personalscraper/dispatch/_transfer.py, after a successful large rsync:
PURGE_THRESHOLD_BYTES = 10 * 1024**3   # 10 GB
if transferred_bytes > PURGE_THRESHOLD_BYTES:
    subprocess.run(["sudo", "-n", "purge"], check=False, timeout=30)
```

Requires a `sudoers` entry to allow `purge` without password prompt:

```
izno ALL=(ALL) NOPASSWD: /usr/sbin/purge
```

**Do not implement this preemptively** — only if measurements after Phases A–D still show UBC growth above ~6 GB during typical operation. The sudoers requirement adds operational complexity that should be justified by data.

## Validation

Before committing Phase B, run an empirical check on a single file to confirm `F_NOCACHE` behaves as expected on the user's macOS 14.5 / arm64 system.

### ACC-12.B.1 — F_NOCACHE does not raise ENOTTY on arm64

```bash
python3 -c "
import os, fcntl
fd = os.open('/Volumes/Disk1/medias/films/'+os.listdir('/Volumes/Disk1/medias/films')[0], os.O_RDONLY)
try:
    fcntl.fcntl(fd, 48, 1)  # F_NOCACHE
    print('OK')
finally:
    os.close(fd)
"
```

**Expected output**: `OK` (single line, no traceback). If `OSError: [Errno 25] Inappropriate ioctl for device` appears, the arm64 ABI issue documented for `F_RDADVISE` in `_macos_io.py` also affects `F_NOCACHE` — fall back to `mmap.madvise(MADV_DONTNEED)` issued *after* the read in fingerprint.py.

### ACC-12.B.2 — Cache footprint measurement (qualitative)

```bash
sudo purge
vm_stat | grep 'File-backed pages'
# Run a cold scan on Disk1 only
personalscraper library-index --mode full --disk Disk1 --budget 600
vm_stat | grep 'File-backed pages'
```

**Expected outcome**: post-scan `File-backed pages` increase by < 500 000 pages (~2 GB at 4 KiB pages) on a Disk1 with ~1 000 video files. Pre-fix baseline on the same disk typically shows 1 500 000+ pages.

### ACC-12.A.1 — rsync argv no longer contains `--checksum`

```bash
rg -n '"--checksum"' personalscraper/dispatch/_transfer.py tests/
```

**Expected output**: zero matches.

### ACC-12.D.1 — Throttle activated and parallelism capped

```bash
python3 -c "
import json5, pathlib
cfg = json5.loads(pathlib.Path('config/indexer.json5').read_text())
scan = cfg['indexer']['scan']
assert scan['max_workers_total'] == 2, scan['max_workers_total']
assert scan['read_rate_mb_per_sec'] == 80, scan['read_rate_mb_per_sec']
print('OK')
"
```

**Expected output**: `OK`.

Also check that `tests/indexer/test_fingerprint.py` still passes — it currently mocks `sequential_hint`; the mock target will change to `disable_cache`.

## Expected Outcome

| Metric | Before | After (estimate) |
|--------|--------|------------------|
| Peak UBC during full scan | 14–16 GB | 2–4 GB |
| `rsync_merge` cache pressure for a 50-episode TV show update | ~150 GB read through UBC | ~5 GB (only new episodes) |
| Cold scan wall-clock (4 × 6 TB) | 4–6 h (per `storage.md`) | 5–8 h |
| Risk of Plex / n8n slowdown mid-scan | High | Low |

## Integration with Existing Plan

Suggested placement in the tech-debt feature plan:

- **Phase A + B + C** are localised, low-risk, and unblock Plex/n8n co-tenancy issues immediately. Could slot into `phase-03-observability.md` (since they reduce cross-process I/O interference visible in observability metrics) or `phase-04-path-cleanup.md`, or warrant their own sub-phase `phase-03b-cache-discipline`.
- **Phase D** (config change) is a one-line edit but changes scan timings used elsewhere — coordinate with whichever phase touches launchd scheduling.
- **Phase E** (docs) goes into `phase-09-archive-docs.md`.
- **Phase F** (sudoers + purge wrapper) is gated on post-deployment measurement; do not schedule until P0/P1 results are known.

### Suggested commit sequence

```
fix(dispatch): drop --checksum, add --inplace and --no-times to rsync
feat(indexer): add disable_cache() helper using F_NOCACHE on Darwin
refactor(indexer): use disable_cache() instead of sequential_hint on fingerprint reads
refactor(indexer): remove sequential_hint from mediainfo (libmediainfo opens its own fd)
chore(indexer): cap parallelism to 2 and enable 80 MB/s read throttle
docs(storage): document UBC pressure mitigation and diagnostic commands
```

Each commit is independently revertible. P0 fixes (first two commits) can ship without waiting for the rest.

### Parallel-execution note

If this audit's work is started while another agent is executing Phase 5 (Conformity / Protocol drop / scraper refactor), **zero file overlap** exists between the two sets:

- Phase 5 touches: `api/metadata/_base.py`, `api/torrent/_contracts.py`, `api/torrent/_factory.py`, `scraper/{tv,movie}_service.py`, `scraper/_xref.py`, `scraper/nfo_generator.py`, related CLI commands.
- This audit touches: `dispatch/_transfer.py`, `indexer/_macos_io.py`, `indexer/fingerprint.py`, `indexer/mediainfo.py`, `config/indexer.json5`, `docs/reference/storage.md`, `tests/indexer/test_fingerprint.py`.

To execute in parallel safely, use a separate git worktree on a dedicated branch (`fix/ntfs-cache`), keep `IMPLEMENTATION.md` untouched (the Phase 5 agent writes to it), and open this work as an independent PR mergeable in any order relative to the tech-debt branch.

## Out of Scope

Items the audit considered but is **not** recommending:

- Switching from macFUSE to Paragon/Tuxera NTFS driver — out of scope for a code-side tech-debt phase; would warrant its own infra ticket.
- Per-process memory limits via `launchctl limit` — too blunt; would degrade other functionality.
- Switching the indexer's SQLite cache config — orthogonal; SQLite uses its own page cache (`PRAGMA cache_size`), not the UBC.

## References

- `docs/reference/storage.md` — existing NTFS/macFUSE mount-flag guidance
- `personalscraper/indexer/_macos_io.py` — module docstring explains the F_RDADVISE arm64 ABI gotcha (relevant when picking between `fcntl` and `mmap.madvise`)
- DESIGN §11.6 — read-rate throttle rationale (already implemented, currently inactive)
- macOS `fcntl(2)` man page — `F_NOCACHE` definition
- `docs/reference/feature-lifecycle.md` — ACCEPTANCE criterion executable-command convention (used for `ACC-12.*` items in §Validation)
