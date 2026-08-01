#!/usr/bin/env bash
# scripts/migrate-config-home.sh
# One-shot migration: relocate the canonical config from
# ~/dev/PersonalScraper/config/ to ~/.torrentmate/config/
# (DESIGN §3.1, D1-D2). Idempotent — refuses to run twice.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

CANONICAL="$HOME/.torrentmate/config"
CANONICAL_PARENT="$HOME/.torrentmate"
OLD_CONFIG="$HOME/dev/PersonalScraper/config"
ECOSYSTEM_JS="$HOME/dev/PersonalScraper/ecosystem.config.js"
DATA_ROOT="/Users/izno/dev/PersonalScraper/.data"

say() { printf "${GREEN}[migrate-config-home]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[migrate-config-home] WARN${NC} %s\n" "$*" >&2; }
die() {
  printf "${RED}[migrate-config-home] FATAL${NC} %s\n" "$*" >&2
  if [ "${STOPS_DONE:-0}" = "1" ]; then
    printf "${RED}╔══════════════════════════════════════════════════════════════╗${NC}\n" >&2
    printf "${RED}║  MIGRATION FAILED AFTER STOPS — RECOVERY                    ║${NC}\n" >&2
    printf "${RED}╠══════════════════════════════════════════════════════════════╣${NC}\n" >&2
    printf "${RED}║  Stopped apps: %-46s ║${NC}\n" "${STOPPED_APPS:-none}" >&2
    printf "${RED}║                                                            ║${NC}\n" >&2
    printf "${RED}║  To restart the daemons:                                    ║${NC}\n" >&2
    printf "${RED}║  pm2 startOrRestart %-40s ║${NC}\n" "$ECOSYSTEM_JS" >&2
    printf "${RED}║    --only torrentmate-web,torrentmate-web-staging,           ║${NC}\n" >&2
    printf "${RED}║    personalscraper-watch,torrentmate-autodeploy              ║${NC}\n" >&2
    printf "${RED}║    --update-env                                             ║${NC}\n" >&2
    printf "${RED}║                                                            ║${NC}\n" >&2
    printf "${RED}║  Then check: pm2 status                                     ║${NC}\n" >&2
    printf "${RED}╚══════════════════════════════════════════════════════════════╝${NC}\n" >&2
  fi
  exit 1
}

# ── Guard 0: idempotence — refuse if canonical already exists with .git ──
if [ -d "$CANONICAL/.git" ]; then
  die "Canonical config already exists at $CANONICAL with a git repo. This script has already been run. Aborting."
fi

# ── Guard 0b: half-init safety — canonical exists but without .git = partial run ──
if [ -d "$CANONICAL" ] && [ -n "$(ls -A "$CANONICAL" 2>/dev/null)" ] && [ ! -d "$CANONICAL/.git" ]; then
  die "Canonical dir exists at $CANONICAL (non-empty, no .git) — looks like a half-finished run. Recover: rm -rf $CANONICAL then re-run this script. NEVER auto-deleted — decision requires operator intent."
fi

# ── Guard 1: old config must exist ──
if [ ! -d "$OLD_CONFIG" ]; then
  die "Old config not found at $OLD_CONFIG. Nothing to migrate."
fi

# ── Guard 2: operator attended confirmation ──
say "This will:"
say "  0. Anchor data_dir to absolute path (prevents silent .data relocation)"
say "  0b. Copy .env layer to canonical parent"
say "  1. Stop all PM2 writers (torrentmate-autodeploy first, then web/watch/crons)"
say "  2. rsync $OLD_CONFIG → $CANONICAL"
say "  3. git init + initial commit in $CANONICAL"
say "  4. Update ecosystem.config.js PERSONALSCRAPER_CONFIG pins (dev repo only)"
say "  5. Restart PM2 daemons (scoped: web+watch then autodeploy last)"
say "  6. Smoke test (canonical boots, data_dir unchanged, plex_token present)"
say ""
read -rp "Proceed? [y/N] " REPLY
[[ "$REPLY" =~ ^[Yy]$ ]] || die "Aborted by operator."

# ── Step 0: Anchor the data root BEFORE stopping anything ──
# The loader resolves relative data_dir against config_dir.parent. After
# relocation, config_dir.parent changes from ~/dev/PersonalScraper to ~/.torrentmate,
# so a relative "./.data" would silently re-root to ~/.torrentmate/.data and
# abandon 1.9 GB of live state (library.db, acquire.db, analysis artifacts).
# Rewrite relative data_dir to the absolute path in the old config dir so the
# rsync copies the anchored version.
say "Step 0/6: Anchoring data_dir to absolute path..."
# Both grep and sed use [[:space:]] (BSD-compatible — macOS sed treats \s as literal).
if grep -q 'data_dir:[[:space:]]*"\./' "$OLD_CONFIG/paths.json5"; then
  say "  data_dir is relative — rewriting to absolute $DATA_ROOT"
  sed -i '' 's|data_dir:[[:space:]]*"\./[^"]*"|data_dir: "'"$DATA_ROOT"'"|' "$OLD_CONFIG/paths.json5"
  # Verify by checking the file text directly (never the loader — it resolves
  # relative paths against the OLD parent so it would falsely ✓ even if the sed
  # were a no-op).
  if grep -qF "$DATA_ROOT" "$OLD_CONFIG/paths.json5"; then
    say "  Verified: data_dir anchored to $DATA_ROOT in paths.json5"
  else
    die "Step 0 FAILED — data_dir not anchored. paths.json5 does not contain $DATA_ROOT"
  fi
else
  say "  data_dir is already absolute — skipping anchor"
fi

# ── Step 0b: Copy the shared .env layer ──
# The canonical env layer is <config parent>/.env — it preserves the PLEX_TOKEN
# fill-in and other secrets shared by all clones (prod, staging, dev). The dev
# checkout's .env is the current live source.
say "Step 0b: Copying .env layer..."
mkdir -p "$CANONICAL_PARENT"
if [ -f "$HOME/dev/PersonalScraper/.env" ]; then
  cp -p "$HOME/dev/PersonalScraper/.env" "$CANONICAL_PARENT/.env"
  say "  Copied .env → $CANONICAL_PARENT/.env"
else
  warn "  No .env found at $HOME/dev/PersonalScraper/.env — skipping (may need manual setup)"
fi

# ── Recovery state — die() prints recovery instructions when stops have begun ──
STOPPED_APPS=""
STOPS_DONE=0

# ── Step 1: Stop writers (autodeploy FIRST, one-at-a-time, verify each) ──
say "Step 1/6: Stopping PM2 writers..."

# 1a: Stop autodeploy FIRST — prevents it from triggering a deploy mid-migration
say "  Stopping torrentmate-autodeploy (first)..."
if pm2 stop torrentmate-autodeploy 2>/dev/null; then
  if pm2 jlist 2>/dev/null | python3 -c "import json,sys; apps={a['name']:a.get('pm2_env',{}).get('status','') for a in json.load(sys.stdin)}; sys.exit(0 if apps.get('torrentmate-autodeploy')=='stopped' else 1)"; then
    say "  ✓ torrentmate-autodeploy → stopped"
    STOPPED_APPS="torrentmate-autodeploy"
  else
    die "torrentmate-autodeploy still running after stop — refusing to proceed"
  fi
else
  say "  torrentmate-autodeploy was not running (ok)"
  STOPPED_APPS=""
fi

# 1b: Stop web + watch — one at a time with verification
for app in torrentmate-web torrentmate-web-staging personalscraper-watch; do
  say "  Stopping $app..."
  if pm2 stop "$app" 2>/dev/null; then
    if pm2 jlist 2>/dev/null | python3 -c "
import json,sys
apps={a['name']:a.get('pm2_env',{}).get('status','') for a in json.load(sys.stdin)}
status=apps.get('$app','')
sys.exit(0 if status=='stopped' else 1)
"; then
      say "  ✓ $app → stopped"
      STOPPED_APPS="$STOPPED_APPS $app"
    else
      die "$app still running after stop — refusing to proceed"
    fi
  else
    say "  $app was not running (ok)"
  fi
done

# 1c: Stop cron one-shots — one at a time, no hard verify (they may not be running)
for app in personalscraper-index-enrich personalscraper-backfill-ids personalscraper-follow-detect personalscraper-search personalscraper-grab personalscraper-health-check; do
  say "  Stopping $app..."
  pm2 stop "$app" 2>/dev/null || true
  # Verify stop only if it was running
  if pm2 jlist 2>/dev/null | python3 -c "
import json,sys
apps={a['name']:a.get('pm2_env',{}).get('status','') for a in json.load(sys.stdin)}
status=apps.get('$app','')
sys.exit(0 if status in ('stopped','') else 1)
" 2>/dev/null; then
    :
  else
    die "$app still running after stop — refusing to proceed"
  fi
  STOPPED_APPS="$STOPPED_APPS $app"
done

sleep 2
say "  All writers stopped. Stopped:${STOPPED_APPS}"
STOPS_DONE=1

# Register the ERR trap AFTER stops (so die() prints recovery instructions).
# ERR fires on any non-zero exit (set -e), calling die() which includes the
# recovery block when STOPS_DONE=1.
trap 'die "Unexpected error during migration (trapped ERR)"' ERR

# ── Step 2: rsync config ──
say "Step 2/6: Copying $OLD_CONFIG → $CANONICAL..."

# Guard: refuse to overwrite a hand-crafted canonical (no .git but non-empty)
if [ -d "$CANONICAL" ] && [ -n "$(ls -A "$CANONICAL" 2>/dev/null)" ] && [ ! -d "$CANONICAL/.git" ]; then
  die "Canonical dir $CANONICAL exists and is non-empty without .git — looks like a hand-crafted config. Refusing to overwrite. Recover: rm -rf $CANONICAL then re-run."
fi

mkdir -p "$CANONICAL"
rsync -a "$OLD_CONFIG/" "$CANONICAL/"
say "  Copied $(find "$CANONICAL" -type f | wc -l | tr -d ' ') files"

# ── Step 3: git init + initial commit ──
say "Step 3/6: Initializing local git repo..."
git -C "$CANONICAL" init
git -C "$CANONICAL" config user.email "izno@iznoserver"
git -C "$CANONICAL" config user.name "IznoServer Config"
git -C "$CANONICAL" add -A
git -C "$CANONICAL" commit -m "initial commit — config migrated from $OLD_CONFIG"
say "  Initial commit: $(git -C "$CANONICAL" rev-parse --short HEAD)"

# ── Step 4: Update ecosystem.config.js pins (dev repo only) ──
say "Step 4/6: Updating ecosystem.config.js PERSONALSCRAPER_CONFIG pins..."
# Only touches the dev repo's ecosystem.config.js (the deploy clone's copy is
# updated by deploy.sh's autodeploy post-merge, or manually after migration).
sed -i '' "s|PERSONALSCRAPER_CONFIG: \"$OLD_CONFIG\"|PERSONALSCRAPER_CONFIG: \"$CANONICAL\"|g" "$ECOSYSTEM_JS"
# Also fix any remaining literal paths outside the PERSONALSCRAPER_CONFIG key
# (e.g. the comment block header on line 29).
sed -i '' "s|$OLD_CONFIG|$CANONICAL|g" "$ECOSYSTEM_JS"

# Verify: fail loud if any old-path occurrence remains.
if grep -q "$OLD_CONFIG" "$ECOSYSTEM_JS"; then
  die "Step 4 FAILED — $ECOSYSTEM_JS still contains references to $OLD_CONFIG"
fi
say "  Updated $ECOSYSTEM_JS"

# ── Step 5: Smoke test (extended — canonical path, data anchor, env layer) ──
say "Step 5/6: Smoke test..."

# Use the prod venv binary if it exists; fall back to dev python3 -m
if [ -x "/Users/izno/deploy/torrentmate-venv/bin/personalscraper" ]; then
  SMOKE_PYTHON="/Users/izno/deploy/torrentmate-venv/bin/python"
else
  SMOKE_PYTHON="python3"
fi

cd "$HOME/dev/PersonalScraper"

# 5a: Basic boot test
if PERSONALSCRAPER_CONFIG="$CANONICAL" "$SMOKE_PYTHON" -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = '$CANONICAL'
from personalscraper.conf.loader import load_config
cfg = load_config()
print('boot_ok')
" 2>&1 | grep -q 'boot_ok'; then
  say "  ✓ personalscraper boots with canonical config"
else
  die "Smoke test FAILED — personalscraper cannot boot with $CANONICAL. Check config."
fi

# 5b: Assert data_dir did NOT move (data anchor guard)
DATA_DIR_OK=false
actual_data_dir="$(PERSONALSCRAPER_CONFIG="$CANONICAL" "$SMOKE_PYTHON" -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = '$CANONICAL'
from personalscraper.conf.loader import load_config
cfg = load_config()
print(cfg.paths.data_dir)
" 2>/dev/null || true)"

if [ "$actual_data_dir" = "$DATA_ROOT" ]; then
  say "  ✓ data_dir anchored: $actual_data_dir"
  DATA_DIR_OK=true
else
  die "DATA ANCHOR FAILED — data_dir resolved to '$actual_data_dir', expected '$DATA_ROOT'. The relative path was not rewritten. Check paths.json5."
fi

# 5c: Assert indexer db_path is under DATA_ROOT
INDEXER_OK=false
actual_db_path="$(PERSONALSCRAPER_CONFIG="$CANONICAL" "$SMOKE_PYTHON" -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = '$CANONICAL'
from personalscraper.conf.loader import load_config
cfg = load_config()
print(cfg.indexer.db_path)
" 2>/dev/null || true)"

case "$actual_db_path" in
  "$DATA_ROOT"/*)
    say "  ✓ indexer db_path under data_root: $actual_db_path"
    INDEXER_OK=true
    ;;
  *)
    die "INDEXER PATH MISMATCH — db_path resolved to '$actual_db_path', expected something under '$DATA_ROOT'"
    ;;
esac

# 5d: Assert plex_token non-empty via Settings (names only, never print values)
# Config has no .settings attribute — secrets live on personalscraper.config.Settings
# (loaded from .env via pydantic-settings), accessed via get_settings().
PLEX_OK=false
plex_check="$(PERSONALSCRAPER_CONFIG="$CANONICAL" "$SMOKE_PYTHON" -c "
import os
os.environ['PERSONALSCRAPER_CONFIG'] = '$CANONICAL'
from personalscraper.config import get_settings
settings = get_settings()
token = settings.plex_token
print('present' if token else 'missing')
" 2>/dev/null || echo "missing")"

if [ "$plex_check" = "present" ]; then
  say "  ✓ plex_token present (value not printed)"
  PLEX_OK=true
else
  warn "  ⚠ plex_token missing or unreadable — Plex refresh will fail until .env is set up"
fi

# ── Step 6: Restart PM2 (scoped — writers first, autodeploy LAST) ──
say "Step 6/6: Restarting PM2 daemons..."

# 6a: Restart web + watch (daemons that need PERSONALSCRAPER_CONFIG)
pm2 startOrRestart "$ECOSYSTEM_JS" \
  --only torrentmate-web,torrentmate-web-staging,personalscraper-watch \
  --update-env
say "  ✓ torrentmate-web, torrentmate-web-staging, personalscraper-watch restarted"
sleep 3

# 6b: Restart autodeploy LAST — prevents it from deploying before writers are stable
pm2 startOrRestart "$ECOSYSTEM_JS" \
  --only torrentmate-autodeploy \
  --update-env
say "  ✓ torrentmate-autodeploy restarted (last)"
sleep 2

# 6c: Refresh cron env (startOrRestart + stop, one at a time)
# The crons were stopped in Step 1c and their stored pm2 env still carries
# the OLD PERSONALSCRAPER_CONFIG pin. A startOrRestart with --update-env
# picks up the updated ecosystem.config.js, then an immediate stop persists
# the NEW env in the pm2 dump so reboot resurrection loads the right pin.
# The ≤2s startup window is accepted — python boot exceeds it, so the cron
# never actually fires during the refresh. Sequence them so only one runs
# at a time (cpu/IO isolation).
for app in personalscraper-index-enrich personalscraper-backfill-ids \
  personalscraper-follow-detect personalscraper-search \
  personalscraper-grab personalscraper-health-check; do
  say "  Refreshing env for $app..."
  pm2 startOrRestart "$ECOSYSTEM_JS" --only "$app" --update-env
  sleep 1
  pm2 stop "$app"
  if pm2 jlist 2>/dev/null | python3 -c "
import json,sys
apps={a['name']:a.get('pm2_env',{}).get('status','') for a in json.load(sys.stdin)}
status=apps.get('$app','')
sys.exit(0 if status=='stopped' else 1)
" 2>/dev/null; then
    say "  ✓ $app env refreshed, stopped"
  else
    die "$app not stopped after env refresh — refusing to proceed"
  fi
done

# ── pm2 save + resurrection guard ──
say "Saving PM2 process list for reboot resurrection..."
pm2 save
# After the env refresh, all 10 apps (4 writers + 6 crons) carry the canonical
# path in their stored env.
count="$(grep -c '.torrentmate/config' "$HOME/.pm2/dump.pm2" 2>/dev/null || echo 0)"
if [ "$count" -ge 10 ]; then
  say "  ✓ pm2 dump contains $count canonical config references (≥ 10)"
else
  die "PM2 dump integrity FAILED — only $count '.torrentmate/config' references found (expected ≥ 10). Reboot would resurrect wrong configs."
fi

# ── Post-check: /api/health ──
say "Post-check: verifying /api/health..."
if curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}" "https://tm.iznogoudatall.xyz/api/health" | grep -q 200; then
  say "  ✓ Post-check PASSED — prod web is responding."
else
  warn "  ⚠ Post-check: prod /api/health not 200 yet — check pm2 logs torrentmate-web"
fi

say ""
say "═══════════════════════════════════════════════════════════════"
say "Migration complete."
say ""
say "Next steps:"
say "  1. Remove old config: rm -rf $OLD_CONFIG (DO THIS MANUALLY after verification)"
say "  2. Set PERSONALSCRAPER_CONFIG=$CANONICAL in your dev shell (.zshrc or equivalent)"
say "  3. Run: personalscraper init-config --sync --dry-run to verify nothing missing"
say "  4. Commit the ecosystem.config.js + migration script changes to the repo"
say "  5. Run deploy.sh in the prod clone (~/deploy/torrentmate) to pick up the new config"
say ""
say "Smoke summary:"
say "  data_dir:    $actual_data_dir $([ "$DATA_DIR_OK" = "true" ] && echo '✓' || echo '✗')"
say "  indexer db:  $actual_db_path $([ "$INDEXER_OK" = "true" ] && echo '✓' || echo '✗')"
say "  plex_token:  $plex_check $([ "$PLEX_OK" = "true" ] && echo '✓' || echo '✗')"
say "═══════════════════════════════════════════════════════════════"
