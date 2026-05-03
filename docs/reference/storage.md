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

## Paths

- Paths contain spaces (`/path/to/staging/`) — always quote paths in shell commands.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails; use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`.
