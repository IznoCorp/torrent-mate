# Phase 4 — Docs + ACCEPTANCE + Phase Gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `docs/reference/architecture.md` with the new `acquire/` symbols and `follow` CLI, write the `ACCEPTANCE.md` for this feature (executable criteria only), run the full gate checklist (`make check` + design-gaps), and cut the phase gate commit.

**Architecture:** Documentation + gate only — no new source code. Every ACCEPTANCE criterion must be an executable shell command with a documented expected output (project rule, SH-16).

**Tech Stack:** bash, pytest, make.

## Gate (start of phase)

Phases 1–3 delivered:

- `FollowedSeries.id`, `find_by_ref`, `list_active`, `list_all`, `set_active` in `_FollowSubStore`
- `FollowSubStore` Protocol updated in `_ports.py`
- `acquire/title_resolver.py` with `resolve_series_title` (fail-soft)
- `commands/follow.py` with `follow add/list/remove`, wired in `cli.py`
- All e2e tests passing

Verify before starting:

```bash
python -m pytest tests/acquire/ tests/commands/test_follow.py -v
# Expected: all pass, 0 errors

python -c "import personalscraper.commands.follow; print('ok')"
# Expected: ok

make lint
# Expected: 0 errors
```

---

## Task 8: Update `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md`

### Sub-phase 4.1 — architecture doc update

- [ ] **Step 8.1: Locate the `acquire/` section in architecture.md**

  ```bash
  grep -n "acquire/" docs/reference/architecture.md | head -20
  ```

  Find the bullet list describing `acquire/` sub-modules (~line 44 region based on prior grep). Identify:
  1. Where `_ports.py` is described (add new Protocol methods).
  2. Where `store.py` is described (add new `_FollowSubStore` methods).
  3. Where commands are listed (add `commands/follow.py`).

- [ ] **Step 8.2: Add `title_resolver.py` to the `acquire/` module listing**

  In the `acquire/` sub-directory listing, add after the existing `_ports.py` line:

  ```
  │   │   ├── title_resolver.py   # Fail-soft series title resolver (Follow D1) — calls provider_registry.chain(TvDetailsProvider), falls back to "tvdb:<id>"
  ```

- [ ] **Step 8.3: Note the new `_FollowSubStore` methods in the store description**

  Update the `store.py` line or its surrounding note to mention:
  `find_by_ref`, `list_active`, `list_all`, `set_active` (Follow D1 CRUD completion).

- [ ] **Step 8.4: Note the new `FollowSubStore` Protocol methods in the `_ports.py` description**

  Update the `_ports.py` line to mention the extended `FollowSubStore` Protocol
  (add/get/find_by_ref/list_active/list_all/set_active).

- [ ] **Step 8.5: Add `commands/follow.py` to the commands listing**

  In the `commands/` listing, add:

  ```
  │   ├── follow.py    # ``personalscraper follow add/list/remove`` — followed-series management (Follow D1)
  ```

- [ ] **Step 8.6: Commit the architecture update**

  ```bash
  git add docs/reference/architecture.md
  git commit -m "docs(follow-list): update architecture.md with follow CRUD + follow CLI"
  ```

---

## Task 9: Write `ACCEPTANCE.md`

**Files:**

- Create: `docs/features/follow-list/ACCEPTANCE.md`

### Sub-phase 4.2 — executable ACCEPTANCE criteria

- [ ] **Step 9.1: Create `docs/features/follow-list/ACCEPTANCE.md`**

  ````markdown
  # ACCEPTANCE — follow-list (Follow D1, v0.29.0)

  Every criterion below is an executable shell command. Run from the repo root
  with `personalscraper` installed (`pip install -e ".[dev]"`) and a valid
  `config/` present. All pytest selectors use `-x` (stop on first failure).

  ---

  ## ACC-01 — follow add inserts a row and resolves title

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_add_inserts_one_row -x -v
  ```
  ````

  Expected output: `1 passed`.

  ## ACC-02 — idempotent double-add produces exactly 1 row

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_add_idempotent_double_add_one_row -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-03 — metadata resolution failure still follows (fallback title)

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_add_metadata_failure_still_follows -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-04 — follow remove soft-unfollows (row preserved, active=False)

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_remove_soft_unfollows -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-05 — add → remove → add reactivates existing row (no duplicate)

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_reactivate_after_remove_one_row -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-06 — follow list (no --all) hides inactive; --all shows it

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_list_hides_inactive_by_default -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-07 — SeriesFollowed emitted on add

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_add_emits_series_followed_event -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-08 — SeriesUnfollowed emitted on remove

  ```bash
  python -m pytest tests/commands/test_follow.py::test_follow_remove_emits_series_unfollowed_event -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-09 — store unit: find_by_ref id round-trip + dedup (LOAD-BEARING)

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_find_by_ref_round_trips_id -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-10 — store unit: list_active excludes inactive (LOAD-BEARING)

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_list_active_excludes_inactive -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-11 — store unit: set_active flips flag + reactivates (LOAD-BEARING)

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_set_active_flips_flag -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-12 — title resolver: all failure modes fall back, never raise (LOAD-BEARING)

  ```bash
  python -m pytest tests/acquire/test_title_resolver.py -x -v
  ```

  Expected output: `7 passed`.

  ## ACC-13 — FollowSubStore Protocol conformance

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_substore_satisfies_protocol -x -v
  ```

  Expected output: `1 passed`.

  ## ACC-14 — make check green

  ```bash
  make check
  ```

  Expected: exits 0, `0 errors` from ruff + mypy, all tests pass, module-size under 1000 LOC.

  ```

  ```

- [ ] **Step 9.2: Commit ACCEPTANCE.md**

  ```bash
  git add docs/features/follow-list/ACCEPTANCE.md
  git commit -m "docs(follow-list): add executable ACCEPTANCE.md (ACC-01 through ACC-14)"
  ```

---

## Task 10: Phase gate checklist

### Sub-phase 4.3 — full gate run

- [ ] **Step 10.1: Run `make lint` (ruff + mypy)**

  ```bash
  make lint
  ```

  Expected: exits 0, 0 ruff errors, 0 mypy errors.

  If mypy reports errors on `commands/follow.py` or `acquire/title_resolver.py`, fix them now. Common issues:
  - `Optional[int]` → use `int | None` (Python 3.10+ style already used in the codebase).
  - Missing `from __future__ import annotations` (already included in templates above).
  - `registry.chain(TvDetailsProvider)` type-abstract warning: the `# type: ignore[type-abstract]` comment is already present in the template.

- [ ] **Step 10.2: Run `make test` (full test suite)**

  ```bash
  make test
  ```

  Expected: summary line shows `N passed` with 0 failed and 0 errors. The exact count will be higher than before this feature (new tests added).

  If any test errors (collection crash): fix imports before proceeding. Do NOT count skipped/deselected tests as failures.

- [ ] **Step 10.3: Residual import grep — verify no stale imports**

  ```bash
  # No old import paths to check (new files only — nothing was deleted).
  # Confirm the new modules are importable:
  python -c "
  from personalscraper.acquire.title_resolver import resolve_series_title
  from personalscraper.commands.follow import follow_app
  from personalscraper.acquire._ports import FollowSubStore
  from personalscraper.acquire.domain import FollowedSeries
  print('id field present:', 'id' in FollowedSeries.__dataclass_fields__)
  print('find_by_ref in Protocol:', hasattr(FollowSubStore, 'find_by_ref'))
  print('all ok')
  "
  ```

  Expected output:

  ```
  id field present: True
  find_by_ref in Protocol: True
  all ok
  ```

- [ ] **Step 10.4: Run `make check` (lint + test + module-size + typed-api)**

  ```bash
  make check
  ```

  Expected: exits 0.

  If module-size warns on `store.py`: the new methods add ~60 LOC to a ~756 LOC file. The soft cap is 800 and hard ceiling is 1000 — this is safe. If the file exceeds 800 LOC the warning is advisory (not a block) until v0.10.0 per `docs/reference/promises.md`.

- [ ] **Step 10.5: Run design-gaps local check**

  ```bash
  python scripts/update_feature_map.py --check 2>&1 | tail -5
  python scripts/audit_design_coverage.py --strict 2>&1 | tail -10
  ```

  Expected: exits 0 (or any pre-existing gap count unchanged — this feature adds no new `test_design_*.py` file, so drift is zero).

- [ ] **Step 10.6: Re-exercise all ACCEPTANCE criteria**

  Run every ACC criterion from `ACCEPTANCE.md` in sequence:

  ```bash
  python -m pytest \
    tests/commands/test_follow.py::test_follow_add_inserts_one_row \
    tests/commands/test_follow.py::test_follow_add_idempotent_double_add_one_row \
    tests/commands/test_follow.py::test_follow_add_metadata_failure_still_follows \
    tests/commands/test_follow.py::test_follow_remove_soft_unfollows \
    tests/commands/test_follow.py::test_follow_reactivate_after_remove_one_row \
    tests/commands/test_follow.py::test_follow_list_hides_inactive_by_default \
    tests/commands/test_follow.py::test_follow_add_emits_series_followed_event \
    tests/commands/test_follow.py::test_follow_remove_emits_series_unfollowed_event \
    tests/acquire/test_store.py::test_follow_find_by_ref_round_trips_id \
    tests/acquire/test_store.py::test_follow_list_active_excludes_inactive \
    tests/acquire/test_store.py::test_follow_set_active_flips_flag \
    tests/acquire/test_title_resolver.py \
    tests/acquire/test_store.py::test_follow_substore_satisfies_protocol \
    -v
  ```

  Expected: `13 passed` (7 title resolver + 6 store + the 6 CLI tests named above).

  Note: `make check` (ACC-14) is already green from Step 10.4.

- [ ] **Step 10.7: Phase gate commit**

  ```bash
  git add -u
  git commit -m "chore(follow-list): phase 4 gate — docs + ACCEPTANCE + make check green"
  ```

---

## Phase 4 completion check

```bash
# All ACCEPTANCE criteria green
python -m pytest tests/commands/test_follow.py tests/acquire/test_title_resolver.py tests/acquire/test_store.py -v
# Expected: all pass, 0 errors.

# make check clean
make check
# Expected: exits 0.

# Architecture doc updated
grep -n "title_resolver\|follow add" docs/reference/architecture.md
# Expected: at least 2 matches.

# ACCEPTANCE.md present and has 14 criteria
grep -c "^## ACC-" docs/features/follow-list/ACCEPTANCE.md
# Expected: 14
```
