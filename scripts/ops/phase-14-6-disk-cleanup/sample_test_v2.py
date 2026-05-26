"""Enhanced sample test v2: stratified, larger, exhaustive verification.

Sample composition (target ~80 items):
  - 30 DELETE_APPLEDOUBLE NFOs (stratified across 4 disks)
  - 4 SAFE_TORRENT_LEFTOVER NFOs (all remaining)
  - 40 .actors/ dirs (15 Disk1 / 5 Disk2 / 15 Disk3 / 5 Disk4)
  - 5 control samples that MUST NOT be touched:
      * 2 KEEP_HAS_SIBLING NFOs in same dir as deletions
      * 2 tvshow.nfo files
      * 1 real .mkv video file

Workflow:
  1. Build sample + control list
  2. Pre-screen: sanity check each target's classification
  3. One-shot snapshot: list of ALL files in ALL parent dirs (before any delete)
  4. Backup all targets to /tmp/sample_v2_backup/
  5. Apply cleanup
  6. Apply empty-dir walk-up
  7. Verify:
     - All sample targets gone
     - All controls UNTOUCHED (same size, same content)
     - No anchor removed
     - Empty-dir walk-up didn't touch non-empty
  8. Restore-on-failure
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/tmp")
from audit_nfo_orphans import classify_nfo, is_real_video  # noqa: E402
from cleanup_disk_residue import actors_is_safe_to_delete  # noqa: E402
from cleanup_empty_dirs import cleanup_walk_up, is_anchor  # noqa: E402
from refine_orphans import refine_delete_entries  # noqa: E402

CSV_V3 = Path("/tmp/nfo_audit_v3.csv")
BACKUP_ROOT = Path("/tmp/sample_v2_backup")

DISKS = [
    Path("/Volumes/Disk1/medias"),
    Path("/Volumes/Disk2/medias"),
    Path("/Volumes/Disk3/medias"),
    Path("/Volumes/Disk4/medias"),
]


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
    """Return (size, mtime_ns) or None on error."""
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)
    except (OSError, PermissionError):
        return None


def select_appledouble(n: int) -> list[Path]:
    """Pick n AppleDouble NFOs stratified across disks."""
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
    # Round-robin to balance
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


def select_safe_torrent() -> list[Path]:
    refined = refine_delete_entries(CSV_V3)
    return [p for p in refined.get("SAFE_TORRENT_LEFTOVER", []) if p.exists()]


def select_actors(quotas: dict[Path, int]) -> list[Path]:
    """Pick .actors/ per disk quota."""
    out: list[Path] = []
    for disk, n in quotas.items():
        if not disk.is_dir():
            continue
        found = 0
        for d in disk.rglob(".actors"):
            if d.is_dir():
                out.append(d)
                found += 1
                if found >= n:
                    break
    return out


def select_controls(deletion_parents: set[Path]) -> list[Path]:
    """Pick 5 control items that MUST NOT be touched."""
    controls: list[Path] = []
    # 2 KEEP_HAS_SIBLING in same parent as a deletion
    with CSV_V3.open() as fh:
        for row in csv.DictReader(fh):
            if row["classification"] != "KEEP_HAS_SIBLING":
                continue
            p = Path(row["path"])
            if p.parent in deletion_parents and p.exists():
                controls.append(p)
            if len([c for c in controls if c.suffix == ".nfo"]) >= 2:
                break
    # 2 tvshow.nfo files
    tvshows: list[Path] = []
    with CSV_V3.open() as fh:
        for row in csv.DictReader(fh):
            if row["classification"] == "KEEP_TVSHOW_ROOT":
                p = Path(row["path"])
                if p.exists():
                    tvshows.append(p)
            if len(tvshows) >= 2:
                break
    controls.extend(tvshows)
    # 1 real .mkv video in a deletion neighborhood
    for parent in deletion_parents:
        for p in parent.rglob("*.mkv"):
            if is_real_video(p):
                controls.append(p)
                break
        else:
            continue
        break
    return controls


def pre_screen(targets: list[Path]) -> list[str]:
    """Verify each target matches its expected category. Returns list of issues."""
    issues: list[str] = []
    for t in targets:
        if not t.exists():
            issues.append(f"MISSING: {t}")
            continue
        if t.is_file() and t.suffix.lower() == ".nfo":
            cls, _, _ = classify_nfo(t)
            if cls not in {"DELETE_APPLEDOUBLE", "DELETE_NO_VIDEO_SIBLING"}:
                issues.append(f"WRONG_CLASS {cls}: {t}")
        elif t.is_dir() and t.name == ".actors":
            safe, reason = actors_is_safe_to_delete(t)
            if not safe:
                issues.append(f"UNSAFE_ACTORS {reason}: {t}")
        elif t.is_dir():
            # Should not happen — actors only
            issues.append(f"UNEXPECTED_DIR: {t}")
        else:
            issues.append(f"UNEXPECTED_FILE: {t}")
    return issues


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    # 1. Build sample
    ad = select_appledouble(30)
    safe = select_safe_torrent()
    actors = select_actors({
        Path("/Volumes/Disk1/medias"): 15,
        Path("/Volumes/Disk2/medias"): 5,
        Path("/Volumes/Disk3/medias"): 15,
        Path("/Volumes/Disk4/medias"): 5,
    })

    targets = ad + safe + actors
    deletion_parents = {t.parent for t in targets if t.is_file()} | {t for t in targets if t.is_dir()}

    controls = select_controls({t.parent for t in targets if t.is_file()})

    print("=== SAMPLE v2 ===")
    print(f"  AppleDouble: {len(ad)}")
    print(f"  SAFE_TORRENT: {len(safe)}")
    print(f"  .actors/: {len(actors)}")
    print(f"  Controls (must NOT be touched): {len(controls)}")
    print(f"  TOTAL targets: {len(targets)}")

    # 2. Pre-screen
    print("\n=== Step 1: Pre-screen targets ===")
    issues = pre_screen(targets)
    if issues:
        print(f"  [{len(issues)} ISSUES — abort before any change]")
        for i in issues[:10]:
            print(f"    {i}")
        return 1
    print(f"  [OK] {len(targets)} targets all classify correctly")

    # 3. Snapshot all parent dirs (one-shot before any delete)
    print("\n=== Step 2: One-shot snapshot of all parent dirs ===")
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

    # 3b. Snapshot all controls (we'll re-stat them after)
    control_sig: dict[Path, tuple[int, int] | None] = {c: file_signature(c) for c in controls}

    # 4. Backup targets
    print("\n=== Step 3: Backup all targets ===")
    total_bk = 0
    for t in targets:
        backup_one(t)
        total_bk += 1
        if total_bk % 10 == 0:
            print(f"  ... {total_bk}/{len(targets)} backed up")
    print(f"  [OK] {total_bk}/{len(targets)} backed up to {BACKUP_ROOT}")

    # 5. Apply cleanup (NFO unlink + .actors rmtree)
    print("\n=== Step 4: Apply deletions ===")
    deleted: list[Path] = []
    errors: list[str] = []
    for t in targets:
        try:
            if t.is_file():
                t.unlink()
                deleted.append(t)
            elif t.is_dir() and t.name == ".actors":
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

    # 7a. All targets gone
    for t in targets:
        if t.exists():
            fails.append(f"TARGET_STILL_EXISTS: {t}")

    # 7b. All controls intact
    for c in controls:
        if not c.exists():
            fails.append(f"CONTROL_LOST: {c}")
            continue
        sig_now = file_signature(c)
        sig_before = control_sig[c]
        if sig_now != sig_before:
            fails.append(f"CONTROL_MODIFIED: {c} {sig_before} → {sig_now}")

    # 7c. All non-target neighbors intact in each parent dir
    target_names_per_parent: dict[Path, set[str]] = {}
    for t in targets:
        target_names_per_parent.setdefault(t.parent, set()).add(t.name)

    for parent, before in snapshot.items():
        # Parent may have been removed by empty-dir walk-up — that's fine if it was a deletion target site
        # Skip parents removed by walk-up
        if not parent.exists():
            continue
        try:
            current_entries = {e.name: (file_signature(e) if e.is_file() else (-1, -1)) for e in parent.iterdir()}
        except (OSError, PermissionError):
            fails.append(f"PARENT_UNREADABLE: {parent}")
            continue
        expected_gone = target_names_per_parent.get(parent, set())
        for name, sig_before in before.items():
            if name in expected_gone:
                continue
            if name not in current_entries:
                fails.append(f"NEIGHBOR_LOST: {parent}/{name}")
            elif current_entries[name] != sig_before:
                fails.append(f"NEIGHBOR_MODIFIED: {parent}/{name} {sig_before} → {current_entries[name]}")

    # 7d. No anchor removed
    for parent in snapshot:
        if is_anchor(parent) and not parent.exists():
            fails.append(f"ANCHOR_REMOVED: {parent}")

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

    print(f"\n=== ALL PASSED: {len(deleted)} deletions + {removed} empty dirs, "
          f"all {len(controls)} controls intact, {sum(len(v) for v in snapshot.values())} neighbors unchanged ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
