# Phase 04 — Layering guard extension (acquire/ → never triage)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `tests/architecture/test_layering.py` with `test_acquire_does_not_import_triage()` covering the full `_TRIAGE_PREFIXES` set, plus a non-vacuous control test pair (positive anchor + negative anchor) that self-pins the guard against bitrot.

**Architecture:** Pure test addition — no source code changes. **Reuses** the existing `_collect_violations_from_source` pure helper by **parametrizing** it with a `prefixes` argument (default `_FORBIDDEN_PREFIXES`, so every existing caller is unchanged), then calling it with `prefixes=_TRIAGE_PREFIXES`. NO duplicate AST-walk helper (DESIGN §5: reuse, not duplicate). The positive control uses a synthetic source attributed under `acquire/`; the negative control uses a downward (`api/`) import.

**Tech Stack:** Python 3.12, pytest, ast (stdlib)

---

## Gate (Phase 03 → Phase 04)

Phase 03 must have produced:

- `AppContext.acquire` field present; `tracker_registry` field gone
- `cli_helpers/__init__.py` wired to `build_acquire_context` + `acquire.close()`
- `make test` green

Verify:

```bash
make test                     # must be green
python -c "
import dataclasses; from personalscraper.core.app_context import AppContext
f = {x.name for x in dataclasses.fields(AppContext)}
assert 'acquire' in f and 'tracker_registry' not in f
print('OK')
"
```

---

## Task 1: Extend the layering guard (parametrize + reuse)

**Files:**

- Modify: `tests/architecture/test_layering.py`

- [ ] **Step 1: Parametrize the existing `_collect_violations_from_source`**

Add a `prefixes` parameter (default `_FORBIDDEN_PREFIXES`) and iterate `prefixes` in the loop
instead of the hardcoded constant. The default keeps **all** existing callers (`test_core_*`,
`test_conf_*`, the synthetic control tests) working with zero edits. This reuses the existing
TYPE_CHECKING exemption + justified-`# layering: allow` marker handling for free — no logic is
duplicated.

```python
def _collect_violations_from_source(
    source: str, rel: str, prefixes: tuple[str, ...] = _FORBIDDEN_PREFIXES
) -> list[str]:
    ...
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            ...
            for prefix in prefixes:          # was: for prefix in _FORBIDDEN_PREFIXES
                ...
```

(No other edit to the helper body. `_collect_violations` — the filesystem wrapper — keeps calling
the helper with the default, so `test_core_*`/`test_conf_*` are untouched.)

- [ ] **Step 2: Add `_TRIAGE_PREFIXES` + the acquire tests (append to the file)**

```python
# ---------------------------------------------------------------------------
# acquire/ layering guard — RP5c (D3)
#
# ``acquire/`` is the acquisition lobe. It must import downward only:
# ``api/``, ``core/``, ``conf/``, ``events/``. It must NEVER import the
# triage packages in ``_TRIAGE_PREFIXES``. The two control tests pin the guard
# non-vacuously: a synthetic triage import attributed under ``acquire/`` MUST be
# flagged (positive anchor); a downward ``api/`` import MUST NOT be (negative).
# ---------------------------------------------------------------------------

_TRIAGE_PREFIXES = (
    "personalscraper.ingest",
    "personalscraper.sort",
    "personalscraper.sorter",
    "personalscraper.process",
    "personalscraper.scraper",
    "personalscraper.dispatch",
    "personalscraper.indexer",
    "personalscraper.enforce",
    "personalscraper.verify",
    "personalscraper.insights",
    "personalscraper.maintenance",
    "personalscraper.reports",
    "personalscraper.trailers",
    "personalscraper.pipeline",
    "personalscraper.pipeline_steps",
    "personalscraper.commands",
)

_ACQUIRE_SYNTHETIC_REL = "personalscraper/acquire/_synthetic_probe.py"


def test_acquire_does_not_import_triage() -> None:
    """No module under acquire/ imports any triage package at runtime."""
    acquire_root = _PACKAGE_ROOT / "acquire"
    if not acquire_root.exists():
        return  # package not yet created — skip gracefully before Phase 01
    violations: list[str] = []
    for py_file in sorted(acquire_root.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        violations.extend(
            _collect_violations_from_source(py_file.read_text(encoding="utf-8"), rel, _TRIAGE_PREFIXES)
        )
    assert not violations, (
        "acquire/ has forbidden triage imports (it must only import downward):\n" + "\n".join(violations)
    )


def test_acquire_triage_import_is_flagged() -> None:
    """POSITIVE control: a triage import attributed to acquire/ IS a violation (non-vacuous anchor)."""
    source = "from personalscraper.dispatch import something\n"
    violations = _collect_violations_from_source(source, _ACQUIRE_SYNTHETIC_REL, _TRIAGE_PREFIXES)
    assert violations, "acquire/ triage guard failed to flag a dispatch import (vacuous guard!)"
    assert "personalscraper.dispatch" in violations[0]


def test_acquire_downward_import_is_not_flagged() -> None:
    """NEGATIVE control: a downward import (api/) attributed to acquire/ is NOT a violation."""
    source = "from personalscraper.api import something\n"
    violations = _collect_violations_from_source(source, _ACQUIRE_SYNTHETIC_REL, _TRIAGE_PREFIXES)
    assert violations == [], f"downward api/ import should not be flagged, got: {violations}"
```

- [ ] **Step 3: Run the new tests**

```bash
pytest tests/architecture/test_layering.py::test_acquire_triage_import_is_flagged \
       tests/architecture/test_layering.py::test_acquire_downward_import_is_not_flagged \
       tests/architecture/test_layering.py::test_acquire_does_not_import_triage -v
```

Expected: all three PASS (the real-tree test passes because `acquire/` exists from Phase 01 with no triage imports).

- [ ] **Step 4: Run the full architecture suite** — proves the parametrization didn't regress existing callers.

```bash
pytest tests/architecture/ -v   # existing test_core_*/test_conf_*/controls + new acquire tests all pass
```

- [ ] **Step 5: Commit**

```bash
git add tests/architecture/test_layering.py
git commit -m "test(acquire-lobe): extend layering guard — acquire/ must never import triage"
```

---

## Phase 04 Exit Criteria

```bash
pytest tests/architecture/test_layering.py -v   # all pass incl. 3 new acquire tests
make lint                                        # zero errors
```
