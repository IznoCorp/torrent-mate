# Phase 05 — ACCEPTANCE.md + Final Gate

**Goal:** Write the executable ACCEPTANCE.md with ACC-01..06 from DESIGN §5, bump version to 0.73.0, run the full quality gate (`make check`), and verify all tests pass.

**Design ref:** §5 Acceptance criteria seeds, §6 Test plan (post-merge re-exercise). ACCEPTANCE criteria format per `docs/reference/feature-lifecycle.md`.

## Gate (entry conditions)

- [ ] Phase 01 complete — sync engine + `init-config --sync` working and tested.
- [ ] Phase 02 complete — `config_git.py` + S4 auto-commit tested.
- [ ] Phase 03 complete — verify check + ecosystem test pins + worktree-invariant test.
- [ ] Phase 04 complete — migration script + ecosystem.config.js + deploy.sh + git ops + docs.
- [ ] Post-migration verification: `git ls-files config/` returns 0.

---

## Sub-phase 5.1 — ACCEPTANCE.md

**Commit:** `docs(config-home): add ACCEPTANCE.md with executable ACC-01..06`

**Files:**

- Create: `docs/features/config-home/ACCEPTANCE.md`

Write `docs/features/config-home/ACCEPTANCE.md`:

````markdown
# ACCEPTANCE — Config Home

Feature: config-home (#326)
DESIGN: docs/features/config-home/DESIGN.md
Plan: docs/features/config-home/plan/
Version: 0.73.0

Every criterion is an executable shell command with a documented expected
output. Post-merge re-exercise of every criterion is mandatory before
squash-merge (feature-lifecycle convention).

---

### ACC-01 — canonical dir exists, is a git repo, and repo carries no live config

```bash
test -d ~/.torrentmate/config/.git && \
  test "$(git -C ~/dev/PersonalScraper ls-files config/ | wc -l)" -eq 0 && \
  echo "PASS: canonical exists, is a git repo, repo carries no live config"
```
````

Expected: `PASS: canonical exists, is a git repo, repo carries no live config`

### ACC-02 — every PM2 app points at the canonical config

```bash
node -e "
const e = require('/Users/izno/dev/ecosystem.config.js');
const canonical = '/Users/izno/.torrentmate/config';
const apps = e.apps || [];
const violations = apps
  .filter(a => {
    const cfg = (a.env && a.env.PERSONALSCRAPER_CONFIG) || '';
    return cfg && cfg !== canonical;
  })
  .map(a => a.name + '=' + (a.env && a.env.PERSONALSCRAPER_CONFIG));
if (violations.length === 0) {
  console.log('PASS: all PM2 apps point at ' + canonical);
  process.exit(0);
} else {
  console.log('FAIL: ' + violations.join(', '));
  process.exit(1);
}
"
```

Expected: `PASS: all PM2 apps point at /Users/izno/.torrentmate/config`

### ACC-03 — repo working tree carries 0 tracked config files

```bash
count=$(git -C ~/dev/PersonalScraper ls-files config/ | wc -l | tr -d ' ')
if [ "$count" -eq 0 ]; then
  echo "PASS: 0 tracked config files"
else
  echo "FAIL: $count tracked config files remain"
  git -C ~/dev/PersonalScraper ls-files config/
  exit 1
fi
```

Expected: `PASS: 0 tracked config files`

### ACC-04 — sync is additive and non-destructive (golden test + live dry-run)

```bash
# Golden tests pass
pytest tests/conf/test_sync.py tests/integration/test_init_config_sync.py -v -q && \
  # Live dry-run exits 0
  personalscraper init-config --sync --dry-run && \
  echo "PASS: sync is additive and non-destructive"
```

Expected: `PASS: sync is additive and non-destructive`

### ACC-05 — prod serves the same build after migration (no boot-break)

```bash
local_sha=$(git -C ~/dev/PersonalScraper rev-parse HEAD)
served_sha=$(curl --connect-timeout 10 --max-time 30 -s \
  -H "Cookie: tm_session=$TM_TOKEN" \
  https://tm.iznogoudatall.xyz/api/version | \
  python3 -c "import json,sys; print(json.load(sys.stdin).get('build_commit',''))")
if [ "$served_sha" = "$local_sha" ]; then
  echo "PASS: served_sha=$served_sha matches local_sha=$local_sha"
else
  echo "FAIL: served_sha=$served_sha != local_sha=$local_sha"
  exit 1
fi
```

Expected: `PASS: served_sha=<sha> matches local_sha=<sha>`

Note: Requires `$TM_TOKEN` set in the environment. Skip if deploying from a
different clone (served sha reflects the deployed clone, not dev).

### ACC-06 — S4 save auto-commits to the mini-repo

```bash
# Check that the canonical repo has at least one commit
count=$(git -C ~/.torrentmate/config rev-list --count HEAD 2>/dev/null || echo 0)
if [ "$count" -ge 1 ]; then
  echo "PASS: canonical mini-repo has $count commit(s)"
  git -C ~/.torrentmate/config log --oneline -3
else
  echo "FAIL: canonical mini-repo has no commits"
  exit 1
fi
```

Expected: `PASS: canonical mini-repo has N commit(s)` with recent commits visible

````

- [ ] Commit: `git add docs/features/config-home/ACCEPTANCE.md && git commit -m "docs(config-home): add ACCEPTANCE.md with executable ACC-01..06"`

---

## Sub-phase 5.2 — Version bump

**Commit:** `chore(config-home): bump version to 0.73.0`

**Files:**
- Modify: `pyproject.toml` — version `"0.72.2"` → `"0.73.0"`
- Modify: `personalscraper/__init__.py` or wherever `__version__` is defined — update to `"0.73.0"`

- [ ] Verify: `rg -n '0\.72\.2' pyproject.toml personalscraper/__init__.py` — identify all version strings
- [ ] Replace: `0.72.2` → `0.73.0`
- [ ] Commit: `git add pyproject.toml personalscraper/__init__.py && git commit -m "chore(config-home): bump version to 0.73.0"`

---

## Sub-phase 5.3 — Final quality gate

**No commit** (verification only — gates pass before the PR is created by the main session)

### Tasks

- [ ] **`make lint`**: zero errors.

```bash
make lint
````

Expected: `ruff` and `mypy` both pass with zero errors.

- [ ] **`make test`**: all tests pass, zero failures/errors.

```bash
make test
```

Expected: summary line shows `NNNN passed` with 0 failed, 0 errors. If any ERROR (not FAILED), the test collection crashed — fix imports before proceeding.

- [ ] **`make check`**: lint + test + module-size + typed-api guardrails.

```bash
make check
```

Expected: all gates green.

- [ ] **Residual import grep**: for any module deleted or moved in this feature, grep both `personalscraper/` and `tests/` for the old import path. For config-home, no modules are deleted, but verify no stale references:

```bash
rg "old_config|dev/PersonalScraper/config" -g '*.py' personalscraper/ tests/ 2>/dev/null || echo "PASS: no stale old-path references"
```

- [ ] **`python -c "import personalscraper"`**: smoke test.

```bash
python -c "import personalscraper; print(personalscraper.__version__)"
```

Expected: prints `0.73.0`.

- [ ] **`python -c "from personalscraper.conf.sync import sync_config_dir; from personalscraper.conf.config_git import commit_config_dir; from personalscraper.verify.config_home import check_config_home; print('All new modules importable')"`** — smoke test for all new modules.

- [ ] **OpenAPI regeneration** (if any web route signature changed): `make openapi` + commit regenerated files. For config-home, the S4 `put_file` route signature is unchanged — no OpenAPI regeneration needed. Verify:

```bash
python -c "from personalscraper.web.routes.config import put_file; print('put_file signature unchanged')"
```

- [ ] **Frontend check** (if any frontend changes): not applicable to config-home (pure backend + ops).

- [ ] **`rg "TODO\|FIXME\|HACK" -g '*.py' personalscraper/conf/sync.py personalscraper/conf/config_git.py personalscraper/verify/config_home.py`** — zero matches in new modules.

---

## Gate (exit conditions — ALL must pass before PR)

- [ ] ACCEPTANCE.md written with 6 executable criteria
- [ ] Version bumped to 0.73.0 in `pyproject.toml` and `__init__.py`
- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass, zero failed/errors
- [ ] `make check` — all gates green
- [ ] No stale old-path references in source or tests
- [ ] `python -c "import personalscraper"` — smoke test with version 0.73.0
- [ ] All new modules importable
- [ ] Post-merge re-exercise of ACC-01..06 planned (per feature-lifecycle convention)
