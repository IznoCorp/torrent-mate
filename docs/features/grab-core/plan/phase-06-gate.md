# Phase 06 — Docs + ACCEPTANCE + Gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update `docs/reference/architecture.md` with the `acquire/` module map additions,
write the grab-core reference doc, write `ACCEPTANCE.md` with executable criteria (per
DESIGN §13 + feature-lifecycle.md convention), run the full phase-gate checklist, and
confirm `make check` + design-gaps local check green.

**Architecture:** Documentation phase only — no new source code. Every `ACCEPTANCE` criterion
is an executable shell command with documented expected output (SH-16 / tech-debt 0.16.0 rule).

---

## Gate (start of phase)

All previous phases complete:

- `acquire/desired.py`, `acquire/_dedup.py`, `acquire/_filters.py`
- `acquire/orchestrator.py`, `acquire/service.py`
- `acquire/context.py` + `acquire/_factory.py` wired
- `personalscraper grab` CLI registered
- All tests passing (`make test` green)

---

## File Map

- **Modify:** `docs/reference/architecture.md` — add `acquire/` module map rows
- **Create:** `docs/reference/grab-core.md` — grab-core reference doc
- **Create:** `docs/features/grab-core/ACCEPTANCE.md`

---

## Task 1: Update `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md`

- [ ] **Step 1: Read the current acquire/ section**

```bash
grep -n "acquire/" /Users/izno/dev/PersonnalScaper/docs/reference/architecture.md | head -20
```

- [ ] **Step 2: Add new module rows to the acquire/ table**

Locate the `acquire/` module map table in `architecture.md`. Add rows for the five new modules:

| Module                    | Responsibility                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `acquire/desired.py`      | `Resolution` IntEnum, `QualityProfile`, `SourceCriteria`, JSON codecs, `effective_quality` |
| `acquire/_dedup.py`       | `SearchOutcome`, `search_candidates` seam, token-set normalizer, `dedup()`                 |
| `acquire/_filters.py`     | Hard-filter stage: resolution floor (fail-open None) + anchored audio language regex       |
| `acquire/orchestrator.py` | `GrabOrchestrator` — single-item §1 grab chain, failure taxonomy, event emission           |
| `acquire/service.py`      | `AcquisitionService` batch loop, `GrabCore` handle, `RunSummary`, attempts cap             |

- [ ] **Step 3: Verify the doc renders without broken references**

```bash
grep -n "desired\|_dedup\|_filters\|orchestrator\|service" \
    /Users/izno/dev/PersonnalScaper/docs/reference/architecture.md | head -20
```

Expected: entries present for all five modules.

- [ ] **Step 4: Commit**

```bash
git add -f docs/reference/architecture.md
git commit -m "docs(grab-core): add acquire/ module map entries to architecture.md"
```

---

## Task 2: Write the grab-core reference doc

**Files:**

- Create: `docs/reference/grab-core.md`

- [ ] **Step 1: Create the reference doc**

Create `docs/reference/grab-core.md` with the following structure. Use `git add -f` because
the global `~/.gitignore` has a `docs/` rule.

```markdown
# grab-core — Download Orchestrator + Acquisition Service

RP5b (0.28.0) — gate of the acquire epic.

## The grab flow
```

WantedItem (with id) ← store.wanted.list_pending() SELECTs id
→ claim_for_search(id, now) ← ATOMIC UPDATE…WHERE status='pending'
→ resolve QualityProfile ← effective_quality(series, item)
→ search_candidates(…) ← SearchOutcome (raw, un-ranked)
→ HARD-FILTERS ← apply_hard_filters(results, profile)
→ DEDUP ← dedup(filtered)
→ rank(survivors, ranking) ← soft score
→ resolve_source(top, …) ← fetch .torrent bytes
→ torrent_client.add(source) ← idempotent
→ mark_grabbed(id, hash) ← persists hash for idempotence guard
→ emit GrabSucceeded

````

## Module map

| Module | Role |
|--------|------|
| `acquire/desired.py` | `Resolution` + `QualityProfile` + `SourceCriteria` + `effective_quality` |
| `acquire/_dedup.py` | `SearchOutcome` + `dedup()` + `normalize_title_core` |
| `acquire/_filters.py` | `apply_hard_filters()` — resolution floor + audio language |
| `acquire/orchestrator.py` | `GrabOrchestrator` — single-item chain |
| `acquire/service.py` | `AcquisitionService` + `GrabCore` + `RunSummary` |

## Failure taxonomy (§6.2)

| Failure | Class | Status transition | Event |
|---------|-------|-------------------|-------|
| All trackers errored | RETRYABLE | searching→pending | `GrabFailed('trackers_unavailable')` |
| `CircuitOpenError` | RETRYABLE | searching→pending | `GrabFailed('circuit_open')` |
| Transient `ApiError` on add | RETRYABLE | searching→pending | `GrabFailed(...)` |
| DB lock on `mark_grabbed` | RETRYABLE | searching→pending | `GrabFailed('db_lock...')` |
| Zero search results | TERMINAL | searching→abandoned | `WantedAbandoned('no_candidates')` |
| All hard-filtered | TERMINAL | searching→abandoned | `WantedAbandoned('all_filtered')` |
| `TrackerAuthError` | TERMINAL | searching→abandoned | `WantedAbandoned('auth_failed:...')` |
| attempts ≥ MAX_ATTEMPTS | TERMINAL | searching→abandoned | `WantedAbandoned('attempts_cap')` |

## Hard-filter defaults (permissive)

- `min_resolution = None` → no floor; None-resolution (REMUX, COMPLETE.BLURAY) **passes**
- `required_audio = frozenset()` → no language requirement; English/VO content grabs cleanly
- A French-only or ≥1080p policy is a per-profile **opt-in** (Follow D4)

## Dedup strategy

1. **Primary key**: `info_hash.lower()` — collapses exact within-tracker dups
2. **Fuzzy fallback**: `normalize_title_core(title) | resolution_tier | release_group | size_bucket(±2%)`
   — collapses cross-tracker repacks of the same cut; VF/VOSTFR preserved as distinct tokens

## CLI

```bash
personalscraper grab                # process all pending items
personalscraper grab --limit 5      # process at most 5 items
personalscraper grab --dry-run      # search+filter+rank, print top, no add
````

## ACCEPTANCE criteria

See `docs/features/grab-core/ACCEPTANCE.md` for executable shell commands.

## Non-goals (deferred)

- Wanted-queue producers (Follow D3/Ratio C1) — waves 4-5
- Per-series QualityProfile producers (Follow D4) — waves 4-5
- Circuit-breaker wiring on tracker transports
- Telegram grab-notify activation

````

- [ ] **Step 2: Commit**

```bash
git add -f docs/reference/grab-core.md
git commit -m "docs(grab-core): add grab-core reference doc"
````

---

## Task 3: Write `ACCEPTANCE.md` with executable criteria

Every criterion is a runnable shell command with documented expected output (SH-16 rule).

**Files:**

- Create: `docs/features/grab-core/ACCEPTANCE.md`

- [ ] **Step 1: Create `ACCEPTANCE.md`**

````markdown
# ACCEPTANCE — grab-core (RP5b)

Every criterion is an executable shell command. Run from the repo root.
All must pass before squash merge.

---

## ACC-01 — Within-tracker same info_hash dedup → one survivor

```bash
python -m pytest tests/acquire/test_dedup.py::test_dedup_same_info_hash_within_tracker_collapses -v
```
````

Expected: `1 passed`

---

## ACC-02 — `-QTZ` cross-tracker pair merges (LOAD-BEARING)

```bash
python -m pytest tests/acquire/test_dedup.py::test_dedup_qtz_cross_tracker_merges -v
```

Expected: `1 passed`

---

## ACC-03 — Sub-floor resolution filtered; None-resolution passes (fail-open)

```bash
python -m pytest \
    tests/acquire/test_filters.py::test_resolution_floor_drops_below_minimum \
    tests/acquire/test_filters.py::test_resolution_none_fails_open \
    -v
```

Expected: `2 passed`

---

## ACC-04 — Mocked add → `GrabSucceeded` emitted

```bash
python -m pytest tests/acquire/test_orchestrator.py::test_grab_happy_path_emits_grab_succeeded -v
```

Expected: `1 passed`

---

## ACC-05 — Two concurrent `claim_for_search` → exactly one wins (LOAD-BEARING)

```bash
python -m pytest tests/acquire/test_service.py::test_claim_for_search_atomic_only_one_wins -v
```

Expected: `1 passed`

---

## ACC-06 — Failure → row retriable; `record_dispatch` never called (LOAD-BEARING)

```bash
python -m pytest \
    tests/acquire/test_orchestrator.py::test_all_trackers_errored_retryable_grab_failed \
    tests/acquire/test_orchestrator.py::test_negative_seed_write_assert \
    -v
```

Expected: `2 passed`

---

## ACC-07 — `personalscraper grab --dry-run` prints ranked candidate without adding

```bash
python -m pytest tests/commands/test_grab.py::test_grab_dry_run_prints_top_candidate -v
```

Expected: `1 passed`

---

## ACC-08 — `\b` boundary guard: MULTILINGUAL/ConVOSTed do NOT match (LOAD-BEARING)

```bash
python -m pytest \
    tests/acquire/test_filters.py::test_audio_regex_boundary_multilingual_does_not_match \
    tests/acquire/test_filters.py::test_audio_regex_boundary_convostfr_does_not_match \
    -v
```

Expected: `2 passed`

---

## ACC-09 — `make check` green

```bash
make check
```

Expected: exit code 0, `0 errors` from ruff and mypy, all tests pass.

---

## ACC-10 — `python -c "import personalscraper"` smoke test

```bash
python -c "import personalscraper; print('OK')"
```

Expected: `OK`

````

- [ ] **Step 2: Commit**

```bash
git add -f docs/features/grab-core/ACCEPTANCE.md
git commit -m "docs(grab-core): ACCEPTANCE.md with 10 executable criteria"
````

---

## Task 4: Phase-gate checklist — `make check` + design-gaps

This is the mandatory phase-gate checklist from `CLAUDE.md`. Execute each step in order.

- [ ] **Step 1: `make lint` — ruff + mypy, zero errors**

```bash
make lint
```

Expected: exit code 0. If ruff or mypy reports errors, fix them before proceeding.
Common issues: missing `TYPE_CHECKING` guards, unused imports, mypy strict mode complaints
on new `desired.py` or `service.py` types.

- [ ] **Step 2: `make test` — all tests pass**

```bash
make test 2>&1 | tail -20
```

Expected: `NNNN passed` with 0 failed/errors. Check the summary line — any `ERROR` in
collection means an import crash that silently skips all downstream tests.

- [ ] **Step 3: `make check` — lint + test + module-size + typed-api guardrails**

```bash
make check
```

Expected: exit code 0.

- [ ] **Step 4: Residual import grep — new modules are clean**

```bash
# Verify no dangling references to old/deleted symbols
python -m rg "from personalscraper.acquire.desired import" --type py personalscraper/ tests/
python -m rg "from personalscraper.acquire._dedup import" --type py personalscraper/ tests/
python -m rg "from personalscraper.acquire._filters import" --type py personalscraper/ tests/
python -m rg "from personalscraper.acquire.orchestrator import" --type py personalscraper/ tests/
python -m rg "from personalscraper.acquire.service import" --type py personalscraper/ tests/
```

Each command must return only valid import sites (no references to symbols that no longer exist).

Note: use `rg` with `--type py`, NOT bare `rg`, to avoid scanning the 14 GB fixture dir.

- [ ] **Step 5: Smoke test**

```bash
python -c "import personalscraper; print('OK')"
python -c "from personalscraper.acquire.desired import Resolution, QualityProfile, SourceCriteria; print('desired OK')"
python -c "from personalscraper.acquire._dedup import SearchOutcome, dedup; print('dedup OK')"
python -c "from personalscraper.acquire._filters import apply_hard_filters; print('filters OK')"
python -c "from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome; print('orchestrator OK')"
python -c "from personalscraper.acquire.service import AcquisitionService, GrabCore, RunSummary; print('service OK')"
```

Expected: all lines print `OK`.

- [ ] **Step 6: Design-gaps local check**

```bash
python scripts/audit_design_coverage.py --strict 2>&1 | tail -10
python scripts/update_feature_map.py --check 2>&1 | tail -10
```

Expected: exit code 0 for both (or only warnings, no errors — see project memory note
that these are CI-only strict checks).

- [ ] **Step 7: Re-exercise all ACCEPTANCE criteria**

Run each ACC-NN command from `ACCEPTANCE.md` in sequence:

```bash
python -m pytest \
    tests/acquire/test_dedup.py::test_dedup_same_info_hash_within_tracker_collapses \
    tests/acquire/test_dedup.py::test_dedup_qtz_cross_tracker_merges \
    tests/acquire/test_filters.py::test_resolution_floor_drops_below_minimum \
    tests/acquire/test_filters.py::test_resolution_none_fails_open \
    tests/acquire/test_orchestrator.py::test_grab_happy_path_emits_grab_succeeded \
    tests/acquire/test_service.py::test_claim_for_search_atomic_only_one_wins \
    tests/acquire/test_orchestrator.py::test_all_trackers_errored_retryable_grab_failed \
    tests/acquire/test_orchestrator.py::test_negative_seed_write_assert \
    tests/commands/test_grab.py::test_grab_dry_run_prints_top_candidate \
    tests/acquire/test_filters.py::test_audio_regex_boundary_multilingual_does_not_match \
    tests/acquire/test_filters.py::test_audio_regex_boundary_convostfr_does_not_match \
    -v
```

Expected: `11 passed`.

- [ ] **Step 8: Commit phase gate**

```bash
git add -f docs/reference/architecture.md docs/reference/grab-core.md \
    docs/features/grab-core/ACCEPTANCE.md
git commit -m "chore(grab-core): phase 06 gate — docs + ACCEPTANCE + make check green"
```
