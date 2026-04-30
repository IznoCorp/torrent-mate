# Phase 3 — Indexer Core: Drift + Reconciliation

## Gate

**Prerequisite (Phase 2 exit gate):**

> Full scan of fixture FS (Stage A) populates `media_file` rows; subsequent `quick` run with no FS changes reads only directory mtimes; `BootstrapError` raised when `diskutil` cannot resolve a UUID.

**This phase's exit gate (verbatim from DESIGN §16):**

> cold→FS-mutate→incremental sequence reproduces expected drift events; soft-delete only after N strikes; rename survives via OSHash; unmounted disk = no strikes.

---

## Scope

Layer drift detection on top of the scanner: racy-mtime escalation, scan-generation miss-strike accounting, N-strikes soft-delete with `deleted_item` tombstones, the repair queue and budget-bounded worker, resumable scans via `scan_run.last_path`, and the per-disk circuit breaker. Also completes the `verify_disk_mounted` state machine (strike/freeze logic deferred from Phase 2). Property-based tests via `hypothesis` cover idempotence and soft-delete invariants.

---

## Sub-phases

### 3.1 — Drift engine: racy-mtime + generation accounting

**Files touched:**

- `personalscraper/indexer/drift.py` _(new)_
- `tests/indexer/test_drift.py` _(new)_
- `tests/indexer/strategies.py` _(new — hypothesis generators)_

**Deliverable:**

- `drift.py` implements the reconciliation loop from DESIGN §8.1:
  - Per-file: compare tier-1 fingerprint; on match + not-racy → update `scan_generation` only; on mismatch or racy → escalate to `xxh3_partial`; on xxh3 mismatch → `enqueue_repair(reason='content_drift')`.
  - Rename detection: if a file is new (no `(path_id, filename)` row) but an OSHash match exists with a now-missing path → treat as rename, update path, reset strikes.
  - OSHash collision guard (DESIGN §17.1): rename only if hash + size match AND old path missing. Otherwise `enqueue_repair(reason='oshash_collision')`.
  - After per-file loop: rows on this disk with `scan_generation < current` AND `disk.is_mounted=1` → `miss_strikes += 1`.
- `strategies.py` hypothesis generators: `valid_file()`, `valid_disk_layout()`, `mutation()` per DESIGN §15.2.1.
- `test_drift.py` property tests (≥ 5 `@given` decorated tests per DESIGN §15.2):
  1. Idempotence: scanning same FS twice → same DB state.
  2. Generation monotonicity: `scan_generation` strictly increasing across runs.
  3. Soft-delete correctness: `miss_strikes < N` → never `deleted_at`; `miss_strikes >= N` → always `deleted_at`.
  4. Hash determinism: `oshash(f) == oshash(f)` unchanged; `oshash(f) != oshash(g)` for any content edit.
  5. Mtime-clamp invariance: future or pre-1970 mtimes never propagate as `racy=true`; clamped value used for storage and comparison.
  - Note: outbox-drain idempotence property test moved to Phase 5.2 (depends on Phase 5 outbox module).
- E2E tests for drift edge cases (DESIGN §15.5):
  - `tests/e2e/test_indexer_oshash_collision.py` _(new)_: fabricate two files with identical crafted OSHash and different content; rescan; assert `repair_queue(reason='oshash_collision')` row exists, no auto-rename applied.
  - `tests/e2e/test_indexer_racy_mtime.py` _(new)_: write file with mtime exactly `scan_started_at`; assert tier-1 fingerprint flagged racy → tier-2 (xxh3_partial) computed; mtime in the future → clamped + `indexer.fs.invalid_mtime` logged.
- Example-based tests: rename survives via OSHash, oshash_collision enqueues repair not rename.

**Tests added:** `tests/indexer/test_drift.py`, `tests/indexer/strategies.py`, `tests/e2e/test_indexer_oshash_collision.py`, `tests/e2e/test_indexer_racy_mtime.py`

**Commit:** `feat(media-indexer): 3.1 indexer/drift.py racy-mtime and generation accounting`

---

### 3.2 — N-strikes soft-delete + deleted_item tombstone

**Files touched:**

- `personalscraper/indexer/drift.py` _(modify — add soft-delete path)_
- `tests/indexer/test_drift.py` _(extend)_

**Deliverable:**

- After per-file loop for a disk: rows where `miss_strikes >= n_strikes_for_softdelete` (from `IndexerConfig`) → set `deleted_at = now`, INSERT `deleted_item(kind='file', original_id=file.id, deleted_at=now, reason='n_strikes', payload_json=snapshot)`.
- Unmounted disk (`is_mounted=0`) → freeze: no strike increment, no soft-delete, only log `indexer.disk.skipped_unmounted`.
- `MOUNTED_WRONG_DISK` → freeze + log `indexer.disk.uuid_mismatch` + no strike, no delete, alert.
- Strike reset: if a previously-struck file reappears on scan, reset `miss_strikes = 0` and clear `deleted_at` if it was set (file came back — treat as restored).
- `deleted_item_retention_days` from config: rows older than retention are purged on `library repair`.
- Tests: 3-scan sequence (file present, missing, missing, missing) → soft-deleted on 3rd miss (default N=3); unmounted disk → no strike after 5 scans; strike reset on reappearance.

**Tests added:** extend `tests/indexer/test_drift.py`

**Commit:** `feat(media-indexer): 3.2 N-strikes soft-delete and deleted_item tombstone`

---

### 3.3 — Repair queue + budget-bounded worker

**Files touched:**

- `personalscraper/indexer/repair.py` _(new)_
- `tests/indexer/test_repair.py` _(new)_

**Deliverable:**

- `enqueue_repair(conn, scope, scope_id, reason, payload) -> None` — inserts `repair_queue` row. Called from `drift.py` and `merkle.py`.
- `drain(conn, budget_seconds: float) -> RepairStats` — processes `repair_queue` rows in FIFO order (`enqueued_at ASC`, `status='pending'`). Each row processed in its own short transaction; `attempted_at`, `attempts` updated. On success: `status='done'`. On exception: `status='failed'`, logged. Stops when `time.monotonic() - start >= budget_seconds`.
- `library status` warns (non-zero exit, WARN level) if `(oldest pending > 7 days) OR (depth > 1000)` per DESIGN §17.1.
- Tests: drain processes FIFO; budget exhaustion stops at correct point; failed row marked `'failed'` not `'done'`; `library status` WARN triggered.

**Tests added:** `tests/indexer/test_repair.py`

**Commit:** `feat(media-indexer): 3.3 indexer/repair.py queue and budget-bounded drain`

---

### 3.4 — Resumable scan via `scan_run.last_path`

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add checkpoint + resume logic)_
- `tests/e2e/test_indexer_budget_resume.py` _(new)_

**Deliverable:**

- Scanner updates `scan_run.last_path` every `checkpoint_every_n_files` (from config, default 100) files, inside a lightweight subtransaction.
- On startup: if most recent `scan_run.status='running'` AND `started_at > 2 h ago` AND PID dead → treat as crashed, resume from `last_path`; log `indexer.scan.resumed`.
- If `started_at < 2 h ago` AND PID alive → `IndexerLockError("scan already running, PID N")`.
- Budget enforcement: at every checkpoint compare `now - started_at` vs `budget_seconds`; on overrun → finish current file, commit, set `scan_run.status='ok'` with `stats_json.budget_exhausted=true`, exit 0.
- E2E test: start scan with `budget_seconds=5`; mock clock to exceed budget mid-walk; assert `scan_run.status='ok'` with `budget_exhausted=true` and `last_path` populated; second invocation resumes from `last_path` and produces same final DB state as uninterrupted run.
- E2E `tests/e2e/test_indexer_cross_dst.py` _(new — DESIGN §15.5)_: scan crossing a DST or leap-second boundary by mocking `time.time()` to jump ±3600 s mid-scan; assert no spurious racy flags, no double-count of files, `scan_run.last_path` resume is correct.

**Tests added:** `tests/e2e/test_indexer_budget_resume.py`, `tests/e2e/test_indexer_cross_dst.py`

**Commit:** `feat(media-indexer): 3.4 resumable scan via scan_run.last_path and budget checkpoint`

---

### 3.5 — Per-disk circuit breaker

**Files touched:**

- `personalscraper/indexer/breaker.py` _(new)_
- `personalscraper/indexer/scanner.py` _(modify — wire circuit breaker on disk IO error)_
- `tests/indexer/test_drift.py` _(extend — circuit breaker open → disk skipped)_

**Deliverable:**

- `DiskCircuitBreaker` delegates to `personalscraper/scraper/circuit_breaker.py` (already exists). Keyed by `disk.uuid`.
- On `OSError(EIO)` during `os.scandir` for a disk: roll back that disk's transaction, set `disk.is_mounted=0`, increment `disk.unreachable_strikes`, log `indexer.disk.io_error`, open circuit breaker for that disk, continue with remaining disks.
- `OSError: Permission denied` on a single file: log `indexer.file.permission_denied` at WARNING, leave existing row untouched (no strike, no soft-delete), continue.
- mtime in the future or pre-1970: clamp to `[0, scan_started_at_ns]`; log `indexer.fs.invalid_mtime`; store clamped value. Never causes `racy=true` from raw value alone.
- Complete the `verify_disk_mounted` integration in the scanner: `UNMOUNTED` → freeze strikes for disk, log `indexer.disk.skipped_unmounted`, continue (no-op, not an error). Full state machine now wired.
- E2E: `test_indexer_unplug_disk.py` — scan all disks, unmount one (mock `os.path.ismount` = False), scan again → no strike, no soft-delete, only `indexer.disk.skipped_unmounted` event logged.

**Tests added:** extend `tests/indexer/test_drift.py`, `tests/e2e/test_indexer_unplug_disk.py`

**Commit:** `feat(media-indexer): 3.5 per-disk circuit breaker and IO error handling`

---

### 3.6 — Disk-swap freeze (Merkle-delta threshold) + `--confirm-bulk-change`

**Files touched:**

- `personalscraper/indexer/merkle.py` _(modify — add Merkle-delta computation)_
- `personalscraper/indexer/scanner.py` _(modify — wire halt-on-bulk-change branch)_
- `personalscraper/indexer/cli.py` _(modify — add `--confirm-bulk-change` flag to `library index`)_
- `tests/e2e/test_indexer_disk_swap.py` _(new — DESIGN §15.5 enumerated)_

**Deliverable:**

- DESIGN §17.1 disk-swap edge case: same UUID, different content (e.g. user restored from backup). Sentinel passes (UUID matches), but the freshly-computed Merkle root differs from `disk.merkle_root` by more than `merkle_delta_freeze_threshold` (default `0.50` = 50 % of files differ on tier-1).
- `merkle.compute_merkle_delta(stored_root: str, fresh_files: Iterable[FileFingerprint]) -> float` — returns ratio in `[0.0, 1.0]` of files whose tier-1 fingerprint differs from the stored value. The function does NOT require recomputing the full Merkle root; it walks the file list once.
- Scanner integration: at start of per-disk pass, after Merkle short-circuit miss, compute delta. If `delta > threshold`: halt that disk, log `indexer.merkle.delta_freeze` with the delta value, mark `scan_run.status='aborted'` for the disk, abort the disk's transaction.
- `library index --confirm-bulk-change --disk D` flag: bypasses the freeze for that one invocation. Without the flag, the user gets an actionable error message: `"disk Disk1 looks like a bulk restore (52% files changed). Re-run with --confirm-bulk-change to proceed."`.
- `IndexerConfig` field added: `indexer.drift.merkle_delta_freeze_threshold: float = 0.50` (defaults to 50 %).
- E2E `test_indexer_disk_swap.py`: scan a fixture, then mutate ≥ 50 % of files (different content, different sizes, same paths), rescan WITHOUT `--confirm-bulk-change` → scan halts that disk + logs `indexer.merkle.delta_freeze`; rescan WITH `--confirm-bulk-change` → proceeds + drift is reconciled normally.

**Tests added:** `tests/e2e/test_indexer_disk_swap.py`

**Commit:** `feat(media-indexer): 3.6 disk-swap Merkle-delta freeze and --confirm-bulk-change`

---

## Acceptance criteria

- [ ] `pytest tests/indexer/test_drift.py` passes with ≥ 5 `@given`-decorated property tests.
- [ ] `pytest tests/indexer/test_repair.py` passes.
- [ ] `pytest tests/e2e/test_indexer_budget_resume.py` passes.
- [ ] `pytest tests/e2e/test_indexer_unplug_disk.py` passes.
- [ ] cold→mutate(rename file)→rescan: renamed file has same `oshash`, `miss_strikes` reset, path updated.
- [ ] cold→mutate(delete file)→rescan×3: file has `deleted_at` set after 3rd miss scan (N=3 default).
- [ ] Unmounted disk: zero strike change across 5 scan cycles.
- [ ] OSHash collision: `repair_queue` row inserted with `reason='oshash_collision'`; no auto-rename.
- [ ] Budget exhaust mid-scan: `scan_run.status='ok'`, `stats_json.budget_exhausted=true`, `last_path` non-null.
- [ ] Resume from `last_path` produces identical final DB state to uninterrupted run.
- [ ] `OSError(EIO)` on a disk: that disk's transaction rolled back, other disks' progress committed.
- [ ] `mtime` in the future stored as clamped value; `indexer.fs.invalid_mtime` logged.
- [ ] `library status` exits non-zero when repair queue oldest pending > 7 days.
- [ ] `tests/e2e/test_indexer_oshash_collision.py` passes.
- [ ] `tests/e2e/test_indexer_racy_mtime.py` passes.
- [ ] `tests/e2e/test_indexer_cross_dst.py` passes.
- [ ] `tests/e2e/test_indexer_disk_swap.py` passes: bulk-change halts disk without `--confirm-bulk-change`, proceeds with it.

---

## DESIGN cross-references

Implements: §8.1 (reconciliation loop), §8.2 (hinted handoff — unmounted freeze), §8.3 (repair queue), §8.4 (resumable scans), §15.2 (property-based tests), §15.2.1 (hypothesis generators), §17.1 (failure-mode policies: DB layer lock, filesystem EIO, permission denied, mtime clamping, drift edge cases: OSHash collision, disk swap, strikes after long unmount).

---

## Out of scope for this phase

- `incremental` and `enrich` modes — Phase 4.
- ThreadPoolExecutor — Phase 4.
- Outbox write-through — Phase 5.
- Outbox-drain idempotence property test (formerly listed as property #4) — moved to Phase 5.2 since it depends on the outbox module.
- Consumer migration — Phases 6–7.
- `library repair` CLI command (beyond `drain` call) — Phase 8.
