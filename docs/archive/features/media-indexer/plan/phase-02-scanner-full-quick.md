# Phase 2 — Indexer Core: Scanner (full + quick)

## Gate

**Prerequisite (Phase 1 exit gate):**

> `personalscraper library-status` runs on a fresh DB and prints "no scans yet".

**This phase's exit gate (verbatim from DESIGN §16):**

> Full scan of fixture FS (Stage A) populates `media_file` rows; subsequent `quick` run with no FS changes reads only directory mtimes (asserted via fs_usage trace or syscall counter); `BootstrapError` raised when `diskutil` cannot resolve a UUID.

---

## Scope

Build the scanner engine for the two foundational scan modes (`full` Stage A and `quick`). This includes fingerprinting (OSHash + xxh3_partial + tier-1 helpers), the mediainfo wrapper stub (wired in Phase 4), per-disk Merkle root with mountpoint sentinel guard, the core directory walk, and the `personalscraper library-index` CLI entry point. No drift reconciliation (Phase 3), no incremental/enrich modes (Phase 4), no outbox (Phase 5).

---

## Sub-phases

### 2.1 — Fingerprint module

**Files touched:**

- `personalscraper/indexer/fingerprint.py` _(new)_
- `tests/indexer/test_fingerprint.py` _(new)_

**Deliverable:**

- `fingerprint_tier1(stat: os.stat_result) -> tuple[int, int, int]` — returns `(size, mtime_ns, ctime_ns)`.
- `is_racy(file_mtime_ns: int, scan_started_at_ns: int, window_ns: int) -> bool` — git-style racy-mtime rule (DESIGN §7.3).
- `oshash(path: Path) -> str` — OpenSubtitles hash: `(filesize + sum(first 64KB u64LE) + sum(last 64KB u64LE)) mod 2^64`, 16-char hex. Reads exactly 128 KB regardless of file size (pad with zeros if file < 128 KB). Returns `"0000000000000000"` for empty files.
- `xxh3_partial(path: Path, partial_bytes: int = 1_048_576) -> str` — `xxh3_64` of first N + last N bytes, 16-char hex.
- `OSHASH_EXTENSIONS: frozenset[str]` — video extensions from DESIGN §11.6 (`mkv,mp4,avi,mov,wmv,flv,mpg,mpeg,m4v,webm,ts,m2ts,mts,3gp,vob,ogv,rmvb`). OSHash is only computed for files whose suffix (lowercased) is in this set.
- Tests: known-vector OSHash test (use the OpenSubtitles reference vector `breakdance.avi` hash `8e245d9679d31e12`), xxh3 determinism, tier-1 on a real `stat_result`, racy detection edge cases (exactly at boundary, outside boundary, future mtime clamped), empty file OSHash.

**Tests added:** `tests/indexer/test_fingerprint.py`

**Commit:** `feat(media-indexer): 2.1 indexer/fingerprint.py OSHash xxh3_partial tier1`

---

### 2.2 — Mediainfo wrapper (stub — not wired to scanner yet)

**Files touched:**

- `personalscraper/indexer/mediainfo.py` _(new)_
- `tests/indexer/test_mediainfo.py` _(new)_

**Deliverable:**

- `MediaInfoWrapper` class with `extract_streams(path: Path) -> list[StreamRow]`. Uses `pymediainfo.MediaInfo.parse()`.
- Respects `min_size_mb` threshold — returns `[]` for files below threshold without calling pymediainfo.
- `parse_speed` flag passed to libmediainfo (float, 0.5 = fast, 1.0 = full).
- Raises `MediaInfoUnavailableError` at import time (not at call time) if `libmediainfo.dylib` cannot be found, with message `"brew install media-info"`.
- `sequential_hint` integration point stubbed as a no-op here (implemented in Phase 4 `_macos_io.py`).
- Tests: small-file skip (below `min_size_mb`), `MediaInfoUnavailableError` on missing lib (mock `pymediainfo`), stream extraction shape (use a real small test video fixture or mock `pymediainfo` return).

**Tests added:** `tests/indexer/test_mediainfo.py`

**Commit:** `feat(media-indexer): 2.2 indexer/mediainfo.py pymediainfo wrapper stub`

---

### 2.3 — Merkle root + mountpoint sentinel guard

**Files touched:**

- `personalscraper/indexer/merkle.py` _(new)_
- `tests/indexer/test_merkle.py` _(new)_

**Deliverable:**

- `compute_merkle_root(files: Iterable[FileFingerprint]) -> str` — `xxh3_64` hex over deterministically sorted `f"{path_id}|{size}|{mtime_ns}|{oshash}\n"` for every file. `FileFingerprint` is a small dataclass `(path_id: int, size: int, mtime_ns: int, oshash: str)`.
- `bootstrap_disk_identity(mount_path: Path) -> str` — calls `diskutil info -plist <mount_path>`, parses `VolumeUUID`. Raises `BootstrapError` if `diskutil` unavailable or returns no UUID. Writes sentinel file `<mount_path>/.personalscraper-disk-id` (UUID, single line). Logs `indexer.disk.bootstrapped`.
- `verify_disk_mounted(disk: DiskRow) -> DiskMountStatus` — returns one of `MOUNTED_AND_VERIFIED`, `MOUNTED_WRONG_DISK`, `UNMOUNTED`, `NO_SENTINEL`. `NO_SENTINEL` path re-derives UUID via `bootstrap_disk_identity`; if matches, re-creates sentinel and returns `MOUNTED_AND_VERIFIED`; if differs, returns `MOUNTED_WRONG_DISK`.
- **Minimal guard for Phase 2**: `UNMOUNTED` → raises `DiskUnmountedError`; `MOUNTED_AND_VERIFIED` → proceed; `NO_SENTINEL` → bootstrap + proceed; `MOUNTED_WRONG_DISK` → raises `DiskMismatchError`. Full strike/pending_op logic lands in Phase 3.
- Tests: Merkle determinism (same files same order = same root), sentinel read/write, `verify_disk_mounted` with mocked `os.path.ismount` and sentinel file states, `BootstrapError` when `diskutil` not found.

**Tests added:** `tests/indexer/test_merkle.py`

**Commit:** `feat(media-indexer): 2.3 indexer/merkle.py Merkle root and sentinel guard`

---

### 2.4 — Scanner core walk

**Files touched:**

- `personalscraper/indexer/scanner.py` _(new)_
- `tests/indexer/test_scanner.py` _(new)_

**Deliverable:**

- `scan(disks: list[DiskRow], mode: ScanMode, generation: int, conn: sqlite3.Connection) -> ScanRunResult` — skeleton function with per-disk loop, `verify_disk_mounted` call, `os.scandir` walk (never following symlinks), hidden/system file exclusion from `patterns.json5` (`.fseventsd`, `$Recycle.Bin`, `.Spotlight-V100`, `.Trashes`, `System Volume Information`, `._*` prefix, `.DS_Store`), `path.dir_mtime_ns` write-through after every directory visit.
- Symlinks recorded as `media_file` rows with `oshash=NULL`, `enriched_at=NULL`, never fingerprinted.
- `O_RDONLY` via `os.open()` for all file opens.
- `os.scandir` uses `entry.stat(follow_symlinks=False)` — never `Path.stat()` after scandir.
- `scan_run` row inserted at start (status=`running`), updated to `ok`/`failed` at end.
- `scan_generation` bumped on each row visited this scan.
- Tests (pyfakefs): walk produces `path` + `media_file` rows, hidden files excluded, symlinks recorded with `oshash=NULL`, `dir_mtime_ns` updated after walk.

**Tests added:** `tests/indexer/test_scanner.py`

**Commit:** `feat(media-indexer): 2.4 indexer/scanner.py core walk skeleton`

---

### 2.5 — `--mode full` Stage A (fingerprint-only)

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add full-mode path)_
- `tests/indexer/test_scanner.py` _(extend)_
- `tests/e2e/test_indexer_cold_to_warm.py` _(new — cold scan half only; warm/incremental half deferred to Phase 3)_

**Deliverable:**

- `--mode full`: walks all files on all mounted disks (or one disk via `--disk D`), calls `fingerprint_tier1` + `oshash` (on video extensions only), inserts/upserts `media_file` rows. No `mediainfo` call. `enriched_at` left NULL.
- `--disk D` scoping: filters disk list to the one matching `disk.label == D`. Raises `IndexerConfigError("no disk with label 'D'")` if not found.
- `ScanMode` enum: `quick | incremental | enrich | full`.
- `scan_run.disk_filter` set when `--disk D` used.
- `drop_indexes_during_full_scan` path: at start of full scan on a disk, drops secondary indexes on `media_file`/`media_stream`, runs `executemany` in batches of 5 000, recreates indexes afterwards (DESIGN §11.7). Only on `full` mode.
- E2E test: build pyfakefs fixture with 10 items across 2 mock disks, run full scan, assert `media_file` row count matches fixture, `enriched_at` all NULL, `scan_run.status='ok'`.

**Tests added:** extend `tests/indexer/test_scanner.py`, `tests/e2e/test_indexer_cold_to_warm.py` (partial)

**Commit:** `feat(media-indexer): 2.5 scanner --mode full Stage A fingerprint-only`

---

### 2.6 — `--mode quick` path

**Files touched:**

- `personalscraper/indexer/scanner.py` _(modify — add quick-mode path)_
- `tests/indexer/test_scanner.py` _(extend)_

**Deliverable:**

- `--mode quick`: per-disk Merkle short-circuit first — recompute Merkle root from existing `media_file` rows in DB (not from FS reads); if equals `disk.merkle_root`, skip disk entirely (zero FS reads).
- On Merkle miss: `dir_mtime_ns` subtree-skip (compare `path.dir_mtime_ns` to current `os.scandir` stat; skip subtree if unchanged); tier-1 fingerprint only on changed files.
- Dir-mtime verification at scan startup: write a temp file in a temp subdir of `.data/`, read dir mtime before/after; if unchanged, log warning and fall back to per-file fingerprinting for this session.
- Tests: full scan → quick scan on unchanged FS → assert zero `os.stat` calls on FS files (use `unittest.mock.patch('os.scandir')` to count calls or pyfakefs stat tracker); Merkle miss forces dir-mtime walk.

**Tests added:** extend `tests/indexer/test_scanner.py`

**Commit:** `feat(media-indexer): 2.6 scanner --mode quick Merkle short-circuit and dir-mtime skip`

---

### 2.7 — `personalscraper library-index` CLI entry point

**Files touched:**

- `personalscraper/indexer/cli.py` _(modify — add `library index` command)_
- `personalscraper/indexer/outbox.py` _(new — no-op stub `drain_if_present(conn)`)_
- `tests/indexer/test_cli.py` _(new — partial; full golden CLI tests deferred to Phase 8)_

**Deliverable:**

- `personalscraper library-index [--mode {full|quick}] [--disk DISK] [--budget SECONDS] [--dry-run]` — acquires writer lock, calls `scan()`, calls `outbox.drain_if_present()` (no-op stub until Phase 5), prints JSON summary `{"mode": ..., "items_added": ..., "items_updated": ..., "files_walked": ..., "budget_exhausted": false}`.
- `--dry-run`: suppresses all `INSERT`/`UPDATE` on `media_*` tables; writes a synthetic `scan_run(status='dry-run')`; `scan_event` rows still written.
- `--wait-for-lock SECONDS` flag (default 0): passes timeout to `indexer_lock()`.
- CLI tests: `library index --mode quick` exits 0; `library index --mode full --disk UnknownDisk` exits 2 with stderr `"no disk with label 'UnknownDisk'"`.

**Tests added:** `tests/indexer/test_cli.py` (partial)

**Commit:** `feat(media-indexer): 2.7 personalscraper library-index CLI full and quick modes`

---

## Acceptance criteria

- [ ] `pytest tests/indexer/` passes.
- [ ] `pytest tests/e2e/test_indexer_cold_to_warm.py` passes (cold scan half).
- [ ] Full scan of a pyfakefs fixture with 20 video files populates exactly 20 `media_file` rows.
- [ ] Subsequent `--mode quick` on unchanged fixture: zero `os.scandir` calls on FS (Merkle hit path confirmed).
- [ ] `oshash` on the OpenSubtitles reference vector returns `8e245d9679d31e12`.
- [ ] `bootstrap_disk_identity` raises `BootstrapError` when `diskutil` is unavailable (mocked).
- [ ] `personalscraper library-index --mode full --disk UnknownDisk` exits 2 with correct error.
- [ ] Symlinks in fixture appear in `media_file` with `oshash=NULL`.
- [ ] Hidden/system files (`.DS_Store`, `$Recycle.Bin`, `._foo`) not present in `media_file`.
- [ ] `scan_run.status='ok'` after successful scan; `'failed'` if disk mount check fails.

---

## DESIGN cross-references

Implements: §7.1 (walk strategy), §7.2 (parallelism skeleton — single-threaded here; ThreadPool in Phase 4), §7.3 (fingerprint tiers), §7.4 (disk bootstrap + sentinel guard), §7.5 (Merkle root), §11.1 (scan modes table — full + quick only), §11.3 (two-stage scan: Stage A), §11.6 (read-traffic minimisation: OSHash extension allowlist, O_RDONLY, scandir stat reuse), §11.7 (bulk-insert during full), §11.10 (dir-mtime subtree skip), §15.5 (E2E cold-to-warm partial).

---

## Out of scope for this phase

- Drift detection, N-strikes, soft-delete, repair queue — Phase 3.
- `incremental` and `enrich` modes — Phase 4.
- ThreadPoolExecutor parallelism — Phase 4.
- macOS `F_RDADVISE` sequential hint — Phase 4.
- Read-rate token bucket — Phase 4.
- Spotlight integration — Phase 4.
- SIGTERM handler — Phase 4.
- Outbox write-through — Phase 5.
- `library verify` command — Phase 8.
- Full CLI golden test suite (12+ cases) — Phase 8.
