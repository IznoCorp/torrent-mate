# Phase 1 — Foundation

**Goal:** Land the infrastructure that the next 7 phases depend on: complexity-check script, `make check` target, doc audit pass for the "8 vs 9 steps" mismatch, and stub modules for `personalscraper/reports/` and `personalscraper/pipeline_protocol.py` so later phases can import them without circular-dependency drama.

**Risk:** Low. Pure addition + targeted doc edits. No production code-path changes.

**Files affected (estimate):**

- Create: `scripts/check-module-size.py`, `tests/scripts/test_check_module_size.py`, `personalscraper/pipeline_protocol.py`, `personalscraper/reports/__init__.py`
- Modify: `Makefile`, `personalscraper/models.py` (docstring), `personalscraper/pipeline.py` (docstring), `docs/reference/architecture.md`, `docs/reference/pipeline-internals.md`, `docs/reference/trailers.md`, `CLAUDE.md`, `.claude/CLAUDE.md`

## Sub-phases

### 1.1 — `check-module-size.py` script (TDD)

**Files:**

- Create: `scripts/check-module-size.py`
- Create: `tests/scripts/test_check_module_size.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/scripts/test_check_module_size.py
"""Tests for the module-size advisory script."""
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-module-size.py"


def test_script_exists():
    assert SCRIPT.is_file()


def test_script_exits_zero_on_clean_dir(tmp_path: Path):
    pkg = tmp_path / "small_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "tiny.py").write_text("x = 1\n" * 50)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "WARN" not in result.stdout


def test_script_warns_above_warn_threshold(tmp_path: Path):
    pkg = tmp_path / "fat_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "big.py").write_text("x = 1\n" * 850)  # > 800
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0  # advisory only in 0.9.0
    assert "WARN" in result.stdout
    assert "big.py" in result.stdout


def test_script_excludes_init_and_tests(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("x = 1\n" * 2000)  # excluded
    (pkg / "tests").mkdir()
    (pkg / "tests" / "test_huge.py").write_text("x = 1\n" * 2000)  # excluded
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert "WARN" not in result.stdout


def test_script_reports_above_block_threshold(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "huge.py").write_text("x = 1\n" * 1100)  # > 1000
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0  # still 0 in 0.9.0; will be 1 in 0.10.0
    assert "REPORT" in result.stdout
    assert "huge.py" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/scripts/test_check_module_size.py -v
```

Expected: FAIL — script does not exist yet.

- [ ] **Step 3: Implement script**

```python
# scripts/check-module-size.py
"""Advisory module-size guardrail.

Walks the personalscraper/ package (or --root) and reports files exceeding
soft (warn) and hard (report) thresholds. Excludes __init__.py and any
test_* files under tests/ subdirectories.

Exit code in 0.9.0: always 0 (advisory).
Exit code in 0.10.0+: 1 if any file exceeds the BLOCK threshold.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

WARN_LOC = 800
BLOCK_LOC = 1000
DEFAULT_ROOT = "personalscraper"
EXCLUDED_FILENAMES = {"__init__.py"}
EXCLUDED_DIR_PARTS = {"tests", "migrations"}


def _count_lines(path: Path) -> int:
    """Count non-blank lines (cheap proxy for cognitive load)."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except (OSError, UnicodeDecodeError):
        return 0


def _is_excluded(path: Path) -> bool:
    if path.name in EXCLUDED_FILENAMES:
        return True
    return any(part in EXCLUDED_DIR_PARTS for part in path.parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=DEFAULT_ROOT, type=Path)
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on REPORT-level findings (post-0.10.0 mode)")
    args = parser.parse_args()

    root: Path = args.root
    if not root.exists():
        print(f"check-module-size: root not found: {root}", file=sys.stderr)
        return 2

    findings: list[tuple[str, Path, int]] = []
    for py in sorted(root.rglob("*.py")):
        if _is_excluded(py):
            continue
        loc = _count_lines(py)
        if loc >= BLOCK_LOC:
            findings.append(("REPORT", py, loc))
        elif loc >= WARN_LOC:
            findings.append(("WARN", py, loc))

    if not findings:
        print(f"check-module-size: clean (root={root}, threshold WARN={WARN_LOC}, BLOCK={BLOCK_LOC})")
        return 0

    print(f"check-module-size: {len(findings)} finding(s) (root={root})")
    for level, path, loc in findings:
        print(f"  [{level}] {path}: {loc} non-blank lines")

    if args.strict and any(level == "REPORT" for level, _, _ in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/scripts/test_check_module_size.py -v
```

Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/check-module-size.py tests/scripts/test_check_module_size.py
git commit -m "feat(arch-cleanup): add advisory module-size check script"
```

### 1.2 — Wire `make check` target

**Files:**

- Modify: `Makefile`

- [ ] **Step 1: Inspect Makefile**

```bash
grep -nE '^[a-z_-]+:' Makefile
```

- [ ] **Step 2: Add `check` target**

Append (or create the section) so `check` runs lint + test + module-size:

```makefile
.PHONY: check
check: lint test
	python3 scripts/check-module-size.py
```

- [ ] **Step 3: Verify**

```bash
make check
```

Expected: lint passes, tests pass, module-size script lists current god modules as REPORT-level (advisory, exit 0).

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "build(arch-cleanup): add make check target running lint+test+module-size"
```

### 1.3 — Doc audit pass: 8→9 steps mismatch

**Files (audit + edit):**

- `personalscraper/models.py` (line ~140 docstring `# 8 steps` mention)
- `personalscraper/pipeline.py` (verify 9 everywhere)
- `docs/reference/pipeline-internals.md`
- `docs/reference/architecture.md`

- [ ] **Step 1: Find all "8 step" / "8 StepReport" mentions**

```bash
grep -rnE '8\s*(step|StepReport|StepReports?)' personalscraper/ docs/ CLAUDE.md README.md 2>/dev/null
grep -rnE 'eight\s*(step|StepReport)' personalscraper/ docs/ CLAUDE.md README.md 2>/dev/null
```

- [ ] **Step 2: Replace each with "9 steps" / "9 StepReports"**

Use Edit tool per occurrence, preserving surrounding context. Verify each change is grammatically correct (e.g., `# Step name → emoji mapping for visual identification (8 steps)` → `# Step name → emoji mapping for visual identification (9 steps)`).

- [ ] **Step 3: Re-grep to verify zero remaining**

```bash
grep -rnE '\b8\s*(step|StepReport)' personalscraper/ docs/ 2>/dev/null
```

Expected: empty.

- [ ] **Step 4: Commit**

```bash
git add personalscraper/ docs/
git commit -m "docs(arch-cleanup): correct pipeline step count to 9 throughout codebase"
```

### 1.4 — Stub `personalscraper/pipeline/` package

**Files:**

- Create: `personalscraper/pipeline/__init__.py`
- Create: `personalscraper/pipeline_protocol.py`

> **Constraint**: `personalscraper/pipeline.py` (the current module) and `personalscraper/pipeline/` (a future package) cannot coexist. Do **not** create `personalscraper/pipeline/` in this feature. The canonical phase-6 import path is the single-file module `personalscraper.pipeline_protocol`; any later package conversion is deferred beyond 0.9.0.

Adjusted plan:

- Create: `personalscraper/pipeline_protocol.py` (placeholder, no public API yet)

- [ ] **Step 1: Create the file**

```python
# personalscraper/pipeline_protocol.py
"""PipelineStep Protocol stub.

Populated in phase 6 (arch-cleanup). Kept as a placeholder so other phases
can land import paths without bouncing through PR-merge order.
"""

from __future__ import annotations

# Phase 6 will populate this module.
__all__: list[str] = []
```

- [ ] **Step 2: Commit**

```bash
git add personalscraper/pipeline_protocol.py
git commit -m "chore(arch-cleanup): add pipeline_protocol stub for phase 6"
```

### 1.5 — Stub `personalscraper/reports/` package

**Files:**

- Create: `personalscraper/reports/__init__.py`

- [ ] **Step 1: Create the file**

```python
# personalscraper/reports/__init__.py
"""Per-step typed *Details payloads for StepReport.details_payload.

Populated in phase 7 (arch-cleanup). Kept as a stub so import paths can
stabilise across phases.
"""

from __future__ import annotations

__all__: list[str] = []

# STEP_REPORT_CONTRACT will be populated in phase 7.
STEP_REPORT_CONTRACT: dict[str, type] = {}
```

- [ ] **Step 2: Verify import**

```bash
python3 -c "from personalscraper.reports import STEP_REPORT_CONTRACT; assert STEP_REPORT_CONTRACT == {}"
```

- [ ] **Step 3: Commit**

```bash
git add personalscraper/reports/__init__.py
git commit -m "chore(arch-cleanup): add reports/ package stub for phase 7"
```

### 1.6 — Document complexity rule in `CLAUDE.md`

**Files:**

- Modify: `CLAUDE.md` (project root)
- Modify: `.claude/CLAUDE.md`

- [ ] **Step 1: Add Code Conventions clause to project `CLAUDE.md`**

Insert after the existing Code Conventions section:

```markdown
- **Module size**: soft warning at 800 non-blank LOC, hard ceiling 1000 LOC. Run `python3 scripts/check-module-size.py` (also wired into `make check`). Advisory in 0.9.0; promoted to hard block in 0.10.0.
```

- [ ] **Step 2: Mirror the rule in `.claude/CLAUDE.md`** (same line, under the relevant section).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md .claude/CLAUDE.md
git commit -m "docs(arch-cleanup): document module-size guardrail rule"
```

## Quality gate (end of phase)

```bash
make check        # lint + test + module-size
pytest tests/scripts/ -v
```

All commands exit 0. Module-size script lists current god modules at REPORT level — that's expected (and is what phases 2-5 reduce).

## Success criteria

- `scripts/check-module-size.py` exists, tested, exits 0 advisory in 0.9.0
- `make check` runs lint + test + module-size
- Zero "8 step" / "8 StepReport" mentions remain in code or docs
- `personalscraper/pipeline_protocol.py` and `personalscraper/reports/` stubs exist
- `CLAUDE.md` documents the size rule

## Rollback plan

Each sub-phase is one commit. To roll back:

Use `git revert <sub-phase-sha>` for committed sub-phases, or apply a targeted reverse patch before commit. Do not use `git reset --hard` unless the user explicitly requests it.

Phase 1 has no production-code changes — full revert to `main` is safe.

## Estimated effort

4-6 commits, ~2 hours of work for an unfamiliar engineer (most time in the doc-audit grep + correction loop).
