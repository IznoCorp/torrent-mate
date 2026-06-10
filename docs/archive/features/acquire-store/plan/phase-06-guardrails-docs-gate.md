# Phase 06 — Guardrails + docs + gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the architecture layering guard to enforce that `maintenance/` and `dispatch/`
never import `acquire/` directly, add lock-order documentation, update reference docs, write the
executable `ACCEPTANCE.md`, re-scope ROADMAP RP3/O2 entries, and run the final `make check` gate.

**Architecture:** All new layering assertions are non-vacuous (positive controls prove the guard
fires on a synthetic bad import). The lock-order invariant is documented in both a new doc section
and in `acquire/store.py` docstring. ACCEPTANCE criteria are executable shell commands per the
project's SH-16 convention.

**Tech stack:** `tests/architecture/test_layering.py` AST-based guard, `docs/reference/`,
`docs/features/acquire-store/ACCEPTANCE.md`, `ROADMAP.md`.

---

## Gate (from Phase 5)

- `dispatch/run.py` and `maintenance/disk_cleaner.py` accept `permit: DeletePermit`.
- All phase 5 tests pass (record_dispatch, crash_window, dispatch, maintenance).
- `make check` green.

---

## File map

| Action | Path                                                                           |
| ------ | ------------------------------------------------------------------------------ |
| Modify | `tests/architecture/test_layering.py` (new deleter⇏acquire assertions)         |
| Create | `docs/features/acquire-store/lock-order.md`                                    |
| Modify | `docs/reference/architecture.md` (acquire/ module map + lock-order summary)    |
| Modify | `docs/reference/config-overlay-layout.md` (verify 16-overlay count is present) |
| Create | `docs/features/acquire-store/ACCEPTANCE.md`                                    |
| Modify | `ROADMAP.md` (RP3 absorbed O2 first-wiring; O2 re-scoped to policy refinement) |

---

### Task 1 — Extend `test_layering.py`: maintenance/dispatch ⇏ acquire

**Files:**

- Modify: `tests/architecture/test_layering.py`

- [ ] **Step 1: Read the existing acquire guard section**

```bash
grep -n "acquire.*layering\|_ACQUIRE_FORBIDDEN\|test_acquire\|_DELETER" \
  /Users/izno/dev/PersonnalScaper/tests/architecture/test_layering.py | head -30
```

Note the existing `test_acquire_does_not_import_triage` and its positive-control pattern —
the new assertions must mirror that pattern.

- [ ] **Step 2: Add deleter⇏acquire guard and non-vacuous controls**

At the end of `tests/architecture/test_layering.py`, append:

```python
# ---------------------------------------------------------------------------
# Deleter ⇏ acquire/ guard — RP3 (D3 extended)
#
# maintenance/ and dispatch/ must import ONLY core.delete_permit port types,
# never the concrete acquire/ implementation.  Injected at the composition root.
# ---------------------------------------------------------------------------

_DELETER_FORBIDDEN_ACQUIRE = ("personalscraper.acquire",)

_DELETER_MODULES = [
    _PACKAGE_ROOT / "maintenance",
    _PACKAGE_ROOT / "dispatch",
]

_DELETER_SYNTHETIC_REL = "personalscraper/dispatch/_synthetic_acquire_probe.py"


def _scan_for_acquire_import(module_dirs: list[Path]) -> list[str]:
    """Return violation strings for any acquire/ import found in the given dirs."""
    violations: list[str] = []
    for module_dir in module_dirs:
        if not module_dir.exists():
            continue
        for py_file in sorted(module_dir.rglob("*.py")):
            rel = str(py_file.relative_to(_REPO_ROOT))
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if any(node.module.startswith(p) for p in _DELETER_FORBIDDEN_ACQUIRE):
                        if not _is_type_checking_block(node, tree):
                            violations.append(
                                f"{rel}: imports {node.module!r} (deleters must only use core.delete_permit)"
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(alias.name.startswith(p) for p in _DELETER_FORBIDDEN_ACQUIRE):
                            if not _is_type_checking_block(node, tree):
                                violations.append(
                                    f"{rel}: imports {alias.name!r} (deleters must only use core.delete_permit)"
                                )
    return violations


def test_deleters_do_not_import_acquire() -> None:
    """No module under dispatch/ or maintenance/ imports acquire/ at runtime."""
    violations = _scan_for_acquire_import(_DELETER_MODULES)
    assert not violations, (
        "dispatch/ or maintenance/ has forbidden acquire/ imports:\n"
        + "\n".join(violations)
    )


def test_deleter_acquire_import_is_flagged() -> None:
    """POSITIVE control: an acquire/ import attributed to dispatch/ IS a violation."""
    source = "from personalscraper.acquire.store import ConcreteAcquireStore\n"
    # Synthesize as if it came from dispatch/
    synthetic_dir = [_REPO_ROOT / "personalscraper" / "dispatch"]
    # Inject synthetic content into violation scanner via a temp attribute
    violations = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(node.module.startswith(p) for p in _DELETER_FORBIDDEN_ACQUIRE):
                    violations.append(f"synthetic: imports {node.module!r}")
    except SyntaxError:
        pass
    assert violations, "Deleter acquire guard failed to flag a synthetic acquire import (vacuous guard!)"
    assert "personalscraper.acquire" in violations[0]


def test_deleter_core_import_is_not_flagged() -> None:
    """POSITIVE control: importing core.delete_permit from dispatch/ is allowed."""
    source = "from personalscraper.core.delete_permit import AllowAllPermit\n"
    violations = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(node.module.startswith(p) for p in _DELETER_FORBIDDEN_ACQUIRE):
                    violations.append(f"synthetic: imports {node.module!r}")
    except SyntaxError:
        pass
    assert not violations, "core.delete_permit import was wrongly flagged as an acquire/ violation"
```

> **CORRECTIVE NOTE (sub-phase 6.1):** The positive control draft above is
> **vacuous** — it reimplements the AST walk inline (`ast.parse(source); for node
in ast.walk(tree): ...`) instead of calling the real scanner. An inline
> reimplementation tests a copy, not the guard. The committed implementation
> uses the real `_scan_deleters_for_acquire_import` → `_collect_violations_from_source`
> path for all three tests (real guard + positive/negative controls), matching
> the `_ACQUIRE_SYNTHETIC_REL` pattern from the existing acquire⇏triage guard.
> Positive control: creates a real tmp-file probe in `dispatch/`, runs the real
> scanner over dispatch/, asserts the import IS flagged, cleans up in `finally`.
> Mutation check: injecting `from personalscraper.acquire.store import
ConcreteAcquireStore` into `dispatch/_movie.py` → `test_deleters_do_not_import_acquire`
> FAILS; reverting → PASSES.

- [ ] **Step 3: Run the new layering tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/architecture/test_layering.py -v -k "deleter" 2>&1 | tail -15
```

Expected: `3 passed` (the two positive controls + the real guard).

- [ ] **Step 4: Run all architecture tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/architecture/ -x -q 2>&1 | tail -10
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/architecture/test_layering.py
git commit -m "test(acquire-store): extend test_layering — maintenance/dispatch ⇏ acquire (non-vacuous)"
```

---

### Task 2 — Lock-order documentation

**Files:**

- Create: `docs/features/acquire-store/lock-order.md`

- [ ] **Step 1: Create the lock-order doc**

```markdown
# acquire-store: Total Lock Order

## Invariant
```

pipeline.lock (outer)
└─ indexer_lock
└─ acquire.db.lock (leaf)

```

No `acquire.db` writer may acquire `pipeline.lock` or `indexer_lock` while
holding `acquire.db.lock`.  Opposite-order pairs are structurally unreachable,
making the system provably deadlock-free.

## Rules

1. **`acquire.db.lock` is a leaf lock** — held only for the duration of a
   single DB write (`INSERT` / `UPDATE` + `COMMIT`).  Never held across:
   - Any filesystem operation (`shutil.move`, `os.unlink`, `rsync`).
   - Any HTTP call to a torrent client or tracker.

2. **`record_dispatch` is lock-free** — uses a raw `sqlite3.connect` +
   `busy_timeout=5000` without acquiring `acquire.db.lock`, to avoid
   deadlock in the dispatch critical path (dispatch holds no acquire lock).

3. **`indexer_lock` is always acquired before `acquire.db.lock`** if both are
   needed in the same call chain.  In practice no RP3 code path holds both
   simultaneously.

## Implementation reference

- Lock acquisition: `personalscraper/core/sqlite/_lock.py::db_lock`
- Acquire store writer: `personalscraper/acquire/store.py` (each sub-store method)
- Lock-free writer: `personalscraper/acquire/delete_authority.py::record_dispatch`
- Pipeline lock: `personalscraper/lock.py::acquire_lock` (existing, unchanged)
- Indexer lock: `personalscraper/indexer/db.py::indexer_lock` → `core/sqlite/_lock.py::db_lock`
```

- [ ] **Step 2: Commit**

```bash
git add docs/features/acquire-store/lock-order.md
git commit -m "docs(acquire-store): lock-order.md — total lock order invariant + rules"
```

---

### Task 3 — Update `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md`

- [ ] **Step 1: Locate the module map section**

```bash
grep -n "acquire\|core/sqlite\|delete_permit\|Module map\|module map" \
  /Users/izno/dev/PersonnalScaper/docs/reference/architecture.md | head -20
```

- [ ] **Step 2: Add `core/sqlite/` and `core/delete_permit` to the module map**

In the `core/` section of the module map, add:

```
core/
  sqlite/         Neutral SQLite machinery (event-free): open_db, db_lock,
                  apply_migrations, _fs_probe, errors.Sqlite*Error
  identity.py     MediaRef — neutral provider-ID value object (tvdb primary)
  delete_permit.py DeletePermit + SeedObligationRecorder Protocols + AllowAllPermit
```

- [ ] **Step 3: Add `acquire/` module map entries**

In the `acquire/` section (or create it), add:

```
acquire/
  domain.py       Frozen VOs: FollowedSeries, WantedItem, SeedObligation, RatioState
  migrations/     SQL migration scripts for acquire.db
  _ports.py       AcquireStore Protocol (extended in RP3)
  store.py        ConcreteAcquireStore — 4 sub-stores over acquire.db.lock (leaf)
  delete_authority.py  DeleteAuthority: DeletePermit + SeedObligationRecorder impl
  _factory.py     build_acquire_context (fills store= + delete_authority=)
```

- [ ] **Step 4: Add lock-order summary paragraph**

Add a brief note referencing `docs/features/acquire-store/lock-order.md`:

```markdown
### Lock order

Total lock order: `pipeline.lock` > `indexer_lock` > `acquire.db.lock` (leaf).
See `docs/features/acquire-store/lock-order.md` for the full invariant and rules.
```

- [ ] **Step 5: Commit**

```bash
git add docs/reference/architecture.md
git commit -m "docs(acquire-store): update architecture.md — core/sqlite, acquire/ module map, lock order"
```

---

### Task 4 — Create `ACCEPTANCE.md` with executable criteria

**Files:**

- Create: `docs/features/acquire-store/ACCEPTANCE.md`

- [ ] **Step 1: Create the acceptance file**

````markdown
# ACCEPTANCE — acquire-store (RP3)

All criteria are executable shell commands with documented expected output.
Re-exercise every ACC-NN criterion before squash merge (SH-16 convention).

## ACC-01 — Smoke import

```bash
python -c "import personalscraper"
```
````

Expected: exit 0 (no ImportError).

## ACC-02 — core/sqlite importable and event-free

```bash
python -c "
from personalscraper.core.sqlite import open_db, db_lock, apply_migrations, probe_mount
from personalscraper.core.sqlite.errors import SqliteLockError, SqliteCorruptError
import inspect, personalscraper.core.sqlite._open as m
sig = inspect.signature(m.open_db)
assert 'event_bus' not in sig.parameters, 'core open_db must be event-free'
print('ACC-02 OK')
"
```

Expected: `ACC-02 OK`

## ACC-03 — IndexerXxxError isinstance core markers

```bash
python -m pytest tests/indexer/test_core_sqlite_isinstance.py -v --tb=short 2>&1 | tail -5
```

Expected: `6 passed`

## ACC-04 — acquire.json5 config overlay

```bash
cd /path/to/repo && personalscraper init-config 2>/dev/null; ls config/acquire.json5
```

Expected: file present (exit 0).

## ACC-05 — AcquireConfig derives db_path

```bash
python -c "
from personalscraper.conf.models.acquire import AcquireConfig
cfg = AcquireConfig(db_path=None)
assert cfg.db_path is None
print('ACC-05 OK: field accepts None for deferred resolve')
"
```

Expected: `ACC-05 OK: field accepts None for deferred resolve`

## ACC-06 — Migration contract on fresh acquire.db

```bash
python -m pytest tests/acquire/test_store.py::test_migration_contract -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-07 — All four tables present

```bash
python -m pytest tests/acquire/test_store.py::test_all_four_tables_exist -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-08 — Fail-open: store-absent deletion proceeds

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_store_absent_returns_allow -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-09 — Fail-open: store lookup error → ALLOW

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_store_lookup_exception_returns_allow -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-10 — VETO on active unmet obligation

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_veto_on_active_unmet_obligation -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-11 — Stale obligation inert (path-exists guard)

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_stale_obligation_inert_when_path_missing -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-12 — record_dispatch HIT writes obligation

```bash
python -m pytest tests/acquire/test_record_dispatch.py::test_record_dispatch_hit_writes_obligation -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-13 — record_dispatch fail-soft on client error

```bash
python -m pytest tests/acquire/test_record_dispatch.py::test_record_dispatch_fail_soft_on_client_error -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-14 — Crash-window: stale obligation + re-run completes

```bash
python -m pytest tests/acquire/test_crash_window.py -v --tb=short 2>&1 | tail -5
```

Expected: `3 passed`

## ACC-15 — Layering: dispatch/maintenance ⇏ acquire

```bash
python -m pytest tests/architecture/test_layering.py -v -k "deleter" --tb=short 2>&1 | tail -5
```

Expected: `3 passed`

## ACC-16 — make check green

```bash
make check 2>&1 | tail -5
```

Expected: exit 0, summary line shows `0 failed` / `0 error`.

````

- [ ] **Step 2: Commit**

```bash
git add docs/features/acquire-store/ACCEPTANCE.md
git commit -m "docs(acquire-store): ACCEPTANCE.md — 16 executable shell criteria (SH-16)"
````

> **Plan-drift (2026-06-10, sub-phase 6.3)**: five ACC commands corrected against live code:
>
> - ACC-06: `test_migration_contract` did not exist → replaced with `TestAcquireMigrations001` (6 tests).
> - ACC-09: `test_store_lookup_exception_returns_allow` renamed → `test_lookup_exception_fail_open_with_mutation_proof`.
> - ACC-10: `test_veto_on_active_unmet_obligation` renamed → `test_seedtime_not_met_veto`.
> - ACC-11: `test_stale_obligation_inert_when_path_missing` renamed → `test_stale_obligation_mutation_proof`.
> - ACC-14: count was 3 in draft → actual 5 tests (two scenarios have sub-tests).
> - ACC-16: expected summary recorded as `6425 passed, 3 skipped, 2 xfailed` (live count).

---

### Task 5 — Update ROADMAP.md (RP3/O2 re-scope) + final make check gate

**Files:**

- Modify: `ROADMAP.md`

- [ ] **Step 1: Locate RP3 and O2 entries in ROADMAP.md**

```bash
grep -n "RP3\|O2\|acquire.db\|deletion.authority\|seed.obligation" \
  /Users/izno/dev/PersonnalScaper/ROADMAP.md | head -20
```

- [ ] **Step 2: Update RP3 entry to record acquire-store delivery**

Find the RP3 entry and add/update a note:

```markdown
**RP3 — `acquire.db` store + single deletion authority** ✅ `acquire-store` (0.26.0)

- Delivered: `core/sqlite/` extraction, `MediaRef`, `AcquireConfig`, 4-table schema,
  `ConcreteAcquireStore`, `DeletePermit` / `SeedObligationRecorder` ports,
  `DeleteAuthority` (deletion-time resolver + `record_dispatch`), per-site wiring.
- Absorbed: O2's first deletion-authority wiring (persisted obligation table +
  permit consulted by deleters). See O2 re-scope below.
```

- [ ] **Step 3: Update O2 entry to reflect re-scope**

Find the O2 entry and add:

```markdown
**O2 — Relocate-not-delete on unmet seed obligation** (re-scoped)

- First wiring (persisted obligation table + permit) absorbed into RP3 (`acquire-store`).
- O2 now owns: policy refinement — relocate-not-delete logic (requires O3 disk-budget
  arbiter, Vague 5). No implementation in RP3.
```

- [ ] **Step 4: Run final make check (the gate)**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -30
```

Expected: lint + test + module-size + typed-api all green. Exit 0.

- [ ] **Step 5: Residual-import grep (mandatory gate check)**

```bash
# Verify no module in dispatch/ or maintenance/ imports acquire/ at runtime:
rg "from personalscraper.acquire\|import personalscraper.acquire" --type py \
  /Users/izno/dev/PersonnalScaper/personalscraper/dispatch/ \
  /Users/izno/dev/PersonnalScaper/personalscraper/maintenance/ 2>/dev/null
```

Expected: zero matches (or only `TYPE_CHECKING`-guarded lines).

- [ ] **Step 6: Smoke test**

```bash
python -c "import personalscraper; print('smoke OK')"
```

Expected: `smoke OK`

- [ ] **Step 7: Final commit**

```bash
git add ROADMAP.md
git commit -m "chore(acquire-store): phase 6 gate — guardrails + docs + ACCEPTANCE + ROADMAP re-scope"
```
