# CI Pipeline Design — PersonalScraper

**Date:** 2026-04-17
**Scope:** Complete CI with linting, type checking, tests, coverage, secret detection, dependency audit, license check
**Repo:** `LounisBou/personal-scraper` (private, GitHub)

## Architecture

Two-stage pipeline with fast-fail. Stage 1 (fast checks) must pass entirely before Stage 2 (tests + security) starts.

```
PR → main
  │
  ├─ Stage 1 (parallel, ~30-45s) ──────────────────────────┐
  │  ├─ lint          ruff check + format --check  (py3.13) │
  │  ├─ typecheck     mypy --strict personalscraper/ (3.13) │
  │  ├─ secrets       gitleaks (PR commits only)            │
  │  └─ licenses      pip-licenses whitelist       (py3.13) │
  └─────────────────────────────────────────────────────────┘
                         │ all pass
                         ▼
  ┌─ Stage 2 (parallel, ~2-3min) ──────────────────────────┐
  │  ├─ test-3.10     pytest + cov ≥80% (fail-fast)        │
  │  ├─ test-3.11     pytest + cov ≥80%                    │
  │  ├─ test-3.12     pytest + cov ≥80%                    │
  │  ├─ test-3.13     pytest + cov ≥80% + Codecov upload   │
  │  └─ security      pip-audit                   (py3.13) │
  └─────────────────────────────────────────────────────────┘
```

## Triggers

```yaml
on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]
```

- PRs targeting `main` only
- Direct push to `main` blocked by branch protection (not CI)
- No scheduled runs, no release workflow

## Permissions

```yaml
permissions:
  contents: read
  pull-requests: read
```

Least privilege — no write access needed.

## Stage 1: Fast Checks

### Job `lint`

- **Runner:** ubuntu-latest, Python 3.13
- **Cache:** pip cache via `actions/cache` (key: `hashFiles('pyproject.toml')`)
- **Steps:**
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` (python 3.13)
  3. Restore pip cache
  4. `pip install ruff`
  5. `ruff check personalscraper/ tests/`
  6. `ruff format --check personalscraper/ tests/`

### Job `typecheck`

- **Runner:** ubuntu-latest, Python 3.13
- **Cache:** pip cache + mypy cache (`.mypy_cache/`)
- **Steps:**
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` (python 3.13)
  3. Restore pip cache
  4. `pip install -e ".[dev]" mypy`
  5. `mypy personalscraper/`
  - Config in `pyproject.toml` (`strict = true`, `python_version = "3.10"`)
  - Scope: `personalscraper/` only, not `tests/` (mock/Any noise)

### Job `secrets`

- **Runner:** ubuntu-latest
- **Steps:**
  1. `actions/checkout@v4` with `fetch-depth: 0`
  2. `gitleaks/gitleaks-action@v2` in PR diff mode
  - Scans only commits in the PR (`base..head`)
  - Config: `.gitleaks.toml` (allowlist for `.env.example`, `assets/torrents/`, `docs/`)

### Job `licenses`

- **Runner:** ubuntu-latest, Python 3.13
- **Cache:** pip cache
- **Steps:**
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` (python 3.13)
  3. Restore pip cache
  4. `pip install -e . pip-licenses`
  5. `pip-licenses --allow-only="MIT;BSD*;Apache*;ISC;PSF;LGPL*;Python*;MPL*"`
  - Whitelist: MIT, BSD, Apache-2.0, ISC, PSF, LGPL, Python, MPL (permissive)
  - Blocks: GPL strict, unknown licenses

## Stage 2: Tests & Security

All jobs have `needs: [lint, typecheck, secrets, licenses]`.

### Jobs `test` (matrix)

- **Runner:** ubuntu-latest
- **Matrix:** `python-version: ["3.10", "3.11", "3.12", "3.13"]`
- **Strategy:** `fail-fast: true`
- **Cache:** pip cache (keyed by python version + `hashFiles('pyproject.toml')`)
- **Steps:**
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` (matrix python version)
  3. Restore pip cache
  4. `pip install -e ".[dev]"`
  5. `python -m pytest -v --cov=personalscraper --cov-report=xml --cov-report=term --cov-fail-under=80`
  6. (Python 3.13 only) `codecov/codecov-action@v4` — upload `coverage.xml`
- E2E/roundtrip/idempotence tests excluded by existing `addopts` in `pyproject.toml`
- Codecov upload on Python 3.13 only (single source of truth for coverage reporting)

### Job `security`

- **Runner:** ubuntu-latest, Python 3.13
- **Cache:** pip cache
- **Steps:**
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` (python 3.13)
  3. Restore pip cache
  4. `pip install -e . pip-audit`
  5. `pip-audit`
  - Scans installed deps against PyPI/OSV vulnerability database

## Configuration Changes in `pyproject.toml`

### New dev dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "pip-audit>=2.7.0",
    "pip-licenses>=4.0.0",
]
```

### New mypy config

```toml
[tool.mypy]
python_version = "3.10"
strict = true
packages = ["personalscraper"]
warn_return_any = true
warn_unused_configs = true
```

### New coverage config

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

## Gitleaks Full History Scan

Separate workflow for one-time historical scan.

### File: `.github/workflows/gitleaks-full.yml`

- **Trigger:** `workflow_dispatch` (manual button in GitHub Actions tab)
- **Steps:**
  1. `actions/checkout@v4` with `fetch-depth: 0`
  2. `gitleaks detect --source . --verbose --report-format json --report-path gitleaks-report.json`
  3. Upload report as artifact (90-day retention)

### File: `.gitleaks.toml`

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

## README Badges

Add at top of `README.md`:

```markdown
![CI](https://github.com/LounisBou/personal-scraper/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/LounisBou/personal-scraper/badge.svg)](https://codecov.io/gh/LounisBou/personal-scraper)
```

## GitHub Secrets Required

| Secret          | Purpose                                      |
| --------------- | -------------------------------------------- |
| `CODECOV_TOKEN` | Upload coverage to Codecov (already created) |

## Branch Protection Rules (manual, GitHub Settings)

Configure on `main` branch:

| Rule                                  | Value                                                                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Require a pull request before merging | Yes                                                                                                                |
| Required approvals                    | 0 (solo repo)                                                                                                      |
| Require status checks to pass         | Yes                                                                                                                |
| Status checks required                | `lint`, `typecheck`, `secrets`, `licenses`, `test (3.10)`, `test (3.11)`, `test (3.12)`, `test (3.13)`, `security` |
| Require branches to be up to date     | Yes                                                                                                                |
| Do not allow bypassing                | No (keep admin bypass for emergencies)                                                                             |
| Allow force pushes                    | No                                                                                                                 |
| Allow deletions                       | No                                                                                                                 |

## Pip Cache Strategy

All jobs use `actions/cache@v4` for `~/.cache/pip`:

- **Key:** `pip-{runner.os}-{python-version}-{hashFiles('pyproject.toml')}`
- **Restore keys:** `pip-{runner.os}-{python-version}-` (partial match for dep updates)
- Shared across PRs from the same branch
- Estimated saving: ~30-60s per job

## Implementation Order

Two separate branches/PRs, merged sequentially:

1. **Branch `style/mypy-strict`** — Fix all mypy strict violations (~79 functions missing annotations + implicit Any fixes)
   - PR title: "style: mypy types corrections"
   - Merge into `main` first

2. **Branch `chore/CI`** — All CI files and config
   - `.github/workflows/ci.yml`
   - `.github/workflows/gitleaks-full.yml`
   - `.gitleaks.toml`
   - `pyproject.toml` updates (mypy, coverage, dev deps)
   - `README.md` badges
   - PR title: "chore: add complete CI pipeline"
   - Merge after mypy PR

3. **Branch protection** — Configure manually in GitHub Settings after first successful CI run (so status check names are auto-discovered)

## Out of Scope

- Notifications (Telegram/Slack) on CI failure
- Release/publish workflow
- Nightly scheduled runs
- macOS runner matrix
- E2E/roundtrip tests in CI (require qBittorrent, storage disks, live API keys)
