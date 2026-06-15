# Phase 5 — Docs + ACCEPTANCE + gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Surgical `docs/reference/architecture.md` edit (add `acquire/cadence.py` entry + Follow D2 boundary note), create `docs/features/follow-detect/ACCEPTANCE.md` with ACC-01..ACC-10 as executable shell commands (SH-16), run full gate including CI-only checks locally.

**Architecture:** Documentation-only changes plus the final quality gate. No new source code.

**Tech Stack:** bash, `make`, `python3 scripts/`

---

## Gate

Phase 4 must be complete:

- [ ] `pytest tests/acquire/test_service_cadence.py` passes with 0 failures.
- [ ] `make check` exits 0 after phase 4.

---

## Sub-phase 5.1 — Architecture doc update

**Files:**

- Modify: `docs/reference/architecture.md`

### Task 1: Add `acquire/cadence.py` to the acquire/ tree

- [ ] **Step 1: Find the acquire/ module listing in `docs/reference/architecture.md`**

```bash
grep -n "cadence\|airing\|desired\|acquire/" docs/reference/architecture.md -m 20
```

- [ ] **Step 2: Add the `cadence.py` line alongside `airing.py` and `desired.py` in the acquire/ tree**

Locate the line for `acquire/airing.py` and insert immediately after it:

```
│   ├── cadence.py          — Cadence/CadenceTier VOs + is_due_by_cadence/is_past_cutoff (Follow D2; pure, stdlib only)
```

- [ ] **Step 3: Add Follow D2 boundary note**

Find the RP9 / airing boundary note in the doc and add alongside it:

```
**Follow D2 boundary:** `acquire/cadence.py` is pure (imports `core`/stdlib only — never `store`, `indexer`, `scraper`, or the event bus). Cadence codecs live in `acquire/desired.py`. The `follow detect` CLI command (`commands/follow.py`) composes the context at the boundary layer and never imports `indexer` or `pipeline`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/reference/architecture.md
git commit -m "docs(follow-detect): add acquire/cadence.py to architecture.md + D2 boundary note"
```

---

## Sub-phase 5.2 — ACCEPTANCE.md

**Files:**

- Create: `docs/features/follow-detect/ACCEPTANCE.md`

### Task 2: Write the ACCEPTANCE file (SH-16 — every criterion an executable command)

- [ ] **Step 1: Create `docs/features/follow-detect/ACCEPTANCE.md`**

````markdown
# ACCEPTANCE — follow-detect (Follow D2)

Every criterion below is an **executable shell command** with a documented
expected output (SH-16 rule). Run from the repo root with the `personalscraper`
package installed (`pip install -e ".[dev]"`).

Re-exercise ALL criteria before squash merge.

---

## ACC-01 — Cadence predicate: all tier boundaries + cutoff

**Command:**

```bash
pytest tests/acquire/test_cadence.py -v -k "is_due or is_past_cutoff" --tb=short
```
````

**Expected:** All boundary tests pass (`11 passed`), `0 failed`.

---

## ACC-02 — `effective_cadence`: series override wins; None → global default

**Command:**

```bash
pytest tests/acquire/test_cadence.py -v -k "effective_cadence" --tb=short
```

**Expected:** `2 passed`, `0 failed`.

---

## ACC-03 — Config: `CadenceConfig` default reproduces Hot/Warm/Cold/30d; absent block loads default

**Command:**

```bash
pytest tests/acquire/test_cadence.py -v -k "config" --tb=short
```

**Expected:** `5 passed`, `0 failed` (broad `-k config` also matches the two
`rejects_*` validator tests + the unit-conversion test, so the real count is 5).

---

## ACC-04 — `store.wanted.find`: returns row for known key, None otherwise; round-trips through `add`

**Command:**

```bash
pytest tests/acquire/test_store_wanted_find.py -v --tb=short
```

**Expected:** `5 passed`, `0 failed`.

---

## ACC-05 — DETECT golden: correct which episodes enqueued vs skipped-owned vs skipped-dup; `WantedEnqueued` emitted once per enqueue with correct fields

**Command:**

```bash
pytest tests/commands/test_follow_detect.py -v -k "golden or skips_owned or skips_duplicate" --tb=short
```

**Expected:** `3 passed`, `0 failed`.

---

## ACC-06 — DETECT `--dry-run`: zero `store.wanted.add` calls, zero emits

**Command:**

```bash
pytest tests/commands/test_follow_detect.py::test_detect_dry_run_no_writes_no_emits -v --tb=short
```

**Expected:** `1 passed`, `0 failed`.

---

## ACC-07 — Cadence-aware `run()`: not-due → skipped (no claim, attempts unchanged); due → claim called; past-cutoff → abandoned + `WantedAbandoned(reason='cutoff_reached')` emitted before any grab

**Command:**

```bash
pytest tests/acquire/test_service_cadence.py -v --tb=short
```

**Expected:** `4 passed`, `0 failed`.

---

## ACC-08 — Boundary preserved: DETECT makes zero grab calls; `poll_aired` negative-boundary tests still pass

**Command:**

```bash
pytest tests/commands/test_follow_detect.py::test_detect_boundary_no_grab_calls tests/acquire/test_airing.py -v --tb=short
```

**Expected:** `25 passed`, `0 failed`.

---

## ACC-09 — Layering guard: `acquire/cadence.py` imports no `indexer`/`store`/`scraper`/event-bus; `commands/follow.py` imports no `indexer`/`pipeline`

**Command:**

```bash
rg "^from .*(indexer|acquire\.store|acquire\._ports|scraper|event_bus)|^import .*(indexer|acquire\.store|scraper)" --type py personalscraper/acquire/cadence.py
pytest tests/commands/test_follow_detect.py::test_detect_layering_no_indexer_import -v --tb=short
```

**Expected:** First command produces no output (exit 1 = no match = correct). Second: `1 passed`.

---

## ACC-10 — `make check` green; `python -c "import personalscraper"` smoke; design-gaps + feature-map scripts exit 0

**Command:**

```bash
make check
python -c "import personalscraper; print('OK')"
python3 scripts/audit_design_coverage.py --strict
python3 scripts/update_feature_map.py --check
```

**Expected:** All four commands exit 0. `make check` summary shows 0 failed/errors. `python -c` prints `OK`.

````

- [ ] **Step 2: Commit**

```bash
git add docs/features/follow-detect/ACCEPTANCE.md
git commit -m "docs(follow-detect): add ACCEPTANCE.md — ACC-01..ACC-10 executable criteria (SH-16)"
````

---

## Sub-phase 5.3 — Full gate

### Task 3: Run the complete gate

- [ ] **Step 1: Run `make check`**

```bash
make check
```

Expected: exits 0. Summary line shows `NNNN passed` with `0 failed` and `0 errors`.

- [ ] **Step 2: Smoke test**

```bash
python -c "import personalscraper; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Run CI-only design-gaps scripts (do NOT pipe to tail)**

```bash
python3 scripts/audit_design_coverage.py --strict
```

Expected: exits 0.

```bash
python3 scripts/update_feature_map.py --check
```

Expected: exits 0.

- [ ] **Step 4: Re-exercise all ACCEPTANCE criteria**

```bash
pytest tests/acquire/test_cadence.py tests/acquire/test_store_wanted_find.py tests/commands/test_follow_detect.py tests/acquire/test_service_cadence.py -v --tb=short
```

Expected: all pass, `0 failed`.

- [ ] **Step 5: Layering rg cross-check**

```bash
rg "^from .*(indexer|acquire\.store|acquire\._ports|scraper|event_bus)|^import .*(indexer|acquire\.store|scraper)" --type py personalscraper/acquire/cadence.py
```

Expected: no output (exit code 1 = no match = correct).

- [ ] **Step 6: Commit gate**

```bash
git add -A
git commit -m "chore(follow-detect): phase 5 gate — docs + ACCEPTANCE + full make check green"
```

---

## Phase 5 Gate

All of the above must be green. This is the final phase — `implement:feature-pr` is invoked next.
