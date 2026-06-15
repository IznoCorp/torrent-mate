# Phase 4 — Docs + ACCEPTANCE + gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `docs/reference/architecture.md` (indexer query layer section + ownership port boundary), create `docs/features/ownership/ACCEPTANCE.md` with executable criteria, run the full gate (`make check` + design-gaps local check), and commit the phase gate.

**Architecture:** Documentation-only + gate pass. No new source files. The ACCEPTANCE criteria follow the SH-16 convention: every `ACC-NN` is an executable shell command with documented expected output. The phase gate commit is a `chore(ownership): phase 4 gate` milestone commit — only after `make check` is green.

**Tech Stack:** Markdown, bash, `make check`.

---

## Gate — what this phase requires

Phases 1–3 delivered:

- `personalscraper/core/ownership.py` (`OwnershipChecker`, `NullOwnershipChecker`)
- `personalscraper/indexer/ownership.py` (`is_owned`, `IndexerOwnershipChecker`)
- `personalscraper/acquire/context.py` (`ownership` field on `AcquireContext`)
- `personalscraper/acquire/_factory.py` (ownership wired at composition root)
- `tests/core/test_ownership.py`
- `tests/indexer/test_ownership_predicate.py`
- `tests/indexer/test_ownership_adapter.py`
- `tests/integration/test_ownership_wiring.py`

Verify all tests pass before starting docs:

```bash
pytest tests/core/test_ownership.py tests/indexer/test_ownership_predicate.py \
       tests/indexer/test_ownership_adapter.py tests/integration/test_ownership_wiring.py \
       -v --tb=short -q 2>&1 | tail -5
```

Expected: all pass, 0 failures.

---

## File map

| Action     | Path                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------ |
| **Modify** | `docs/reference/architecture.md` — add ownership port boundary + indexer query-layer entry |
| **Create** | `docs/features/ownership/ACCEPTANCE.md` — executable acceptance criteria                   |

---

## Task 4.1 — Update `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md`

- [ ] **Step 1: Read the architecture doc to find the right insertion points**

```bash
grep -n "indexer\|query layer\|delete_permit\|ownership\|acquire.*port\|port.*acquire" \
     docs/reference/architecture.md | head -30
```

Look for:

- The section describing the indexer query layer (where `query.py` is documented).
- The section describing the `core/` port pattern (where `delete_permit` is documented).

- [ ] **Step 2: Add the ownership port to the core/ port section**

Find the paragraph or bullet describing `core/delete_permit.py` and add a sibling entry immediately after it:

```markdown
- **`core/ownership.py`** — `OwnershipChecker` Protocol (RP6): `@runtime_checkable`
  port answering "does the library already contain this work?".
  `NullOwnershipChecker` (fail-open: always `False`) is the default when no
  library is wired. `acquire/` imports only this port — never `indexer/`.
  The concrete adapter (`indexer/ownership.py::IndexerOwnershipChecker`) is
  injected at the composition root.
```

- [ ] **Step 3: Add `is_owned` to the indexer query-layer section**

Find the paragraph or bullet describing `indexer/query.py` (the flex-attr query parser) and add a sibling entry:

```markdown
- **`indexer/ownership.py`** — Ownership predicate (RP6): `is_owned(conn, *, kind,
tvdb_id, tmdb_id, imdb_id, season, episode) -> bool`. SELECT-only. Matches
  `media_item` on tvdb_id → tmdb_id → imdb_id (priority order), follows the
  release chain to `media_file WHERE deleted_at IS NULL` (live-file liveness
  filter). Also contains `IndexerOwnershipChecker` — the port impl injected
  by the composition root into `AcquireContext.ownership`.
```

- [ ] **Step 4: Add a boundary rule note**

In the boundary rules section (or near the `acquire/` layering description), add:

```markdown
**Ownership boundary (RP6):** `acquire/` reads ownership via `ctx.acquire.ownership`
(a `core.ownership.OwnershipChecker`). It NEVER imports `personalscraper.indexer`.
The adapter (`IndexerOwnershipChecker`) lives in `indexer/` and is wired at the
composition root — same shape as the deletion authority (`core.delete_permit`).
```

- [ ] **Step 5: Commit the architecture doc update**

```bash
git add -f docs/reference/architecture.md
git commit -m "docs(ownership): architecture.md — ownership port boundary + indexer query layer"
```

Note: `git add -f` is required because `docs/` is in the global `.gitignore`.

---

## Task 4.2 — Write `docs/features/ownership/ACCEPTANCE.md`

**Files:**

- Create: `docs/features/ownership/ACCEPTANCE.md`

- [ ] **Step 6: Write the ACCEPTANCE file**

````markdown
# ACCEPTANCE — ownership (RP6)

All criteria are executable shell commands with documented expected output.
Re-exercise every ACC-NN criterion before squash merge (SH-16 convention).

## ACC-01 — Smoke import

```bash
python -c "import personalscraper"
```
````

Expected: exit 0 (no ImportError).

## ACC-02 — Core port importable

```bash
python -c "
from personalscraper.core.ownership import OwnershipChecker, NullOwnershipChecker
from personalscraper.core.identity import MediaRef
checker = NullOwnershipChecker()
assert checker.owns(MediaRef(tvdb_id=1), kind='movie') is False
print('ACC-02 OK')
"
```

Expected: `ACC-02 OK`

## ACC-03 — NullOwnershipChecker satisfies Protocol

```bash
python -c "
from personalscraper.core.ownership import OwnershipChecker, NullOwnershipChecker
assert isinstance(NullOwnershipChecker(), OwnershipChecker)
print('ACC-03 OK')
"
```

Expected: `ACC-03 OK`

## ACC-04 — Predicate: owned movie returns True

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestIsOwnedMovie::test_owned_movie_tvdb_match_returns_true -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-05 — Predicate: soft-deleted movie returns False

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestIsOwnedMovie::test_soft_deleted_movie_returns_false -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-06 — Predicate: provider-id fallback (tmdb) returns True

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestIsOwnedMovie::test_provider_id_fallback_tmdb -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-07 — Mutation proof: deleted_at IS NULL filter is load-bearing

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestSoftDeleteFilterLoadBearing -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-08 — Adapter: fail-soft on broken connection returns False (no raise)

```bash
python -m pytest tests/indexer/test_ownership_adapter.py::test_fail_soft_broken_connection_returns_false -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-09 — Adapter: fail-soft on any exception returns False (no raise)

```bash
python -m pytest tests/indexer/test_ownership_adapter.py::test_fail_soft_does_not_raise_on_any_exception -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-10 — Full ownership test suite

```bash
python -m pytest tests/core/test_ownership.py tests/indexer/test_ownership_predicate.py tests/indexer/test_ownership_adapter.py tests/integration/test_ownership_wiring.py -v --tb=short 2>&1 | tail -5
```

Expected: all pass, 0 failures, 0 errors.

## ACC-11 — Layering: acquire/ does NOT import indexer/

```bash
python -m pytest tests/architecture/test_layering.py::test_acquire_does_not_import_triage -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-12 — Layering: core/ does NOT import indexer/

```bash
python -m pytest tests/architecture/test_layering.py::test_core_does_not_import_upward -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-13 — Composition root: NullOwnershipChecker when no library.db

```bash
python -m pytest tests/integration/test_ownership_wiring.py::test_ownership_null_when_no_library_db -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-14 — Composition root: IndexerOwnershipChecker wired when library.db exists

```bash
python -m pytest tests/integration/test_ownership_wiring.py::test_ownership_wired_with_library_db -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-15 — make check green

```bash
make check 2>&1 | tail -5
```

Expected: exit 0, summary line shows 0 failed / 0 errors.

````

- [ ] **Step 7: Commit the ACCEPTANCE file**

```bash
git add -f docs/features/ownership/ACCEPTANCE.md
git commit -m "docs(ownership): ACCEPTANCE.md — executable criteria (SH-16)"
````

Note: `git add -f` is required because `docs/` is in the global `.gitignore`.

---

## Task 4.3 — Phase gate checklist

Run all checks in order. Fix any failure before proceeding to the gate commit.

- [ ] **Step 8: make lint — zero errors**

```bash
make lint 2>&1 | tail -10
```

Expected: exit 0. Fix any ruff or mypy errors before continuing.

Common issues to watch for:

- `check_logging.py` will fail if `personalscraper/indexer/ownership.py` uses `structlog.get_logger` directly. It MUST use `personalscraper.logger.get_logger`. Verify:
  ```bash
  grep "structlog.get_logger" personalscraper/indexer/ownership.py
  ```
  Expected: no output. If found, replace with `from personalscraper.logger import get_logger`.
- Unused imports in `_factory.py` — check the `OwnershipChecker` type hint is under `TYPE_CHECKING`.

- [ ] **Step 9: make test — all tests pass**

```bash
make test 2>&1 | tail -10
```

Expected: summary line shows 0 failed, 0 errors. (Count may be higher than `make check` — see project memory note on `make test` vs `make check` count gap.)

- [ ] **Step 10: make check — full gate**

```bash
make check 2>&1 | tail -10
```

Expected: exit 0.

- [ ] **Step 11: Residual import grep — no old paths leaked**

```bash
rg --type py "from personalscraper.indexer.ownership import" personalscraper/acquire/ personalscraper/core/
```

Expected: zero matches. `acquire/` and `core/` must never import `indexer/ownership` directly.

```bash
rg --type py "from personalscraper.acquire" personalscraper/indexer/ownership.py
```

Expected: zero matches. `indexer/ownership.py` must never import `acquire/`.

- [ ] **Step 12: design-gaps local check**

```bash
python scripts/update_feature_map.py --check 2>&1 | tail -5
```

Expected: exit 0 (no drift). If it fails, the feature map needs regenerating — run without `--check` and re-stage.

- [ ] **Step 13: Smoke import**

```bash
python -c "import personalscraper; print('OK')"
```

Expected: `OK`.

- [ ] **Step 14: Phase gate commit**

```bash
git add personalscraper/ tests/ docs/
git commit -m "chore(ownership): phase 4 gate — docs + ACCEPTANCE + make check green"
```
