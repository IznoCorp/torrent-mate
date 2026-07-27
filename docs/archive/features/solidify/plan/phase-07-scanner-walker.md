# Phase 7 — Scanner walk skeleton (T8)

## Gate

```bash
make lint && make test && make check

# Mock-patch-target moves for the walker seams (zero stale patches)
rg -n "patch\(.*scanner\.__init__" -g '*.py' tests/                 # 0 — patch the real _walker seams
rg -n "def _walk_dir_full|def _walk_dir_quick|def _walk_dir_incremental" -g '*.py' personalscraper/indexer/  # collapsed to _walker.py only

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-08 — one walker: scandir only in _walker.py within scanner/)
test "$(rg -l 'scandir' -t py personalscraper/indexer/scanner/ | wc -l)" = "1" && echo ACC-08-OK
```

## Objective

Collapse the five near-identical walkers into ONE `walk(root, visitor, *, budget,
shutdown, checkpoint)` skeleton in `indexer/scanner/_walker.py` with per-dir/per-file
visitor callbacks (DESIGN §5 T8); quick/incremental/enrich/full become visitors. SIGTERM /
budget / checkpoint are handled once (closing the drift gap where the walkers diverged on
SIGTERM handling). Merkle short-circuit + bulk-freeze + root-recompute become one
implementation. The 22-parameter `scan()` signature collapses into a frozen `ScanRequest`
dataclass; mode dispatch becomes a registry dict. Mock-patch-target hostages in
`scanner/__init__.py` move to real modules so tests patch the new seams.

## Findings addressed

INDEXER-01 (five near-identical walkers diverged on SIGTERM handling), INDEXER-02, INDEXER-05,
INDEXER-06, MECHANICAL-DUP-02.

## Code anchors (verified)

- `personalscraper/indexer/scanner/__init__.py`: `scan(...)` :337 — 22-ish parameters (`disks, mode, generation, conn, disk_filter, drop_indexes, *, budget_seconds, db_path, checkpoint_every_n_files, disk_breaker, confirm_bulk_change, merkle_delta_freeze_threshold, quick_enrich, backfill_streams, max_workers, read_rate_mb_per_sec, staging_dir, spotlight_enabled, paranoia_window_seconds, no_enqueue, fs_type_overrides, event_bus, config`) returning `ScanRunResult`; recursive `os.scandir` walk documented at :395. Note `event_bus: EventBus` is a REQUIRED keyword-only parameter (no default) — preserve that.
- `personalscraper/indexer/scanner/_walker.py`: multiple walkers to collapse — `_walk_dir` :258, `_walk_dir_full` :420, `_walk_dir_full_buffered` :583, `_walk_dir_quick` :659, plus helpers `_verify_dir_mtime_reliable` :63, `_build_disk_fingerprints` :106, `_sample_fresh_fingerprints` :176, `_log_stat_failed` :42.
- `personalscraper/indexer/scanner/_modes/`: `incremental.py::_walk_dir_incremental` :201 (own `os.scandir` :272), `enrich.py` (`os.scandir` :172, :268), `quick.py` (`os.scandir` sampling :302), `full.py`, `verify.py`, `_item_stage.py`, `_canonical.py`, `backfill*.py`. These are the mode implementations that become visitors.
- scandir call-sites today (ACC-08 target = only `_walker.py`): `_walker.py`, `_modes/enrich.py`, `_modes/incremental.py`, `_modes/quick.py`, and `scanner/__init__.py` (:395). After this phase, scandir lives only in `_walker.py`.
- `ScanRequest`: NEW frozen dataclass (verified absent); `ScanRunResult` is the existing return type to keep.

## Tasks

1. **P7.1 — memtrace guard.** Diff `get_impact` for the scanner community against the P0 baseline (the scanner feeds `scan_run` lifecycle + outbox). Note callers of `scan()` (CLI library scan, web maintenance). Verify: recorded in IMPLEMENTATION.md; no surprise caller.
2. **P7.2 — `ScanRequest` dataclass.** Add a frozen `ScanRequest` dataclass capturing the 22 `scan()` params (keeping `event_bus` REQUIRED and `config` as provided); `scan()` accepts a `ScanRequest` (or builds one internally first) without changing behaviour. Update the CLI/web callers to construct `ScanRequest`. Verify: `pytest tests -k "scan_request or scanner_scan" -q`; the CLI `library scan` and web maintenance scan produce identical `ScanRunResult`.
3. **P7.3 — `walk(root, visitor, *, budget, shutdown, checkpoint)`.** Implement the single walk skeleton in `_walker.py` with per-dir + per-file visitor callbacks; SIGTERM/budget/checkpoint handled once (unify the divergent SIGTERM handling — the drift gap). Verify: `pytest tests -k "walker or walk_skeleton or scan_shutdown" -q`; a SIGTERM mid-walk produces a clean checkpoint in every mode (previously divergent).
4. **P7.4 — Modes become visitors.** Reimplement quick/incremental/enrich/full as visitor objects (per-dir/per-file callbacks) over `walk()`, removing `_walk_dir_full`/`_walk_dir_full_buffered`/`_walk_dir_quick` from `_walker.py` and `_walk_dir_incremental` + the `os.scandir` loops from `_modes/*`. Keep the enrich visitor writing the single `artwork_json`/NFO truth from P5. Verify: `rg -l 'scandir' -t py personalscraper/indexer/scanner/` == 1 (`_walker.py`); each mode's row-level output unchanged on a fixture disk.
5. **P7.5 — One merkle short-circuit + bulk-freeze + root-recompute.** Consolidate the merkle short-circuit, bulk-change freeze (`confirm_bulk_change`/`merkle_delta_freeze_threshold`) and root-recompute into one implementation shared by the visitors. Verify: `pytest tests -k "merkle or bulk_freeze or root_recompute" -q`; the freeze threshold behaviour is identical.
6. **P7.6 — Mode-dispatch registry + move patch hostages.** Replace the inline `mode == ScanMode.*` dispatch in `scanner/__init__.py` with a registry dict mapping mode → visitor factory; move the symbols tests patch (currently hostages in `__init__.py`) into the real modules and update the patch targets in `tests/`. Verify: `rg -n "patch\(.*scanner\.__init__" -g '*.py' tests/` == 0; scan-mode tests patch the real seams and pass.
7. **P7.7 — Green + module-size.** Full gate; confirm `_walker.py` and `scanner/__init__.py` stay ≤800 non-blank LOC after consolidation (the visitors carry mode-specific logic). Verify: `python3 scripts/check-module-size.py` no new scanner finding; ACC-08 grep == 1.

## Non-goals

- Do not change `scan_run` lifecycle, `repair_queue`, or outbox-drain semantics (single-writer
  library.db; the BDD-validator invariants stay green).
- Do not alter the NFD-raw `media_file.filename` handling or the case-sensitivity gotchas
  (macFUSE/ntfs-3g) — preserve exactly.
- Do not make `event_bus` optional anywhere in the scan path (REQUIRED parameter rule).
- Do not touch the artwork_json/NFO *definition* (P5 owns it); the enrich visitor only writes
  the truth P5 defined.

## Commit

```
refactor(solidify): frozen ScanRequest replaces the 22-param scan() signature
refactor(solidify): one walk(root, visitor, *, budget, shutdown, checkpoint) in _walker.py
refactor(solidify): scan modes become visitors; merkle short-circuit single-impl; move patch seams
```

Phase-gate commit:

```
chore(solidify): phase 7 gate — scanner walk skeleton + ScanRequest + merkle single-impl
```
