"""Full cleanup orchestrator, batched.

Configuration:
  - 1615 items total = 15 batches of 100 + 1 batch of 115
  - No backup (validated via v1+v2+v3 sample tests, 233 deletions, 0 regression)
  - Per-batch: delete + empty-dir walk-up + progress log
  - Single log file: /tmp/full_cleanup_<timestamp>.log

Safety:
  - Deletes ONLY items from validated SAFE lists (AppleDouble + .actors/)
  - Empty-dir cleanup uses os.rmdir (kernel-enforced) + anchor protection
  - Final invariant check: no anchor missing
"""

from __future__ import annotations

import csv
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/tmp")
from cleanup_disk_residue import actors_is_safe_to_delete, list_actors_dirs  # noqa: E402
from cleanup_empty_dirs import DISKS as ANCHOR_DISKS  # noqa: E402
from cleanup_empty_dirs import cleanup_walk_up  # noqa: E402

CSV_V3 = Path("/tmp/nfo_audit_v3.csv")
BATCH_SIZE = 100
LAST_BATCH_SIZE = 115
TOTAL_EXPECTED = 1615


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)
    except (OSError, PermissionError):
        return None


def build_smoke_pool() -> dict[Path, tuple[int, int] | None]:
    """Random sample of KEEPs + tvshow.nfo + .mkv to verify between batches.

    These files MUST remain untouched throughout the full run. If any
    changes signature OR disappears between batches → abort cleanup.
    """
    import random
    random.seed(2026)
    pool: list[Path] = []

    # 30 random KEEP_HAS_SIBLING NFOs
    keeps: list[Path] = []
    tvshows: list[Path] = []
    rows = []
    with CSV_V3.open() as fh:
        rows = list(csv.DictReader(fh))
    random.shuffle(rows)
    for row in rows:
        if row["classification"] == "KEEP_HAS_SIBLING" and len(keeps) < 30:
            p = Path(row["path"])
            if p.exists():
                keeps.append(p)
        elif row["classification"] == "KEEP_TVSHOW_ROOT" and len(tvshows) < 15:
            p = Path(row["path"])
            if p.exists():
                tvshows.append(p)
        if len(keeps) >= 30 and len(tvshows) >= 15:
            break
    pool.extend(keeps + tvshows)

    # 20 real .mkv via FS scan
    mkvs = 0
    for disk in ANCHOR_DISKS:
        if not disk.is_dir():
            continue
        for p in disk.rglob("*.mkv"):
            if p.is_file() and not p.name.startswith("._"):
                pool.append(p)
                mkvs += 1
                if mkvs >= 20:
                    break
        if mkvs >= 20:
            break

    return {p: file_signature(p) for p in pool}


def verify_smoke_pool(pool: dict[Path, tuple[int, int] | None]) -> list[str]:
    """Re-check the smoke pool. Returns list of failures (empty = OK)."""
    fails: list[str] = []
    for p, sig_before in pool.items():
        if not p.exists():
            fails.append(f"SMOKE_LOST: {p}")
            continue
        sig_now = file_signature(p)
        if sig_now != sig_before:
            fails.append(f"SMOKE_MODIFIED: {p} {sig_before} → {sig_now}")
    return fails


def collect_targets() -> list[Path]:
    """Build the full safe list of items to delete. Deterministic order."""
    targets: list[Path] = []

    # 1. DELETE_APPLEDOUBLE NFOs from CSV (only ones still existing)
    ad_count = 0
    with CSV_V3.open() as fh:
        for row in csv.DictReader(fh):
            if row["classification"] != "DELETE_APPLEDOUBLE":
                continue
            p = Path(row["path"])
            if p.exists():
                targets.append(p)
                ad_count += 1

    # 2. .actors/ dirs (live discovery, sorted for determinism)
    actors = sorted([d for d in list_actors_dirs() if d.is_dir()])
    actors_count = len(actors)
    targets.extend(actors)

    print(f"  AppleDouble NFOs still present: {ad_count}")
    print(f"  .actors/ dirs still present: {actors_count}")
    print(f"  TOTAL targets: {len(targets)}")
    return targets


def split_batches(items: list[Path], batch_size: int, last_batch_size: int) -> list[list[Path]]:
    """Split into N batches where the last one has last_batch_size."""
    batches: list[list[Path]] = []
    remaining = list(items)
    while len(remaining) > last_batch_size + batch_size - 1:
        batches.append(remaining[:batch_size])
        remaining = remaining[batch_size:]
    if remaining:
        batches.append(remaining)
    return batches


def delete_one(target: Path, log) -> tuple[bool, str]:
    """Return (success, msg)."""
    try:
        if not target.exists():
            return (False, "SKIP_MISSING")
        if target.is_file():
            size = target.stat().st_size
            target.unlink()
            return (True, f"FILE {size}b")
        if target.is_dir() and target.name == ".actors":
            safe, reason = actors_is_safe_to_delete(target)
            if not safe:
                return (False, f"SKIP_UNSAFE: {reason}")
            files = list(target.iterdir())
            total = sum(p.stat().st_size for p in files if p.is_file())
            shutil.rmtree(target)
            return (True, f"ACTORS {len(files)}files {total}b")
        return (False, "UNEXPECTED_TYPE")
    except OSError as exc:
        return (False, f"ERROR: {exc}")


def run_batch(batch_no: int, total_batches: int, batch: list[Path], log) -> tuple[int, int, int]:
    """Process one batch. Returns (deleted, skipped, empty_removed)."""
    deleted = 0
    skipped = 0
    deletion_sites: list[Path] = []

    log.write(f"\n=== BATCH {batch_no}/{total_batches} ({len(batch)} items) ===\n")
    log.flush()

    for t in batch:
        ok, msg = delete_one(t, log)
        log.write(f"  {msg} {t}\n")
        if ok:
            deleted += 1
            deletion_sites.append(t)
        else:
            skipped += 1
    log.flush()

    # Empty-dir walk-up per batch
    log.write(f"--- empty-dir walk-up (batch {batch_no}) ---\n")
    log.flush()

    class LogPrint:
        """Redirect cleanup_walk_up print output to log."""
        def __init__(self, real_log):
            self.log = real_log
        def write(self, s):
            self.log.write(s)
        def flush(self):
            self.log.flush()

    # cleanup_walk_up uses print(), capture via stdout swap
    import io
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        _, empty_removed = cleanup_walk_up(deletion_sites, max_up=3, apply=True)
    finally:
        sys.stdout = old_stdout
    log.write(captured.getvalue())
    log.flush()

    return (deleted, skipped, empty_removed)


def final_invariant_check() -> list[str]:
    """Verify anchor dirs still exist and are dirs."""
    issues: list[str] = []
    for d in ANCHOR_DISKS:
        if not d.is_dir():
            issues.append(f"ANCHOR_MISSING: {d}")
    return issues


def main() -> int:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = Path(f"/tmp/full_cleanup_{timestamp}.log")
    print(f"=== Full cleanup (batched) — log: {log_path} ===\n")

    print("=== Collecting targets ===")
    targets = collect_targets()
    if not targets:
        print("No targets — nothing to do.")
        return 0

    actual_count = len(targets)
    if actual_count != TOTAL_EXPECTED:
        print(f"  [WARN] expected {TOTAL_EXPECTED}, got {actual_count}")

    batches = split_batches(targets, BATCH_SIZE, LAST_BATCH_SIZE)
    print(f"  Splitting into {len(batches)} batches: " +
          ", ".join(str(len(b)) for b in batches))

    # Build smoke pool (verified between every batch)
    print("\n=== Building smoke pool ===")
    smoke_pool = build_smoke_pool()
    print(f"  {len(smoke_pool)} items in smoke pool (KEEPs + tvshow.nfo + real .mkv)")

    total_deleted = 0
    total_skipped = 0
    total_empty = 0
    start_time = time.time()

    with log_path.open("w") as log:
        log.write(f"# Full cleanup — {timestamp}\n")
        log.write(f"# Targets: {actual_count}\n")
        log.write(f"# Batches: {len(batches)}\n")
        log.write(f"# Smoke pool: {len(smoke_pool)} items\n\n")

        for i, batch in enumerate(batches, 1):
            t0 = time.time()
            print(f"\n--- BATCH {i}/{len(batches)} ({len(batch)} items) ---")
            deleted, skipped, empty = run_batch(i, len(batches), batch, log)
            elapsed = time.time() - t0
            total_deleted += deleted
            total_skipped += skipped
            total_empty += empty
            total_elapsed = time.time() - start_time
            avg_per_item = total_elapsed / max(total_deleted + total_skipped, 1)
            eta_remaining = (actual_count - (total_deleted + total_skipped)) * avg_per_item
            print(f"  deleted={deleted}, skipped={skipped}, empty_removed={empty} "
                  f"({elapsed:.1f}s, total {total_elapsed:.0f}s, ETA {eta_remaining:.0f}s)")
            log.write(f"# batch_{i}: deleted={deleted}, skipped={skipped}, empty={empty}, time={elapsed:.1f}s\n")
            log.flush()

            # Smoke check after every batch
            smoke_fails = verify_smoke_pool(smoke_pool)
            if smoke_fails:
                print(f"  ❌ SMOKE CHECK FAILED ({len(smoke_fails)}) — ABORT")
                log.write(f"# SMOKE_CHECK_FAIL after batch {i}:\n")
                for f in smoke_fails:
                    log.write(f"#   {f}\n")
                    print(f"    {f}")
                log.flush()
                return 1
            print(f"  ✓ smoke check OK ({len(smoke_pool)} items intact)")
            log.write(f"# smoke_check_ok: {len(smoke_pool)} items\n")
            log.flush()

    print("\n=== FINAL ===")
    print(f"  Deleted: {total_deleted}")
    print(f"  Skipped: {total_skipped}")
    print(f"  Empty dirs removed: {total_empty}")
    print(f"  Total time: {time.time() - start_time:.0f}s")

    # Invariant check
    print("\n=== Invariant check ===")
    issues = final_invariant_check()
    if issues:
        print(f"  [ISSUES: {len(issues)}]")
        for i in issues:
            print(f"    {i}")
        return 1
    print("  [OK] All anchor dirs intact")

    print(f"\nLog: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
