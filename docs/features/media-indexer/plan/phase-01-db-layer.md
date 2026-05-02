# Phase 1 — Indexer Core: DB Layer

## Gate

**Prerequisite (Phase 0 exit gate):**

> Full test suite green on v2 config; `config migrate-to-v2` produces an exactly-equivalent `Config`.

**This phase's exit gate (verbatim from DESIGN §16):**

> `personalscraper library-status` runs on a fresh DB and prints "no scans yet".

---

## Scope

Stand up the SQLite database layer: connection + PRAGMAs, the full `001_init.sql` schema, the migration applier, dataclass row types, and per-table Repository skeletons. No scanner, no fingerprinter — just the persistent store and its typed access layer. The `personalscraper library-status` command gets a minimal stub sufficient to open the DB and confirm it is empty.

---

## Sub-phases

### 1.1 — DB connection + PRAGMAs + writer lock + disk-full guard

**Files touched:**

- `personalscraper/indexer/__init__.py` _(new — empty)_
- `personalscraper/indexer/db.py` _(new)_
- `tests/indexer/__init__.py` _(new — empty)_
- `tests/indexer/test_db.py` _(new)_
- `tests/e2e/test_indexer_db_corrupt_recovery.py` _(new — DESIGN §15.5 enumerated)_

**Deliverable:**

- `db.py` exposes `open_db(path: Path) -> sqlite3.Connection` with exact PRAGMAs from DESIGN §6.1 (`WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, `cache_size=-65536`, `mmap_size=268435456`, `wal_autocheckpoint=1000`, `busy_timeout=5000`, `foreign_keys=ON`).
- `indexer_lock(db_path: Path, timeout: float = 0) -> ContextManager` backed by `filelock.FileLock` on `<db_path>.lock`. Lockfile content: JSON `{pid, started_at, hostname}`. On timeout: reads lockfile, checks `os.kill(pid, 0)` liveness; if dead → log `indexer.lock.stale_recovered` and break; if alive → raise `IndexerLockError` with PID in message.
- `open_db()` raises `IndexerCorruptError` on `sqlite3.DatabaseError: database disk image is malformed`; quarantines file to `<path>.corrupt-<unix_ts>`. Refuses to start unless `--rebuild` flag is passed (Phase 8.1 wires the flag into `library index`).
- `open_db()` rejects `db_path` on a macFUSE-NTFS volume (checks `mount` output for the path's mount point).
- **Disk-full guard (DESIGN §17.1)**: `open_db()` (and any caller about to start a write transaction with significant expected growth — `scan(mode='full')`) calls `check_free_space(path: Path, expected_growth_bytes: int) -> None`. The helper uses `os.statvfs(path.parent)` and refuses if `free < 2 × expected_growth_bytes`, raising `IndexerDiskFullError`. For `--mode full` the expected growth is estimated as `expected_rows × 4 KB` (rough WAL + row size).
- **Mid-scan disk-full handling**: scanner wraps `executemany` and `commit()` in `try/except sqlite3.OperationalError`. On match of `"disk I/O error"` or `"database or disk is full"`: explicit `PRAGMA wal_checkpoint(TRUNCATE)`, commit current disk transaction, log `indexer.db.disk_full`, exit non-zero. The handler is a one-line helper in `db.py` so that scanner sub-phases (Phase 2+) can reuse it.
- E2E `test_indexer_db_corrupt_recovery.py`: corrupt `library.db` mid-byte; restart indexer → quarantine + refusal without `--rebuild`; passing `--rebuild` triggers full Stage-A rescan that succeeds.
- Tests: PRAGMA assertions on fresh `:memory:` DB, lock acquired/released, stale lock recovery (mock `os.kill`), malformed DB quarantine, disk-full pre-check refuses when free space below threshold, `wal_checkpoint(TRUNCATE)` invoked on simulated mid-scan disk-full.

**Tests added:** `tests/indexer/test_db.py`, `tests/e2e/test_indexer_db_corrupt_recovery.py`

**Commit:** `feat(media-indexer): 1.1 indexer/db.py PRAGMAs writer lock and disk-full guard`

---

### 1.2 — Full schema SQL (`001_init.sql`)

**Files touched:**

- `personalscraper/indexer/migrations/__init__.py` _(new — empty)_
- `personalscraper/indexer/migrations/001_init.sql` _(new)_

**Deliverable:** The complete SQL from DESIGN §6.2, verbatim:

- Tables: `disk`, `path`, `media_item`, `item_attribute`, `season`, `episode`, `media_release`, `media_file`, `media_stream`, `item_issue`, `index_outbox`, `pending_op`, `repair_queue`, `scan_run`, `scan_event`, `deleted_item`, `schema_version`.
- All indexes listed in §6.2.
- Triggers: `trg_season_requires_show`.
- Generated columns: `has_poster`, `has_fanart` on `media_item` (DESIGN §6.5).
- Indexes on generated columns.
- `INSERT INTO schema_version(version) VALUES (1)`.
- `PRAGMA user_version = 1` at end of script.

**Tests added:** None at this sub-phase (tested via migration applier in 1.3).

**Commit:** `feat(media-indexer): 1.2 indexer/migrations/001_init.sql full schema`

---

### 1.3 — Migration applier

**Files touched:**

- `personalscraper/indexer/db.py` _(modify — add `apply_migrations`)_
- `tests/indexer/test_migrations.py` _(new)_
- `tests/indexer/migration_fixtures/v1.sql` _(new — snapshot of post-001 schema for chain-replay test)_

**Deliverable:**

- `apply_migrations(conn: sqlite3.Connection, dir_: Path) -> None` — applies all `*.sql` files whose number > `PRAGMA user_version`. Each file in a single transaction; on success, `PRAGMA user_version` bumped. Idempotent and re-runnable.
- Takes a `.pre-migration-<ver>.bak` snapshot before applying each script. On failure: restore from snapshot, log `indexer.migration.failed`, raise.
- Chain-replay test per DESIGN §15.5.1:
  - Path A: load `v1.sql` fixture, apply `002..NNN` (none yet, no-op).
  - Path B: empty DB, apply all from `001`.
  - Assert `dump_schema(db_a) == dump_schema(db_b)`.
- `PRAGMA user_version` matches `schema_version.version` after apply.

**Tests added:** `tests/indexer/test_migrations.py`

**Commit:** `feat(media-indexer): 1.3 indexer migrations applier with chain-replay test`

---

### 1.4 — Schema dataclasses + Repository skeletons

**Files touched:**

- `personalscraper/indexer/schema.py` _(new)_
- `personalscraper/indexer/repos/__init__.py` _(new — empty)_
- `personalscraper/indexer/repos/disk_repo.py` _(new)_
- `personalscraper/indexer/repos/item_repo.py` _(new)_
- `personalscraper/indexer/repos/release_repo.py` _(new)_
- `personalscraper/indexer/repos/file_repo.py` _(new)_
- `personalscraper/indexer/repos/tv_repo.py` _(new)_
- `personalscraper/indexer/repos/log_repo.py` _(new)_
- `personalscraper/indexer/repos/outbox_repo.py` _(new)_
- `tests/indexer/test_schema.py` _(new)_

**Deliverable:**

- `schema.py`: one `@dataclass` per table row type (e.g. `DiskRow`, `PathRow`, `MediaItemRow`, `MediaFileRow`, etc.) with field names and types matching DESIGN §6.2. JSON columns represented as `str` (raw) at DB boundary; pydantic models (`ArtworkInventory`, `OutboxPayload`, `RepairPayload`, `ScanStats`, `ScanEventPayload`, `DeletedSnapshot`) validate shape at write time.
- Per-repo files expose at minimum: `insert`, `get_by_id`, `upsert`, `delete` (where applicable). Raw `sqlite3` — no ORM. `conn.row_factory = sqlite3.Row` used for reads.
- Timestamp convention enforced: suffix `_at` = epoch seconds int, `_ns` = epoch nanoseconds int (DESIGN §6.5). Any column without the correct suffix raises `SchemaConventionError` at test time.
- Structlog events from all repo methods follow the `indexer.{component}.{action}` pattern (DESIGN §6.6).
- `test_schema.py`: round-trip insert/read for each repo using in-memory DB.

**Tests added:** `tests/indexer/test_schema.py`

**Commit:** `feat(media-indexer): 1.4 schema dataclasses and repo skeletons`

---

### 1.5 — Per-repo unit tests + library status stub

**Files touched:**

- `tests/indexer/test_repos_disk.py` _(new)_
- `tests/indexer/test_repos_item.py` _(new)_
- `tests/indexer/test_repos_file.py` _(new)_
- `tests/indexer/test_repos_tv.py` _(new)_
- `tests/indexer/test_repos_log.py` _(new)_
- `personalscraper/indexer/cli.py` _(new — minimal `library status` stub)_

**Deliverable:**

- Per-repo tests use `:memory:` DB seeded via `apply_migrations`. Test coverage per repo:
  - `disk_repo`: insert disk, get by uuid, update `mount_path`, `is_mounted`, `merkle_root`.
  - `item_repo`: insert item, find by `tmdb_id`, upsert flex attr, cascade delete item → `item_attribute`.
  - `file_repo`: insert file, lookup by `(path_id, filename)`, soft-delete (`deleted_at`), miss-strike increment.
  - `tv_repo`: insert season + episode, trigger `trg_season_requires_show` rejects `kind='movie'`.
  - `log_repo`: insert `scan_run`, update `status`, insert `scan_event`, insert `deleted_item`.
- `indexer/cli.py`: `personalscraper library-status` — opens DB (creates if absent via `apply_migrations`), queries `scan_run` for the most recent completed run. If none, prints "no scans yet". Gate check passes when this runs on a fresh DB.

**Tests added:** `tests/indexer/test_repos_disk.py`, `tests/indexer/test_repos_item.py`, `tests/indexer/test_repos_file.py`, `tests/indexer/test_repos_tv.py`, `tests/indexer/test_repos_log.py`

**Commit:** `feat(media-indexer): 1.5 per-repo unit tests and library status stub`

---

## Acceptance criteria

- [ ] `pytest tests/indexer/` passes (all new tests green).
- [ ] `pytest` (full suite) passes — no Phase 0 test regression.
- [ ] `personalscraper library-status` on a fresh (non-existent) `library.db` prints "no scans yet" and exits 0.
- [ ] `open_db()` on a malformed `.db` file quarantines it to `*.corrupt-<ts>` and raises `IndexerCorruptError`.
- [ ] `open_db()` on a path on a macFUSE-NTFS volume raises `IndexerConfigError` with message explaining WAL unreliability.
- [ ] `apply_migrations` on an already-current DB is a no-op (idempotent).
- [ ] Migration failure mid-script restores from `.pre-migration-<ver>.bak`.
- [ ] `trg_season_requires_show` trigger fires correctly (confirmed by `test_repos_tv.py`).
- [ ] Generated columns `has_poster`, `has_fanart` return correct values from `artwork_json`.
- [ ] All structlog events from repo methods match `indexer.{component}.{action}` pattern.
- [ ] Stale lockfile (dead PID) is recovered automatically; live-PID lockfile raises `IndexerLockError`.

---

## DESIGN cross-references

Implements: §6.1 (connection + PRAGMAs), §6.2 (schema), §6.3 (migrations + applier), §6.4 (concurrency model + lock), §6.5 (naming + JSON-shape conventions), §6.6 (logging event-name convention), §15.1 (unit tests), §15.5.1 (migration chain-replay test), §17.1 (DB layer failure modes: locked, malformed, stale lock, migration failure).

---

## Out of scope for this phase

- Scanner, fingerprinter, drift engine — Phase 2+.
- `outbox_repo` full implementation (schema exists; write-through logic lands in Phase 5).
- `repair_queue` drain worker — Phase 3.
- `personalscraper library-index` (beyond the no-op status stub) — Phase 2.
- Consumer migration of `dispatch/media_index.py` — Phase 6.
- Property-based tests (hypothesis) — Phase 3.
