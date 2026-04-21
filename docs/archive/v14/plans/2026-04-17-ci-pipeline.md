# CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete CI pipeline to PersonalScraper with linting, strict type checking, tests, coverage, secret detection, dependency audit, and license checks.

**Architecture:** Two-stage GitHub Actions pipeline with fast-fail. Stage 1 (lint, mypy, gitleaks, licenses) gates Stage 2 (pytest matrix 3.10-3.13 + pip-audit). Two sequential PRs: mypy corrections first, then CI config.

**Tech Stack:** GitHub Actions, ruff, mypy (strict), pytest-cov, Codecov, gitleaks, pip-audit, pip-licenses

---

## PR 1: `style/mypy-strict` — "style: mypy types corrections"

### Task 1: Branch setup and dev deps

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Create branch from main**

```bash
git checkout main
git pull origin main
git checkout -b style/mypy-strict
```

- [ ] **Step 2: Add mypy and types-requests to dev deps**

In `pyproject.toml`, replace the `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "types-requests>=2.31.0",
]
```

`types-requests` resolves 12 of the 14 `import-untyped` errors (all `requests` imports).

- [ ] **Step 3: Add mypy config to pyproject.toml**

Append after the `[tool.ruff.lint.pydocstyle]` section:

```toml
[tool.mypy]
python_version = "3.10"
strict = true
packages = ["personalscraper"]
warn_return_any = true
warn_unused_configs = true

[[tool.mypy.overrides]]
module = ["guessit", "guessit.*"]
ignore_missing_imports = true
```

The `guessit` override handles the 2 remaining `import-untyped` errors (guessit has no type stubs and never will — it's a regex-heavy library).

- [ ] **Step 4: Install updated deps**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 5: Verify baseline — count remaining errors**

```bash
python -m mypy personalscraper/ 2>&1 | tail -1
```

Expected: `Found ~167 errors in ~28 files` (down from 183 — the 14 `import-untyped` and 2 `guessit` errors are gone).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml
git commit -m "style: add mypy strict config and type stubs"
```

---

### Task 2: Fix cli.py — state dict typing (51 attr-defined + 14 misc + 6 others)

This is the largest file (71 errors). The root cause is:

- `state = {"console": Console(), "verbose": False, "quiet": False}` — values typed as `object`
- Typer's `@app.command()` decorator has no type stubs

**Files:**

- Modify: `personalscraper/cli.py`

- [ ] **Step 1: Read cli.py to understand the state usage pattern**

```bash
python -m mypy personalscraper/cli.py 2>&1 | head -80
```

Understand the error patterns before making changes.

- [ ] **Step 2: Add TypedDict for state and fix console typing**

At the top of `cli.py`, after the imports, replace the `state` dict:

```python
from typing import TypedDict

class _State(TypedDict):
    console: Console
    verbose: bool
    quiet: bool

state: _State = {"console": Console(), "verbose": False, "quiet": False}
```

This fixes all 51 `attr-defined` errors (mypy now knows `state["console"]` is `Console`).

- [ ] **Step 3: Fix Typer untyped decorator errors**

For each `@app.command()` decorated function, the decorator makes the function untyped. Add `# type: ignore[misc]` on each `@app.command()` line. There are 14 such decorators in cli.py:

```python
@app.command()  # type: ignore[misc]
def ingest(...) -> None:
```

Apply to all `@app.command()` and `@app.callback()` decorators in the file.

- [ ] **Step 4: Fix remaining cli.py errors**

Fix any remaining `type-arg`, `no-untyped-def`, `name-defined`, or `arg-type` errors in cli.py. These are typically:

- `dict` → `dict[str, Any]` for generic types
- Missing return type annotations on helper functions
- Missing import for `re` if used

- [ ] **Step 5: Verify cli.py is clean**

```bash
python -m mypy personalscraper/cli.py 2>&1
```

Expected: `Success: no issues found`

- [ ] **Step 6: Commit**

```bash
git add personalscraper/cli.py
git commit -m "style: fix mypy strict types in cli.py"
```

---

### Task 3: Fix scraper/ module (44 errors across 10 files)

The scraper module has the second-most errors. Patterns:

- `type-arg`: `dict` → `dict[str, Any]` (nfo_generator, tvdb_client, tmdb_client, episode_manager, providers)
- `no-any-return`: functions returning API response values without cast (tvdb_client, nfo_generator)
- `no-untyped-def`: missing return annotations (tvdb_client)
- `attr-defined`: accessing dict values typed as `object` (scraper, artwork)

**Files:**

- Modify: `personalscraper/scraper/providers.py` (3 errors)
- Modify: `personalscraper/scraper/nfo_generator.py` (13 errors)
- Modify: `personalscraper/scraper/tvdb_client.py` (17 errors)
- Modify: `personalscraper/scraper/tmdb_client.py` (17 errors)
- Modify: `personalscraper/scraper/episode_manager.py` (5 errors)
- Modify: `personalscraper/scraper/artwork.py` (6 errors)
- Modify: `personalscraper/scraper/scraper.py` (7 errors)
- Modify: `personalscraper/scraper/http_retry.py` (2 errors)
- Modify: `personalscraper/scraper/circuit_breaker.py` (2 errors)
- Modify: `personalscraper/scraper/mediainfo.py` (1 error)

- [ ] **Step 1: Fix providers.py — 3 type-arg errors**

Add type parameters to all bare `dict` annotations:

```python
# Before
def get_movie(self, tmdb_id: int) -> dict:
# After
def get_movie(self, tmdb_id: int) -> dict[str, Any]:
```

Read each file, identify bare `dict` and `list` annotations, add proper type parameters.

- [ ] **Step 2: Fix nfo_generator.py — 13 errors (11 type-arg + 2 no-any-return)**

- Add type parameters to all bare `dict` annotations (11 errors)
- For `no-any-return` errors: add explicit `str()` cast or `assert isinstance()` before return

- [ ] **Step 3: Fix tvdb_client.py — 17 errors**

- Add type parameters to bare `dict` (type-arg)
- Add return type annotations to untyped functions (no-untyped-def)
- Fix `no-any-return` with explicit casts
- `import-untyped` already handled by `types-requests` in Task 1

- [ ] **Step 4: Fix tmdb_client.py — 17 errors**

Same patterns as tvdb_client.py: bare `dict`, missing annotations, `no-any-return`.

- [ ] **Step 5: Fix remaining scraper files**

Fix episode_manager.py (5), artwork.py (6), scraper.py (7), http_retry.py (2), circuit_breaker.py (2), mediainfo.py (1). Same patterns: `type-arg` and `attr-defined`.

- [ ] **Step 6: Verify scraper/ is clean**

```bash
python -m mypy personalscraper/scraper/ 2>&1
```

Expected: `Success: no issues found`

- [ ] **Step 7: Run tests to verify no regressions**

```bash
python -m pytest tests/scraper/ -x -q
```

Expected: all tests pass (type annotations don't change runtime behavior, but verify anyway).

- [ ] **Step 8: Commit**

```bash
git add personalscraper/scraper/
git commit -m "style: fix mypy strict types in scraper module"
```

---

### Task 4: Fix remaining modules (22 errors across 16 files)

**Files:**

- Modify: `personalscraper/library/models.py` (3 errors)
- Modify: `personalscraper/library/reporter.py` (5 errors)
- Modify: `personalscraper/library/disk_cleaner.py` (1 error)
- Modify: `personalscraper/library/analyzer.py` (4 errors)
- Modify: `personalscraper/library/scanner.py` (1 error)
- Modify: `personalscraper/library/validator.py` (1 error)
- Modify: `personalscraper/sorter/cleaner.py` (3 errors — 1 type-arg + 1 no-any-return + 1 import-untyped already handled)
- Modify: `personalscraper/pipeline.py` (3 errors)
- Modify: `personalscraper/enforce/run.py` (5 errors)
- Modify: `personalscraper/logger.py` (2 errors)
- Modify: `personalscraper/ingest/tracker.py` (2 errors)
- Modify: `personalscraper/dispatch/media_index.py` (2 errors)
- Modify: `personalscraper/dispatch/dispatcher.py` (1 error)
- Modify: `personalscraper/verify/checker.py` (1 error)
- Modify: `personalscraper/naming_patterns.py` (1 error — `name-defined` for missing `re` import)
- Modify: `personalscraper/notifier.py` (1 error — import-untyped already handled)
- Modify: `personalscraper/process/reclean.py` (1 error — import-untyped already handled)
- Modify: `personalscraper/models.py` (1 error — type-arg)
- Modify: `personalscraper/ingest/qbit_client.py` (1 error — import-untyped already handled)
- Modify: `personalscraper/ingest/ingest.py` (1 error — import-untyped already handled)

- [ ] **Step 1: Fix library/ module (15 errors)**

- `library/models.py`: fix `call-overload` on `asdict()` — add proper type annotation or cast
- `library/reporter.py`: add type params to 4 bare `dict` + 1 bare `list`
- `library/analyzer.py`: fix 4 errors (likely `type-arg` and `attr-defined`)
- `library/disk_cleaner.py`, `library/scanner.py`, `library/validator.py`: 1 error each (bare generics)

- [ ] **Step 2: Fix pipeline.py, enforce/run.py, logger.py**

- `pipeline.py` (3 errors): bare `dict` type params
- `enforce/run.py` (5 errors): bare `dict` type params and `attr-defined`
- `logger.py` (2 errors): fix `arg-type` on structlog `configure()` — cast processor list, fix `no-any-return` on `get_logger()`

- [ ] **Step 3: Fix remaining scattered files**

- `naming_patterns.py`: add `import re` (name-defined error)
- `ingest/tracker.py`: bare `dict` type params
- `dispatch/media_index.py`: bare `list` type params
- `dispatch/dispatcher.py`: 1 error
- `verify/checker.py`: add type annotation to `results` variable
- `sorter/cleaner.py`: fix `no-any-return`
- `models.py`: bare `dict` type params
- Files with only `import-untyped` (already handled by types-requests and guessit override): verify they're clean

- [ ] **Step 4: Full mypy check — zero errors**

```bash
python -m mypy personalscraper/ 2>&1
```

Expected: `Success: no issues found in 65 source files`

- [ ] **Step 5: Full test suite — no regressions**

```bash
python -m pytest -x -q
```

Expected: `1215 passed` (or similar — all unit tests pass)

- [ ] **Step 6: Ruff lint — no new issues**

```bash
python -m ruff check personalscraper/ tests/
```

Expected: clean (type annotation changes shouldn't introduce lint issues)

- [ ] **Step 7: Commit**

```bash
git add personalscraper/
git commit -m "style: fix mypy strict types in remaining modules"
```

---

### Task 5: Create PR and merge

- [ ] **Step 1: Push branch**

```bash
git push -u origin style/mypy-strict
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "style: mypy types corrections" --body "$(cat <<'EOF'
## Summary
- Add mypy strict mode config to pyproject.toml
- Add types-requests stub package
- Fix 183 mypy strict violations across 30 files
- Zero mypy errors, all tests pass

## Changes by category
- **type-arg (74):** Added type parameters to bare `dict` and `list` generics
- **attr-defined (54):** Fixed state dict typing in cli.py with TypedDict
- **import-untyped (14):** Added types-requests, guessit override in mypy config
- **misc (14):** Added type: ignore for Typer untyped decorators
- **Other (27):** no-any-return casts, missing annotations, name-defined fixes

## Test plan
- [ ] `python -m mypy personalscraper/` passes with zero errors
- [ ] `python -m pytest -x -q` — all 1215 tests pass
- [ ] `ruff check personalscraper/ tests/` — clean
EOF
)"
```

- [ ] **Step 3: Merge after review**

Merge PR into `main`. This must be done before the CI PR (chore/CI) so that mypy strict passes on the first CI run.

---

## PR 2: `chore/CI` — "chore: add complete CI pipeline"

### Task 6: Branch setup and pyproject.toml updates

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Create branch from main (after mypy PR is merged)**

```bash
git checkout main
git pull origin main
git checkout -b chore/CI
```

- [ ] **Step 2: Add CI-only dev deps to pyproject.toml**

Update `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "types-requests>=2.31.0",
    "pip-audit>=2.7.0",
    "pip-licenses>=4.0.0",
]
```

- [ ] **Step 3: Add coverage config to pyproject.toml**

Append after the `[tool.mypy]` section:

```toml
[tool.coverage.run]
source = ["personalscraper"]
omit = ["personalscraper/__main__.py"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add coverage config and CI dev deps"
```

---

### Task 7: Create CI workflow

**Files:**

- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create directory**

```bash
mkdir -p ".github/workflows"
```

- [ ] **Step 2: Write ci.yml**

```yaml
name: CI

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: read

jobs:
  # ── Stage 1: Fast checks (parallel) ───────────────────
  lint:
    name: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-3.13-${{ hashFiles('pyproject.toml') }}
          restore-keys: pip-${{ runner.os }}-3.13-
      - run: pip install ruff
      - run: ruff check personalscraper/ tests/
      - run: ruff format --check personalscraper/ tests/

  typecheck:
    name: typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: actions/cache@v4
        with:
          path: |
            ~/.cache/pip
            .mypy_cache
          key: pip-mypy-${{ runner.os }}-3.13-${{ hashFiles('pyproject.toml') }}
          restore-keys: pip-mypy-${{ runner.os }}-3.13-
      - run: pip install -e ".[dev]"
      - run: mypy personalscraper/

  secrets:
    name: secrets
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Install gitleaks
        run: |
          curl -sSfL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_8.24.3_linux_x64.tar.gz | tar xz
          sudo mv gitleaks /usr/local/bin/
      - name: Scan PR commits for secrets
        run: |
          gitleaks detect --source . --log-opts="${{ github.event.pull_request.base.sha }}..${{ github.event.pull_request.head.sha }}" --verbose

  licenses:
    name: licenses
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-3.13-${{ hashFiles('pyproject.toml') }}
          restore-keys: pip-${{ runner.os }}-3.13-
      - run: pip install -e . pip-licenses
      - run: pip-licenses --allow-only="MIT;BSD*;Apache*;ISC;PSF;LGPL*;Python*;MPL*"

  # ── Stage 2: Tests & security (depend on Stage 1) ─────
  test:
    name: test (${{ matrix.python-version }})
    runs-on: ubuntu-latest
    needs: [lint, typecheck, secrets, licenses]
    strategy:
      fail-fast: true
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('pyproject.toml') }}
          restore-keys: pip-${{ runner.os }}-${{ matrix.python-version }}-
      - run: pip install -e ".[dev]"
      - run: python -m pytest -v --cov=personalscraper --cov-report=xml --cov-report=term --cov-fail-under=80
      - uses: codecov/codecov-action@v4
        if: matrix.python-version == '3.13'
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: coverage.xml
          fail_ci_if_error: true

  security:
    name: security
    runs-on: ubuntu-latest
    needs: [lint, typecheck, secrets, licenses]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-3.13-${{ hashFiles('pyproject.toml') }}
          restore-keys: pip-${{ runner.os }}-3.13-
      - run: pip install -e . pip-audit
      - run: pip-audit
```

- [ ] **Step 3: Verify YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

If `pyyaml` is not installed: `pip install pyyaml` first, or use an online YAML validator.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: add CI workflow with 2-stage pipeline"
```

---

### Task 8: Create gitleaks config and full-scan workflow

**Files:**

- Create: `.gitleaks.toml`
- Create: `.github/workflows/gitleaks-full.yml`

- [ ] **Step 1: Write .gitleaks.toml**

```toml
[extend]
useDefault = true

[allowlist]
paths = [
    '''.env\.example''',
    '''assets/torrents/''',
    '''docs/''',
]
```

- [ ] **Step 2: Write gitleaks-full.yml**

```yaml
name: Gitleaks Full History Scan

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  scan-history:
    name: scan-history
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Install gitleaks
        run: |
          curl -sSfL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_8.24.3_linux_x64.tar.gz | tar xz
          sudo mv gitleaks /usr/local/bin/
      - name: Run gitleaks on full history
        run: |
          gitleaks detect --source . --verbose --report-format json --report-path gitleaks-report.json
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gitleaks-report
          path: gitleaks-report.json
          retention-days: 90
```

- [ ] **Step 3: Commit**

```bash
git add .gitleaks.toml .github/workflows/gitleaks-full.yml
git commit -m "chore: add gitleaks config and full history scan workflow"
```

---

### Task 9: Add README badges

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Add badges at top of README.md**

Insert after line 1 (`# PersonalScraper`), before the description paragraph:

```markdown
![CI](https://github.com/LounisBou/personal-scraper/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/LounisBou/personal-scraper/badge.svg)](https://codecov.io/gh/LounisBou/personal-scraper)
```

The file should start:

```markdown
# PersonalScraper

![CI](https://github.com/LounisBou/personal-scraper/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/LounisBou/personal-scraper/badge.svg)](https://codecov.io/gh/LounisBou/personal-scraper)

Pipeline d'automatisation media — ingestion, tri, scraping, verification, dispatch.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "chore: add CI and coverage badges to README"
```

---

### Task 10: Create PR and merge

- [ ] **Step 1: Push branch**

```bash
git push -u origin chore/CI
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "chore: add complete CI pipeline" --body "$(cat <<'EOF'
## Summary
- 2-stage GitHub Actions CI: fast checks gate test matrix
- Stage 1: ruff lint/format, mypy strict, gitleaks secrets, pip-licenses
- Stage 2: pytest matrix (3.10-3.13) with 80% coverage gate, pip-audit, Codecov
- Gitleaks full history scan (manual dispatch)
- README badges (CI status + Codecov)

## Files
- `.github/workflows/ci.yml` — Main CI workflow
- `.github/workflows/gitleaks-full.yml` — One-shot history scan
- `.gitleaks.toml` — Gitleaks allowlist config
- `pyproject.toml` — Coverage config, CI dev deps
- `README.md` — CI and coverage badges

## Test plan
- [ ] CI runs on this PR (self-test)
- [ ] Stage 1 jobs pass: lint, typecheck, secrets, licenses
- [ ] Stage 2 jobs pass: test (3.10-3.13), security
- [ ] Coverage uploads to Codecov
- [ ] Badges render correctly after merge
EOF
)"
```

- [ ] **Step 3: Verify CI passes on this PR**

The CI workflow triggers on this PR itself — all 9 jobs should pass. If any fail, fix and push.

- [ ] **Step 4: Merge after CI passes**

---

## Post-merge: Branch Protection (manual)

### Task 11: Configure branch protection rules

This is done in GitHub web UI, not via code.

- [ ] **Step 1: Go to GitHub Settings > Branches > Add rule for `main`**

- [ ] **Step 2: Configure rules**

| Setting                                          | Value                                                                                                              |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| Branch name pattern                              | `main`                                                                                                             |
| Require a pull request before merging            | ✅                                                                                                                 |
| Required approvals                               | 0                                                                                                                  |
| Require status checks to pass before merging     | ✅                                                                                                                 |
| Status checks                                    | `lint`, `typecheck`, `secrets`, `licenses`, `test (3.10)`, `test (3.11)`, `test (3.12)`, `test (3.13)`, `security` |
| Require branches to be up to date before merging | ✅                                                                                                                 |
| Do not allow bypassing the above settings        | ❌                                                                                                                 |
| Allow force pushes                               | ❌                                                                                                                 |
| Allow deletions                                  | ❌                                                                                                                 |

- [ ] **Step 3: Save and verify**

Try pushing directly to `main` — should be rejected. Create a test branch, push, verify status checks appear on the PR.

---

## Post-merge: Run gitleaks full scan

### Task 12: Execute one-time history scan

- [ ] **Step 1: Go to Actions tab > "Gitleaks Full History Scan" > "Run workflow"**

- [ ] **Step 2: Review results**

If secrets found: revoke and rotate them immediately. The secrets are in git history forever (unless you rewrite history with `git filter-repo`).

- [ ] **Step 3: Done**

The incremental scan in `ci.yml` prevents future leaks. The full scan only needs to run once.
