# Phase 7 — Consumer Migration: Library + Trailers

## Gate

**Prerequisite (Phase 6 exit gate):**

> Full pipeline run end-to-end with no `media_index.json` on disk; dispatch decisions identical to v0.7 on a fixture FS.

**This phase's exit gate (verbatim from DESIGN §16):**

> Full `personalscraper trailers scan` run produces the same result set as v0.7 on a fixture FS.

---

## Scope

Migrate all remaining consumers of the legacy JSON scan files to query the indexer directly: `library/scanner.py` (populates DB instead of returning a JSON tree), `library/analyzer.py`, `library/reporter.py`, `library/rescraper.py`, `library/disk_cleaner.py`, `library/recommender.py`, and `trailers/scanner.py`. Remove `library_scan.json`, `library_analysis.json`, and the `library_scan_max_age_hours` TTL cache. Prove consumer parity via the v0.7 fixture snapshot test.

---

## Sub-phases

### 7.1 — Rewrite `library/scanner.py`

**Files touched:**

- `personalscraper/library/scanner.py` _(rewrite)_
- `tests/library/test_scanner.py` _(rewrite — assert DB rows, not JSON output)_

**Deliverable:**

- `scan_library(config, conn) -> None` — populates the indexer (calls `indexer.scanner.scan(disks, mode='full', ...)`) instead of returning a `LibraryScanResult` dataclass tree.
- Old return type `LibraryScanResult` removed. Callers that previously used `scan_library()` return value are migrated in sub-phases 7.2–7.4.
- Any caller that passed the result to `analyzer.analyze()` is updated to call `analyzer.analyze(conn)` instead (no argument — queries DB directly).
- Tests rewritten: assert that `media_item`, `media_file`, `season`, `episode` rows are populated correctly after `scan_library()`. Use pyfakefs fixture with 5 movies + 2 TV shows.

**Tests added:** Rewrite `tests/library/test_scanner.py`

**Commit:** `refactor(media-indexer): 7.1 library/scanner.py populates indexer DB`

---

### 7.2 — Rewrite `library/analyzer.py`

**Files touched:**

- `personalscraper/library/analyzer.py` _(rewrite)_
- `tests/library/test_analyzer.py` _(rewrite)_

**Deliverable:**

- `analyze(conn) -> AnalysisResult` — queries the indexer (e.g. `SELECT ... FROM media_item JOIN media_file ...`) instead of parsing a JSON blob. `AnalysisResult` dataclass preserved for callers (`reporter.py`, `rescraper.py`).
- Example queries replacing old JSON traversal:
  - Items on Disk1 with `nfo_status='invalid'`: `SELECT * FROM media_item JOIN ... WHERE disk.label='Disk1' AND nfo_status='invalid'`.
  - Items missing artwork: `SELECT * FROM media_item WHERE json_extract(artwork_json, '$.poster') = 0`.
  - TV shows missing season posters: `SELECT * FROM season WHERE has_poster=0`.
- `library_analysis.json` no longer written (remove write call).
- Tests: seed DB with known fixture; `analyze(conn)` returns expected counts; no JSON file created.

**Tests added:** Rewrite `tests/library/test_analyzer.py`

**Commit:** `refactor(media-indexer): 7.2 library/analyzer.py queries indexer DB`

---

### 7.3 — Rewrite `library/reporter.py`

**Files touched:**

- `personalscraper/library/reporter.py` _(modify — query indexer directly)_
- `tests/library/test_reporter.py` _(modify)_

**Deliverable:**

- `reporter.py` reads `AnalysisResult` (from `analyzer.analyze(conn)`) or queries the indexer directly where `AnalysisResult` is insufficient.
- No longer reads `library_analysis.json` from disk.
- Tests: reporter output matches expected strings on a seeded DB fixture.

**Tests added:** Modify `tests/library/test_reporter.py`

**Commit:** `refactor(media-indexer): 7.3 library/reporter.py reads indexer analysis`

---

### 7.4 — Migrate remaining library consumers

**Files touched:**

- `personalscraper/library/rescraper.py` _(modify — drive via indexer)_
- `personalscraper/library/disk_cleaner.py` _(modify — use indexer write-through)_
- `personalscraper/library/recommender.py` _(unchanged — confirm; if it reads JSON, update)_

**Deliverable:**

- `rescraper.py`: finds items needing rescrape by querying `media_item WHERE nfo_status != 'valid' OR date_metadata_refreshed IS NULL`. No longer parses `library_scan.json`.
- `disk_cleaner.py`: uses `item_repo.find_on_disk(disk_id)` instead of parsing JSON; writes outbox rows for any file it removes (DESIGN §10.2).
- `recommender.py`: confirm it does not read JSON directly (uses `AnalysisResult` from analyzer). If it does, update.
- `library_scan.json` write call removed from all paths.

**Tests added:** Extend existing tests in `tests/library/` as needed (surgical edits only).

**Commit:** `refactor(media-indexer): 7.4 migrate rescraper disk_cleaner recommender to indexer`

---

### 7.5 — Migrate `trailers/scanner.py`

**Files touched:**

- `personalscraper/trailers/scanner.py` _(rewrite)_
- `tests/trailers/test_scanner.py` _(modify — replace TTL-cache assertions with indexer-query assertions)_

**Deliverable:**

- `trailers/scanner.py` replaces the TTL-cached library scan with a single-call `indexer.query.find_items_without_trailer(conn) -> list[MediaItemRow]`. The query: `SELECT media_item.* FROM media_item LEFT JOIN item_attribute ia ON ia.item_id=media_item.id AND ia.key='trailer_found' WHERE ia.value IS NULL`.
- `find_items_without_trailer` is added to `personalscraper/indexer/query.py` (stub module created here; full query parser in Phase 8).
- The `library_scan_max_age_hours` config knob is removed from usage (marked deprecated in `conf/migration.py` in Phase 0, now fully removed from the call site).
- The in-memory TTL cache layer (`_cached_scan`, `_cache_timestamp`) removed from `trailers/scanner.py`.
- Expected outcome: `trailers/scanner.py` is significantly shorter (entire cache-warming path removed).
- Tests: assert `find_items_without_trailer` returns items without `item_attribute(key='trailer_found')`; TTL-cache assertions removed; test uses seeded DB fixture.

**Tests added:** Modify `tests/trailers/test_scanner.py`

**Commit:** `refactor(media-indexer): 7.5 trailers/scanner.py uses indexer query`

---

### 7.6 — Remove legacy JSON files + TTL knob + consumer parity test

**Files touched:**

- `.data/library_scan.json` _(delete or add to .gitignore)_
- `.data/library_analysis.json` _(delete or add to .gitignore)_
- `personalscraper/conf/models.py` _(modify — remove `library_scan_max_age_hours` field)_
- `.personalscraper/config/trailers.json5` _(modify — remove `library_scan_max_age_hours` key)_
- `personalscraper/conf/migration.py` _(modify — add removal note for the knob in migration-warnings.txt)_
- `tests/integration/test_consumer_parity.py` _(new — consumes Phase 0.6 fixtures)_

**Deliverable:**

- `library_scan.json` and `library_analysis.json` not written anywhere; if tracked in repo, `git rm` them.
- `library_scan_max_age_hours` removed from `Config`/`TrailersConfig` pydantic model and from `trailers.json5`.
- Consumer parity test per DESIGN §15.4.1:
  - `tests/fixtures/parity/v0.7-fs/`, `tests/fixtures/parity/v0.7-library_scan.json`, `tests/fixtures/parity/v0.7-media_index.json` — these snapshots were captured in **Phase 0.6** (before any consumer migration started, i.e. before Phase 6 stripped `media_index.json`). This sub-phase consumes them, does not produce them.
  - Assertion shape from DESIGN §15.4.1: 1:1 set match on `(disk_label, rel_path)`; per-item: `nfo_status` matches, `artwork_present` matches, season numbers match for TV shows.
  - Test must pass before Phase 7 can be considered closed.

**Tests added:** `tests/integration/test_consumer_parity.py`

**Commit:** `test(media-indexer): 7.6 consumer parity test and remove legacy JSON files`

---

## Acceptance criteria

- [ ] `pytest tests/library/` passes (rewritten tests green).
- [ ] `pytest tests/trailers/` passes (TTL-cache assertions replaced by indexer-query assertions).
- [ ] `pytest tests/integration/test_consumer_parity.py` passes (1:1 set match against v0.7 snapshot).
- [ ] `personalscraper trailers scan` on the parity fixture produces the same result set as v0.7.
- [ ] No `library_scan.json` or `library_analysis.json` written or read anywhere in codebase.
- [ ] `library_scan_max_age_hours` no longer appears in `Config`, `trailers.json5`, or any call site.
- [ ] `trailers/scanner.py` has no in-memory TTL cache; queries indexer directly.
- [ ] `disk_cleaner.py` writes outbox rows for files it removes.
- [ ] `pytest tests/dispatch/` still passes (no regressions from lib migration).
- [ ] `pytest tests/e2e/test_pipeline_indexer.py` still passes.

---

## DESIGN cross-references

Implements: §10.2 (library/scanner + analyzer migration), §10.3 (trailers/scanner migration — TTL removal), §10.4 (trailers/orchestrator outbox — already done in Phase 5; disk_cleaner outbox here), §15.4 (golden tests — consumer parity), §15.4.1 (consumer parity contract, fixture shape, assertion pattern).

---

## Out of scope for this phase

- Full `indexer/query.py` parser (only `find_items_without_trailer` stub needed here) — Phase 8.
- `library search`, `library verify`, `library repair`, `library show` CLI — Phase 8.
- Three launchd plist templates — Phase 8.
- `docs/reference/indexer.md` — Phase 8.
