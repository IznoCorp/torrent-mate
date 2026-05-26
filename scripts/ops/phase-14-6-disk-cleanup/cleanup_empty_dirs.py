"""Strict empty-directory cleanup. Removes ONLY directories with 0 entries.

Safety contract:
  - Uses os.rmdir() (kernel-level "directory must be empty" check), NEVER shutil.rmtree().
  - Exclusion list: anchor directories that must never be removed even if empty.
  - Walks UP from deletion sites for max N levels (default 3) — never recursive walk.
  - Dry-run by default. Real delete requires --apply.

Usage:
    python3 cleanup_empty_dirs.py [--starts-from /path1 /path2 ...] [--apply]

If --starts-from omitted: scans all 4 disk roots looking for empty leaf dirs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DISKS = [
    Path("/Volumes/Disk1/medias"),
    Path("/Volumes/Disk2/medias"),
    Path("/Volumes/Disk3/medias"),
    Path("/Volumes/Disk4/medias"),
]

# Anchor dirs that must NEVER be removed, even if they become empty.
ANCHOR_DIRS_BY_NAME = {
    "medias",
    "films",
    "series",
    "series animations",
    "series animes",
    "series documentaires",
    "emissions",
    "theatres",
    "spectacles",
    "concerts",
    "animation",
    "anime",
    "docu",
    "documentaires",
    "movies",
    "tv_shows",
}


def is_anchor(path: Path) -> bool:
    """True if this path is an anchor that must not be removed."""
    if path.name in ANCHOR_DIRS_BY_NAME:
        return True
    # The disk root itself
    for disk in DISKS:
        if path == disk:
            return True
    return False


def is_strictly_empty(directory: Path) -> tuple[bool, list[str]]:
    """Return (empty, contents). empty=True iff os.listdir returns []."""
    try:
        contents = os.listdir(directory)
    except (OSError, PermissionError) as exc:
        return (False, [f"<error: {exc}>"])
    return (len(contents) == 0, contents)


def find_empty_leaf_dirs(roots: list[Path], max_per_root: int = 5000) -> list[Path]:
    """Scan recursively, return all strictly-empty leaf dirs."""
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        count_here = 0
        for current_dir, subdirs, files in os.walk(root, topdown=False):
            current = Path(current_dir)
            if is_anchor(current):
                continue
            try:
                if not any(current.iterdir()):
                    found.append(current)
                    count_here += 1
                    if count_here >= max_per_root:
                        break
            except (OSError, PermissionError):
                continue
    return found


def safe_rmdir(directory: Path) -> tuple[bool, str]:
    """Rmdir with safety net. Returns (ok, message)."""
    if is_anchor(directory):
        return (False, "ANCHOR_PROTECTED")
    empty, contents = is_strictly_empty(directory)
    if not empty:
        return (False, f"NOT_EMPTY: {contents[:5]}")
    try:
        os.rmdir(directory)  # Kernel-enforced: fails if not actually empty
        return (True, "removed")
    except OSError as exc:
        return (False, f"rmdir failed: {exc}")


def cleanup_walk_up(starts: list[Path], max_up: int, apply: bool) -> tuple[int, int]:
    """For each start path, walk up to max_up levels; rmdir each empty dir.

    `start` can be either:
      - A deleted file path (doesn't exist anymore) → walk up from start.parent
      - A directory that might be empty → check start itself first, then walk up
    """
    would = 0
    removed = 0
    seen: set[Path] = set()
    for start in starts:
        # Begin at the directory that might be empty: if start is a file/missing,
        # begin at its parent; if start is a directory, begin at start itself.
        if start.is_dir():
            current = start
        else:
            current = start.parent
        for _ in range(max_up + 1):
            if current in seen:
                break
            seen.add(current)
            if is_anchor(current):
                break
            if not current.is_dir():
                break
            empty, _ = is_strictly_empty(current)
            if not empty:
                break
            would += 1
            if apply:
                ok, msg = safe_rmdir(current)
                action = "RMDIR" if ok else f"SKIP ({msg})"
                print(f"  {action}: {current}")
                if ok:
                    removed += 1
            else:
                print(f"  WOULD-RMDIR: {current}")
            current = current.parent
    return would, removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--starts-from", nargs="*", type=Path,
                        help="Paths to start walking up from (typically just-deleted items' parents)")
    parser.add_argument("--apply", action="store_true", help="Actually remove dirs (default: dry-run)")
    parser.add_argument("--max-up", type=int, default=3, help="Max walk-up levels (default 3)")
    parser.add_argument("--full-scan", action="store_true",
                        help="Scan all 4 disks for empty leaf dirs (slow)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Empty-dir cleanup (anchor-safe, kernel-empty-check)", file=sys.stderr)

    if args.full_scan:
        print(f"Full scan of {len(DISKS)} disks...", file=sys.stderr)
        empties = find_empty_leaf_dirs(DISKS)
        print(f"Found {len(empties)} empty leaf dirs", file=sys.stderr)
        starts = empties
    elif args.starts_from:
        starts = args.starts_from
    else:
        print("ERROR: pass --starts-from <path>... or --full-scan", file=sys.stderr)
        return 2

    would, removed = cleanup_walk_up(starts, args.max_up, args.apply)
    print(f"\n{mode}: would_rmdir={would}, removed={removed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
