# Phase 05 — ACCEPTANCE.md + architecture.md update + make check gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `ACCEPTANCE.md` with ACC-1 through ACC-5 as executable shell commands, update `docs/reference/architecture.md` to include `acquire/` in the module map, and verify `make check` is fully green.

**Architecture:** Documentation and gate only — no source code changes.

**Tech Stack:** Bash, make, pytest

---

## Gate (Phase 04 → Phase 05)

Phase 04 must have produced:

- `tests/architecture/test_layering.py` extended with `test_acquire_does_not_import_triage` + 2 control tests
- All architecture tests passing

Verify:

```bash
pytest tests/architecture/test_layering.py -v   # all pass
make test                                        # all pass
```

---

## Sub-phase 5.1: Write `ACCEPTANCE.md`

**Files:**

- Create: `docs/features/acquire-lobe/ACCEPTANCE.md`

- [ ] **Step 1: Create ACCEPTANCE.md with executable criteria**

````markdown
# ACCEPTANCE — RP5c: acquire/ lobe + single injection handle

Each criterion is an executable shell command. Run from the repo root
(venv active, `pip install -e ".[dev]"` done).

## ACC-1 — Package importable

```bash
python -c "import personalscraper.acquire; from personalscraper.acquire.context import AcquireContext; print('ACC-1 OK')"
```
````

Expected output: `ACC-1 OK`

## ACC-2 — Single handle on AppContext; no stray `tracker_registry` field

```bash
python -c "
import dataclasses
from personalscraper.core.app_context import AppContext
f = {x.name for x in dataclasses.fields(AppContext)}
assert 'acquire' in f, f\"'acquire' missing — got {f}\"
assert 'tracker_registry' not in f, f\"'tracker_registry' still present — got {f}\"
print('ACC-2 OK')
"
```

Expected output: `ACC-2 OK`

## ACC-3 — Boot builds AcquireContext with tracker_registry present

```bash
python -c "
from unittest.mock import MagicMock, patch
from personalscraper.cli_helpers import _build_app_context

config = MagicMock()
config.thresholds.circuit_breaker_threshold = 5
config.thresholds.circuit_breaker_cooldown = 30.0
config.providers = {}
config.torrent.active = ''
settings = MagicMock()

with patch('personalscraper.acquire._factory.build_tracker_registry') as mock_btr:
    mock_btr.return_value = MagicMock()
    with patch('personalscraper.api.metadata.registry.ProviderRegistry'):
        ctx = _build_app_context(config, settings)

assert ctx.acquire is not None, 'ctx.acquire is None'
assert ctx.acquire.tracker_registry is not None, 'tracker_registry is None'
print('ACC-3 OK')
"
```

Expected output: `ACC-3 OK`

## ACC-4 — Layering guard active and non-vacuous

```bash
pytest tests/architecture/test_layering.py -q
```

Expected: all tests pass, including `test_acquire_does_not_import_triage`,
`test_acquire_triage_import_is_flagged`, and `test_acquire_downward_import_is_not_flagged`.

## ACC-5 — Full gate

```bash
make check
```

Expected: `NNNN passed`, 0 failed, 0 errors.

````

- [ ] **Step 2: Verify each criterion manually**

```bash
# ACC-1
python -c "import personalscraper.acquire; from personalscraper.acquire.context import AcquireContext; print('ACC-1 OK')"

# ACC-2
python -c "
import dataclasses
from personalscraper.core.app_context import AppContext
f = {x.name for x in dataclasses.fields(AppContext)}
assert 'acquire' in f and 'tracker_registry' not in f
print('ACC-2 OK')
"

# ACC-4
pytest tests/architecture/test_layering.py -q
````

Expected: all print `OK` or pass.

- [ ] **Step 3: Commit**

```bash
git add docs/features/acquire-lobe/ACCEPTANCE.md
git commit -m "docs(acquire-lobe): add ACCEPTANCE.md with ACC-1 through ACC-5"
```

---

## Sub-phase 5.2: Update `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md`

- [ ] **Step 1: Read the current module map section**

Open `docs/reference/architecture.md` and locate the section that lists top-level packages (look for `ingest`, `sort`, `dispatch`, `indexer`, etc. in the module map).

- [ ] **Step 2: Add `acquire/` entry**

In the module map table or list (wherever `ingest`, `sort`, `dispatch`, `indexer` appear), add a row for `acquire/`. Use the same format as surrounding entries. Example if it is a table:

```
| `acquire/`       | Acquisition lobe (RP5c). Owns `TrackerRegistry` (RP5a) and the `AcquireStore` slot (RP3). No behaviour — injection handle only. Import direction: downward only (`api/`, `core/`, `conf/`, `events/`); never triage packages. |
```

If it is a bullet list, add:

```
- **`acquire/`** — Acquisition lobe (RP5c). Peer of `ingest`, `sort`, `dispatch`. Owns `TrackerRegistry` and the `AcquireStore` seam slot. Import direction enforced by `tests/architecture/test_layering.py::test_acquire_does_not_import_triage`.
```

- [ ] **Step 3: Add the import-direction invariant note**

Below (or alongside) the `acquire/` entry, add a note:

```
**`acquire/` import-direction invariant**: `acquire/` must import downward only
(`api/`, `core/`, `conf/`, `events/`). It must never import the triage packages
(`ingest`, `sort`, `sorter`, `process`, `scraper`, `dispatch`, `indexer`,
`enforce`, `verify`, `insights`, `maintenance`, `reports`, `trailers`,
`pipeline`, `pipeline_steps`, `commands`). Enforced by the AST layering guard
in `tests/architecture/test_layering.py`.
```

- [ ] **Step 4: Commit**

```bash
git add -f docs/reference/architecture.md
git commit -m "docs(acquire-lobe): add acquire/ to module map with import-direction invariant"
```

---

## Sub-phase 5.3: Final `make check` gate

**Files:** none (gate only)

- [ ] **Step 1: Run `make check`**

```bash
make check
```

Expected: `NNNN passed`, 0 failed, 0 errors. This runs lint + tests + module-size check.

- [ ] **Step 2: Run residual import grep**

Verify no stray `tracker_registry` references leaked outside the acquire lobe:

```bash
rg "tracker_registry" --type py personalscraper/ tests/
```

Expected: zero matches outside `personalscraper/acquire/` and `personalscraper/api/tracker/` (the field name `tracker_registry` is used inside `AcquireContext` itself — that is correct; any match in `cli_helpers/`, `core/app_context.py`, or top-level `tests/` files indicates a missed update).

- [ ] **Step 3: Smoke test**

```bash
python -c "import personalscraper"
```

Expected: exit 0.

- [ ] **Step 4: Phase gate commit**

```bash
git add -A   # only if any lint auto-fixes were applied
git commit -m "chore(acquire-lobe): phase 5 gate — make check green, ACC-1..5 verified"
```

---

## Phase 05 Exit Criteria (= Feature Done)

All five ACCEPTANCE criteria pass:

```bash
# ACC-1
python -c "import personalscraper.acquire; from personalscraper.acquire.context import AcquireContext; print('OK')"
# ACC-2
python -c "import dataclasses; from personalscraper.core.app_context import AppContext; f={x.name for x in dataclasses.fields(AppContext)}; assert 'acquire' in f and 'tracker_registry' not in f; print('OK')"
# ACC-4
pytest tests/architecture/test_layering.py -q
# ACC-5
make check
```
