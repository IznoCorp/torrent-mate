# Phase 5 — Outbox + Write-through

## Gate

**Prerequisite (Phase 4 exit gate):**

> All four modes hit their target times in §11.11; SIGTERM during a `--full` scan results in resumable state on next run; Spotlight detection is exercised on a real APFS volume in CI when available, dir-mtime fallback path covered by pyfakefs tests.

**This phase's exit gate (verbatim from DESIGN §16):**

> A pipeline run leaves an empty outbox at end (drained) and the indexer reflects every mutation.

---

## Scope

Wire the best-effort write-through log: `index_outbox` and `pending_op` repos, the drainer with retry/backoff/deferred semantics, hooks in the four pipeline mutation points (dispatcher, nfo_generator, artwork, trailers orchestrator), integration tests asserting outbox rows are produced and consumed correctly, and wiring the drainer into `personalscraper library index`. The no-op `outbox.drain_if_present()` stub from Phase 2 is replaced.

---

## Sub-phases

### 5.1 — `index_outbox` + `pending_op` repos

**Files touched:**

- `personalscraper/indexer/repos/outbox_repo.py` _(implement — was skeleton in Phase 1)_
- `tests/indexer/test_outbox.py` _(new)_

**Deliverable:**

- `OutboxRepo.insert(conn, source, op, payload_json) -> int` — INSERT row with `status='pending'`, `created_at=now`.
- `OutboxRepo.fetch_pending(conn, limit=100) -> list[OutboxRow]` — SELECT pending rows ORDER BY `id ASC`.
- `OutboxRepo.mark_done(conn, row_id) -> None` — UPDATE `status='done'`, `processed_at=now`.
- `OutboxRepo.mark_failed(conn, row_id) -> None` — UPDATE `status='failed'`.
- `OutboxRepo.mark_deferred(conn, row_id) -> None` — UPDATE `status='deferred'`.
- `PendingOpRepo.insert(conn, disk_id, op, payload_json) -> int`.
- `PendingOpRepo.fetch_for_disk(conn, disk_id) -> list[PendingOpRow]`.
- `PendingOpRepo.mark_replayed(conn, row_id) -> None` — UPDATE `replayed_at=now`.
- `PendingOpRepo.purge_expired(conn, ttl_days=30) -> int` — DELETE rows where `created_at < now - ttl_days*86400`; log `indexer.pending_op.ttl_expired` per purged row.
- Tests: insert/fetch/mark round-trips; deduplication (multiple rows same `(disk_id, rel_path, filename)` — only latest wins on drain, tested in 5.2); TTL purge.

**Tests added:** `tests/indexer/test_outbox.py`

**Commit:** `feat(media-indexer): 5.1 index_outbox and pending_op repos`

---

### 5.2 — Outbox drainer

**Files touched:**

- `personalscraper/indexer/outbox.py` _(replace no-op stub — full implementation)_
- `tests/indexer/test_outbox.py` _(extend)_

**Deliverable:**

- `drain(conn, config: IndexerConfig) -> DrainStats` — replaces the no-op stub from Phase 2.
- Processes rows in `id ASC` order (FIFO). For multiple rows targeting the same `(disk_id, rel_path, filename)` tuple, only the latest one is applied; older rows are marked `done` without applying.
- Each row processed in its own short transaction. On `OperationalError: database is locked`: retry up to 3× with backoff (50 ms, 200 ms, 1 s); after exhaustion mark `failed`, log `indexer.outbox.row_failed` with row id.
- Target disk unreachable at drain time: move row to `pending_op` with `status='deferred'`; log `indexer.outbox.deferred`.
- `pending_op` replay on remount: at start of each scan, for every disk newly `is_mounted=1`, fetch its `pending_op` rows and replay via the same drain logic; set `replayed_at`; log `indexer.pending_op.replayed`.
- Per-`op` idempotence contracts from DESIGN §9.3:
  - `move`: UPSERT `media_file` keyed by `(path_id, filename)` resolved from `(disk_id, dst_rel_path)`.
  - `nfo_write`: UPDATE `media_item.nfo_status` and `tmdb_id`/`imdb_id` for matched item.
  - `artwork_write`: flip boolean in `media_item.artwork_json` (use JSON1 `json_set`).
  - `trailer_download`: UPSERT `item_attribute(item_id, key='trailer_found', value=trailer_path)`.
- `drain_if_present(conn, config) -> None` — public convenience wrapper (replaces the Phase 2 stub).
- Tests: FIFO order; deduplication (3 rows for same file → only latest applied); retry on locked DB (mock `OperationalError`); deferred to `pending_op` when disk unreachable; replay on remount; all four `op` idempotence proofs.

**Tests added:** extend `tests/indexer/test_outbox.py`

**Commit:** `feat(media-indexer): 5.2 indexer/outbox.py drainer with retry and deferred semantics`

---

### 5.3 — Hooks in pipeline mutation points

**Files touched:**

- `personalscraper/dispatch/dispatcher.py` _(modify — outbox publish after rsync move)_
- `personalscraper/scraper/nfo_generator.py` _(modify — outbox publish after NFO write)_
- `personalscraper/scraper/artwork.py` _(modify — outbox publish after artwork download)_
- `personalscraper/trailers/orchestrator.py` _(modify — outbox publish after trailer download)_

**Deliverable:**

- Each mutation point, **immediately after the FS operation succeeds**, opens a short SQLite transaction on `library.db` and inserts one `index_outbox` row. If the insert fails (DB locked, disk full): the FS op is NOT rolled back; log `indexer.db.outbox_lost` with payload; continue. This is the "best-effort" contract from DESIGN §9.1.
- `dispatcher.py` hook: after successful `rsync` move, publish `op='move'` payload `{disk_id, src_rel_path, dst_rel_path, filename, size_bytes, mtime_ns}`.
- `nfo_generator.py` hook: after successful NFO write, publish `op='nfo_write'` payload `{disk_id, rel_path, item_kind, tmdb_id, imdb_id}`.
- `artwork.py` hook: after successful artwork download, publish `op='artwork_write'` payload `{disk_id, rel_path, kind}`.
- `trailers/orchestrator.py` hook: after successful trailer download, publish `op='trailer_download'` payload `{disk_id, rel_path, trailer_path}`.
- All four callers import `from personalscraper.indexer.outbox import publish_event` — a thin helper that opens `library.db`, inserts the row, closes. Does NOT acquire `indexer_lock` (outbox publishers must write while a scan holds the lock — per DESIGN §6.4).

**Tests added:** None at this sub-phase (integration tests in 5.4).

**Commit:** `feat(media-indexer): 5.3 outbox publish hooks in dispatcher nfo artwork trailers`

---

### 5.4 — Integration tests: outbox row presence + drain

**Files touched:**

- `tests/integration/__init__.py` _(new — empty, if not exists)_
- `tests/integration/test_outbox_writethrough_dispatch.py` _(new)_
- `tests/integration/test_outbox_writethrough_nfo.py` _(new)_
- `tests/integration/test_outbox_writethrough_artwork.py` _(new)_
- `tests/integration/test_outbox_writethrough_trailer.py` _(new)_

**Deliverable:**

- Each test uses a real `tmp_path` filesystem fixture (no heavy mocking — per test-realism contract from PR #14).
- `test_outbox_writethrough_dispatch.py`: call `dispatch.move(file)` on a fixture item; assert one `index_outbox` row with `op='move'` and matching payload; run drainer; assert `media_file` row reflects new path; outbox row `status='done'`.
- `test_outbox_writethrough_nfo.py`: call `nfo_generator.write_nfo(...)`; assert `op='nfo_write'` row; drain; assert `media_item.nfo_status` and IDs updated.
- `test_outbox_writethrough_artwork.py`: call `artwork.download(...)`; assert `op='artwork_write'` row; drain; assert `media_item.artwork_json` flag flipped.
- `test_outbox_writethrough_trailer.py`: call `trailers/orchestrator.download_trailer(...)`; assert `op='trailer_download'` row; drain; assert `item_attribute(key='trailer_found')` upserted.
- **These tests MUST NOT go in `tests/dispatch/test_dispatcher.py`** — that file was trimmed in PR #14 and must not regrow.

**Tests added:** `tests/integration/test_outbox_writethrough_dispatch.py`, `tests/integration/test_outbox_writethrough_nfo.py`, `tests/integration/test_outbox_writethrough_artwork.py`, `tests/integration/test_outbox_writethrough_trailer.py`

**Commit:** `test(media-indexer): 5.4 integration tests for outbox write-through all four ops`

---

### 5.5 — Drainer wired into `personalscraper library index`

**Files touched:**

- `personalscraper/indexer/cli.py` _(modify — replace no-op stub with real drain call)_
- `tests/indexer/test_cli.py` _(extend)_

**Deliverable:**

- `personalscraper library index` calls `outbox.drain_if_present(conn, config)` after the scan completes (synchronous, short).
- Full pipeline run (`ingest → sort → process → verify → dispatch`) on a fixture followed by `library index` leaves zero `status='pending'` rows in `index_outbox`.
- E2E test `tests/e2e/test_pipeline_indexer.py` _(new)_: full pipeline run on a fabricated 50-item FS fixture; asserts indexer reflects final state; outbox empty at end.
- CLI test: `library index --mode quick` on fixture with pre-seeded outbox rows → all rows drained after command exits.

**Tests added:** extend `tests/indexer/test_cli.py`, `tests/e2e/test_pipeline_indexer.py`

**Commit:** `feat(media-indexer): 5.5 drain outbox in library index CLI`

---

## Acceptance criteria

- [ ] `pytest tests/indexer/test_outbox.py` passes.
- [ ] `pytest tests/integration/` passes (all four write-through tests green, using real `tmp_path`).
- [ ] `pytest tests/e2e/test_pipeline_indexer.py` passes.
- [ ] After a full pipeline run + `library index`: zero `status='pending'` rows in `index_outbox`.
- [ ] `outbox.drain_if_present()` failure (DB locked) logs `indexer.db.outbox_lost` and does NOT roll back the FS operation.
- [ ] Drainer deduplication: 3 rows for the same `(disk_id, rel_path, filename)` → only latest applied; other 2 marked `done`.
- [ ] Retry on locked DB: up to 3× with 50 ms / 200 ms / 1 s backoff; after exhaustion row marked `failed`.
- [ ] Disk unreachable at drain time: row moved to `pending_op`; replayed on next scan that finds disk mounted.
- [ ] `pending_op` rows older than 30 days purged with `indexer.pending_op.ttl_expired` log.
- [ ] No new assertions added to `tests/dispatch/test_dispatcher.py` (outbox assertions live exclusively in `tests/integration/`).
- [ ] All four `op` idempotence contracts verified: replaying a drained row produces identical DB state.

---

## DESIGN cross-references

Implements: §9.1 (outbox pattern + best-effort contract), §9.2 (drainer behaviour), §9.3 (drain idempotence per `op`), §9.4 (write-through rationale), §15.5 (integration tests, E2E pipeline test), §17.1 (outbox drainer crash mid-row, unmounted disk deferral, pipeline crash between FS mutation and outbox insert — "paranoia branch" in scanner `quick` mode: re-walk paths from last 24 h of `scan_event` rows of type `outbox.*` regardless of dir mtime).

---

## Out of scope for this phase

- Consumer migration of `dispatch/media_index.py` — Phase 6.
- Consumer migration of `library/scanner.py` and `trailers/scanner.py` — Phase 7.
- `library search`, `library verify`, `library repair`, `library show` CLI — Phase 8.
- Web UI — out of scope entirely.
