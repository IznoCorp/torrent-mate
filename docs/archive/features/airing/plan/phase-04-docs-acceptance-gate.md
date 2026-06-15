# Phase 4 — Docs + ACCEPTANCE + gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surgical edit of `docs/reference/architecture.md` (add airing service to the acquire/ block), create `docs/features/airing/ACCEPTANCE.md` (SH-16: every criterion is an executable shell command), then run `make check` and local design-gaps scripts.

**Architecture:** Documentation-only phase — no source code changes. The architecture.md edit is surgical (two lines added inside the existing acquire/ tree block at line 53–63). The ACCEPTANCE.md maps each DESIGN §8 verification requirement to a concrete `pytest` selector or `rg`/`python -c` command.

**Tech Stack:** `make check`, `python3 scripts/audit_design_coverage.py`, `python3 scripts/update_feature_map.py`

---

## Gate

Phase 3 must have produced:

- All airing tests passing (predicate + service + negative + layering).
- `poll_aired` signature confirmed, `AcquireContext` unchanged.

Verify before starting:

```bash
pytest tests/acquire/test_airing.py -v --tb=short 2>&1 | tail -5
```

---

## Sub-phase 4.1 — Surgical edit of `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md` — add `airing.py` entry inside the `acquire/` tree block (lines ~53–63) and extend the RP9↔D2 boundary note near line 431.

### Task 1: Add `airing.py` to the acquire/ module tree

- [ ] **Step 1: Open `docs/reference/architecture.md` and locate the acquire/ file-tree block (around lines 44–63)**

  The current last file entry in the acquire/ tree ends with:

  ```
  │   │   └── migrations/         # SQL migration scripts for acquire.db
  ```

  Add a new line for `airing.py` immediately **before** the `migrations/` line:

  ```
  │   │   ├── airing.py          # RP9 — stateless set-poll: poll_aired(series, registry, *, today) → list[AiredEpisode]; capability-only (no store/ownership/cadence); unblocks Follow D2
  │   │   └── migrations/         # SQL migration scripts for acquire.db
  ```

- [ ] **Step 2: Locate the ownership boundary paragraph (around line 426–431) and add the RP9 boundary note**

  Current text ending the acquire/ notes block:

  ```
  **Ownership boundary (RP6):** `acquire/` reads ownership via
  `ctx.acquire.ownership` (a `core.ownership.OwnershipChecker`). It NEVER imports
  `personalscraper.indexer`. The adapter (`IndexerOwnershipChecker`) lives in
  `indexer/` and is wired at the composition root — same shape as the deletion
  authority (`core.delete_permit`).
  ```

  Append directly after (new paragraph before `## Provider Registry`):

  ```
  **Airing capability (RP9):** `acquire/airing.py` exposes `poll_aired(series, registry, *, today)` — a **stateless** free function (no `AcquireContext` field) that returns `list[AiredEpisode]` (see `acquire/domain.py`). It performs **zero** `store.wanted.*` writes, never calls `ownership.owns()`, and never reads `cadence_json` — surfacing aired episodes is RP9's sole responsibility; applying policy (wanted enqueue, ownership skip, cadence backoff) is Follow D2's job. Unblocks Follow D2 (calendar-first detection → wanted enqueue).
  ```

- [ ] **Step 3: Verify the edit did not break any existing markdown anchors**

  ```bash
  python -m ruff check docs/reference/architecture.md 2>/dev/null || true
  grep -c "airing" docs/reference/architecture.md
  ```

  Expected: `grep` count >= 2 (tree entry + boundary paragraph).

- [ ] **Step 4: Commit the architecture.md edit**

  ```bash
  git add docs/reference/architecture.md
  git commit -m "docs(airing): add airing.py to acquire/ module tree + RP9↔D2 boundary note"
  ```

---

## Sub-phase 4.2 — Create `docs/features/airing/ACCEPTANCE.md` (CREATE)

**Files:**

- Create: `docs/features/airing/ACCEPTANCE.md`

### Task 2: Write the ACCEPTANCE file (SH-16: every criterion is an executable command)

- [ ] **Step 5: Create `docs/features/airing/ACCEPTANCE.md`**

  ````markdown
  # ACCEPTANCE — airing (RP9)

  Every criterion below is an **executable shell command** with a documented
  expected output (SH-16 rule). Run from the repo root with the `personalscraper`
  package installed (`pip install -e ".[dev]"`).

  Re-exercise ALL criteria before squash merge.

  ---

  ## ACC-01 — AiredEpisode VO is importable and frozen

  **Command:**

  ```bash
  python -c "
  from personalscraper.acquire.domain import AiredEpisode
  from datetime import date
  from personalscraper.core.identity import MediaRef
  ep = AiredEpisode(media_ref=MediaRef(tvdb_id=81189), season=1, episode=1, air_date=date(2024,1,1))
  try:
      object.__setattr__(ep, 'season', 2)
      print('FAIL: frozen dataclass allows mutation')
  except (AttributeError, TypeError):
      print('OK: AiredEpisode is frozen')
  "
  ```
  ````

  **Expected:** `OK: AiredEpisode is frozen`

  ***

  ## ACC-02 — Predicate tests (past / future / today / empty / malformed)

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py -v -k "parse_date or is_aired" --tb=short
  ```

  **Expected:** `8 passed` (3 `_parse_date` + 5 `_is_aired` tests), `0 failed`

  ***

  ## ACC-03 — Golden test (assert WHICH episodes are surfaced)

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_golden -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-04 — Set-poll aggregate (2 series, each AiredEpisode carries its media_ref)

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_set_poll_aggregate -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-05 — Fail-soft (one series raises → others still polled)

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_fail_soft_one_series_raises -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-06 — Empty chain (chain() returns [] → empty result, no crash)

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_empty_chain_no_crash -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-07 — Season selection (season 0 excluded, seasons 1+ polled)

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_season_selection_excludes_season_zero -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-08 — NEGATIVE: no store.wanted.\* call

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_makes_no_store_wanted_calls -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-09 — NEGATIVE: no ownership.owns() call

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_makes_no_ownership_calls -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-10 — NEGATIVE: cadence_json not read

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_poll_aired_does_not_read_cadence_json -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-11 — Layering guard (no store/indexer import in airing.py)

  **Command:**

  ```bash
  pytest tests/acquire/test_airing.py::test_airing_module_has_no_store_or_indexer_import -v --tb=short
  ```

  **Expected:** `1 passed`

  ***

  ## ACC-12 — No store/indexer import (rg cross-check)

  **Command:**

  ```bash
  rg "indexer|acquire\.store|acquire\._ports" --type py personalscraper/acquire/airing.py
  ```

  **Expected:** no output (exit code 1 = no match = correct)

  ***

  ## ACC-13 — Full test suite green

  **Command:**

  ```bash
  make check
  ```

  **Expected:** `make check` exits 0 — `make lint` (ruff + mypy) + `make test` (all tests pass, 0 failed) + module-size guard green.

  ***

  ## ACC-14 — poll_aired signature matches DESIGN §3

  **Command:**

  ```bash
  python -c "
  import inspect
  from personalscraper.acquire.airing import poll_aired
  sig = inspect.signature(poll_aired)
  params = list(sig.parameters.keys())
  assert params == ['series', 'registry', 'today'], f'Wrong params: {params}'
  assert sig.parameters['today'].kind.name == 'KEYWORD_ONLY', 'today must be keyword-only'
  print('OK:', params)
  "
  ```

  **Expected:** `OK: ['series', 'registry', 'today']`

  ***

  ## ACC-15 — AcquireContext unchanged (no airing field)

  **Command:**

  ```bash
  python -c "
  from personalscraper.acquire.context import AcquireContext
  import dataclasses
  fields = [f.name for f in dataclasses.fields(AcquireContext)]
  assert 'airing' not in fields, f'Unexpected field: {fields}'
  print('OK — AcquireContext has no airing field')
  "
  ```

  **Expected:** `OK — AcquireContext has no airing field`

  ```

  ```

- [ ] **Step 6: Commit ACCEPTANCE.md**

  ```bash
  git add docs/features/airing/ACCEPTANCE.md
  git commit -m "docs(airing): ACCEPTANCE criteria (ACC-01..ACC-15, all executable)"
  ```

---

## Sub-phase 4.3 — Final gate

### Task 3: Run the full gate checklist

- [ ] **Step 7: Run `make check` (lint + test + module-size)**

  ```bash
  make check
  ```

  Expected: exits 0. If `make test` shows any ERROR (collection crash), fix imports before proceeding. If ruff flags `I001` (import order), run `ruff check --fix` and re-commit.

- [ ] **Step 8: Run design-gaps scripts (CI-only, but run locally here)**

  ```bash
  python3 scripts/audit_design_coverage.py --strict
  ```

  Expected: exits 0. If a new `Design:` section in ACCEPTANCE.md lacks a paired `Contract:` test, add it.

  ```bash
  python3 scripts/update_feature_map.py --check
  ```

  Expected: exits 0. If the feature map is stale (pre-commit hook may have regenerated it), stage and commit the updated JSON:

  ```bash
  git add tests/feature_map/
  git commit -m "chore(airing): update feature map after phase 4"
  ```

- [ ] **Step 9: Residual import check — confirm no old symbol references**

  ```bash
  rg "from personalscraper.acquire.airing" --type py personalscraper/ tests/
  ```

  Expected: only `tests/acquire/test_airing.py` and any `__init__.py` that re-exports. No stale import paths.

- [ ] **Step 10: Smoke test the package**

  ```bash
  python -c "import personalscraper; from personalscraper.acquire.airing import poll_aired; print('smoke OK')"
  ```

  Expected: `smoke OK`

- [ ] **Step 11: Phase gate commit**

  ```bash
  git commit --allow-empty -m "chore(airing): phase 4 gate — docs + ACCEPTANCE + make check green"
  ```

  (Use `--allow-empty` only if there are no staged changes at this point; otherwise stage and commit any remaining files first.)
