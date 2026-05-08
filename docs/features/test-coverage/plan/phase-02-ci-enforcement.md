# Phase 2 — CI enforcement (test-cov + design-gaps + monotonic)

**Type**: infra
**Effort**: M (~2 h)
**Entry**: Phase 1 gate done. Local `make test-cov` green.
**Exit**:

- CI `test` job uses `make test-cov` instead of inline pytest invocation.
- New `coverage-monotonic` job rejects PRs that lower `fail_under`.
- New `design-gaps` job runs `audit_design_coverage.py` (warning-mode) + `update_feature_map.py --check`.
- Codecov token policy clarified.

## Task 2.1 — Update `test` job to use `make test-cov`

**Files modified**: `.github/workflows/ci.yml`

The existing `test` job (line ~107) invokes pytest directly with `--cov-fail-under=80`. Replace with `make test-cov` so the threshold is read from `pyproject.toml` via the helper script.

- [ ] **Step 1**: Replace the inline `pytest` invocation with `- run: make test-cov`.
- [ ] **Step 2**: Move codecov upload after `make test-cov` so `coverage.xml` exists.
- [ ] **Step 3**: For `codecov/codecov-action@v4`:
  - Confirm `secrets.CODECOV_TOKEN` is set in repo settings (manual check via `gh secret list`).
  - If not set: change `fail_ci_if_error: true` → `false` and add a comment explaining the constraint.
  - For PRs from forks (`github.event.pull_request.head.repo.fork == true`), force `fail_ci_if_error: false` regardless — forks cannot inherit the secret.
- [ ] **Step 4**: Commit.

```
ci(test-coverage): use make test-cov for the coverage gate
```

## Task 2.2 — Add `coverage-monotonic` job

**Files modified**: `.github/workflows/ci.yml`

New job. Reads `fail_under` from `pyproject.toml` on the PR HEAD and from `origin/main`, fails if HEAD < main.

```yaml
coverage-monotonic:
  name: coverage-monotonic
  runs-on: ubuntu-latest
  if: github.event_name == 'pull_request'
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Install tomli (Python 3.10 fallback)
      run: pip install 'tomli; python_version < "3.11"'
    - name: Verify fail_under is monotonic
      run: |
        head_threshold=$(python3 scripts/get_coverage_threshold.py)
        main_threshold=$(git show origin/${{ github.base_ref }}:pyproject.toml | python3 scripts/get_coverage_threshold.py --stdin)
        echo "HEAD: $head_threshold | base (${{ github.base_ref }}): $main_threshold"
        if [ "$head_threshold" -lt "$main_threshold" ]; then
          if echo "${{ join(github.event.pull_request.labels.*.name, ',') }}" | grep -q 'coverage-rollback'; then
            echo "::warning::fail_under decreased ($main_threshold → $head_threshold) — rollback acknowledged via label."
            exit 0
          fi
          echo "::error::fail_under decreased ($main_threshold → $head_threshold). Add 'coverage-rollback' label to override."
          exit 1
        fi
```

- [ ] **Step 1**: Add the job.
- [ ] **Step 2**: Validate YAML: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`.
- [ ] **Step 3**: Commit.

```
ci(test-coverage): add coverage-monotonic ratchet job
```

## Task 2.3 — Add `design-gaps` job

**Files modified**: `.github/workflows/ci.yml`

```yaml
design-gaps:
  name: design-gaps
  runs-on: ubuntu-latest
  needs: [] # reads tests/feature_map/ + design docs only; no .coverage artifact needed
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
    - run: pip install -e ".[dev]"
    - name: Map freshness check
      run: python3 scripts/update_feature_map.py --check
    - name: Design coverage audit
      run: python3 scripts/audit_design_coverage.py
      continue-on-error: true # warning-mode; promoted to hard error in Phase 8
```

- [ ] **Step 1**: Add the job.
- [ ] **Step 2**: Validate YAML.
- [ ] **Step 3**: Commit.

```
ci(test-coverage): add design-gaps job (warning-mode)
```

## Task 2.4 — Phase 2 gate

- [ ] All YAML valid.
- [ ] CI green on the PR (the new jobs at least _run_ — `design-gaps` may print warnings, that's expected).
- [ ] `coverage-monotonic` correctly accepts the bump from 80 → 44 IF the PR carries `coverage-rollback` label (or document that this PR is the rebaselining one).
- [ ] Single milestone commit:

```
chore(test-coverage): phase 2 gate — CI enforcement done
```
