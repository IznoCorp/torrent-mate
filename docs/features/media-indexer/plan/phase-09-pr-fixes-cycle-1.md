# Phase 9 — PR fixes cycle 1

## Context

Findings retained from `/pr-review-toolkit:review-pr` on PR #16 after Opus filtering against DESIGN.md. 2 critical (DESIGN contract violations) + 4 major (correctness / security / resource). Minor / observability / type-tightening items deferred to a follow-up PR.

## Sub-phases

### 9.1 — Thread `cfg` through `publish_event` and `disk_id_for_path`

**Finding (Critical, C1)**: `personalscraper/indexer/outbox.py:809–810, 845–846` — `publish_event()` and `disk_id_for_path()` call `IndexerConfig()` directly, returning the default `db_path`. Every write-through call site (`scraper/artwork.py`, `scraper/nfo_generator.py`, `dispatch/dispatcher.py`, `trailers/orchestrator.py`, `library/disk_cleaner.py`) ignores the user's actual `Config.indexer.db_path` from `config.json5`. If the user customises the path, every write-through event silently targets the wrong DB.

**Rule violated**: DESIGN §9.4 (write-through publishers must use the configured DB).

**Fix shape**:

- Change `publish_event(...)` signature to accept either `cfg: Config` or `db_path: Path` as a required parameter.
- Update all consumers to pass the loaded config / resolved path.
- Update tests in `tests/integration/test_outbox_writethrough_*.py` to pass the same.

**Acceptance**: no call to `IndexerConfig()` (default-constructor) inside `publish_event`/`disk_id_for_path`. Adding a unit test that customises `db_path` and asserts the row lands in the customised DB.

---

### 9.2 — Use next-generation in `scan_library` indexer call

**Finding (Critical, C2)**: `personalscraper/library/scanner.py:672` — `_indexer_scan(..., generation=1)` is hardcoded. Per DESIGN §8.1, generations are monotonic and used for miss-strike escalation; reusing generation=1 across library walks defeats this.

**Rule violated**: DESIGN §8.1 (monotonic scan generations).

**Fix shape**: allocate the next generation the same way `library_index_command` does (`personalscraper/indexer/cli.py:339`):

```python
generation = (conn.execute("SELECT COALESCE(MAX(scan_generation), 0) FROM scan_run").fetchone()[0] or 0) + 1
```

Pass that to `_indexer_scan` instead of literal `1`. Add an assertion test in `tests/library/test_scanner.py` (skipped on Python 3.10) that two consecutive `scan_library` calls produce strictly-increasing `scan_generation` values.

**Acceptance**: no hardcoded generation in `scan_library`; consecutive calls increment it monotonically.

---

### 9.3 — Make `_inventory_artwork` and `_check_nfo_status` fail-safe

**Finding (Major, M3)**: `personalscraper/indexer/scanner/_modes.py:982–984, 1013–1019` — both functions swallow `OSError` and return an "all-false" `ArtworkInventory` / `nfo_status='missing'`. The caller then writes that into `media_item.artwork_json` / `media_item.nfo_status`, **overwriting previously-valid data** on a transient permission error or filesystem hiccup. Symptom: `analyzer.analyze` and `rescraper._collect_rescrape_candidates` queue real-content-OK items for re-scrape after a brief read failure.

**Fix shape**:

- Change return to `ArtworkInventory | None` and `Literal["missing", "invalid", "valid"] | None` — `None` signals "scan_dir failed; do not update".
- Caller (in the enrich UPDATE step) skips the column update when `None` (preserves the prior value).
- Log `indexer.enrich.artwork_inventory_failed` / `indexer.enrich.nfo_check_failed` at `warning` with `error=str(exc)` and `error_type=type(exc).__name__`.

**Acceptance**: a unit test in `tests/indexer/scanner/test_modes.py` that simulates `OSError` on the directory and asserts (a) the column update is skipped, and (b) a warning log is emitted.

---

### 9.4 — Honor `scan()` docstring re-raise contract

**Finding (Major, M4)**: `personalscraper/indexer/scanner/__init__.py:770–786` — docstring at lines 342–344 promises _"any unexpected exception from the walk loop is re-raised after the scan_run row is updated to status='failed'"_, but the `except Exception` block returns a `ScanRunResult(status="failed", error=str(exc))` instead of re-raising. Tracebacks lost; callers (e.g. `library/scanner.scan_library` at line 669) don't check the return value at all and silently treat catastrophic failures as completed.

**Fix shape**: pick one of:

1. Re-raise after recording status (matches `DiskBulkChangeDetected` immediately above and the documented contract).
2. Update the docstring to reflect the swallow-and-return-status behaviour AND audit every caller to assert `result.status == "ok"`.

Prefer option 1 (less invasive, keeps the documented contract).

**Acceptance**: a regression test in `tests/indexer/test_scanner.py` that injects an unexpected exception during walk and asserts it propagates (with the `scan_run` row updated to `status='failed'`).

---

### 9.5 — `MediaIndex` connection lifecycle (`close` / context manager)

**Finding (Major, M2)**: `personalscraper/dispatch/media_index.py:182–187` — `MediaIndex.__init__` opens a `sqlite3.Connection` via `open_db` and stores it on `self._conn`, but the class never closes it. Each construction in tests/CLI/dispatch leaks a SQLite connection until process exit.

**Fix shape**:

- Add `close(self) -> None` method that calls `self._conn.close()`.
- Implement `__enter__` / `__exit__` for `with` syntax.
- Add a `__del__` that calls `close()` defensively (log if already closed).
- Update `personalscraper/dispatch/run.py` and `personalscraper/dispatch/dispatcher.py` callers to use `with MediaIndex(...) as idx:`.
- Update `personalscraper/indexer/cli.py` library\_\* commands to use `from contextlib import closing` around `open_db(...)` calls.

**Acceptance**: `lsof` / FD-leak test in `tests/dispatch/test_media_index.py` showing FD count returns to baseline after `with` block exits.

---

### 9.6 — Whitelist `kind` in `_apply_artwork_write` SQL

**Finding (Major, M1)**: `personalscraper/indexer/outbox.py:307–319` — `_apply_artwork_write` builds the SQL UPDATE with an f-string that interpolates `payload["kind"]` directly into the `json_set('$.<kind>', ...)` path expression. A malformed payload `kind` value can break out of the JSON path. Internal trust boundary, but defensive depth is cheap.

**Fix shape**:

- Define the allowed set as a module-level frozen set: `_ALLOWED_ARTWORK_KINDS = frozenset({"poster", "fanart", "banner", "thumb", "logo", "clearart", "clearlogo", "discart"})` (cross-check against `ArtworkInventory` Pydantic model field names).
- Validate `kind` at entry to `_apply_artwork_write`: `if kind not in _ALLOWED_ARTWORK_KINDS: raise OutboxPayloadError(f"unknown artwork kind: {kind!r}")`.
- Keep the f-string interpolation (the value is now whitelisted).

**Acceptance**: unit test in `tests/indexer/test_outbox.py` that sends a payload with `kind="malicious; DROP TABLE"` and asserts `OutboxPayloadError` is raised before any DB UPDATE runs.

---

## Out of scope for this fix phase (deferred to follow-up PR)

- Type design tightening (Literal aliases for stringly-typed enum columns, bool for is_mounted/is_locked, frozen=True on result dataclasses) — ~10 items
- Observability gaps (debug-vs-warning log levels, missing `exc_info=True`, missing `error_type` on errors) — ~12 items
- Comment sweep (orphan plan refs, "Phase 7.2+" markers, `F_RDADVISE` vs `mmap+madvise` docstring) — ~10 items
- `library_search` CLI header/data column mismatch
- Test coverage suggestions (`breaker` unit tests, full v1→v2 splitter test)
- Documentation of `apply_migrations` closed-connection invariant on `IndexerMigrationError`
