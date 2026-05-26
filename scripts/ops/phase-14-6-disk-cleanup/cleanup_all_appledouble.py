"""Cleanup ALL `._*` AppleDouble sidecars across the 4 NAS disks.

Followup to Phase 14.6 (which only handled `._*.nfo`). This script
extends the same SAFE pattern to ALL `._*` files — they are macOS resource
forks created by Finder/macFUSE on NTFS volumes and serve no purpose.

Identified during Phase 14.6:
  Disk1: 3983 `._*.mkv` (out of 5166 total across all disks)
  Disk2:  825 `._*.mkv`
  Disk3:  271 `._*.mkv`
  Disk4:   87 `._*.mkv`
  Plus an unknown number of `._*.jpg`, `._*.png`, `._*-thumb.jpg`, etc.

USAGE:
    python3 cleanup_all_appledouble.py            # dry-run, print counts
    python3 cleanup_all_appledouble.py --apply    # real delete + log
    python3 cleanup_all_appledouble.py --disk /Volumes/Disk4/medias [--apply]

Safety:
  - Only deletes files matching `._*` (starts with `._`).
  - NEVER touches files that don't start with `._` (the real videos, NFOs,
    artwork all have normal names).
  - Each deletion logged to /tmp/cleanup_appledouble_<timestamp>.log.
  - Inter-batch smoke check (re-uses Phase 14.6 pattern).
  - Empty-dir walk-up disabled by default (AppleDouble removal alone does
    not typically empty parent dirs).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

DISKS = [
    Path("/Volumes/Disk1/medias"),
    Path("/Volumes/Disk2/medias"),
    Path("/Volumes/Disk3/medias"),
    Path("/Volumes/Disk4/medias"),
]

BATCH_SIZE = 500


def collect_appledouble_files(root: Path) -> list[Path]:
    """Robust walk for ._* files (survives transient FileNotFoundError)."""
    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            try:
                if entry.is_dir():
                    stack.append(entry)
                elif entry.is_file() and entry.name.startswith("._"):
                    found.append(entry)
            except (OSError, PermissionError):
                continue
    return found


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)
    except (OSError, PermissionError):
        return None


def build_smoke_pool(disks: list[Path], pool_size: int = 50) -> dict[Path, tuple[int, int] | None]:
    """Pick `pool_size` real video files to verify between batches."""
    import random
    random.seed(2026)
    candidates: list[Path] = []
    for d in disks:
        if not d.is_dir():
            continue
        # Walk for .mkv files (skip ._*); take first 200 per disk
        n_found = 0
        for p in d.rglob("*.mkv"):
            if p.is_file() and not p.name.startswith("._"):
                candidates.append(p)
                n_found += 1
                if n_found >= 200:
                    break
    random.shuffle(candidates)
    pool = candidates[:pool_size]
    return {p: file_signature(p) for p in pool}


def verify_smoke_pool(pool: dict[Path, tuple[int, int] | None]) -> list[str]:
    fails: list[str] = []
    for p, sig_before in pool.items():
        if not p.exists():
            fails.append(f"SMOKE_LOST: {p}")
            continue
        if file_signature(p) != sig_before:
            fails.append(f"SMOKE_MODIFIED: {p}")
    return fails


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Real deletes (default: dry-run)")
    parser.add_argument("--disk", type=Path, default=None,
                        help="Limit to one disk root (e.g. /Volumes/Disk4/medias)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    disks = [args.disk] if args.disk else DISKS
    mode = "APPLY" if args.apply else "DRY-RUN"
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = Path(f"/tmp/cleanup_appledouble_{timestamp}.log")

    print(f"[{mode}] AppleDouble cleanup — log: {log_path}")
    print(f"Scanning {len(disks)} disk(s)...")

    all_files: list[Path] = []
    for d in disks:
        if not d.is_dir():
            print(f"  skip {d} (not mounted)")
            continue
        files = collect_appledouble_files(d)
        print(f"  {d}: {len(files)} ._* files")
        all_files.extend(files)

    total = len(all_files)
    print(f"\nTotal AppleDouble files: {total}")
    if total == 0:
        print("Nothing to do.")
        return 0

    # Group by extension for visibility
    by_ext: dict[str, int] = {}
    for f in all_files:
        ext = f.suffix.lower() or "<no-ext>"
        by_ext[ext] = by_ext.get(ext, 0) + 1
    print("\nBy extension:")
    for ext, count in sorted(by_ext.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {ext:<15} {count}")

    if not args.apply:
        print(f"\n[DRY-RUN] Re-run with --apply to delete {total} files.")
        return 0

    # Build smoke pool (real videos that must NOT be touched)
    print("\n=== Building smoke pool ===")
    smoke = build_smoke_pool(disks, pool_size=50)
    print(f"  {len(smoke)} real .mkv files in smoke pool")

    # Apply in batches
    batch_size = args.batch_size
    n_batches = (total + batch_size - 1) // batch_size
    deleted = errors = 0
    start = time.time()

    with log_path.open("w") as log:
        log.write(f"# AppleDouble cleanup — {timestamp}\n")
        log.write(f"# Total: {total}, batches: {n_batches}, batch_size: {batch_size}\n\n")
        for i in range(n_batches):
            batch = all_files[i * batch_size : (i + 1) * batch_size]
            t0 = time.time()
            log.write(f"\n=== BATCH {i + 1}/{n_batches} ({len(batch)} items) ===\n")
            for f in batch:
                try:
                    size = f.stat().st_size if f.exists() else 0
                    f.unlink()
                    log.write(f"DELETED {size}b {f}\n")
                    deleted += 1
                except OSError as exc:
                    log.write(f"ERROR {f}: {exc}\n")
                    errors += 1
            log.flush()

            # Smoke check
            fails = verify_smoke_pool(smoke)
            if fails:
                print(f"  ❌ SMOKE FAILED batch {i + 1}: {len(fails)} regressions — ABORT")
                log.write(f"\n# SMOKE_FAIL after batch {i + 1}:\n")
                for f in fails:
                    log.write(f"#   {f}\n")
                return 1

            elapsed = time.time() - t0
            total_elapsed = time.time() - start
            done = deleted + errors
            eta = (total - done) / max(done, 1) * total_elapsed
            print(f"  batch {i + 1}/{n_batches}: {len(batch)} items in {elapsed:.1f}s  "
                  f"(total {total_elapsed:.0f}s, ETA {eta:.0f}s) ✓ smoke OK")
            log.write(f"# batch_{i + 1}: deleted={deleted}, errors={errors}, time={elapsed:.1f}s\n")

    print("\n=== FINAL ===")
    print(f"  Deleted: {deleted}")
    print(f"  Errors: {errors}")
    print(f"  Time: {time.time() - start:.0f}s")
    print(f"  Log: {log_path}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
