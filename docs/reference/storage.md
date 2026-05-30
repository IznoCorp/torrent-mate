# Storage Reference

Storage disk layout, NTFS/macFUSE constraints, rsync flags, and disk space rules.

## Storage Disks

All 4 disks are **NTFS** formatted, mounted via **macFUSE** (ntfstool driver) over USB.

| Disk  | Mount                 | Filesystem | Categories                                                                                                                                                   |
| ----- | --------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Disk1 | /Volumes/Disk1/medias | NTFS       | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, series animes, spectacles, theatres, emissions |
| Disk2 | /Volumes/Disk2/medias | NTFS       | series, series animes                                                                                                                                        |
| Disk3 | /Volumes/Disk3/medias | NTFS       | films, films animations, films documentaires, series, series animations, series documentaires, spectacles, theatres, emissions                               |
| Disk4 | /Volumes/Disk4/medias | NTFS       | films, films animations, series, series animations, series documentaires                                                                                     |

## Move Rules (dispatch)

- **Movies** (films, animations, documentaires, spectacles, theatre): if a folder with the same name already exists on a disk, **replace it** with the new version from staging area.
- **TV Shows** (series, animations, documentaires): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

## NTFS via macFUSE constraints

- **No Unix permissions** — `chmod`, `chown`, `chgrp` are no-ops or fail with EPERM. All files appear as `rwxrwxrwx` owned by the mounting user.
- **rsync must use `--no-perms --no-owner --no-group`** — `rsync -a` (which includes `-pgo`) fails with `Operation not permitted` on set times/permissions. The dispatcher uses `-a --no-perms --no-owner --no-group` to work around this.
- **Mount flags**: `macfuse, local, synchronous, noatime, nobrowse` — `synchronous` means every write is committed immediately (slower but safer for USB).
- **`_force_rmtree` limitation** — `os.chmod()` before retry has no effect on NTFS. Deletion failures on `.actors/` or `.DS_Store` are NTFS metadata issues, not permission issues.

## Recommended Mount Flags for NTFS-via-macFUSE

The media indexer scanner checks for the following five flags at scan start and
emits a `WARNING` (`indexer.disk.mount_flags_missing`) if any are absent.
Missing flags do not abort the scan but degrade I/O performance or cause macOS
to inject unwanted metadata files.

| Flag                | Purpose                                                                                                                                                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `noatime`           | Disables access-time updates on every file read. Critical for large media libraries: without this, each sequential read during a scan triggers a write back to the NTFS journal, roughly doubling effective I/O and exhausting USB bandwidth.            |
| `noappledouble`     | Prevents macFUSE from creating `._<filename>` AppleDouble resource-fork sidecar files alongside every media file. These ghost files pollute directory listings and trigger false positives in the scanner's change detector.                             |
| `noapplexattr`      | Suppresses storage of macOS extended attributes (xattrs) inside the NTFS volume. Without this flag, Finder and Spotlight write `com.apple.metadata:*` xattrs to every touched file, causing unnecessary journal writes and inflating file sizes on NTFS. |
| `defer_permissions` | Allows unprivileged access to the mount without requiring SUID helpers. Needed when the volume is mounted by a regular user (the typical case with macFUSE on an Apple Silicon server). Without it, all file opens may fail with EPERM.                  |
| `allow_other`       | Permits processes running as other users (e.g. the Plex media server daemon) to traverse and read the mount. Without this flag, Plex cannot access files owned by the mounting user, leading to empty library scans.                                     |

> **Note**: `nodiratime` (directory access-time suppression) is Linux-only and
> is **not** in this list. macOS has no separate `nodiratime` flag; `noatime`
> already covers both file and directory access times on Darwin.

Example `/etc/fstab` or `ntfstool` mount invocation:

```
ntfstool mount --disk /dev/diskXsY --mountpoint /Volumes/DiskN \
    -o noatime,noappledouble,noapplexattr,defer_permissions,allow_other
```

## Disk Space Threshold

Unified formula:

```
free_space_gb >= max(min_free_gb, item_size_gb * 1.5)
```

The `Dispatcher` class selects the target disk for new items via `conf.resolver.pick_disk_for()`. A disk is eligible only when it is mounted, accepts the target category, and satisfies the free-space formula above. `get_disk_status()` returns a `DiskStatus` dataclass with the `free_space_gb` property.

Movie vs TV dispatch routing is inline in `process()` (no named `MOVIES_REPLACE`/`TVSHOWS_MERGE` constants): `dispatch_movie()` replaces the existing folder, `dispatch_tvshow()` merges new episodes into it.

## 24 TB Operations Guide

Operational guidelines for managing the full four-disk array (~24 TB total capacity).

### Cold Rebuild Rotation

A cold rebuild re-indexes a disk from scratch when its index is corrupt, stale, or
missing. With 6 TB disks and ~100 MB/s USB-3 sequential throughput, a full scan
takes roughly 60–90 minutes per disk. To avoid saturating the USB hub and blocking
the pipeline during normal operation, rotate cold rebuilds one disk at a time:

1. **Identify the target disk**: use `personalscraper library-status` to find disks
   with a stale generation or a high `unreachable_strikes` count.
2. **Unmount other disks** (optional but recommended): reduces USB contention and
   ensures the scanner can dedicate full bandwidth to the rebuild disk.
3. **Run a scoped full scan**: `personalscraper library-index --mode full --disk <label>`.
   The `--disk` flag limits the scan to one disk and forces `max_workers=1`
   (DESIGN §11.8), preventing accidental parallel I/O to neighbouring disks.
4. **Verify the result**: `personalscraper library-status --disk <label>` — confirm
   `generation` advanced and `unreachable_strikes` reset to 0.
5. **Rotate to the next disk** only after the previous rebuild completes and its
   `scan_run.status` is `'ok'`.

Recommended rotation cadence: one disk per week in normal operation, or on-demand
after any unclean unmount (power loss, USB disconnect during a scan).

### Budget Planning

Full-array operations (all 4 disks, full mode) consume significant I/O budget.
Use `budget_seconds` to cap wall-clock time and resume across multiple sessions:

| Operation                | Estimated duration | Recommended budget |
| ------------------------ | ------------------ | ------------------ |
| Full scan, 1 × 6 TB      | 60–90 min          | 5 400 s (90 min)   |
| Full scan, 4 × 6 TB      | 4–6 h              | 21 600 s (6 h)     |
| Incremental scan, 1 disk | 2–5 min            | 600 s (10 min)     |
| Incremental scan, all    | 8–20 min           | 1 800 s (30 min)   |
| Enrich pass, 1 disk      | 10–30 min          | 1 800 s (30 min)   |

The `budget_seconds` parameter is passed via the CLI flag `--budget` or
set in `config.json5` under `indexer.scan.budget_seconds`. When the budget is
exhausted the scanner writes a checkpoint and exits with `budget_exhausted=True`;
the next invocation resumes from the last checkpoint automatically.

For nightly scheduled scans (launchd), set the budget to ≤ 3 600 s (1 hour) to
ensure the job completes before the next wake window. Use `--mode quick` for
nightly runs, `--mode incremental` for more frequent scans (e.g. every few hours
during the day), and reserve `--mode full` for weekend maintenance windows.

## Indexer Cold-Rebuild Playbook

Use these steps after any of the following events:

- `library.db` is corrupted (`library-status` exits 1 with `IndexerCorruptError`).
- A disk was replaced and its volume UUID changed.
- The database was lost (e.g. the `paths.data_dir` directory deleted or the internal disk reformatted).
- An unclean unmount left the index inconsistent with the disks.

The default DB path is `paths.data_dir / "library.db"` (configurable via `indexer.db_path` in `config/indexer.json5`).

### Quick path — use `--rebuild`

```bash
# Quarantines the existing DB and runs a full Stage-A rescan from scratch.
personalscraper library-index --rebuild

# Verify the result
personalscraper library-status
```

The quarantined database is renamed to `<db_path>.corrupt-<unix_ts>` (e.g.
`library.db.corrupt-1714567890` inside the configured `data_dir`).

### Manual path (if `--rebuild` itself fails)

```bash
# 1. Remove or quarantine the corrupt database manually
mv .data/library.db .data/library.db.bak

# 2. Run a full scan — creates a fresh database
personalscraper library-index --mode full

# 3. Verify
personalscraper library-status
```

### Per-disk cold rebuild (disk replaced or UUID changed)

When only one disk needs rebuilding, scope the scan to avoid I/O on healthy disks:

```bash
# Step 1: update disk registry (re-detect new UUID on remount)
personalscraper library-index --mode full --disk Disk3

# Step 2: verify
personalscraper library-status
```

If the old disk row is still in the database with a stale UUID, the scanner
detects the mismatch and logs `indexer.disk.uuid_changed` at INFO level. The
row is updated automatically; no manual SQL is needed.

### Recovery timing

See §Budget Planning above for expected scan durations. For a 6 TB NTFS disk
over USB 3.0, allow 60–90 minutes for a full cold rebuild. Use `--budget`
to cap wall-clock time and resume across sessions:

```bash
# Cap at 90 minutes; resumes from checkpoint on next invocation
personalscraper library-index --mode full --disk Disk3 --budget 5400
```

## UBC Pressure During Scans

A full-array indexer scan reads tens of thousands of file headers from
NTFS-via-macFUSE mounts. Even with the cache-bypass mitigations in
`fingerprint.py` (`F_NOCACHE` on the oshash / xxh3_partial read paths) and
the removal of the prefetch hint from `mediainfo.py`, residual UBC growth is
normal — `Activity Monitor` may show several GB under "Cached Files" during
a cold scan. This is expected and the cache is fully reclaimable.

### Diagnostic commands

```bash
# Distinguish reclaimable cache from real wired/app memory
vm_stat
top -l 1 -o mem | head -20
memory_pressure

# Identify which NTFS driver is in use
mount | grep -i ntfs
kextstat | grep -i ntfs
brew list | grep -iE 'ntfs|paragon|tuxera|fuse'
```

If `Activity Monitor` shows the growth under "Cached Files" (yellow), it
is reclaimable and benign. If the growth appears under "Wired" or against
the macFUSE process itself, the driver is leaking and a remount is needed.

### Releasing cache

To force release after a scan completes:

```bash
sudo purge
```

To bound the vnode cache (defaults to ~260 000 entries on macOS, which is
oversized for a 4-disk media library):

```bash
sudo sysctl -w kern.maxvnodes=100000
```

`kern.maxvnodes` is volatile — to persist, add to `/etc/sysctl.conf`.

### Scan-time tuning

The `config/indexer.json5` settings that directly bound UBC pressure:

| Setting                | Default (post-audit/13) | Effect                                                                                                                                  |
| ---------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `max_workers_total`    | `2`                     | Limits concurrent disk I/O; 4-way parallel quadruples instantaneous cache ingest without doubling real throughput on a shared USB-3 hub |
| `read_rate_mb_per_sec` | `80`                    | Token-bucket throttle aligned with USB-3 sequential throughput (~100 MB/s per disk)                                                     |

Both settings are reversible. See `audit/13-ntfs-cache-pressure.md` for the
full diagnosis and measured impact estimates.

## Paths

- Paths contain spaces (`/path/to/staging/`) — always quote paths in shell commands.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails; use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`.

## Filesystem capability layer (v0.18.0+)

The pipeline adapts its rsync flags and indexer drift behaviour to the
destination filesystem via a `FilesystemCapability` strategy table
(`personalscraper/indexer/_fs_capability.py`). The same
`resolve_capability(path, fs_type_override)` resolver is consumed by **both**
the transfer layer (`dispatch.dispatcher.Dispatcher`) and the indexer scanner
(`indexer/scanner/_scan_orchestrator.py`), so a disk's filesystem type is
honoured uniformly end-to-end — transfer and scan can never diverge.
Resolution order: an explicit `DiskConfig.fs_type` override wins and skips the
probe entirely; otherwise the type is auto-detected via `probe_mount`; an
unmounted path or non-Darwin host falls back to the NTFS-safe `unknown`
capability.

### FsProbe consolidation

A single cached `probe_mount(path)` call (`personalscraper/indexer/_fs_probe.py`)
replaces the three independent `mount` parsers that previously lived in
`db.py`, `scanner/_spotlight.py`, and `scanner/__init__.py`.

**Timeout:** 10 seconds (consolidated from the former 5s in `db.py` and 10s in
the scanner modules). The result is cached for the process lifetime — `mount`
output does not change mid-run.

`canonical_fs_type` matches NTFS-via-macFUSE driver tokens by **substring**
(`ufsd_ntfs`, `fuse_osxfuse`, `osxfuse`, `macfuse`, `ntfs`, `fuse-t`), which
fixes the `ufsd_NTFS` exact-token dead branch that previously lived in
`_spotlight.try_attach`.

### Capability table

| fs_type        | rsync extra flags                                              | Unix perms | Apple metadata | NTFS name check | ctime in tier-1 | mtime granularity |
| -------------- | -------------------------------------------------------------- | ---------- | -------------- | --------------- | --------------- | ----------------- |
| `ntfs_macfuse` | `--no-perms --no-owner --no-group --no-times --omit-dir-times` | blocked    | excluded       | yes             | yes             | exact (1 ns)      |
| `unknown`      | **same as `ntfs_macfuse`** (restrictive fallback)              | blocked    | excluded       | yes             | yes             | exact (1 ns)      |
| `apfs`         | _(none beyond `-a --inplace --partial`)_                       | allowed    | allowed        | no              | yes             | exact (1 ns)      |
| `hfsplus`      | _(none beyond `-a --inplace --partial`)_                       | allowed    | allowed        | no              | yes             | 1 s               |
| `exfat`        | `--exclude=.DS_Store --exclude=._*`                            | allowed    | excluded       | no              | no (no ctime)   | 2 s               |
| `ext4`         | _(none beyond `-a --inplace --partial`)_                       | allowed    | allowed        | no              | yes†            | exact (1 ns)      |

† ext4 ctime mutates on metadata ops; granularity widening is deferred until a
real ext4 target exists (DESIGN §8.4).

The "rsync extra flags" column lists only the **perms/time** flags for brevity;
the AppleDouble excludes (`--exclude=.DS_Store --exclude=._*`) are NOT absent —
they are captured by the "Apple metadata: excluded" column and apply to every FS
marked _excluded_ there (`ntfs_macfuse`, `unknown`, and `exfat`). The complete,
authoritative `ntfs_macfuse` prefix — including the AppleDouble excludes — is
listed under "NTFS flags" below and is the value pinned in
`_fs_capability.py::_NTFS_RSYNC_FLAGS`.

The FS-aware tier-1 drift comparison is implemented by
`fingerprint.normalize_tier1` / `round_mtime_ns`, consumed by the live scanner
modes `scanner/_modes/incremental.py` and `scanner/_modes/quick.py`. On
`exfat`, ctime is dropped from the tier-1 tuple and mtime is floored to a
2-second bucket; on `hfsplus`, mtime is floored to a 1-second bucket;
`ntfs_macfuse` / `apfs` / `ext4` keep the legacy `(size, mtime_ns, ctime_ns)`
3-tuple unchanged.

The same capability bucketing now governs the **gating** layer in quick and
incremental mode, not only the per-file compare and the paranoia branch: the
Merkle root short-circuit, the `compute_merkle_delta` bulk-change freeze guard
(`DiskBulkChangeDetected`), and the dir-mtime subtree skip all floor mtime
through `round_mtime_ns` (the DB side in `_walker.py::_build_disk_fingerprints`,
the FS side in `_sample_fresh_fingerprints`, and both sides of the dir-mtime
compare). Because both sides bucket with the same capability, sub-bucket mtime
jitter on a coarse filesystem can no longer defeat the Merkle short-circuit nor
spuriously trip the bulk-change freeze on a healthy disk. For `ntfs_macfuse` /
`apfs` / `ext4` (granularity 1) the bucketing is the identity transform, so the
Merkle root, the delta, and the dir-mtime compare are all byte-identical to the
pre-multi-filesystem behaviour.

The remaining Merkle-root consumers outside the scanner bucket through the same
`_build_disk_fingerprints` helper, so a stored bucketed root is never compared
against a raw recomputation: `reconcile.detect_merkle_drift` (the
`library-doctor` drift check, fed the operator override from its caller) and
`repair._refresh_disk_merkle` (the `library-repair` post-cascade rewrite, which
auto-detects the capability from the disk mount). On a coarse filesystem this is
what keeps the doctor from emitting a false drift warning after a clean scan and
keeps the repair-written root reproducible by the next scan's short-circuit.

### NTFS flags (byte-identical to pre-0.18.0)

The full `ntfs_macfuse` rsync prefix:

```
-a --no-perms --no-owner --no-group --no-times --omit-dir-times --inplace --partial --exclude=.DS_Store --exclude=._*
```

These flags are pinned in `_fs_capability.py::_NTFS_RSYNC_FLAGS` and verified
by a golden test (`tests/dispatch/test_transfer_argv.py`).

### Operator override

To force a specific filesystem type for a disk (e.g. when the macFUSE driver
token is not auto-recognised):

```json5
// config/disks.json5
{
  id: "raid",
  path: "/Volumes/AppleRAID",
  categories: ["movies", "tv_shows"],
  fs_type: "hfsplus", // override: unlocks Unix perms, disables NTFS name check
}
```

When `fs_type` is omitted, the type is auto-detected via `probe_mount`.
