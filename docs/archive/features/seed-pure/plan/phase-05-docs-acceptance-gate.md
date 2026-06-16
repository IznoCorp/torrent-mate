# Phase 5 — Docs + ACCEPTANCE + gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Update `docs/reference/architecture.md` to document `core/tags.py` and the seed-pure skip contract; create `docs/features/seed-pure/ACCEPTANCE.md` with criteria 1-9 as executable shell commands (SH-16); run the full phase gate including design-gap scripts.

**Architecture:** Documentation-only phase. No source code changes. The ACCEPTANCE criteria mirror the format of `docs/archive/features/follow-detect/ACCEPTANCE.md` — each criterion is an executable shell command with a documented expected output. Every ACC command must be run before writing the expected output so the count is real, not estimated.

**Tech Stack:** Markdown, bash

---

## Gate

**Previous phase produced:**

- `SortConfig.verify_seed_pure` and `ProcessCleanConfig.verify_seed_pure` (default False) in `conf/models/scraper.py`.
- `run_sort` and `run_clean` accept optional `torrent_client`.
- `SortStep` and `CleanStep` thread the client when the flag is enabled.
- `pytest tests/sorter/test_sort_seed_pure_guard.py tests/process/test_clean_seed_pure_guard.py` pass (0 failed).

Verify:

```bash
pytest tests/sorter/test_sort_seed_pure_guard.py tests/process/test_clean_seed_pure_guard.py --tb=short -q
make check
```

Expected: tests pass; `make check` exits 0.

---

## Sub-phase 5.1 — Update `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md`

### Task 1: Add `core/tags.py` entry and seed-pure skip-contract note

- [ ] **Step 1: Find the `core/` section in architecture.md**

```bash
rg "core/" docs/reference/architecture.md -n | head -20
```

Expected: lines referencing existing `core/` modules (e.g. `core/event_bus.py`, `core/app_context.py`, `core/identity.py`).

- [ ] **Step 2: Add `core/tags.py` to the module listing**

In the `core/` module table (or list), add:

```
| `core/tags.py` | Tag vocabulary — `SEED_PURE = "seed-pure"` constant shared by all pipeline layers. Bottom layer: imports nothing project-internal. |
```

- [ ] **Step 3: Add the seed-pure skip-contract note**

Locate the Watcher / pipeline-orchestration section (or the ingest section) and add:

```markdown
### seed-pure skip contract

The `seed-pure` tag on a torrent is the single triage↔acquisition seam:

- **Acquisition writes it** — manually via `personalscraper seed mark <hash>` (O1) or automatically by Follow D3 / Ratio (future).
- **Triage reads it and skips** — the ingest loop skips any completed torrent whose `TorrentItem.tags` contains `"seed-pure"` (always on, unconditional). An opt-in guard at sort/process time (`config.sort.verify_seed_pure` / `config.process_clean.verify_seed_pure`, default off) re-queries the client and skips matched items.
- **The Watcher must consult the same rule** — before triggering a pipeline run, the Watcher must ignore torrents tagged `seed-pure` so it never double-ingests a seed-only torrent. The constant `core.tags.SEED_PURE` is the canonical import.
```

- [ ] **Step 4: Commit**

```bash
git add -f docs/reference/architecture.md
git commit -m "docs(seed-pure): add core/tags.py entry + seed-pure skip-contract note to architecture.md"
```

---

## Sub-phase 5.2 — Create `docs/features/seed-pure/ACCEPTANCE.md`

**Files:**

- Create: `docs/features/seed-pure/ACCEPTANCE.md`

### Task 2: Run each acceptance command and record real expected output

Before writing the file, run every command below and capture the real output. Replace the placeholder counts with what you actually observe.

- [ ] **Step 1: Run ACC-01**

```bash
pytest tests/api/torrent/test_tagger.py::test_seed_pure_importable_and_value tests/api/torrent/test_tagger.py::test_seed_pure_in_all --tb=short -v
```

Record the pass count (expected: `2 passed`).

- [ ] **Step 2: Run ACC-02**

```bash
pytest tests/api/torrent/test_tagger.py -k "qbit" --tb=short -v
```

Record the pass count (expected: `5 passed`).

- [ ] **Step 3: Run ACC-03**

```bash
pytest tests/api/torrent/test_tagger.py -k "tx or transmission" --tb=short -v
```

Record the pass count (expected: `7 passed`).

- [ ] **Step 4: Run ACC-04**

```bash
pytest tests/commands/test_seed.py --tb=short -v
```

Record the pass count (expected: `5 passed` or actual count).

- [ ] **Step 5: Run ACC-05**

```bash
pytest tests/ingest/test_ingest_seed_pure.py -k "skipped or event or content_path" --tb=short -v
```

Record the pass count.

- [ ] **Step 6: Run ACC-06**

```bash
pytest tests/ingest/test_ingest_seed_pure.py::test_seed_pure_and_below_ratio_counted_once --tb=short -v
```

Record the pass count (expected: `1 passed`).

- [ ] **Step 7: Run ACC-07**

```bash
pytest tests/sorter/test_sort_seed_pure_guard.py tests/process/test_clean_seed_pure_guard.py --tb=short -v
```

Record the pass count.

- [ ] **Step 8: Run ACC-08**

```bash
rg "^from.*indexer|^import.*indexer" --type py personalscraper/core/tags.py
rg "SEED_PURE" --type py personalscraper/ingest/ingest.py personalscraper/sorter/run.py personalscraper/process/run.py
```

First command: must produce no output (exit code 1). Second: must show imports from `core.tags`, not raw string literals.

- [ ] **Step 9: Run ACC-09**

```bash
make check
python -c "import personalscraper; print('OK')"
python3 scripts/audit_design_coverage.py --strict
python3 scripts/update_feature_map.py --check
```

Record that all exit 0.

### Task 3: Create `docs/features/seed-pure/ACCEPTANCE.md`

- [ ] **Step 1: Write the file with real expected outputs from the runs above**

````markdown
# ACCEPTANCE — seed-pure (Seed Safety O1)

Every criterion below is an **executable shell command** with a documented
expected output (SH-16 rule). Run from the repo root with the `personalscraper`
package installed (`pip install -e ".[dev]"`).

Re-exercise ALL criteria before squash merge.

---

## ACC-01 — `SEED_PURE` constant importable from `core.tags`, value `"seed-pure"`

**Command:**

```bash
pytest tests/api/torrent/test_tagger.py::test_seed_pure_importable_and_value tests/api/torrent/test_tagger.py::test_seed_pure_in_all --tb=short -v
```
````

**Expected:** `2 passed`, `0 failed` — both the value assertion and the `__all__` membership test pass.

---

## ACC-02 — qBittorrent tagger: `add_tags`/`remove_tags` call the right `qbittorrentapi` endpoints; idempotent (empty list = no-op); protocol compliance

**Command:**

```bash
pytest tests/api/torrent/test_tagger.py -k "qbit" --tb=short -v
```

**Expected:** `5 passed`, `0 failed` — covers `torrents_addTags`/`torrents_removeTags` call assertions, empty-list no-ops, and `isinstance(client, TorrentTagger)` check.

---

## ACC-03 — Transmission tagger: `add_tags`/`remove_tags` preserve `labels[0]` (category) via read-first write; idempotent

**Command:**

```bash
pytest tests/api/torrent/test_tagger.py -k "tx or transmission" --tb=short -v
```

**Expected:** `7 passed`, `0 failed` — covers category-preservation golden (category='movies' + tag1 → add seed-pure → labels=['movies','tag1','seed-pure']), idempotent add/remove, empty-list no-ops, and protocol compliance.

---

## ACC-04 — `seed mark`/`unmark` call the tagger with `[SEED_PURE]`; `seed list` filters by tag; no-client exits 1

**Command:**

```bash
pytest tests/commands/test_seed.py --tb=short -v
```

**Expected:** `5 passed`, `0 failed` — covers mark calls `add_tags(hash, [SEED_PURE])`, unmark calls `remove_tags(hash, [SEED_PURE])`, list shows only seed-pure torrents, no-client exits 1, layering guard.

---

## ACC-05 — Ingest skip golden: seed-pure torrent skipped (`skip_count` incremented, `ItemProgressed(status='skipped', reason='seed_pure')` emitted, `get_content_path` not called); non-tagged torrent NOT skipped by this check

**Command:**

```bash
pytest tests/ingest/test_ingest_seed_pure.py -k "not counted_once" --tb=short -v
```

**Expected:** `4 passed`, `0 failed` — covers `skip_count == 1`, the `ItemProgressed` event with correct `step`/`item`/`status`/`reason`, `get_content_path` not called for seed-pure torrents, and `get_content_path` IS called for non-tagged torrents.

---

## ACC-06 — Skip ordering: below-ratio + seed-pure torrent counted exactly once (ratio fires first); no double-processing

**Command:**

```bash
pytest tests/ingest/test_ingest_seed_pure.py::test_seed_pure_and_below_ratio_counted_once --tb=short -v
```

**Expected:** `1 passed`, `0 failed` — `skip_count == 1`, `reason == 'ratio_below_threshold'` (not `seed_pure`), zero `seed_pure` events.

---

## ACC-07 — Sort/process guard off by default (no client query); guard on + stub client → seed-pure item skipped; guard on + no client → inert (no crash)

**Command:**

```bash
pytest tests/sorter/test_sort_seed_pure_guard.py tests/process/test_clean_seed_pure_guard.py --tb=short -v
```

**Expected:** `6 passed`, `0 failed` — covers flag-off (zero `get_completed` calls), flag-on + seed-pure item skipped (`skip_count >= 1`), flag-on + no client (no crash) for both sort and clean.

---

## ACC-08 — Layering guard: `core/tags.py` imports nothing project-internal; `ingest`/`sorter`/`process` import `SEED_PURE` from `core.tags` (not a raw literal)

**Command:**

```bash
rg "^from.*indexer|^import.*indexer|^from.*scraper|^from.*sorter|^from.*ingest|^from.*commands" --type py personalscraper/core/tags.py
rg "SEED_PURE" --type py personalscraper/ingest/ingest.py personalscraper/sorter/run.py personalscraper/process/run.py
```

**Expected:** First command produces **no output** (exit code 1 = no project-internal imports in `core/tags.py`). Second command shows `from personalscraper.core.tags import SEED_PURE` in each file — no raw `"seed-pure"` string literals in these files.

---

## ACC-09 — `make check` green; `python -c "import personalscraper"` smoke; design-gaps + feature-map scripts exit 0

**Command:**

```bash
make check
python -c "import personalscraper; print('OK')"
python3 scripts/audit_design_coverage.py --strict
python3 scripts/update_feature_map.py --check
```

**Expected:** All four commands exit 0. `make check` summary shows 0 failed / 0 errors. `python -c` prints `OK`. `audit_design_coverage.py --strict` exits 0. `update_feature_map.py --check` exits 0 with no output.

````

- [ ] **Step 2: Commit**

```bash
git add -f docs/features/seed-pure/ACCEPTANCE.md
git commit -m "docs(seed-pure): create ACCEPTANCE.md with ACC-01..ACC-09 executable criteria (SH-16)"
````

---

## Sub-phase 5.3 — Final phase gate

### Task 4: Full gate

- [ ] **Step 1: `make lint`** — ruff + mypy + check_logging. Must exit 0.

```bash
make lint
```

- [ ] **Step 2: `make test`** — full test suite. Must show `0 failed`, `0 errors`.

```bash
make test
```

- [ ] **Step 3: `make check`** — lint + test + module-size + typed-api guardrails. Must exit 0.

```bash
make check
```

- [ ] **Step 4: Smoke test.**

```bash
python -c "import personalscraper; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Residual import grep** — for every new module, confirm no stale references.

```bash
rg "core\.tags|core/tags" --type py tests/ personalscraper/ | grep -v "from personalscraper.core.tags import SEED_PURE" | grep -v "core/tags.py"
```

Expected: any remaining matches should be legitimate (e.g. architecture.md references, test imports). No stale raw `"seed-pure"` strings.

- [ ] **Step 6: Run design-gaps scripts (CI-only scripts — run locally here).**

```bash
python3 scripts/audit_design_coverage.py --strict
python3 scripts/update_feature_map.py --check
```

Expected: both exit 0.

- [ ] **Step 7: Re-exercise all ACCEPTANCE criteria.**

Run each ACC command from `ACCEPTANCE.md` in order. Record that all pass. If any fail, fix before the gate commit.

- [ ] **Step 8: Gate commit.**

```bash
git add -f docs/reference/architecture.md docs/features/seed-pure/ACCEPTANCE.md
git commit -m "chore(seed-pure): phase 5 gate — docs + ACCEPTANCE + make check green"
```

---

## Phase 5 Gate (= Feature Complete)

- [ ] All ACC-01..ACC-09 commands exit 0 with expected output.
- [ ] `make check` exits 0 (0 failed, 0 errors).
- [ ] `python -c "import personalscraper"` exits 0.
- [ ] `python3 scripts/audit_design_coverage.py --strict` exits 0.
- [ ] `python3 scripts/update_feature_map.py --check` exits 0.
- [ ] No raw `"seed-pure"` string literals in `ingest/`, `sorter/`, `process/` (only `SEED_PURE` constant imported from `core.tags`).
