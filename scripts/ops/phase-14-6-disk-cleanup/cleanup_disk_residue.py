"""Cleanup orphan NFO files + `.actors/` directories on production disks.

Reads the CSV produced by `audit_nfo_orphans.py` and deletes only entries
classified as `DELETE_*`. Dry-run by default.

Also handles `.actors/` directories: lists them across all 4 disks, optionally
deletes those that contain ONLY image files (no videos, no .nfo, no .mkv/.mp4).

USAGE:
    python3 cleanup_disk_residue.py --nfo-csv audit.csv          # dry-run NFO
    python3 cleanup_disk_residue.py --nfo-csv audit.csv --apply  # real delete
    python3 cleanup_disk_residue.py --actors                     # dry-run .actors
    python3 cleanup_disk_residue.py --actors --apply             # real delete
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tbn"}
DISKS = [
    Path("/Volumes/Disk1/medias"),
    Path("/Volumes/Disk2/medias"),
    Path("/Volumes/Disk3/medias"),
    Path("/Volumes/Disk4/medias"),
]

DELETE_CLASSIFICATIONS = {"DELETE_NO_VIDEO_SIBLING", "DELETE_DEAD_SEASON"}


def cleanup_nfos(csv_path: Path, apply: bool) -> tuple[int, int, int]:
    """Return (would_delete, deleted, skipped) tuple."""
    would_delete = 0
    deleted = 0
    skipped = 0

    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            classification = row["classification"]
            path = Path(row["path"])
            if classification not in DELETE_CLASSIFICATIONS:
                skipped += 1
                continue
            if not path.is_file():
                skipped += 1
                continue
            would_delete += 1
            if apply:
                try:
                    path.unlink()
                    deleted += 1
                except OSError as exc:
                    print(f"# delete failed {path}: {exc}", file=sys.stderr)
    return would_delete, deleted, skipped


def list_actors_dirs() -> list[Path]:
    """Find .actors/ dirs across all disks. Robust to transient FileNotFoundError."""
    found: list[Path] = []
    for disk in DISKS:
        if not disk.is_dir():
            continue
        stack = [disk]
        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except (OSError, PermissionError):
                continue
            for entry in entries:
                try:
                    if entry.is_dir():
                        if entry.name == ".actors":
                            found.append(entry)
                        else:
                            stack.append(entry)
                except (OSError, PermissionError):
                    continue
    return found


def actors_is_safe_to_delete(actors_dir: Path) -> tuple[bool, str]:
    """Return (safe, reason). Safe = contains only images, nothing else."""
    try:
        for child in actors_dir.iterdir():
            if child.is_dir():
                return (False, f"contains subdir: {child.name}")
            ext = child.suffix.lower()
            if ext in VIDEO_EXTS:
                return (False, f"VIDEO found: {child.name}")
            if ext == ".nfo":
                return (False, f"NFO found: {child.name}")
            if ext not in IMAGE_EXTS:
                return (False, f"unknown ext: {child.name}")
    except (OSError, PermissionError) as exc:
        return (False, f"scan error: {exc}")
    return (True, "images only")


def cleanup_actors(apply: bool) -> tuple[int, int, int]:
    """Return (would_delete, deleted, skipped) tuple."""
    actors = list_actors_dirs()
    would_delete = 0
    deleted = 0
    skipped = 0

    for d in actors:
        safe, reason = actors_is_safe_to_delete(d)
        if not safe:
            print(f"# SKIP {d}: {reason}", file=sys.stderr)
            skipped += 1
            continue
        would_delete += 1
        if apply:
            try:
                shutil.rmtree(d)
                deleted += 1
            except OSError as exc:
                print(f"# rmtree failed {d}: {exc}", file=sys.stderr)
    return would_delete, deleted, skipped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nfo-csv", type=Path, help="path to audit CSV produced by audit_nfo_orphans.py")
    parser.add_argument("--actors", action="store_true", help="cleanup .actors/ directories")
    parser.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    if args.nfo_csv:
        print(f"[{mode}] NFO cleanup from {args.nfo_csv}", file=sys.stderr)
        wd, d, s = cleanup_nfos(args.nfo_csv, args.apply)
        print(f"NFO: would_delete={wd} deleted={d} skipped={s}", file=sys.stderr)

    if args.actors:
        print(f"[{mode}] .actors/ cleanup", file=sys.stderr)
        wd, d, s = cleanup_actors(args.apply)
        print(f".actors/: would_delete={wd} deleted={d} skipped={s}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
