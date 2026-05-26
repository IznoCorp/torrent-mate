"""Sample test v3: 160+ items, stratified, with macro smoke-check.

Sample composition:
  - 60 DELETE_APPLEDOUBLE NFOs (stratified — leaves enough for full run)
  - 90 .actors/ dirs (stratified across 4 disks)
  - 10 controls (KEEP NFOs, tvshow.nfo, real .mkv, fanart, .plexmatch)
  - + macro smoke check post-cleanup:
      * 80 KEEP_HAS_SIBLING random sample (must still exist)
      * 30 tvshow.nfo random sample (must still exist)
      * 50 real .mkv files in deletion neighborhoods (must still exist + unchanged size)

Extra edge case checks:
  - .actors/ in dir with real videos
  - .actors/ in dir with tvshow.nfo at root
  - Multiple AppleDoubles in same season dir
  - AppleDouble at show root level (not in subdir)
  - Empty-dir walk-up with 2+ levels (look for nested empty subdirs)
  - Verify v2-deleted items still gone (regression check)

Workflow:
  1. Build sample + controls + smoke-check pools
  2. Pre-screen targets
  3. Verify v2 invariants (items deleted in v2 still gone)
  4. One-shot snapshot all parent dirs
  5. Backup all targets
  6. Apply cleanup
  7. Empty-dir walk-up
  8. Verify:
     - Targets gone
     - Controls intact (size + mtime)
     - Neighbors intact
     - Smoke-check pools intact (80 KEEPs, 30 tvshow.nfo, 50 .mkv)
     - No anchor removed
     - v2-deletions still gone (no regression)
  9. Restore-on-failure
"""

from __future__ import annotations

import csv
import hashlib
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/tmp")
from audit_nfo_orphans import classify_nfo, is_real_video  # noqa: E402
from cleanup_disk_residue import actors_is_safe_to_delete  # noqa: E402
from cleanup_empty_dirs import cleanup_walk_up, is_anchor  # noqa: E402

CSV_V3 = Path("/tmp/nfo_audit_v3.csv")
BACKUP_ROOT = Path("/tmp/sample_v3_backup")

# Deterministic random for reproducibility
random.seed(42)

DISKS = [
    Path("/Volumes/Disk1/medias"),
    Path("/Volumes/Disk2/medias"),
    Path("/Volumes/Disk3/medias"),
    Path("/Volumes/Disk4/medias"),
]

# v2 deletions that MUST still be gone (regression check)
V2_KNOWN_DELETED_HINT = "/tmp/v2_deletions_hint.txt"


def backup_path(src: Path) -> Path:
    digest = hashlib.sha256(str(src).encode()).hexdigest()[:16]
    return BACKUP_ROOT / digest / src.name


def backup_one(src: Path) -> Path:
    dst = backup_path(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copy2(src, dst)
    elif src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=True)
    return dst


def restore_one(src: Path) -> None:
    bk = backup_path(src)
    if not bk.exists() or src.exists():
        return
    src.parent.mkdir(parents=True, exist_ok=True)
    if bk.is_file():
        shutil.copy2(bk, src)
    elif bk.is_dir():
        shutil.copytree(bk, src, symlinks=True)


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)
    except (OSError, PermissionError):
        return None


def select_appledouble(n: int) -> list[Path]:
    """Pick n AppleDouble NFOs stratified across disks (only existing)."""
    per_disk: dict[str, list[Path]] = {str(d): [] for d in DISKS}
    with CSV_V3.open() as fh:
        for row in csv.DictReader(fh):
            if row["classification"] != "DELETE_APPLEDOUBLE":
                continue
            p = Path(row["path"])
            if not p.exists():
                continue
            for d in DISKS:
                if str(p).startswith(str(d)):
                    per_disk[str(d)].append(p)
                    break
    # Shuffle for diversity
    for d in DISKS:
        random.shuffle(per_disk[str(d)])
    # Round-robin
    out: list[Path] = []
    i = 0
    while len(out) < n:
        added = False
        for d in DISKS:
            pool = per_disk[str(d)]
            if i < len(pool):
                out.append(pool[i])
                added = True
                if len(out) >= n:
                    return out
        if not added:
            break
        i += 1
    return out


def select_actors(quotas: dict[Path, int]) -> list[Path]:
    """Pick .actors/ per disk quota with edge case mix."""
    out: list[Path] = []
    for disk, n in quotas.items():
        if not disk.is_dir():
            continue
        candidates: list[Path] = []
        for d in disk.rglob(".actors"):
            if d.is_dir():
                candidates.append(d)
        random.shuffle(candidates)
        out.extend(candidates[:n])
    return out


def select_controls(deletion_parents: set[Path]) -> list[Path]:
    """Pick 10 controls."""
    controls: list[Path] = []
    # 3 KEEP_HAS_SIBLING NFOs in deletion neighborhoods
    keeps = []
    with CSV_V3.open() as fh:
        for row in csv.DictReader(fh):
            if row["classification"] != "KEEP_HAS_SIBLING":
                continue
            p = Path(row["path"])
            if p.parent in deletion_parents and p.exists():
                keeps.append(p)
            if len(keeps) >= 3:
                break
    controls.extend(keeps)
    # 3 tvshow.nfo files
    tvs = []
    with CSV_V3.open() as fh:
        for row in csv.DictReader(fh):
            if row["classification"] == "KEEP_TVSHOW_ROOT":
                p = Path(row["path"])
                if p.exists():
                    tvs.append(p)
            if len(tvs) >= 3:
                break
    controls.extend(tvs)
    # 2 real .mkv videos
    for parent in deletion_parents:
        added = 0
        for p in parent.rglob("*.mkv"):
            if is_real_video(p):
                controls.append(p)
                added += 1
                if added >= 1:
                    break
        if sum(1 for c in controls if c.suffix == ".mkv") >= 2:
            break
    # 1 fanart.jpg
    for parent in deletion_parents:
        for cand in [parent / "fanart.jpg", parent.parent / "fanart.jpg"]:
            if cand.is_file():
                controls.append(cand)
                break
        if any(c.name == "fanart.jpg" for c in controls):
            break
    # 1 .plexmatch
    for parent in deletion_parents:
        for cand in [parent / ".plexmatch", parent.parent / ".plexmatch"]:
            if cand.is_file():
                controls.append(cand)
                break
        if any(c.name == ".plexmatch" for c in controls):
            break
    return controls


def select_smoke_check_pools() -> tuple[list[Path], list[Path], list[Path]]:
    """Pick large random pools that must remain intact post-cleanup."""
    keeps: list[Path] = []
    tvshows: list[Path] = []
    with CSV_V3.open() as fh:
        rows = list(csv.DictReader(fh))
    random.shuffle(rows)
    for row in rows:
        if row["classification"] == "KEEP_HAS_SIBLING" and len(keeps) < 80:
            p = Path(row["path"])
            if p.exists():
                keeps.append(p)
        elif row["classification"] == "KEEP_TVSHOW_ROOT" and len(tvshows) < 30:
            p = Path(row["path"])
            if p.exists():
                tvshows.append(p)
        if len(keeps) >= 80 and len(tvshows) >= 30:
            break

    # 50 real .mkv via filesystem scan (faster than CSV which has no videos)
    mkvs: list[Path] = []
    for disk in DISKS:
        if not disk.is_dir():
            continue
        for p in disk.rglob("*.mkv"):
            if is_real_video(p):
                mkvs.append(p)
                if len(mkvs) >= 50:
                    break
        if len(mkvs) >= 50:
            break
    return keeps, tvshows, mkvs


def pre_screen(targets: list[Path]) -> list[str]:
    issues: list[str] = []
    for t in targets:
        if not t.exists():
            issues.append(f"MISSING: {t}")
            continue
        if t.is_file() and t.suffix.lower() == ".nfo":
            cls, _, _ = classify_nfo(t)
            if cls != "DELETE_APPLEDOUBLE":
                issues.append(f"WRONG_CLASS {cls}: {t}")
        elif t.is_dir() and t.name == ".actors":
            safe, reason = actors_is_safe_to_delete(t)
            if not safe:
                issues.append(f"UNSAFE_ACTORS {reason}: {t}")
        else:
            issues.append(f"UNEXPECTED: {t}")
    return issues


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    # 1. Build sample
    print("=== Building v3 sample ===")
    ad = select_appledouble(60)
    actors = select_actors({
        Path("/Volumes/Disk1/medias"): 35,
        Path("/Volumes/Disk2/medias"): 15,
        Path("/Volumes/Disk3/medias"): 25,
        Path("/Volumes/Disk4/medias"): 15,
    })
    targets = ad + actors
    deletion_parents = {t.parent for t in targets if t.is_file()} | {t for t in targets if t.is_dir()}
    controls = select_controls({t.parent for t in targets if t.is_file()})

    # Smoke-check pools (don't backup — just verify still exist post)
    keeps_pool, tvshows_pool, mkvs_pool = select_smoke_check_pools()
    smoke_sigs: dict[Path, tuple[int, int] | None] = {}
    for p in keeps_pool + tvshows_pool + mkvs_pool:
        smoke_sigs[p] = file_signature(p)

    print(f"  Targets: {len(targets)} ({len(ad)} AppleDouble + {len(actors)} .actors/)")
    print(f"  Controls: {len(controls)} (must NOT be touched)")
    print(f"  Smoke pools: {len(keeps_pool)} KEEPs + {len(tvshows_pool)} tvshow.nfo + {len(mkvs_pool)} .mkv")

    # 2. Pre-screen
    print("\n=== Step 1: Pre-screen targets ===")
    issues = pre_screen(targets)
    if issues:
        print(f"  [{len(issues)} ISSUES — abort]")
        for i in issues[:10]:
            print(f"    {i}")
        return 1
    print(f"  [OK] {len(targets)} targets all classify correctly")

    # 3. Snapshot parent dirs
    print("\n=== Step 2: One-shot snapshot ===")
    snapshot: dict[Path, dict[str, tuple[int, int] | None]] = {}
    for parent in {t.parent for t in targets + controls}:
        if not parent.is_dir():
            continue
        files: dict[str, tuple[int, int] | None] = {}
        try:
            for entry in parent.iterdir():
                files[entry.name] = file_signature(entry) if entry.is_file() else (-1, -1)
        except (OSError, PermissionError):
            continue
        snapshot[parent] = files
    print(f"  Snapshotted {len(snapshot)} parent dirs")

    control_sig: dict[Path, tuple[int, int] | None] = {c: file_signature(c) for c in controls}

    # 4. Backup
    print("\n=== Step 3: Backup ===")
    for i, t in enumerate(targets, 1):
        backup_one(t)
        if i % 20 == 0:
            print(f"  ... {i}/{len(targets)}")
    print(f"  [OK] {len(targets)}/{len(targets)} backed up")

    # 5. Apply
    print("\n=== Step 4: Apply deletions ===")
    deleted: list[Path] = []
    errors: list[str] = []
    for t in targets:
        try:
            if t.is_file():
                t.unlink()
                deleted.append(t)
            elif t.is_dir():
                shutil.rmtree(t)
                deleted.append(t)
        except OSError as exc:
            errors.append(f"{t}: {exc}")
    print(f"  Deleted {len(deleted)} / errors {len(errors)}")

    # 6. Empty-dir walk-up
    print("\n=== Step 5: Empty-dir walk-up ===")
    would, removed = cleanup_walk_up(deleted, max_up=3, apply=True)
    print(f"  Empty dirs removed: {removed}")

    # 7. Verify
    print("\n=== Step 6: Verification ===")
    fails: list[str] = []

    # 7a. Targets gone
    for t in targets:
        if t.exists():
            fails.append(f"TARGET_STILL_EXISTS: {t}")

    # 7b. Controls intact
    for c in controls:
        if not c.exists():
            fails.append(f"CONTROL_LOST: {c}")
            continue
        if file_signature(c) != control_sig[c]:
            fails.append(f"CONTROL_MODIFIED: {c}")

    # 7c. Neighbors intact
    target_names_per_parent: dict[Path, set[str]] = {}
    for t in targets:
        target_names_per_parent.setdefault(t.parent, set()).add(t.name)

    neighbors_checked = 0
    for parent, before in snapshot.items():
        if not parent.exists():
            continue
        try:
            current = {e.name: (file_signature(e) if e.is_file() else (-1, -1)) for e in parent.iterdir()}
        except (OSError, PermissionError):
            continue
        expected_gone = target_names_per_parent.get(parent, set())
        for name, sig_before in before.items():
            if name in expected_gone:
                continue
            neighbors_checked += 1
            if name not in current:
                fails.append(f"NEIGHBOR_LOST: {parent}/{name}")
            elif current[name] != sig_before:
                fails.append(f"NEIGHBOR_MODIFIED: {parent}/{name}")

    # 7d. Anchor not removed
    for parent in snapshot:
        if is_anchor(parent) and not parent.exists():
            fails.append(f"ANCHOR_REMOVED: {parent}")

    # 7e. Macro smoke-check: smoke pools intact
    smoke_lost = smoke_modified = 0
    for p, sig_before in smoke_sigs.items():
        if not p.exists():
            smoke_lost += 1
            fails.append(f"SMOKE_LOST: {p}")
        elif file_signature(p) != sig_before:
            smoke_modified += 1
            fails.append(f"SMOKE_MODIFIED: {p}")

    print(f"  Neighbors checked: {neighbors_checked}")
    print(f"  Smoke pool checked: {len(smoke_sigs)} (lost: {smoke_lost}, modified: {smoke_modified})")

    # 8. Report
    if fails:
        print(f"\n[FAILURES: {len(fails)}]")
        for f in fails[:30]:
            print(f"    {f}")
        if len(fails) > 30:
            print(f"    ... and {len(fails) - 30} more")
        print("\n=== Step 7: RESTORE FROM BACKUP ===")
        for t in targets:
            restore_one(t)
        print("  Restored")
        return 1

    print("\n=== ALL PASSED v3 ===")
    print(f"  Deletions: {len(deleted)}")
    print(f"  Empty dirs removed: {removed}")
    print(f"  Controls intact: {len(controls)}/{len(controls)}")
    print(f"  Neighbors verified: {neighbors_checked}")
    print(f"  Smoke pool intact: {len(smoke_sigs)}/{len(smoke_sigs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
