# Phase 04 — Migration Script + Config Pointer Changes + Docs

**Goal:** Create the one-shot migration script, update every pointer that references the old config path (`ecosystem.config.js`, `deploy.sh`), git-untrack the 5 tracked config files, update `.gitignore`, remove the local `config/` directory, and update reference docs.

**Design ref:** §3.1 Relocation (D1, D2), §3.4 Migration + guard tests, §7 Risks.

## Gate (entry conditions)

- [ ] Phase 01 complete — `personalscraper init-config --sync` works.
- [ ] Phase 02 complete — `config_git.py` and S4 auto-commit ready.
- [ ] Phase 03 tests written (ecosystem test pins updated, worktree-invariant test in place — will pass after this phase's ecosystem.config.js update).

---

## Sub-phase 4.1 — Migration script + `ecosystem.config.js` update

**Commit:** `feat(config-home): add migrate-config-home.sh + update ecosystem.config.js pins`

**Files:**

- Create: `scripts/migrate-config-home.sh`
- Modify: `ecosystem.config.js` — 9 occurrences of `PERSONALSCRAPER_CONFIG`

### Task 4.1.1: Create migration script

```bash
#!/usr/bin/env bash
# scripts/migrate-config-home.sh
# One-shot migration: relocate the canonical config from
# ~/dev/PersonalScraper/config/ to ~/.torrentmate/config/
# (DESIGN §3.1, D1-D2). Idempotent — refuses to run twice.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

CANONICAL="$HOME/.torrentmate/config"
OLD_CONFIG="$HOME/dev/PersonalScraper/config"
ECOSYSTEM_JS="$HOME/dev/ecosystem.config.js"

say() { printf "${GREEN}[migrate-config-home]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[migrate-config-home] WARN${NC} %s\n" "$*" >&2; }
die() { printf "${RED}[migrate-config-home] FATAL${NC} %s\n" "$*" >&2; exit 1; }

# ── Guard 0: idempotence — refuse if canonical already exists with .git ──
if [ -d "$CANONICAL/.git" ]; then
  die "Canonical config already exists at $CANONICAL with a git repo. This script has already been run. Aborting."
fi

# ── Guard 1: old config must exist ──
if [ ! -d "$OLD_CONFIG" ]; then
  die "Old config not found at $OLD_CONFIG. Nothing to migrate."
fi

# ── Guard 2: operator attended confirmation ──
say "This will:"
say "  1. Stop all PM2 writers (torrentmate-web, torrentmate-web-staging, watch, crons)"
say "  2. rsync $OLD_CONFIG → $CANONICAL"
say "  3. git init + initial commit in $CANONICAL"
say "  4. Update ecosystem.config.js PERSONALSCRAPER_CONFIG pins"
say "  5. Restart PM2 with new config"
say "  6. Smoke test (personalscraper --config $CANONICAL info)"
say ""
read -rp "Proceed? [y/N] " REPLY
[[ "$REPLY" =~ ^[Yy]$ ]] || die "Aborted by operator."

# ── Step 1: Stop writers ──
say "Step 1/6: Stopping PM2 writers..."
pm2 stop torrentmate-web torrentmate-web-staging personalscraper-watch 2>/dev/null || true
pm2 stop personalscraper-index-enrich personalscraper-backfill-ids personalscraper-follow-detect 2>/dev/null || true
pm2 stop personalscraper-search personalscraper-grab personalscraper-health-check 2>/dev/null || true
sleep 2

# ── Step 2: rsync config ──
say "Step 2/6: Copying $OLD_CONFIG → $CANONICAL..."
mkdir -p "$CANONICAL"
rsync -a "$OLD_CONFIG/" "$CANONICAL/"

# ── Step 3: git init + initial commit ──
say "Step 3/6: Initializing local git repo..."
git -C "$CANONICAL" init
git -C "$CANONICAL" config user.email "izno@iznoserver"
git -C "$CANONICAL" config user.name "IznoServer Config"
git -C "$CANONICAL" add -A
git -C "$CANONICAL" commit -m "initial commit — config migrated from $OLD_CONFIG"

# ── Step 4: Update ecosystem.config.js pins ──
say "Step 4/6: Updating ecosystem.config.js PERSONALSCRAPER_CONFIG pins..."
# Replace all occurrences of the old path with the new canonical
sed -i '' "s|PERSONALSCRAPER_CONFIG: \"$OLD_CONFIG\"|PERSONALSCRAPER_CONFIG: \"$CANONICAL\"|g" "$ECOSYSTEM_JS"
say "Updated $ECOSYSTEM_JS"

# ── Step 5: Smoke test ──
say "Step 5/6: Smoke test..."
cd "$HOME/dev/PersonalScraper"
if command python -m personalscraper --config "$CANONICAL" info >/dev/null 2>&1; then
  say "Smoke test PASSED — personalscraper boots with $CANONICAL"
else
  die "Smoke test FAILED — personalscraper cannot boot with $CANONICAL. Check config."
fi

# ── Step 6: Restart PM2 ──
say "Step 6/6: Restarting PM2..."
pm2 startOrRestart "$ECOSYSTEM_JS" --update-env
sleep 3

# ── Post-check: /api/version ──
say "Post-check: verifying /api/version..."
if curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}" "https://tm.iznogoudatall.xyz/api/health" | grep -q 200; then
  say "Post-check PASSED — prod web is responding."
else
  warn "Post-check: prod /api/health not 200 yet — check pm2 logs torrentmate-web"
fi

say "Migration complete. Next steps:"
say "  1. Remove old config: rm -rf $OLD_CONFIG (DO THIS MANUALLY after verification)"
say "  2. Set PERSONALSCRAPER_CONFIG=$CANONICAL in your dev shell (.zshrc or equivalent)"
say "  3. Run: personalscraper init-config --sync --dry-run to verify nothing missing"
say "  4. Commit the ecosystem.config.js changes to the repo"
```

### Task 4.1.2: Update ecosystem.config.js

In `/Users/izno/dev/PersonalScraper/ecosystem.config.js`, replace all 9 occurrences of:

```
PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
```

with:

```
PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
```

These appear in the `env:` blocks of these apps:

- `personalscraper-watch` (line 50)
- `torrentmate-web` (line 76)
- `torrentmate-web-staging` (line 97 — if present)
- `personalscraper-index-enrich` (line 133)
- `personalscraper-backfill-ids` (line 147)
- `personalscraper-follow-detect` (line 165)
- `personalscraper-search` (line 181)
- `personalscraper-grab` (line 196)
- `personalscraper-health-check` (line 213)

- [ ] Verify: `rg -n 'PERSONALSCRAPER_CONFIG' ecosystem.config.js` — all occurrences show `~/.torrentmate/config`
- [ ] Commit: `git add scripts/migrate-config-home.sh ecosystem.config.js && git commit -m "feat(config-home): add migrate-config-home.sh + update ecosystem.config.js pins"`

---

## Sub-phase 4.2 — `deploy.sh` + git operations + `.gitignore`

**Commit:** `chore(config-home): update deploy.sh for canonical config + git-untrack live config files`

**Files:**

- Modify: `scripts/deploy.sh` — line 130, resolve `$PERSONALSCRAPER_CONFIG` with fallback to canonical
- Modify: `.gitignore` — add `config/` to gitignore
- Run: `git rm --cached` for the 5 tracked config files

### Task 4.2.1: Update `deploy.sh`

In `scripts/deploy.sh`, change line 130 from:

```bash
web_cfg = (repo / "config" / "web.json5").read_text()
```

to:

```python
config_dir = Path(os.environ.get("PERSONALSCRAPER_CONFIG", str(Path.home() / ".torrentmate" / "config")))
web_cfg = (config_dir / "web.json5").read_text()
```

- [ ] Verify: the JWT-forge post-check still works after this change (it reads `web.json5` from the canonical path)
- [ ] Verify: `rg "repo / \"config\"" scripts/deploy.sh` returns 0 matches (old hardcode gone)

### Task 4.2.2: Git-untrack live config + update `.gitignore`

```bash
# Un-track the 5 files currently tracked in config/
git rm --cached config/config.json5
git rm --cached config/indexer.json5
git rm --cached config/tracker.json5
git rm --cached config/watch_seed.json5
git rm --cached config/web.json5

# Add config/ to .gitignore
echo "config/" >> .gitignore
```

- [ ] Verify: `git -C ~/dev/PersonalScraper ls-files config/ | wc -l` returns `0`
- [ ] Verify: `git status` shows the 5 deletions as staged + `.gitignore` modified
- [ ] Commit: `git add .gitignore config/config.json5 config/indexer.json5 config/tracker.json5 config/watch_seed.json5 config/web.json5 scripts/deploy.sh && git commit -m "chore(config-home): update deploy.sh for canonical config + git-untrack live config files"`

---

## Sub-phase 4.3 — Reference docs + CLAUDE.md pointers

**Commit:** `docs(config-home): update reference docs for canonical config relocation`

**Files:**

- Modify: `CLAUDE.md` — update Web-UI Environments section (the 3-checkout topology description) and add config-home pointer
- Modify: `docs/reference/config-overlay-layout.md` — note the canonical location
- Modify: `docs/reference/web-ui.md` — update any references to `config/` path

### Task 4.3.1: Update CLAUDE.md

In `CLAUDE.md`, find the "Web-UI Environments (ENV-SEP) & Binding Invariants" section. Update the bullet:

```
- Shared between all three: `library.db`, `.data/`, `config/`, storage disks.
```

to:

```
- Shared between all three: `library.db`, `.data/`, storage disks.
- Canonical config at `~/.torrentmate/config` (outside all working trees — see `docs/features/config-home/DESIGN.md` §3.1).
```

In the "Reference Index" table, add:

```
| Config home relocation — canonical location, migration runbook | `docs/features/config-home/DESIGN.md` |
```

### Task 4.3.2: Update `config-overlay-layout.md`

Add a note at the top:

```markdown
> **Canonical location** (≥0.73.0): The live config directory is
> `~/.torrentmate/config` — outside every git working tree. The repo
> carries `config.example/` only. See `docs/features/config-home/DESIGN.md`.
```

- [ ] Commit: `git add CLAUDE.md docs/reference/config-overlay-layout.md docs/reference/web-ui.md && git commit -m "docs(config-home): update reference docs for canonical config relocation"`

---

## Gate (exit conditions)

- [ ] `scripts/migrate-config-home.sh` is executable and passes shellcheck
- [ ] `ecosystem.config.js` has 0 occurrences of the old config path (`/Users/izno/dev/PersonalScraper/config`)
- [ ] `deploy.sh` reads `web.json5` from `$PERSONALSCRAPER_CONFIG` with canonical fallback
- [ ] `git ls-files config/` returns empty (no tracked config files)
- [ ] `config/` is in `.gitignore`
- [ ] CLAUDE.md and reference docs updated with canonical path
- [ ] `make lint` — zero errors
