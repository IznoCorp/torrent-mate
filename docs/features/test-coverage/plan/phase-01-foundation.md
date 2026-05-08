# Phase 1 — Foundation: scripts + Makefile + baseline

**Type**: infra
**Effort**: M (~3 h)
**Entry**: clean tree on `feat/test-coverage`. CI red on `main` due to `--cov-fail-under=80` + 44 % actual coverage.
**Exit**:

- 4 new scripts (`get_coverage_threshold.py`, `_codename_overrides.py`, `update_feature_map.py`, `audit_design_coverage.py`) with unit tests.
- `tomli` added to dev deps.
- `pyproject.toml` rebaselined with branch coverage on, `parallel = true`, `concurrency = ["multiprocessing"]`.
- Makefile gains `test-unit`, `test-integration`, `test-cov` targets.
- `make test-cov` green at the rebaselined `fail_under`.

## Task 1.1 — Add `tomli` to dev deps + rebaseline `pyproject.toml`

**Files modified**:

- `pyproject.toml`

- [ ] **Step 1**: Add `'tomli; python_version < "3.11"'` to `[project.optional-dependencies].dev`.
- [ ] **Step 2**: In `[tool.coverage.run]`, add `branch = true`, `parallel = true`, `concurrency = ["multiprocessing"]`.
- [ ] **Step 3**: In `[tool.coverage.report]`, lower `fail_under` to `44` (provisional) and add `exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:", "@overload", "raise NotImplementedError"]`.
- [ ] **Step 4**: Create `tests/feature_map/.gitkeep` (empty file). The directory must exist before any script writes to it.
- [ ] **Step 5**: Measure real branch baseline locally:
  ```bash
  pip install -e ".[dev]"
  python3 -m pytest tests/ --ignore=tests/e2e -q --no-header \
    --cov=personalscraper --cov-branch --cov-report=term -n auto 2>&1 | tail -5
  ```
  Note the TOTAL line. If branch lowers the percentage (e.g. 38 %), update `fail_under` in `pyproject.toml` to match.
- [ ] **Step 6**: Verify `--cov-fail-under=$BASELINE` passes. Commit.

```
chore(test-coverage): rebaseline pyproject.toml with branch coverage
```

## Task 1.2 — Create `scripts/get_coverage_threshold.py`

**Files created**: `scripts/get_coverage_threshold.py`

The Makefile cannot inline `try/except` import logic in `$(shell python3 -c "...")` — the embedded `\n` is passed literally and `python3 -c` does not interpret it. This script is the supported path.

```python
#!/usr/bin/env python3
"""Read [tool.coverage.report].fail_under from pyproject.toml.

Used by the Makefile (``THRESHOLD := $(shell python3 scripts/get_coverage_threshold.py)``)
and by the coverage-monotonic CI job (``--stdin`` mode reads main's pyproject.toml
without a checkout).

Exit codes:
  0 — value printed to stdout.
  1 — pyproject.toml missing or fail_under absent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read pyproject.toml content from stdin (used by coverage-monotonic CI step).",
    )
    args = parser.parse_args()

    if args.stdin:
        data = tomllib.loads(sys.stdin.read())
    else:
        path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return 1
        with path.open("rb") as f:
            data = tomllib.load(f)

    try:
        threshold = data["tool"]["coverage"]["report"]["fail_under"]
    except KeyError:
        print("error: [tool.coverage.report].fail_under not set", file=sys.stderr)
        return 1

    print(threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1**: Write the script.
- [ ] **Step 2**: Verify `python3 scripts/get_coverage_threshold.py` prints the rebaselined value.
- [ ] **Step 3**: Verify `--stdin`: `cat pyproject.toml | python3 scripts/get_coverage_threshold.py --stdin` prints the same value.
- [ ] **Step 4**: Commit.

```
feat(test-coverage): add get_coverage_threshold.py helper
```

## Task 1.3 — Create `scripts/_codename_overrides.py`

**Files created**: `scripts/_codename_overrides.py`

Holds the override table for reference docs (`docs/reference/scraping.md` → `scraper`, etc.). Imported by both `update_feature_map.py` and `audit_design_coverage.py`.

```python
"""Codename override table for design-doc → feature-codename resolution.

Reference docs (e.g. ``docs/reference/scraping.md``) do not follow the
``docs/features/<codename>/`` convention. The override table maps each known
reference doc to its canonical codename so the two-direction audit works.
"""

from __future__ import annotations

from typing import Final

CODENAME_OVERRIDES: Final[dict[str, str]] = {
    "docs/reference/scraping.md": "scraper",
    "docs/reference/storage.md": "dispatch",
    "docs/reference/pipeline-internals.md": "pipeline",
    "docs/reference/trailers.md": "trailers",
    "docs/reference/indexer.md": "indexer",
    "docs/reference/indexer-json-shapes.md": "indexer",
    "docs/reference/architecture.md": "architecture",
    # Provider docs auto-resolve via stem (tmdb-api.md → tmdb, etc.).
    # Add explicit entries here if a provider doc uses a non-stem codename.
}


def resolve_codename(design_path: str) -> str:
    """Resolve a design doc path to its canonical codename.

    Order: explicit override → ``features/<codename>/`` segment → file stem.

    Args:
        design_path: Relative path from repo root.

    Returns:
        Canonical codename (filename-safe, lowercase).
    """
    if design_path in CODENAME_OVERRIDES:
        return CODENAME_OVERRIDES[design_path]

    from pathlib import Path

    parts = Path(design_path).parts
    if "features" in parts:
        idx = parts.index("features")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    stem = Path(design_path).stem
    # Provider doc convention: foo-api.md → foo
    if stem.endswith("-api"):
        stem = stem[: -len("-api")]
    return stem
```

- [ ] **Step 1**: Write the module.
- [ ] **Step 2**: Commit.

```
feat(test-coverage): add codename override table
```

## Task 1.4 — Create `scripts/update_feature_map.py`

**Files created**: `scripts/update_feature_map.py`

Scans `tests/` for `Design:` markers, groups by codename via `resolve_codename()`, writes one `.json` file per codename. Implements `--check` for CI.

Key behaviors per DESIGN §3.2 and §3.3:

- Markers parsed via `ast.get_docstring(node, clean=True)` on `FunctionDef` / `AsyncFunctionDef` only (no class/module docstrings).
- Both `Design:` AND `Contract:` required; if `Contract:` missing, skip with warning (not an error — legacy tests may pre-date the convention).
- Multiple `Design:` lines per docstring are allowed (cross-cutting tests).
- Tests under `tests/e2e/` are scanned (the map is documentation-of-record, even if e2e tests don't count toward `fail_under`).
- Map files: standard JSON, `.json` extension, indent=2.
- `--check` mode: compare what we'd generate against committed files. Exit 1 on drift.
- Detects codename collisions (two different design paths resolving to the same codename) and exits non-zero.

The full source listing is reserved for the implementing PR — this plan documents the contract, not the line-by-line code.

- [ ] **Step 1**: Implement script following the contract above.
- [ ] **Step 2**: Implement `tests/unit/test_update_feature_map.py` covering:
  - `extract_codename` for the 4 default cases + each override
  - `Design:`/`Contract:` parsing (both present, only Design, only Contract, multiple Design)
  - Skip module/class docstrings
  - `--check` mode passes on a synthesized fixture
  - `--check` mode fails on drift
  - Codename collision detection
- [ ] **Step 3**: Verify both run cleanly.
- [ ] **Step 4**: Commit.

```
feat(test-coverage): add update_feature_map.py + unit tests
```

## Task 1.5 — Create `scripts/audit_design_coverage.py`

**Files created**: `scripts/audit_design_coverage.py`

Two-direction audit per DESIGN §7.2:

1. **Orphan sections**: design sections without a matching test. Severity Warning until cycle 4, then Error.
2. **Stale references**: tests whose `Design:` markers point to nonexistent anchors. Severity Error from day 1.

Anchor algorithm per DESIGN §3.2.1 (NFC, Unicode-aware, dedup `-1`/`-2`/…). The implementation is in `github_anchor()`. The corresponding unit test (`tests/unit/test_audit_design_coverage.py::TestGithubAnchor`) covers all reference cases listed in DESIGN §3.2.1.

`skip_audit` entries with `expires` past today produce a warning.

- [ ] **Step 1**: Implement script.
- [ ] **Step 2**: Implement `tests/unit/test_audit_design_coverage.py` covering:
  - `github_anchor` for all DESIGN §3.2.1 reference cases
  - NFC normalization (NFD input → same anchor as NFC)
  - Empty heading skipped
  - Duplicate handling (`title`, `title-1`, `title-2`)
  - Orphan section detection
  - Stale reference detection (test marker → missing anchor)
  - `skip_audit` with `expires` in past → warning
  - `--strict` exit code
- [ ] **Step 3**: Run on the current repo. Expected output: many orphan sections (no contract tests yet); zero stale refs.
- [ ] **Step 4**: Commit.

```
feat(test-coverage): add audit_design_coverage.py + unit tests
```

## Task 1.6 — Add Makefile targets

**Files modified**: `Makefile`

```makefile
THRESHOLD := $(shell python3 scripts/get_coverage_threshold.py)

test-unit:
	@echo "Running unit tests..."
	python3 -m pytest tests/ --ignore=tests/integration --ignore=tests/e2e -q -n auto

test-integration:
	@echo "Running integration tests..."
	python3 -m pytest tests/integration/ -q -n auto

test-cov:
	@echo "Running tests with branch coverage (fail_under=$(THRESHOLD))..."
	python3 -m pytest tests/ --ignore=tests/e2e -q --no-header -n auto \
		--cov=personalscraper --cov-branch --cov-report=xml --cov-report=term \
		--cov-fail-under=$(THRESHOLD)
```

Update `.PHONY`: append `test-unit test-integration test-cov`.

Update `check:` target: replace `test` with `test-cov` (so the existing module-size and typed-api guardrails follow coverage):

```makefile
check: lint test-cov
	python3 scripts/check-module-size.py
	python3 scripts/check-typed-api.py
```

The existing `gate` target (residual import audit + smoke) is preserved unchanged.

- [ ] **Step 1**: Edit Makefile.
- [ ] **Step 2**: `make -n test-cov` (sanity).
- [ ] **Step 3**: `make test-cov` actually runs and passes at the rebaselined threshold. `coverage.xml` produced.
- [ ] **Step 4**: `make test-unit` runs without coverage, fast.
- [ ] **Step 5**: Commit.

```
feat(test-coverage): add test-unit, test-integration, test-cov targets
```

## Task 1.7 — Phase 1 gate

- [ ] `make check` green
- [ ] `python3 -c "import personalscraper"` smoke test
- [ ] `python3 scripts/update_feature_map.py --check` exits 0 (empty map dir, no markers yet — should be a no-op)
- [ ] Single milestone commit:

```
chore(test-coverage): phase 1 gate — foundation done
```
