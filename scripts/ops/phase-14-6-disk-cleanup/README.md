# Phase 14.6 — Disk Residue Cleanup Tooling

**Operator-only scripts** developed and validated during tech-debt 0.16.0 Phase 14.6 (re-run pipeline-monitor 2026-05-25 23h49 findings — invariants AG + AJ). Kept here for future reference and re-use (e.g. periodic cleanup of new AppleDouble accumulation on macFUSE-NTFS volumes).

**Scope cleaned in 2026-05-26 run** :

- 109/109 `._*.nfo` AppleDouble (macOS resource forks)
- 9/9 SAFE_TORRENT_LEFTOVER NFOs (nested torrent-name subdirs)
- 1729/1730 `.actors/` MediaElch cast image directories
- 19 empty dirs walked-up post-cleanup

**Residual** : 1 NTFS zombie file (`Hunger Games La Ballade.../`.actors/Zoë_Renee.jpg`) needs `chkdsk /F` from Windows.

---

## Workflow at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. audit_nfo_orphans.py  → /tmp/nfo_audit_v3.csv                 │
│    Classify every *.nfo on all 4 disks (6 categories)            │
├──────────────────────────────────────────────────────────────────┤
│ 2. refine_orphans.py  → splits DELETE_NO_VIDEO_SIBLING into      │
│    SAFE_TORRENT_LEFTOVER (no video anywhere) vs                  │
│    REVIEW_SHOW_ROOT (subdir videos exist — risk Plex metadata)   │
├──────────────────────────────────────────────────────────────────┤
│ 3. sample_test_v{2,3}.py  → validates classifier + cleanup       │
│    behavior on stratified samples (74 + 150 items, 1804 + 1022  │
│    neighbors verified, smoke pool intact)                        │
├──────────────────────────────────────────────────────────────────┤
│ 4. run_full_cleanup_batched.py  → applies cleanup in batches     │
│    with smoke check after each batch (abort on any signature     │
│    change in 65-item KEEP+tvshow+mkv pool)                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Script reference

### `audit_nfo_orphans.py`

**Purpose**: classify every `.nfo` file across the 4 disks into 6 categories.

**Categories** :

| Category                  | Action                                                                         |
| ------------------------- | ------------------------------------------------------------------------------ |
| `KEEP_HAS_SIBLING`        | NFO with matching same-stem `.<video_ext>` voisin — paired, keep               |
| `KEEP_TVSHOW_ROOT`        | `tvshow.nfo` at show root (whitelisted, even if no immediate video)            |
| `KEEP_SEASON_HAS_VIDEOS`  | `season.nfo` with ≥1 video in the season dir                                   |
| `DELETE_APPLEDOUBLE`      | `._*.nfo` macOS resource fork (always delete)                                  |
| `DELETE_NO_VIDEO_SIBLING` | NFO with no video in parent dir (refine via `refine_orphans.py` before delete) |
| `REVIEW`                  | Parent has videos but none matches stem — manual review                        |

**Key implementation details** :

- `VIDEO_EXTS` includes `.mkv`, `.mp4`, `.ts`, `.mpg`, `.mpeg`, `.iso`, `.vob`, `.divx`, `.m2ts`, `.mts`, etc. — extended after Phase 14.6 sample v1 caught `.ts` missing (Le Discours movie).
- `is_real_video()` excludes `._*.<ext>` AppleDouble pseudo-videos from "video sibling" check.
- Robust iteration (no `pathlib.rglob`) — survives transient `FileNotFoundError` during scan (NAS file disappearing mid-traversal).

**Output**: CSV at stdout — `path, classification, parent_kind, sibling_video_count, size_bytes`.

```bash
python3 audit_nfo_orphans.py > /tmp/nfo_audit_v3.csv 2> /tmp/nfo_audit_v3.log
```

---

### `refine_orphans.py`

**Purpose**: re-classify entries marked `DELETE_NO_VIDEO_SIBLING` based on whether parent dir has subdirs containing videos.

**Refined categories** :

| Refined                 | Meaning                                                                                                                                                                                      |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SAFE_TORRENT_LEFTOVER` | No video anywhere in parent's tree → confirmed orphan, safe to delete                                                                                                                        |
| `REVIEW_SHOW_ROOT`      | Parent has subdirs with videos (e.g. `Saison NN/` with `.mkv`) → likely a legacy show-root NFO that Plex/Kodi may index as the show's metadata. **Manual review only — do not auto-delete.** |

**Why this matters**: a `tvshow.nfo` at a show root is whitelisted in `audit_nfo_orphans.py`, but show roots sometimes carry a release-name NFO (e.g. `How I Met Your Mother Integrale MULTi DVDRiP x264.nfo`) without a `tvshow.nfo`. Those are NOT auto-orphans because they may be the Plex-indexed show metadata.

```bash
python3 refine_orphans.py   # prints refined classification with samples
```

---

### `cleanup_disk_residue.py`

**Purpose**: low-level cleanup primitives, used as building blocks by the orchestrator.

**Provides** :

- `list_actors_dirs()` — robust scan for `.actors/` directories across all 4 disks (no `rglob` — survives transient file disappearance).
- `actors_is_safe_to_delete(dir)` — returns `(safe, reason)`. Safe = contains only image files (`.jpg`/`.jpeg`/`.png`/`.webp`/`.tbn`) and no subdirs, no videos, no NFOs.
- `DISKS` constant — the 4 NAS disk roots.

Not normally run standalone — imported by `run_full_cleanup_batched.py`.

---

### `cleanup_empty_dirs.py`

**Purpose**: kernel-enforced empty-dir removal with anchor protection. Walks up from deletion sites and `os.rmdir()` (not `shutil.rmtree`) — fails if dir is not strictly empty.

**Safety contract** :

- `os.rmdir()` — kernel-enforced "directory must be empty" check. Cannot accidentally delete a non-empty dir.
- `ANCHOR_DIRS_BY_NAME` — never removes `medias/`, `films/`, `series/`, `series animations/`, `series animes/`, `series documentaires/`, `emissions/`, `theatres/`, `spectacles/`, `concerts/`, `animation/`, `anime/`, `docu/`, `documentaires/`, `movies/`, `tv_shows/`, even if empty.
- Walk-up limited to 3 levels (`--max-up=3`).
- Stops walking the moment a non-empty dir or anchor is hit.

```bash
python3 cleanup_empty_dirs.py --starts-from <path>... [--apply] [--max-up=3]
python3 cleanup_empty_dirs.py --full-scan [--apply]
```

---

### `sample_test_v2.py` / `sample_test_v3.py`

**Purpose**: validate classifier + cleanup behavior on real items before the full run.

| Version                                 | Targets | Controls | Smoke pool                               | Neighbors verified |
| --------------------------------------- | ------- | -------- | ---------------------------------------- | ------------------ |
| v1 (inline in `sample_cleanup_test.py`) | 13      | —        | —                                        | basic              |
| v2                                      | 74      | 5        | —                                        | 1022               |
| v3                                      | 150     | 10       | 160 (80 KEEPs + 30 tvshow.nfo + 50 .mkv) | 1804               |

**Workflow** :

1. Build sample stratified across 4 disks.
2. Pre-screen each target (must classify correctly).
3. One-shot snapshot of all parent dirs (size + mtime for each entry).
4. Backup all targets to `/tmp/sample_v*_backup/<sha256>/<name>`.
5. Apply real deletes.
6. Run empty-dir walk-up.
7. Verify :
   - All targets gone.
   - All controls intact (same size + mtime).
   - All neighbors in snapshot intact.
   - No anchor removed.
   - Smoke pool intact (size + mtime for 160 items).
8. If any failure → restore from backup, return 1.

**v3 result** : 150 deletions + 2 empty dirs, 10/10 controls intact, 1804/1804 neighbors unchanged, 160/160 smoke pool intact. 0 failures.

---

### `sample_cleanup_test.py`

**Purpose**: original v1 sample test (13 items). Has a known false-positive bug in neighbor-verification when multiple targets share a parent dir (fixed in v2 via the `targets_per_parent` exclusion set). Kept for historical reference.

---

### `run_full_cleanup_batched.py`

**Purpose**: production orchestrator. Splits the full target list into batches and applies cleanup with smoke-check verification after each batch.

**Configuration** (constants at top of file) :

- `BATCH_SIZE = 100` (first 15 batches)
- `LAST_BATCH_SIZE = 115` (16th batch)
- `TOTAL_EXPECTED = 1615`
- Smoke pool : 30 KEEPs + 15 tvshow.nfo + 20 real `.mkv` = 65 items, randomly selected (seed=2026 for reproducibility)

**Workflow** :

1. Collect targets : all `DELETE_APPLEDOUBLE` from CSV (existing) + `list_actors_dirs()` live.
2. Split into 16 batches (15×100 + 1×115).
3. Build smoke pool, capture signature (size + mtime_ns) of each.
4. For each batch :
   - Delete each item (`unlink()` for files, `shutil.rmtree()` for `.actors/` after safety check).
   - Walk up empty dirs (kernel `rmdir`, anchor-protected).
   - Verify smoke pool : every item still exists with same signature.
   - On smoke-fail → log + abort (return 1).
5. Final invariant check : all anchor dirs still exist.

**Log path** : `/tmp/full_cleanup_<YYYYMMDD-HHMMSS>.log` (every delete recorded with size + path).

**2026-05-26 run result** : 1614/1615 deleted, 1 transient skip (NTFS zombie), 15 empty dirs walked-up, 65/65 smoke pool intact across all 16 batches. Total time 98s.

```bash
python3 run_full_cleanup_batched.py [--apply] [--disk /Volumes/Disk4/medias]
```

Dry-run by default. `--apply` to execute.

---

## `AUDIT_LOG_full_cleanup.log`

Verbatim log of the 2026-05-26 production run. Every deletion is logged with `FILE <size>b <path>` or `ACTORS <N>files <total>b <path>`. Each batch's `# batch_N: deleted=X, skipped=Y, empty=Z, time=Ts` summary appended. The 1 skipped item appears as `ERROR: [Errno 2] No such file or directory: 'Zoë_Renee.jpg' ...` — the NTFS zombie file mentioned above.

---

## Future use cases

1. **Periodic AppleDouble re-cleanup** : macFUSE creates new `._*` files on every macOS-side write to NTFS. Re-run audit + cleanup quarterly to keep disks clean.

2. **5,166 `._*.mkv` cleanup** (deferred from Phase 14.6) : extend `audit_nfo_orphans.py` `DELETE_APPLEDOUBLE` rule to all `._*` files (not just `.nfo`). Same safety pattern applies.

3. **Adapt to new disks** : update `DISKS` list in `audit_nfo_orphans.py` + `cleanup_disk_residue.py` + `cleanup_empty_dirs.py`.

---

## Safety summary

- ✅ Real `.mkv` videos never touched (50 verified in v3 + smoke pool across full run)
- ✅ `tvshow.nfo` whitelist (715 preserved during full run)
- ✅ NFO with same-stem video sibling preserved (~27,500 across all disks)
- ✅ Empty-dir cleanup kernel-enforced (`rmdir` not `rmtree`)
- ✅ Anchor dirs (`medias/`, `films/`, etc.) never removed
- ✅ Smoke pool inter-batch verification (abort on any signature change)
- ⚠️ macFUSE NTFS may create zombie files (`-?????????` perms) that resist `rm -f` — operator must run `chkdsk /F` from Windows to clean
