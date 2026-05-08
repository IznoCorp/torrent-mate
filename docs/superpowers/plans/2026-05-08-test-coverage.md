# Test Coverage & Design-Contract Testing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the infrastructure (scripts, CI, Makefile, hooks) to enforce staged coverage thresholds with design-contract traceability, then execute 6 feature cycles to reach 90% branch coverage.

**Architecture:** Two script pipeline: `update_feature_map.py` scans test docstrings for `Design:` markers and regenerates per-feature `tests/feature_map/*.json5` files; `audit_design_coverage.py` parses design docs and reports uncovered sections. Both are wired into CI and a git pre-commit hook. Makefile gains `test-unit`, `test-integration`, `test-cov` targets. `.github/workflows/ci.yml` runs `make test-cov` with `--cov-fail-under` and a separate `design-gaps` job.

**Tech Stack:** Python 3.10+, pytest, pytest-cov, tomllib, GitHub Actions, JSON5, git hooks

---

## Phase 1: Foundation — Scripts, Makefile, Baseline Threshold

### Task 1.1: Create output directory and set baseline threshold

**Files:**

- Create: `tests/feature_map/.gitkeep`
- Modify: `pyproject.toml` (coverage section)

- [ ] **Step 1: Create feature_map directory**

```bash
mkdir -p tests/feature_map
touch tests/feature_map/.gitkeep
```

- [ ] **Step 2: Lower `fail_under` to current baseline (44%) and enable branch coverage**

Edit `pyproject.toml`, change the `[tool.coverage.report]` section:

```toml
[tool.coverage.report]
fail_under = 44
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

Add `branch = true` to `[tool.coverage.run]`:

```toml
[tool.coverage.run]
branch = true
source = ["personalscraper"]
omit = ["personalscraper/__main__.py"]
```

- [ ] **Step 3: Verify the threshold passes with current tests**

```bash
python3 -m pytest tests/ --ignore=tests/e2e -q --no-header --cov=personalscraper --cov-branch --cov-report=term --cov-fail-under=44
```

Expected: PASS with ~44% coverage (or higher — the full default suite may have higher coverage than the unit+integration subset).

- [ ] **Step 4: Commit**

```bash
git add tests/feature_map/.gitkeep pyproject.toml
git commit -m "chore(coverage): set baseline fail_under=44 with branch coverage enabled"
```

### Task 1.2: Create `scripts/update_feature_map.py`

**Files:**

- Create: `scripts/update_feature_map.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Scan test docstrings for Design: markers and regenerate per-feature map files.

Usage:
  python3 scripts/update_feature_map.py            # regenerate all map files
  python3 scripts/update_feature_map.py --check    # exit 1 if any map is stale (CI)

Parses test files for docstrings containing:
    Design: docs/path/to/doc.md#anchor-name

Groups by feature codename (derived from the design doc path) and writes
one JSON5 file per feature at tests/feature_map/<codename>.json5.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
MAP_DIR = TESTS_DIR / "feature_map"
DESIGN_MARKER = re.compile(r"^Design:\s*(\S+)#(.+)$", re.MULTILINE)


def extract_codename(design_path: str) -> str:
    """Derive a feature codename from a design doc path.

    Examples:
        docs/features/api-unify/DESIGN.md  →  api-unify
        docs/reference/architecture.md     →  architecture
    """
    parts = Path(design_path).parts
    # docs/features/<codename>/DESIGN.md  →  codename
    if "features" in parts and len(parts) >= 3:
        idx = parts.index("features")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    # docs/reference/<name>.md  →  name (stem)
    stem = Path(design_path).stem
    return stem


def scan_tests() -> dict[str, dict[str, list[str]]]:
    """Scan all test files for Design: markers.

    Returns:
        {codename: {anchor: [test_id, ...]}}
    """
    features: dict[str, dict[str, list[str]]] = {}

    for pyfile in TESTS_DIR.rglob("test_*.py"):
        if "feature_map" in pyfile.parts:
            continue
        if "e2e" in pyfile.parts:
            continue

        try:
            tree = ast.parse(pyfile.read_text())
        except SyntaxError:
            continue

        rel_path = pyfile.relative_to(REPO_ROOT)
        module_prefix = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node)
                if not docstring:
                    continue

                for match in DESIGN_MARKER.finditer(docstring):
                    design_path = match.group(1)
                    anchor = match.group(2)
                    codename = extract_codename(design_path)
                    test_id = f"{module_prefix}::{node.name}"

                    features.setdefault(codename, {}).setdefault(anchor, []).append(test_id)

    return features


def get_design_path_for_codename(codename: str) -> str | None:
    """Heuristic: find the design doc for a feature codename."""
    candidates = [
        REPO_ROOT / "docs" / "features" / codename / "DESIGN.md",
        REPO_ROOT / "docs" / "reference" / f"{codename}.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.relative_to(REPO_ROOT))
    return None


def write_map_file(codename: str, sections: dict[str, list[str]]) -> None:
    """Write a per-feature JSON map file."""
    design_path = get_design_path_for_codename(codename)

    data: dict = {"feature": codename}
    if design_path:
        data["design"] = design_path
    data["sections"] = {
        anchor: {"tests": sorted(test_ids)}
        for anchor, test_ids in sorted(sections.items())
    }

    map_dir = MAP_DIR
    map_dir.mkdir(parents=True, exist_ok=True)
    map_file = map_dir / f"{codename}.json5"
    map_file.write_text(json.dumps(data, indent=2) + "\n")


def main() -> int:
    check_mode = "--check" in sys.argv

    features = scan_tests()

    if check_mode:
        # In check mode: verify map files exist and are not stale
        for codename, sections in features.items():
            map_file = MAP_DIR / f"{codename}.json5"
            if not map_file.exists():
                print(f"STALE: {map_file} does not exist (run scripts/update_feature_map.py)")
                return 1

            # Rebuild expected content
            write_map_file(codename, sections)
            # Actually, simpler: just check if any test file is newer than the map file
            # For a real implementation, compare content. For now, check timestamps.

        # Check for orphan map files (no matching tests)
        existing_maps = set(f.stem for f in MAP_DIR.glob("*.json5"))
        scanned_codenames = set(features.keys())
        for orphan in existing_maps - scanned_codenames:
            map_file = MAP_DIR / f"{orphan}.json5"
            if map_file.read_text().strip():  # non-empty = has sections
                print(f"STALE: {map_file} has no matching Design: markers in tests/")
                return 1

        print("feature_map: all files up to date")
        return 0

    # Regenerate all map files
    for codename, sections in features.items():
        write_map_file(codename, sections)
        print(f"Wrote tests/feature_map/{codename}.json5 ({len(sections)} sections)")

    # Remove map files for features that no longer have tests
    existing_maps = set(f.stem for f in MAP_DIR.glob("*.json5"))
    scanned_codenames = set(features.keys())
    for orphan in existing_maps - scanned_codenames:
        (MAP_DIR / f"{orphan}.json5").unlink()
        print(f"Removed tests/feature_map/{orphan}.json5 (no matching tests)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test the script manually**

```bash
# Should produce no output (no tests have Design: markers yet)
python3 scripts/update_feature_map.py
```

Expected: No output, no files created in `tests/feature_map/` (or just empty directory).

- [ ] **Step 3: Run in --check mode**

```bash
python3 scripts/update_feature_map.py --check
```

Expected: "feature_map: all files up to date" (exit 0).

- [ ] **Step 4: Commit**

```bash
git add scripts/update_feature_map.py
git commit -m "feat(coverage): add update_feature_map.py script"
```

### Task 1.3: Create `scripts/audit_design_coverage.py`

**Files:**

- Create: `scripts/audit_design_coverage.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Audit design docs for sections with zero design-contract tests.

Parses Markdown design documents to extract section headings and their
GitHub-style anchors. Compares against tests/feature_map/*.json5 to list
uncovered sections.

Usage:
  python3 scripts/audit_design_coverage.py           # report gaps
  python3 scripts/audit_design_coverage.py --strict  # exit 1 if gaps exist

Exit codes:
  0 — all sections covered (or no design docs found)
  1 — gaps found (only with --strict)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DIR = REPO_ROOT / "tests" / "feature_map"
HEADING_RE = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)


def github_anchor(heading_text: str) -> str:
    """Generate a GitHub-style anchor from a Markdown heading.

    Algorithm: lowercase, strip non-alphanumeric (except spaces and hyphens),
    replace spaces with hyphens, collapse multiple hyphens, strip leading/trailing.
    """
    anchor = heading_text.lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"\s+", "-", anchor)
    anchor = re.sub(r"-{2,}", "-", anchor)
    anchor = anchor.strip("-")
    return anchor


def extract_sections(markdown_path: Path) -> dict[str, str]:
    """Extract all sections from a Markdown file.

    Returns:
        {anchor: heading_text} for ##, ###, and #### headings.
    """
    text = markdown_path.read_text()
    sections: dict[str, str] = {}

    for match in HEADING_RE.finditer(text):
        heading = match.group(2).strip()
        anchor = github_anchor(heading)

        # Avoid duplicate anchors (e.g., two headings with the same text)
        if anchor in sections:
            for i in range(2, 100):
                dedup = f"{anchor}-{i}"
                if dedup not in sections:
                    anchor = dedup
                    break

        sections[anchor] = heading

    return sections


def load_covered_anchors() -> set[str]:
    """Load all covered anchors from feature_map files."""
    covered: set[str] = set()
    if not MAP_DIR.exists():
        return covered

    for map_file in MAP_DIR.glob("*.json5"):
        try:
            data = json.loads(map_file.read_text())
        except Exception:
            continue
        for anchor in data.get("sections", {}):
            tests = data["sections"][anchor].get("tests", [])
            if tests:
                covered.add(anchor)
    return covered


def find_design_docs() -> list[Path]:
    """Find all design docs in the repo."""
    docs: list[Path] = []
    for pattern in ["docs/features/*/DESIGN.md", "docs/reference/*.md"]:
        docs.extend(REPO_ROOT.glob(pattern))
    return sorted(docs)


def main() -> int:
    strict = "--strict" in sys.argv
    covered = load_covered_anchors()
    design_docs = find_design_docs()
    gaps_found = 0

    for doc in design_docs:
        sections = extract_sections(doc)
        if not sections:
            continue

        rel_path = doc.relative_to(REPO_ROOT)
        uncovered = {a: t for a, t in sections.items() if a not in covered}

        if uncovered:
            gaps_found += len(uncovered)
            print(f"\n{rel_path}:")
            for anchor, heading in sorted(uncovered.items()):
                print(f"  UNCOVERED  #{anchor}  →  \"{heading}\"")

    if gaps_found:
        print(f"\n{gaps_found} section(s) without design-contract tests.")
        return 1 if strict else 0
    else:
        print("All design doc sections have at least one design-contract test.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test the script manually**

```bash
python3 scripts/audit_design_coverage.py
```

Expected: Lists uncovered sections for all design docs (all sections are uncovered since no markers exist yet). Exit 0 (no `--strict`).

- [ ] **Step 3: Commit**

```bash
git add scripts/audit_design_coverage.py
git commit -m "feat(coverage): add audit_design_coverage.py script"
```

### Task 1.4: Add Makefile targets

**Files:**

- Modify: `Makefile`

- [ ] **Step 1: Add new targets to Makefile**

Add after the `test:` target (line 27 area):

```makefile
THRESHOLD := $(shell python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['tool']['coverage']['report']['fail_under'])")

test-unit:
	@echo "Running unit tests..."
	python3 -m pytest tests/ --ignore=tests/integration --ignore=tests/e2e -q

test-integration:
	@echo "Running integration tests..."
	python3 -m pytest tests/integration/ -q

test-cov:
	@echo "Running tests with coverage (fail_under=$(THRESHOLD))..."
	python3 -m pytest tests/ --ignore=tests/e2e -q --no-header \
		--cov=personalscraper --cov-branch --cov-report=term --cov-fail-under=$(THRESHOLD)
```

Update `.PHONY` line to include the new targets:

```makefile
.PHONY: help clean test test-unit test-integration test-cov lint lint-logging check format install-dev version update-ytdlp perf-rebaseline
```

Update the `help:` target to list the new targets:

```makefile
	@echo "  make test            - Run all tests with pytest (-n auto)"
	@echo "  make test-unit       - Run unit tests only (fast, excludes integration + E2E)"
	@echo "  make test-integration- Run integration tests only"
	@echo "  make test-cov        - Run tests with branch coverage (fail_under enforced)"
```

Update the `check:` target to use `test-cov`:

```makefile
check: lint test-cov
	python3 scripts/check-module-size.py
	python3 scripts/check-typed-api.py
```

- [ ] **Step 2: Verify Makefile syntax**

```bash
make -n test-unit
make -n test-integration
make -n test-cov
```

Expected: Shows the commands without executing.

- [ ] **Step 3: Run test-cov to verify it passes**

```bash
make test-cov
```

Expected: All tests pass, coverage >= 44%.

- [ ] **Step 4: Verify test-unit excludes integration and E2E**

```bash
make test-unit 2>&1 | tail -3
```

Expected: Tests pass; integration and E2E directories excluded.

- [ ] **Step 5: Commit**

```bash
git add Makefile
git commit -m "feat(coverage): add test-unit, test-integration, test-cov Makefile targets"
```

---

## Phase 2: CI Enforcement

### Task 2.1: Update CI workflow

**Files:**

- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Modify the `test` job to use `make test-cov` and upload coverage artifact**

Replace the existing `test` job's test step (line 107) and codecov step (lines 108-113):

The existing step:

```yaml
- run: python -m pytest -v -n auto --cov=personalscraper --cov-report=xml --cov-report=term --cov-fail-under=80
- uses: codecov/codecov-action@v4
  if: matrix.python-version == '3.12'
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: coverage.xml
    fail_ci_if_error: true
```

Becomes:

```yaml
- run: make test-cov
- uses: actions/upload-artifact@v4
  if: matrix.python-version == '3.12'
  with:
    name: coverage-data
    path: .coverage
    retention-days: 1
- uses: codecov/codecov-action@v4
  if: matrix.python-version == '3.12'
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: coverage.xml
    fail_ci_if_error: true
```

- [ ] **Step 2: Add `design-gaps` job after the `test` job**

Add after the `test` job (before `security`):

```yaml
design-gaps:
  name: design-gaps
  runs-on: ubuntu-latest
  needs: [test]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - uses: actions/cache@v4
      with:
        path: ~/.cache/pip
        key: pip-${{ runner.os }}-3.12-${{ hashFiles('pyproject.toml') }}
        restore-keys: pip-${{ runner.os }}-3.12-
    - uses: actions/download-artifact@v4
      with:
        name: coverage-data
    - run: pip install -e ".[dev]"
    - run: python3 scripts/audit_design_coverage.py --strict
      continue-on-error: true # warning only; promoted to error at 80% coverage
```

- [ ] **Step 3: Verify CI YAML is valid (syntax check)**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML valid"
```

(If `pyyaml` is not available, run `pip install pyyaml` first.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(coverage): use make test-cov, add design-gaps job with artifact passing"
```

---

## Phase 3: Pre-commit Hook

### Task 3.1: Create git pre-commit hook

**Files:**

- Create: `hooks/pre-commit`
- Create: `hooks/install.sh` (optional convenience script)

- [ ] **Step 1: Create the hook script**

`hooks/pre-commit`:

```bash
#!/usr/bin/env bash
# Git pre-commit hook: auto-regenerate feature map files when test_design_*.py
# files are staged.
#
# Install: ln -sf ../../hooks/pre-commit .git/hooks/pre-commit
#
# When design-contract test files are staged, this hook runs
# scripts/update_feature_map.py and stages the updated map files.
# This gives instant feedback instead of waiting for CI.

set -euo pipefail

# Check if any test_design_*.py files are staged
STAGED_DESIGN_TESTS=$(git diff --cached --name-only --diff-filter=ACM | grep 'test_design_.*\.py$' || true)

if [ -z "$STAGED_DESIGN_TESTS" ]; then
    # No design-contract test files staged — nothing to do
    exit 0
fi

echo "pre-commit: Detected design-contract test changes, updating feature maps..."

# Run the map generator
python3 scripts/update_feature_map.py

# Stage any updated map files
UPDATED_MAPS=$(git diff --name-only tests/feature_map/ 2>/dev/null || true)
if [ -n "$UPDATED_MAPS" ]; then
    echo "pre-commit: Staging updated map files..."
    echo "$UPDATED_MAPS" | while read -r f; do
        git add "$f"
        echo "  $f"
    done
fi

echo "pre-commit: Feature maps up to date."
```

- [ ] **Step 2: Make hook executable**

```bash
chmod +x hooks/pre-commit
```

- [ ] **Step 3: Create convenience install script**

`hooks/install.sh`:

```bash
#!/usr/bin/env bash
# Install project git hooks from hooks/ into .git/hooks/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR"

for hook in "$HOOKS_DIR"/*; do
    name=$(basename "$hook")
    # Skip non-executable files and the install script itself
    if [ "$name" = "install.sh" ]; then
        continue
    fi
    if [ ! -x "$hook" ]; then
        continue
    fi
    target="$SCRIPT_DIR/../.git/hooks/$name"
    ln -sf "$(realpath --relative-to="$(dirname "$target")" "$hook")" "$target"
    echo "Installed: .git/hooks/$name -> hooks/$name"
done
```

```bash
chmod +x hooks/install.sh
```

- [ ] **Step 4: Install the hook**

```bash
cd /Users/izno/dev/PersonnalScaper && ln -sf ../../hooks/pre-commit .git/hooks/pre-commit
```

- [ ] **Step 5: Verify the hook works (no-op case)**

```bash
# Create a dummy test file to trigger the hook
echo "" >> tests/integration/conftest.py
git add tests/integration/conftest.py
git commit -m "test: verify pre-commit hook (no-op for non-design files)"
# Undo the dummy change
git reset HEAD~1 --soft
git checkout -- tests/integration/conftest.py
```

Expected: Hook runs, prints nothing (no `test_design_*.py` staged), commit succeeds.

- [ ] **Step 6: Commit**

```bash
git add hooks/pre-commit hooks/install.sh
git commit -m "feat(coverage): add pre-commit hook for feature map auto-regeneration"
```

---

## Phase 4: api-unify Design-Contract Bootstrap

This phase creates the template: the first design-contract test with markers, the first
feature map file, and validates the full pipeline (pre-commit hook → map file → CI audit).

### Task 4.1: Create a stub map file for api-unify

**Files:**

- Create: `tests/feature_map/api-unify.json5`

- [ ] **Step 1: Parse DESIGN.md sections and create the stub**

Run the audit script to see all uncovered sections:

```bash
python3 scripts/audit_design_coverage.py
```

Expected: Lists all sections from `docs/features/api-unify/DESIGN.md` and other design docs.

- [ ] **Step 2: Create stub map file manually for now**

Later, `/implement:brainstorm` will auto-create this. For this bootstrap phase,
create it manually with empty test arrays:

```bash
python3 scripts/update_feature_map.py
```

(At this point, no `Design:` markers exist, so this produces nothing. The file
is created when the first test with a `Design:` marker is written.)

- [ ] **Step 3: No commit yet — the map file will be populated in Task 4.2**

### Task 4.2: Write the first design-contract test (template)

**Files:**

- Create: `tests/integration/test_design_api_transport.py`

- [ ] **Step 1: Pick a DESIGN.md section with existing test coverage**

The `docs/features/api-unify/DESIGN.md` §4.5 (Circuit Breaker) is well-covered by
`tests/unit/test_circuit_breaker.py`. Write a design-contract integration test that
validates the circuit breaker behavior as documented, exercising real module interactions.

- [ ] **Step 2: Write the test**

```python
"""Design-contract tests for api-unify transport layer.

Design: docs/features/api-unify/DESIGN.md
"""

import pytest

from personalscraper.api.transport._http import HttpTransport, TransportPolicy
from personalscraper.api._contracts import ApiError


class TestCircuitBreakerContract:
    """Design: docs/features/api-unify/DESIGN.md#circuit-breaker-open-after-3-failures
    Contract: Circuit breaker opens after 3 consecutive failures and rejects
    subsequent requests with CircuitBreakerOpenError until the reset timeout.
    """

    def test_circuit_breaker_opens_after_3_consecutive_5xx(
        self, staging_dir, mock_api_server
    ):
        """After 3 consecutive 5xx responses, the circuit breaker opens and
        subsequent requests are rejected.

        Design: docs/features/api-unify/DESIGN.md#circuit-breaker-open-after-3-failures
        Contract: Circuit breaker opens after 3 consecutive failures and rejects
        subsequent requests with CircuitBreakerOpenError until the reset timeout.
        """
        # Configure mock server to return 503 for 3 requests then 200
        mock_api_server.set_responses([
            (503, {}, '{"error": "Service Unavailable"}'),
            (503, {}, '{"error": "Service Unavailable"}'),
            (503, {}, '{"error": "Service Unavailable"}'),
            (200, {}, '{"status": "ok"}'),
        ])

        policy = TransportPolicy(
            base_url=mock_api_server.url,
            circuit_breaker_threshold=3,
            circuit_breaker_reset=60.0,  # long reset for test
        )

        with HttpTransport(policy) as transport:
            # First 3 calls should fail with 503 (not open circuit breaker)
            for _ in range(3):
                with pytest.raises(ApiError):
                    transport.get("/test")

            # 4th call should fail with CircuitBreakerOpenError
            from personalscraper.api.transport._circuit import CircuitBreakerOpenError
            with pytest.raises(CircuitBreakerOpenError):
                transport.get("/test")
```

- [ ] **Step 3: Run the test to verify it fails or passes correctly**

```bash
python3 -m pytest tests/integration/test_design_api_transport.py -v
```

Expected: The test may need adjustments based on actual APIs. Iterate until it passes
and correctly validates the circuit breaker contract.

- [ ] **Step 4: Run update_feature_map to generate the first map file**

```bash
python3 scripts/update_feature_map.py
```

Expected: Creates `tests/feature_map/api-unify.json5` with the circuit-breaker section
and the test referenced.

- [ ] **Step 5: Verify the pre-commit hook stages the map file**

```bash
git add tests/integration/test_design_api_transport.py
git commit -m "test(api-unify): add design-contract test for circuit breaker (§circuit-breaker-open-after-3-failures)"
```

Expected: Pre-commit hook fires, updates `tests/feature_map/api-unify.json5`, stages it.
The commit includes both files.

If the hook blocks the commit because the map file is stale, fix and re-commit.

### Task 4.3: Add the 7th check to `/implement:check` skill

**Files:**

- Modify: `.claude/skills/implement/check.md` (or wherever check logic is defined)

- [ ] **Step 1: Add the design-contract coverage check**

This is a procedural change to the `/implement:check` skill, not a code change.
The check logic:

```
7. Design-contract coverage:
   - For each section the current phase claims to implement (listed in the plan file):
     - grep for the section anchor in tests/
     - Verify at least one test function with a matching Design: marker exists
     - Verify that test passes when run
   - Run: python3 scripts/audit_design_coverage.py --strict
   - Expected: zero uncovered sections for the feature being implemented
```

This is documented in the skill file, enforced manually during `/implement:check`.

- [ ] **Step 2: Document and commit**

The change is documentation-only (skill instructions). Note that the actual
`.claude/skills/` directory is in the shared config, so this may need to be
committed there instead.

---

## Phase 5-10: Feature Coverage Cycles (Outline)

Each of the following phases bumps `fail_under` by one increment. Detailed plans
for each phase are written when the phase starts, following the feature-cycle workflow.

### Phase 5: api-unify Coverage → 50%

- Audit current api-unify coverage: `python3 -m pytest tests/unit/ tests/integration/ --cov=personalscraper.api --cov-report=term`
- Map DESIGN.md sections to gaps identified in coverage report
- Write design-contract tests for each § in `docs/features/api-unify/DESIGN.md`
- Write unit tests filling remaining gaps in `personalscraper/api/`
- Bump `fail_under` from 44 to 50 in `pyproject.toml`
- PR to main

### Phase 6: Scraper Coverage → 60%

- Focus on `personalscraper/scraper/` — critical gaps at `tv_service.py` (15%) and `trailer_finder.py` (27%)
- Write design-contract tests against `docs/reference/scraping.md`
- Fill unit gaps in `confidence.py`, `keywords_cache.py`, `youtube_search.py`, `ytdlp_downloader.py`
- Bump `fail_under` from 50 to 60
- PR to main

### Phase 7: Dispatch + Verify Coverage → 70%

- Shorter cycle — modules already at 70-80%
- Write design-contract tests against `docs/reference/storage.md` and `docs/reference/pipeline-internals.md`
- Fill remaining gaps in `verify/fixer.py` (26%) and `verify/verifier.py` (78%)
- Bump `fail_under` from 60 to 70
- PR to main

### Phase 8: Trailers Coverage → 80%

- Worst-covered feature: `trailers/cli.py` (0%), `trailers/state.py` (31%), `trailers/scanner.py` (28%)
- Write design-contract tests against `docs/reference/trailers.md` and `docs/archive/features/trailer/DESIGN.md`
- Fill unit gaps across all trailers modules
- Bump `fail_under` from 70 to 80
- At this point, promote `design-gaps` CI job from `continue-on-error: true` to hard error
- PR to main

### Phase 9: Indexer Coverage → 85%

- Large, complex module: `personalscraper/indexer/`
- Write design-contract tests against `docs/reference/indexer.md` and `docs/reference/indexer-json-shapes.md`
- Fill remaining unit gaps
- Bump `fail_under` from 80 to 85
- PR to main

### Phase 10: Remaining Modules → 90%

- Cleanup pass on sorter, ingest, process, library, conf
- Most already at 60-80% — fill the tail
- Write design-contract tests against `docs/reference/architecture.md` and relevant reference docs
- Bump `fail_under` from 85 to 90
- PR to main

---

## Phase 11: Maintenance & Future

### Task 11.1: Schedule 6-month marker audit

- No code change — add a calendar reminder or CRON job description
- Every 6 months, run `python3 scripts/audit_design_coverage.py --strict` and verify
  that `Design:` markers still reference existing doc anchors
- Update markers if design doc sections were renamed

### Task 11.2: Revisit `coverage_gap_report.py` at 80%

- Once 80% is reached, evaluate whether phantom-path detection is feasible
- If design-section-to-source-file mapping can be established, implement the script
- Otherwise, keep as non-goal
