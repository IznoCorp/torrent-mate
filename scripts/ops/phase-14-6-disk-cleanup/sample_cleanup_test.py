"""Sample cleanup test: backup + apply + verify + restore-on-failure.

Workflow:
  1. Pick 5 SAFE_TORRENT_LEFTOVER NFOs + 5 DELETE_APPLEDOUBLE + 3 .actors/
  2. Backup each to /tmp/sample_backup/<sha256>/
  3. Apply cleanup (real delete)
  4. Verify:
     - All sample items deleted
     - Their direct neighbors UNTOUCHED
  5. If verification fails → restore from backup
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/tmp")
from refine_orphans import refine_delete_entries  # noqa: E402

CSV_V3 = Path("/tmp/nfo_audit_v3.csv")
BACKUP_ROOT = Path("/tmp/sample_backup_phase14_6")


def backup_path(src: Path) -> Path:
    """Stable backup location for a source path."""
    digest = hashlib.sha256(str(src).encode()).hexdigest()[:16]
    return BACKUP_ROOT / digest / src.name


def backup_one(src: Path) -> Path:
    """Copy src to backup location; return backup path."""
    dst = backup_path(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copy2(src, dst)
    elif src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=True)
    return dst


def snapshot_neighbors(target: Path) -> dict[str, int]:
    """Return {name: size_or_-1} for everything in target's parent dir EXCEPT target itself."""
    parent = target.parent
    snapshot: dict[str, int] = {}
    try:
        for entry in parent.iterdir():
            if entry == target:
                continue
            try:
                if entry.is_file():
                    snapshot[entry.name] = entry.stat().st_size
                elif entry.is_dir():
                    snapshot[entry.name + "/"] = -1
                else:
                    snapshot[entry.name] = -2
            except (OSError, PermissionError):
                snapshot[entry.name] = -3
    except (OSError, PermissionError):
        pass
    return snapshot


def verify_neighbors_unchanged(target: Path, before: dict[str, int]) -> tuple[bool, list[str]]:
    """Return (ok, diffs)."""
    after = snapshot_neighbors(target)
    diffs: list[str] = []
    for name, size in before.items():
        if name not in after:
            diffs.append(f"LOST: {name}")
        elif after[name] != size:
            diffs.append(f"CHANGED: {name} {size} → {after[name]}")
    for name in after:
        if name not in before:
            diffs.append(f"APPEARED: {name}")
    return (len(diffs) == 0, diffs)


def restore_from_backup(src: Path) -> None:
    bk = backup_path(src)
    if not bk.exists():
        print(f"  [WARN] no backup for {src}")
        return
    if src.exists():
        print(f"  [SKIP RESTORE] {src} already exists")
        return
    src.parent.mkdir(parents=True, exist_ok=True)
    if bk.is_file():
        shutil.copy2(bk, src)
    elif bk.is_dir():
        shutil.copytree(bk, src, symlinks=True)
    print(f"  [RESTORED] {src}")


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"Backup root: {BACKUP_ROOT}")

    # 1. Pick samples
    refined = refine_delete_entries(CSV_V3)
    safe_torrent = refined.get("SAFE_TORRENT_LEFTOVER", [])[:5]

    appledoubles: list[Path] = []
    with CSV_V3.open() as fh:
        for row in csv.DictReader(fh):
            if row["classification"] == "DELETE_APPLEDOUBLE":
                p = Path(row["path"])
                if p.exists():
                    appledoubles.append(p)
                if len(appledoubles) >= 5:
                    break

    actors_dirs: list[Path] = []
    for disk in [Path("/Volumes/Disk4/medias"), Path("/Volumes/Disk2/medias")]:
        for d in disk.rglob(".actors"):
            if d.is_dir():
                actors_dirs.append(d)
            if len(actors_dirs) >= 3:
                break
        if len(actors_dirs) >= 3:
            break
    actors_dirs = actors_dirs[:3]

    nfo_samples = safe_torrent + appledoubles
    all_samples = nfo_samples + actors_dirs

    print(f"\nSamples: {len(safe_torrent)} SAFE_TORRENT, {len(appledoubles)} APPLEDOUBLE, {len(actors_dirs)} .actors/")
    print()
    for s in all_samples:
        print(f"  TARGET: {s}")

    # 2. Snapshot neighbors + backup
    # Build a "target name set" per parent dir so verification ignores
    # the case where multiple targets share a parent (each was expected gone).
    print("\n=== Step 2: Backup + neighbor snapshot ===")
    targets_per_parent: dict[Path, set[str]] = {}
    for s in all_samples:
        targets_per_parent.setdefault(s.parent, set()).add(s.name)

    snapshots: dict[Path, dict[str, int]] = {}
    for s in all_samples:
        raw = snapshot_neighbors(s)
        # Strip co-target names from the snapshot (we expect them to disappear)
        cleaned = {name: size for name, size in raw.items() if name not in targets_per_parent.get(s.parent, set())}
        snapshots[s] = cleaned
        bk = backup_one(s)
        size = bk.stat().st_size if bk.is_file() else sum(p.stat().st_size for p in bk.rglob("*") if p.is_file())
        print(f"  backed up {s} → {bk} ({size} bytes, {len(cleaned)} non-target neighbors)")

    # 3. Apply cleanup
    print("\n=== Step 3: Apply cleanup ===")
    for s in all_samples:
        try:
            if s.is_file():
                s.unlink()
                print(f"  DELETED file: {s}")
            elif s.is_dir():
                shutil.rmtree(s)
                print(f"  DELETED dir:  {s}")
        except OSError as exc:
            print(f"  [ERROR] {s}: {exc}")

    # 4. Verify
    print("\n=== Step 4: Verification ===")
    failures: list[Path] = []
    for s in all_samples:
        # 4a. Target is gone
        if s.exists():
            print(f"  [FAIL] {s} STILL EXISTS after delete")
            failures.append(s)
            continue
        # 4b. Neighbors unchanged
        ok, diffs = verify_neighbors_unchanged(s, snapshots[s])
        if ok:
            print(f"  [OK]   {s.name} deleted, neighbors intact")
        else:
            print(f"  [FAIL] {s}: neighbor diffs:")
            for d in diffs:
                print(f"      {d}")
            failures.append(s)

    # 5. Restore on failure
    if failures:
        print(f"\n=== Step 5: RESTORING {len(failures)} failed targets ===")
        for s in failures:
            restore_from_backup(s)
        return 1
    print("\n=== ALL SAMPLES CLEAN: behavior validated ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
