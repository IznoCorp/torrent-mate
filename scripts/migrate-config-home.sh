#!/usr/bin/env bash
# scripts/migrate-config-home.sh
# One-shot migration: relocate the canonical config from
# ~/dev/PersonalScraper/config/ to ~/.torrentmate/config/
# (DESIGN §3.1, D1-D2). Idempotent — refuses to run twice.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

CANONICAL="$HOME/.torrentmate/config"
OLD_CONFIG="$HOME/dev/PersonalScraper/config"
ECOSYSTEM_JS="$HOME/dev/PersonalScraper/ecosystem.config.js"

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
say "  6. Smoke test (python3 -m personalscraper --config $CANONICAL info)"
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
# Idempotent: the repo's ecosystem.config.js is already flipped by the config-home
# feature branch, but we also check the prod deploy clone so this sed covers both
# and is a no-op if already correct.
sed -i '' "s|PERSONALSCRAPER_CONFIG: \"$OLD_CONFIG\"|PERSONALSCRAPER_CONFIG: \"$CANONICAL\"|g" "$ECOSYSTEM_JS"
# Also fix any remaining literal paths outside the PERSONALSCRAPER_CONFIG key
# (e.g. the comment block header on line 29).
sed -i '' "s|$OLD_CONFIG|$CANONICAL|g" "$ECOSYSTEM_JS"

# Verify: fail loud if any old-path occurrence remains.
if grep -q "$OLD_CONFIG" "$ECOSYSTEM_JS"; then
  die "Step 4 FAILED — $ECOSYSTEM_JS still contains references to $OLD_CONFIG"
fi
say "Updated $ECOSYSTEM_JS"

# ── Step 5: Smoke test ──
say "Step 5/6: Smoke test..."
cd "$HOME/dev/PersonalScraper"
if python3 -m personalscraper --config "$CANONICAL" info >/dev/null 2>&1; then
  say "Smoke test PASSED — personalscraper boots with $CANONICAL"
else
  die "Smoke test FAILED — personalscraper cannot boot with $CANONICAL. Check config."
fi

# ── Step 6: Restart PM2 ──
say "Step 6/6: Restarting PM2..."
pm2 startOrRestart "$ECOSYSTEM_JS" --update-env
sleep 3

# ── Post-check: /api/version ──
say "Post-check: verifying /api/health..."
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
