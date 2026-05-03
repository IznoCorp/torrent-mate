# Phase 4 — Performance + Incremental + Enrich Modes

## Gate

**Prerequisite (Phase 3 exit gate):**

> cold→FS-mutate→incremental sequence reproduces expected drift events; soft-delete only after N strikes; rename survives via OSHash; unmounted disk = no strikes.

**This phase's exit gate (verbatim from DESIGN §16):**

> All four modes hit their target times in §11.11; SIGTERM during a `--full` scan results in resumable state on next run; Spotlight detection is exercised on a real APFS volume in CI when available, dir-mtime fallback path covered by pyfakefs tests.

---

## Scope

Complete the four scan modes by adding `incremental` (OSHash recompute + rename resolution) and `enrich` (pymediainfo + NFO + artwork, budget-bounded). Layer all performance optimisations: ThreadPoolExecutor per-disk parallelism, macOS `F_RDADVISE` sequential hint, read-rate token bucket, bulk-insert during `full`, mount-flag detection, Spotlight probe (APFS staging only), and SIGTERM clean shutdown. Deliver the performance regression test fixture and baseline.

---

## Sub-phases

### 4.1 — `--mode incremental`

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add incremental path)_
- `tests/indexer/test_scanner.py` _(extend)_

**Deliverable:**

- `incremental` = `quick` + recompute OSHash on every new or changed file (tier-1 mismatch → OSHash recompute, not just xxh3_partial) + rename resolution via OSHash lookup against existing rows.
- Rename resolution rule from DESIGN §17.1: rename only if hash + size match AND old path is absent this scan. Otherwise `enqueue_repair(reason='oshash_collision')`.
- Tests: new file → OSHash computed and stored; renamed file (same content, new path) → row updated, no new `deleted_item`, no new `media_file` row.

**Tests added:** extend `tests/indexer/test_scanner.py`

**Commit:** `feat(media-indexer): 4.1 scanner --mode incremental OSHash and rename resolution`

---

### 4.2 — `--mode enrich`

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add enrich path)_
- `personalscraper/indexer/mediainfo.py` _(modify — wire into scanner)_
- `tests/indexer/test_scanner.py` _(extend)_
- `tests/e2e/test_indexer_cold_to_warm.py` _(extend — enrich half)_

**Deliverable:**

- `enrich` = `incremental` + pymediainfo + NFO parse + artwork inventory on rows where `enriched_at IS NULL OR enriched_at < MAX(mtime_ns)/1_000_000_000`.
- Budget-bounded: prioritises files by `media_item.date_modified DESC` (most recently touched first). Stops when `budget_seconds` elapsed. Remaining files retain `enriched_at=NULL`.
- Per-file commit (not per-disk) for enrich — ensures partial progress is saved.
- `parse_speed=0.5` when `--quick` flag passed alongside `--mode enrich`; otherwise `parse_speed=1.0`.
- `media_stream` rows populated from pymediainfo output via `MediaInfoWrapper.extract_streams()`.
- `media_item.nfo_status` updated (`missing`/`invalid`/`valid`) from NFO presence check.
- `media_item.artwork_json` updated with `ArtworkInventory` from disk scan.
- `enriched_at` set to current epoch seconds after successful enrich of a file.
- Tests: file with `enriched_at=NULL` gets `media_stream` rows after enrich; budget exhaustion leaves remaining files with `enriched_at=NULL`; `library status` shows enrich-pending count.

**Tests added:** extend `tests/indexer/test_scanner.py`, extend `tests/e2e/test_indexer_cold_to_warm.py`

**Commit:** `feat(media-indexer): 4.2 scanner --mode enrich pymediainfo budget-bounded`

---

### 4.3 — ThreadPoolExecutor per-disk parallelism

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — wrap disk loop in ThreadPoolExecutor)_
- `tests/indexer/test_scanner.py` _(extend)_

**Deliverable:**

- `ThreadPoolExecutor(max_workers=min(len(mounted_disks), config.indexer.scan.max_workers_total))` — one worker per physical disk.
- `--full --disk D` degrades to single worker (disk-friendliness over speed per DESIGN §11.8).
- Walk within each disk remains sequential (avoids thrashing macFUSE FUSE queue).
- Per-disk transactions still isolated — a failure on one disk does not roll back others.
- SIGTERM handler (see 4.9) must be compatible with the executor: on signal, cancel pending futures, allow running worker to finish its current file cleanly.
- Tests: two mock disks scanned concurrently; each disk's rows appear in DB; a simulated IOError on disk 2 does not lose disk 1's progress.

**Tests added:** extend `tests/indexer/test_scanner.py`

**Commit:** `feat(media-indexer): 4.3 scanner ThreadPoolExecutor per-disk parallelism`

---

### 4.4 — Mount-flag detection + storage.md update

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add mount-flag check at scan start)_
- `docs/reference/storage.md` _(modify — add mount flags + 24 TB ops guide section)_

**Deliverable:**

- At scan start, parse `mount` command output for each disk's mount point. Warn via structlog `indexer.disk.mount_flags_missing` if any of `noatime`, `noappledouble`, `noapplexattr`, `defer_permissions`, `allow_other` is absent. Note: `nodiratime` is Linux-only; correct set for macOS NTFS-via-macFUSE is the above five (DESIGN §11.6).
- Warning is non-fatal — scan proceeds regardless.
- `docs/reference/storage.md` gains a section "Recommended mount flags for NTFS-via-macFUSE" listing the five flags with explanation, and a "24 TB operations guide" section (cold rebuild rotation, budget planning).

**Tests added:** None (mount detection tested via mocked `subprocess.run` in `test_scanner.py` extension).

**Commit:** `feat(media-indexer): 4.4 mount-flag detection and storage.md 24TB ops guide`

---

### 4.5 — macOS `F_RDADVISE` sequential hint

**Files touched:**

- `personalscraper/indexer/_macos_io.py` _(new)_
- `personalscraper/indexer/fingerprint.py` _(modify — call `sequential_hint` before each file open)_
- `personalscraper/indexer/mediainfo.py` _(modify — call `sequential_hint` before mediainfo open)_
- `tests/indexer/test_fingerprint.py` _(extend — hint no-op on non-Darwin)_

**Deliverable:**

- `_macos_io.py` exposes `sequential_hint(fd: int, offset: int = 0, length: int = 0) -> None`.
- On Darwin: calls `fcntl(fd, F_RDADVISE, struct.pack('qi', offset, length))`. `F_RDADVISE = 35` on macOS.
- On non-Darwin: no-op (no import error).
- `os.posix_fadvise` is explicitly NOT used (does not exist on Darwin per DESIGN §11.6).
- Tests: on non-Darwin, `sequential_hint` runs without error; on Darwin (CI), call does not raise.

**Tests added:** extend `tests/indexer/test_fingerprint.py`

**Commit:** `feat(media-indexer): 4.5 indexer/_macos_io.py F_RDADVISE sequential hint`

---

### 4.6 — Read-rate token bucket

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — thread-safe token bucket wrapping file reads)_
- `tests/indexer/test_scanner.py` _(extend)_

**Deliverable:**

- `TokenBucket(rate_mb_per_sec: float | None)` — if `None`, all reads pass through immediately (default, DESIGN §11.6).
- When set: fingerprint and mediainfo reads acquire tokens before each read chunk. Token bucket is shared across all worker threads.
- Tests: with rate=1 MB/s and a 2 MB read, elapsed time ≥ 2 s (mocked clock); with rate=None, no delay.

**Tests added:** extend `tests/indexer/test_scanner.py`

**Commit:** `feat(media-indexer): 4.6 read-rate token bucket for throttled scanning`

---

### 4.7 — Bulk-insert optimisation (already partially in 2.5 — verify + test)

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — confirm drop-indexes path, add `executemany` batching)_
- `tests/indexer/test_scanner.py` _(extend)_

**Deliverable:**

- Confirms and completes the bulk-insert path introduced in 2.5: on `--mode full` start for a disk, explicitly drop all secondary indexes on `media_file` and `media_stream` (`DROP INDEX IF EXISTS idx_*`), run `executemany` in batches of 5 000 inside `BEGIN IMMEDIATE`, recreate indexes afterwards (DESIGN §11.7).
- `incremental`/`enrich`/`quick` modes keep indexes intact.
- Tests: full scan on 6 000-item fixture uses `executemany`; incremental scan does not drop indexes (spy on `conn.execute` for `DROP INDEX`).

**Tests added:** extend `tests/indexer/test_scanner.py`

**Commit:** `test(media-indexer): 4.7 bulk-insert coverage and assertions for full scan`

---

### 4.8 — Spotlight probe (APFS staging only)

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add Spotlight probe at scan start)_
- `tests/e2e/test_indexer_spotlight_unavailable.py` _(new)_
- `tests/e2e/test_indexer_spotlight_partial.py` _(new)_

**Deliverable:**

- At scan start: run `mdutil -s <mount>` for every disk and the staging dir. Log `indexer.spotlight.available` or `indexer.spotlight.unavailable` per path.
- `SpotlightChangeDetector` attaches only on APFS paths (detected via `mount` type). On macFUSE paths: refuses to attach, logs `indexer.spotlight.skipped_macfuse` once per session. Storage disks always use dir-mtime walk regardless of Spotlight state.
- `disks.json5` `spotlight_enabled: bool` (default false) is respected only for APFS; ignored for macFUSE with a warning.
- E2E tests: mock `mdutil -s` returning `off` / `Indexing enabled but rebuilding` / timeout → assert dir-mtime walk fallback runs in each case; `indexer.spotlight.skipped_*` logged with reason.

**Tests added:** `tests/e2e/test_indexer_spotlight_unavailable.py`, `tests/e2e/test_indexer_spotlight_partial.py`

**Commit:** `feat(media-indexer): 4.8 Spotlight probe APFS-only with macFUSE fallback`

---

### 4.9 — SIGTERM clean-shutdown handler

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add `signal.signal(SIGTERM, ...)` handler)_
- `tests/e2e/test_indexer_sigterm.py` _(new — SIGTERM-specific test, distinct from unplug)_

**Deliverable:**

- `signal.signal(SIGTERM, _handle_sigterm)` registered at scan start. Handler sets a `threading.Event` flag `_shutdown_requested`.
- Scanner checks the flag at each file boundary (not mid-file). On flag set: finish current file, commit current disk's transaction, update `scan_run.last_path`, set `scan_run.status='ok'` with `budget_exhausted=true`, exit 0.
- Compatible with ThreadPoolExecutor: main thread checks flag; workers finish their current file and drain naturally.
- E2E test: `test_indexer_sigterm.py` — start a scan, send SIGTERM mid-walk via subprocess; assert `scan_run.status='ok'`, `scan_run.last_path` populated, exit code 0; next invocation resumes from `last_path` and produces identical final DB state to an uninterrupted run.

**Tests added:** `tests/e2e/test_indexer_sigterm.py`

**Commit:** `feat(media-indexer): 4.9 SIGTERM clean-shutdown handler for scanner`

---

### 4.9b — Disk-unplug-during-scan handling (macFUSE EIO mid-scan)

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — strengthen per-disk EIO handling on top of 3.5 circuit breaker)_
- `tests/e2e/test_indexer_unplug_during_scan.py` _(new — DESIGN §15.5 enumerated)_

**Deliverable:**

- Builds on the per-disk circuit breaker (Phase 3.5) and the ThreadPool isolation (4.3): when a worker thread encounters `OSError(EIO)` mid-walk on its assigned disk, the per-disk transaction rolls back cleanly without disturbing the other workers' transactions.
- Sentinel file remains intact (no write attempt during the unplug window).
- E2E `test_indexer_unplug_during_scan.py`: monkey-patch `os.path.ismount` to flip false at file 50/100 of Disk2 mid-scan; assert per-disk transaction for Disk2 rolled back, Disk1 progress committed, sentinel intact, `indexer.disk.io_error` logged, `disk.unreachable_strikes += 1`. This test is distinct from the SIGTERM test (4.9) — different failure trigger, different recovery path.

**Tests added:** `tests/e2e/test_indexer_unplug_during_scan.py`

**Commit:** `feat(media-indexer): 4.9b strengthen disk-unplug-mid-scan handling and E2E test`

---

### 4.10a — Perf fixture builder + baseline data

**Files touched:**

- `tests/e2e/perf/__init__.py` _(new — empty)_
- `tests/e2e/perf/build_fixture.py` _(new)_
- `tests/e2e/perf/FIXTURE_VERSION` _(new — integer `1`)_
- `tests/e2e/perf/baseline.json` _(new — initial baseline data only, no test assertions)_

**Deliverable:**

- `build_fixture.py`: deterministic 1 000-item / ~1 TB virtual FS using pinned random seed. File-size distribution: 5 % > 50 GB (sparse via `truncate(2)`), 70 % 1–5 GB (sparse), 25 % < 100 MB (real pseudo-random content). Output to `tests/e2e/perf/.fixture/` (gitignored). Fixture version from `FIXTURE_VERSION`.
- `baseline.json` schema: `[{fixture_version, mode, target_seconds, last_measured_seconds, last_measured_at}]` per DESIGN §15.6.1. **Six rows** corresponding to the six rows in DESIGN §11.11 — including the two distinct `quick` rows (`quick_merkle_hit` and `quick_merkle_miss`). Without this split, a regression from <5 s → 60 s could pass the "quick" target check if only the slower row is recorded.
- Initial `baseline.json` populated with targets from DESIGN §11.11 as `target_seconds`; `last_measured_seconds` set to `target_seconds * 0.8` as placeholder until first real CI run.

**Tests added:** None (data-only sub-phase).

**Commit:** `test(media-indexer): 4.10a perf fixture builder and baseline data`

---

### 4.10b — Perf regression test + Makefile rebaseline target

**Files touched:**

- `tests/e2e/perf/test_indexer_perf.py` _(new)_
- `Makefile` _(modify — add `perf-rebaseline` target)_

**Deliverable:**

- `test_indexer_perf.py`: `@pytest.mark.slow` (off by default). Tests all six rows from DESIGN §11.11 (`quick_merkle_hit`, `quick_merkle_miss`, `quick_changed_100`, `incremental_new_100`, `enrich_missing_1000`, `full_one_disk`). Regression rule: fail if `current > last_measured_seconds * 1.5`.
- Additional invariant tests: splittable cold scan (`--full --disk D1` then `--full --disk D2` = same as `--full`); two-stage path (cold `quick` then `enrich` = single `full`).
- `make perf-rebaseline`: runs tests, writes new `baseline.json`, CI job commits with `[bot] perf baseline` message.
- Per-PR CI compares against the file; only scheduled CI on `main` regenerates.

**Tests added:** `tests/e2e/perf/test_indexer_perf.py`

**Commit:** `test(media-indexer): 4.10b perf regression test and Makefile rebaseline target`

---

## Acceptance criteria

- [ ] `pytest tests/indexer/` and `pytest tests/e2e/` (excluding `@pytest.mark.slow`) pass.
- [ ] `--mode incremental` on a fixture with 100 renamed files: all 100 rows updated, zero new `media_file` rows, zero `deleted_item` rows.
- [ ] `--mode enrich` on 1 000-item fixture with budget: stops within budget + 10 s; remaining files have `enriched_at=NULL`.
- [ ] Two-disk fixture scan uses 2 concurrent workers (confirmed via thread count assertion).
- [ ] `sequential_hint` runs without error on both Darwin and non-Darwin CI.
- [ ] Read-rate token bucket at 1 MB/s slows a 2 MB read to ≥ 2 s (mocked clock).
- [ ] Mount-flag missing warning logged (`indexer.disk.mount_flags_missing`) when `noatime` absent from mock `mount` output.
- [ ] Spotlight skipped on macFUSE mount (`indexer.spotlight.skipped_macfuse` logged); dir-mtime walk runs.
- [ ] `tests/e2e/test_indexer_sigterm.py` passes: SIGTERM mid-scan → `scan_run.status='ok'`, `last_path` non-null, resume produces identical DB state.
- [ ] `tests/e2e/test_indexer_unplug_during_scan.py` passes: Disk1 progress committed; Disk2 transaction rolled back; `disk.unreachable_strikes` incremented.
- [ ] `pytest -m slow tests/e2e/perf/test_indexer_perf.py` runs all six budget rows from DESIGN §11.11 and measures within 1.5× baseline.
- [ ] `baseline.json` contains six rows including both `quick_merkle_hit` and `quick_merkle_miss`.

---

## DESIGN cross-references

Implements: §11.1 (all four scan modes), §11.2 (disk rotation for cold scans), §11.3 (two-stage fingerprint+enrich), §11.4 (deferred enzyme/mutagen noted as out-of-scope V1), §11.5 (Spotlight APFS-only constraint), §11.6 (read-traffic minimisation: noatime flags, F_RDADVISE, OSHash extension allowlist, O_RDONLY, scandir stat reuse, token bucket), §11.7 (ingest-side bulk-insert + executemany), §11.8 (ThreadPoolExecutor parallelism), §11.9 (crash safety + SIGTERM), §11.10 (dir-mtime subtree skip — verified), §11.11 (performance budget targets), §15.5 (E2E: budget/resume, unplug-during-scan, spotlight, disk-swap), §15.6 (performance regression tests), §15.6.1 (fixture builder + baseline).

---

## Out of scope for this phase

- Outbox write-through — Phase 5.
- Consumer migration — Phases 6–7.
- `library verify`, `library search`, `library repair`, `library show` CLI — Phase 8.
- `enzyme`/`mutagen` container fast-path — V1.1 (DESIGN §11.4, §17.3).
- `getattrlistbulk` ctypes wrapper — V1.1 (DESIGN §17.3).
- Web UI — out of scope entirely (DESIGN §3).
