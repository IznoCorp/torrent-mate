# Phase 6 — Consumer Migration: Dispatch

## Gate

**Prerequisite (Phase 5 exit gate):**

> A pipeline run leaves an empty outbox at end (drained) and the indexer reflects every mutation.

**This phase's exit gate (verbatim from DESIGN §16):**

> Full pipeline run end-to-end with no `media_index.json` on disk; dispatch decisions identical to v0.7 on a fixture FS.

---

## Scope

Replace `dispatch/media_index.py`'s JSON-file backend with a thin wrapper over the indexer repos. The public API (`find`, `add`, `rebuild`, `remove_stale`, `load`, `save`) is preserved exactly — callers (`dispatch/dispatcher.py`, `dispatch/run.py`) need zero behavioural change. `media_index.json` is removed. First-run detection triggers an indexer rebuild for affected disks when the JSON is absent.

---

## Sub-phases

### 6.1 — Rewrite `MediaIndex` as indexer wrapper

**Files touched:**

- `personalscraper/dispatch/media_index.py` _(rewrite)_
- `tests/dispatch/test_media_index.py` _(modify — surgical edits only; no new assertions; existing tests must pass)_

**Deliverable:**

- `MediaIndex.__init__(index_path)`: `index_path` accepted for backward compat but ignored. Opens `library.db` via `open_db`.
- `MediaIndex.load()`: no-op. The DB has its own lifecycle.
- `MediaIndex.save()`: no-op.
- `MediaIndex.find(name: str) -> IndexEntry | None`: delegates to `item_repo.find_by_normalized_name(name)`. Returns `IndexEntry` dataclass (preserved at module level per DESIGN §10.1) built from indexer rows. `normalized_name` = the same normalization logic currently used by `MediaIndex` (lowercased, stripped punctuation — keep existing helper).
- `MediaIndex.add(entry: IndexEntry) -> None`: delegates to `item_repo.upsert` + `file_repo.upsert`.
- `MediaIndex.rebuild(disk_configs) -> None`: calls `indexer.scanner.scan(disks, mode='full')` for each disk in `disk_configs`.
- `MediaIndex.remove_stale(disk_configs) -> None`: delegates to `item_repo.remove_items_not_on_disks(disk_configs)`.
- `IndexEntry` dataclass fields unchanged: `name`, `disk`, `category`, `path`, `media_type`, `last_updated`.
- Tests: existing `tests/dispatch/test_media_index.py` must pass with zero new `@patch` calls. Surgical edits only to swap fixture setup if it referenced the old JSON file.

**Tests added:** Surgical edits to `tests/dispatch/test_media_index.py` only.

**Commit:** `refactor(media-indexer): 6.1 MediaIndex thin wrapper over indexer repos`

---

### 6.2 — Remove `media_index.json` writes/reads

**Files touched:**

- `personalscraper/dispatch/media_index.py` _(modify — confirm no JSON I/O remains)_
- `.data/media_index.json` _(delete — if tracked in repo; else add to `.gitignore`)_
- `personalscraper/conf/migration.py` _(modify — note legacy file in migration-warnings.txt if found)_

**Deliverable:**

- No code path in `media_index.py` reads or writes `*.json` files.
- If `.data/media_index.json` is tracked in the repo, remove it via `git rm`. If not tracked, add `.data/media_index.json` to `.gitignore`.
- `conf/migration.py` notes in `migration-warnings.txt` that `.data/media_index.json` can be safely deleted once `rebuild()` has been run.
- `personalscraper/conf/loader.py` removes any reference to `media_index.json` path resolution.

**Tests added:** None.

**Commit:** `chore(media-indexer): 6.2 remove media_index.json writes and reads`

---

### 6.3 — First-run detection: missing JSON triggers rebuild

**Files touched:**

- `personalscraper/dispatch/media_index.py` _(modify — add first-run detection in `__init__`)_
- `tests/dispatch/test_media_index.py` _(extend — one new test for first-run path)_

**Deliverable:**

- `MediaIndex.__init__`: if `library.db` does not exist OR `SELECT COUNT(*) FROM media_item` = 0, log `indexer.config.no_index` and trigger `rebuild(disk_configs)` automatically (disk_configs sourced from global `Config`).
- If `media_index.json` is found on disk (legacy), log a one-time deprecation warning: "media_index.json found; it is no longer used — run `personalscraper library index --mode full` to populate the indexer." Do not read the JSON.
- First-run rebuild only runs once: once `media_item` rows exist, subsequent `__init__` calls skip it.
- Test: initialise `MediaIndex` with empty `library.db` → `rebuild` called automatically → `media_item` rows exist after init.

**Tests added:** Extend `tests/dispatch/test_media_index.py` (one test, no new `@patch` calls).

**Commit:** `feat(media-indexer): 6.3 first-run detection triggers indexer rebuild`

---

### 6.4 — Full dispatch test suite passes

**Files touched:**

- `tests/dispatch/test_dispatcher.py` _(surgical edits only — no new assertions, no new @patch calls)_
- `tests/dispatch/test_media_index.py` _(confirm all pass)_

**Deliverable:**

- `pytest tests/dispatch/` passes in full with zero regressions.
- No new `@patch` decorators added to `test_dispatcher.py` (preserves the PR #14 trim).
- E2E dispatch test: `tests/e2e/test_pipeline_indexer.py` (from Phase 5) asserts dispatch decisions (which disk an item lands on) are identical to v0.7 behaviour on a fixture FS.
- `tests/e2e/test_indexer_writer_lock_contention.py` _(new)_: spawn two subprocesses racing on `library.db.lock`; first acquires; second with `--wait-for-lock 0` fails fast with holding PID in error; second with `--wait-for-lock 60` waits until first releases then succeeds; no DB corruption.

**Tests added:** `tests/e2e/test_indexer_writer_lock_contention.py`

**Commit:** `test(media-indexer): 6.4 dispatch tests pass and writer lock contention E2E`

---

## Acceptance criteria

- [ ] `pytest tests/dispatch/` passes with zero regressions and zero new `@patch` calls in `test_dispatcher.py`.
- [ ] Full pipeline run (`personalscraper run`) with no `media_index.json` on disk completes successfully.
- [ ] Dispatch decisions (which disk an item moves to) match v0.7 output on the fixture FS.
- [ ] `MediaIndex.find()` returns correct `IndexEntry` for items populated by `rebuild()`.
- [ ] `MediaIndex.load()` and `MediaIndex.save()` are no-ops (no file I/O, no errors).
- [ ] First-run with empty DB: `rebuild()` triggered automatically; subsequent `__init__` skips rebuild.
- [ ] Legacy `media_index.json` present on disk: deprecation warning logged; JSON not read.
- [ ] `tests/e2e/test_indexer_writer_lock_contention.py` passes: second process fails fast, then succeeds with `--wait-for-lock`; no DB corruption.
- [ ] No `.data/media_index.json` file present or referenced after this phase.

---

## DESIGN cross-references

Implements: §10.1 (dispatch/media_index migration — API preservation, `load`/`save` no-ops, `IndexEntry` preserved, first-run detection), §17.1 (outbox edge cases: lock contention — `test_indexer_writer_lock_contention.py`).

---

## Out of scope for this phase

- `library/scanner.py`, `library/analyzer.py`, `trailers/scanner.py` migration — Phase 7.
- Removal of `library_scan.json` and `library_analysis.json` — Phase 7.
- `library search`, `library verify`, `library repair`, `library show` CLI — Phase 8.
- Query language — Phase 8.
