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

Expected: `PASS: canonical exists, is a git repo, repo carries no live config`

**Status**: PENDING

### ACC-02 — every PM2 app points at the canonical config

```bash
node -e "
const e = require('/Users/izno/dev/PersonalScraper/ecosystem.config.js');
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

**Status**: PENDING

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

**Status**: PENDING

### ACC-04 — sync is additive and non-destructive (golden test + live dry-run)

```bash
pytest tests/conf/test_sync.py tests/integration/test_init_config_sync.py -v -q && \
  personalscraper init-config --sync --dry-run && \
  echo "PASS: sync is additive and non-destructive"
```

Expected: `PASS: sync is additive and non-destructive`

**Status**: PENDING

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

**Status**: PENDING

### ACC-06 — S4 save auto-commits to the mini-repo

```bash
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

**Status**: PENDING
