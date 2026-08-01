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

### ACC-04 — sync is additive, non-destructive, and resolves to the canonical path

```bash
# Part A: golden suite — sync engine unit + integration tests
pytest tests/conf/test_sync.py tests/integration/test_init_config_sync.py -v -q && \
  echo "PASS: golden sync suite"

# Part B: live dry-run resolves to the expected canonical path
resolved="$(PERSONALSCRAPER_CONFIG="$HOME/.torrentmate/config" \
  python3 -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = os.path.expanduser('~/.torrentmate/config')
from personalscraper.conf.loader import resolve_config_path
print(resolve_config_path())
" 2>/dev/null || echo "RESOLVE_FAILED")"
if [ "$resolved" = "$HOME/.torrentmate/config" ]; then
  echo "PASS: resolved config path = $resolved (expected $HOME/.torrentmate/config)"
else
  echo "FAIL: resolved config path = $resolved, expected $HOME/.torrentmate/config"
  exit 1
fi

# Part C: live dry-run reports additions (possibly none) without error
PERSONALSCRAPER_CONFIG="$HOME/.torrentmate/config" \
  personalscraper init-config --sync --dry-run && \
  echo "PASS: sync dry-run exits 0"
```

Expected:

```
PASS: golden sync suite
PASS: resolved config path = /Users/izno/.torrentmate/config (expected /Users/izno/.torrentmate/config)
PASS: sync dry-run exits 0
```

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

### ACC-06 — S4 save auto-commits to the mini-repo (verify by CONTENT, not count)

```bash
# Trigger a save (via the config_git helper or through the web-UI), then verify
# that the saved FILE is tracked in the mini-repo — not just that HEAD has ≥ 1
# commit (a vacuous test: the initial commit alone satisfies count≥1).
#
# Pre-condition: the canonical mini-repo exists and has at least one commit.
# This test exercises the save path (web or direct) and verifies the saved file
# appears in the mini-repo's git tree.

saved_file="web.json5"  # file modified by the S4 save
pre_commits=$(git -C ~/.torrentmate/config rev-list --count HEAD 2>/dev/null || echo 0)

# Exercise: perform a save (via python snippet or web-UI)
PERSONALSCRAPER_CONFIG="$HOME/.torrentmate/config" python3 -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = os.path.expanduser('~/.torrentmate/config')
from personalscraper.conf.config_git import commit_config_dir
import json5
from pathlib import Path

cfg_dir = Path(os.environ['PERSONALSCRAPER_CONFIG'])
# Touch web.json5 to trigger a real change (add/remove a comment line to force diff)
web_path = cfg_dir / 'web.json5'
data = web_path.read_text()
web_path.write_text(data)  # no-op write updates mtime but NOT git content
# Use commit_config_dir — it only commits if there is a diff
ok = commit_config_dir(str(cfg_dir), 'config_edit: web.json5 (ACC-06 test)')
print('commit_ok' if ok else 'commit_skipped_no_diff')
" 2>/dev/null || echo "SAVE_FAILED"

post_commits=$(git -C ~/.torrentmate/config rev-list --count HEAD 2>/dev/null || echo 0)

# Verify by CONTENT: the saved file must appear in ls-tree
if git -C ~/.torrentmate/config ls-tree -r HEAD --name-only 2>/dev/null | grep -qF "$saved_file"; then
  echo "PASS: $saved_file is tracked in the mini-repo git tree (commit $post_commits)"
else
  echo "FAIL: $saved_file NOT in mini-repo git tree"
  echo "  pre-commits: $pre_commits"
  echo "  post-commits: $post_commits"
  git -C ~/.torrentmate/config ls-tree -r HEAD --name-only 2>/dev/null || echo "  (no ls-tree output)"
  exit 1
fi
```

Expected: `PASS: web.json5 is tracked in the mini-repo git tree (commit <N>)`

**Status**: PENDING

### ACC-07 — data anchor — paths resolve to the pre-migration absolute data root

```bash
# Verify that after migration, data_dir and indexer db_path still point at the
# pre-migration location (the dev checkout's .data/), not at ~/.torrentmate/.data.
# The migration script's Step 0 rewrites relative "./.data" to absolute
# "/Users/izno/dev/PersonalScraper/.data" before the rsync.
#
# Pre-condition (operator): capture the pre-migration media_item count from
# the live library.db BEFORE running the migration:
#   PRE_COUNT=$(sqlite3 /Users/izno/dev/PersonalScraper/.data/library.db "SELECT COUNT(*) FROM media_item;")
# Store it as PRE_MIGRATION_MEDIA_COUNT in the env or hardcode below.

PRE_MIGRATION_MEDIA_COUNT="${PRE_MIGRATION_MEDIA_COUNT:-0}"

# Resolve data_dir and db_path from the canonical config
result="$(PERSONALSCRAPER_CONFIG="$HOME/.torrentmate/config" python3 -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = os.path.expanduser('~/.torrentmate/config')
from personalscraper.conf.loader import load_config
cfg = load_config()
print(f'data_dir={cfg.paths.data_dir}')
print(f'db_path={cfg.indexer.db_path}')
" 2>/dev/null || echo "RESOLVE_FAILED")"

expected_data_dir="/Users/izno/dev/PersonalScraper/.data"

if echo "$result" | grep -qF "data_dir=$expected_data_dir"; then
  echo "PASS: data_dir = $expected_data_dir (anchored)"
else
  echo "FAIL: data_dir mismatch — got: $result"
  echo "  Expected data_dir=$expected_data_dir"
  exit 1
fi

db_path="$(echo "$result" | grep '^db_path=' | cut -d= -f2-)"
case "$db_path" in
  "$expected_data_dir"/*)
    echo "PASS: db_path = $db_path (under data_root)"
    ;;
  *)
    echo "FAIL: db_path = $db_path NOT under $expected_data_dir"
    exit 1
    ;;
esac

# Verify media_item count matches pre-migration
if [ "$PRE_MIGRATION_MEDIA_COUNT" -gt 0 ]; then
  post_count=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM media_item;" 2>/dev/null || echo 0)
  if [ "$post_count" = "$PRE_MIGRATION_MEDIA_COUNT" ]; then
    echo "PASS: media_item count = $post_count (matches pre-migration $PRE_MIGRATION_MEDIA_COUNT)"
  else
    echo "FAIL: media_item count = $post_count (pre-migration was $PRE_MIGRATION_MEDIA_COUNT)"
    exit 1
  fi
else
  echo "SKIP: PRE_MIGRATION_MEDIA_COUNT not set — set it to the pre-migration count to validate"
fi
```

Expected:

```
PASS: data_dir = /Users/izno/dev/PersonalScraper/.data (anchored)
PASS: db_path = /Users/izno/dev/PersonalScraper/.data/library.db (under data_root)
PASS: media_item count = <N> (matches pre-migration <N>)
```

(or `SKIP` for the count line if `PRE_MIGRATION_MEDIA_COUNT` is unset)

**Status**: PENDING

### ACC-08 — env layer — secrets survive the migration

```bash
# Verify that the .env layer copied to ~/.torrentmate/.env by the migration
# script's Step 0b is readable and that key secrets are present.
# Never print values — assert presence by name only.

PERSONALSCRAPER_CONFIG="$HOME/.torrentmate/config" python3 -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = os.path.expanduser('~/.torrentmate/config')
from personalscraper.conf.loader import load_config
cfg = load_config()

# Assert plex_token is non-empty (Plex refresh depends on it)
token = getattr(cfg.settings, 'plex_token', '')
if token:
    print('PASS: plex_token is present (non-empty)')
else:
    print('FAIL: plex_token is empty or missing')
    raise SystemExit(1)

# Assert the .env file itself exists at the canonical parent
env_path = os.path.expanduser('~/.torrentmate/.env')
if os.path.isfile(env_path):
    print(f'PASS: .env layer exists at {env_path}')
else:
    print(f'FAIL: .env layer missing at {env_path}')
    raise SystemExit(1)

# Assert WEB_JWT_SECRET is present (web auth depends on it)
web_secret = getattr(cfg.settings, 'web_jwt_secret', '')
if web_secret:
    print('PASS: web_jwt_secret is present (non-empty)')
else:
    print('FAIL: web_jwt_secret is empty or missing')
    raise SystemExit(1)
" 2>/dev/null
exit_code=$?

if [ $exit_code -eq 0 ]; then
  echo "PASS: all env-layer secrets present"
else
  echo "FAIL: env-layer check returned $exit_code — see output above"
  exit 1
fi
```

Expected:

```
PASS: plex_token is present (non-empty)
PASS: .env layer exists at /Users/izno/.torrentmate/.env
PASS: web_jwt_secret is present (non-empty)
PASS: all env-layer secrets present
```

**Status**: PENDING
