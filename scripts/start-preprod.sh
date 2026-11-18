#!/usr/bin/env bash
#
# start-preprod.sh — the PM2 step of a staging deploy (scripts/deploy-staging.sh).
#
# Starts or restarts the preprod's apps of ecosystem.config.js, never one of prod's:
#   - its web always (the staging UI must come back after a deploy);
#   - its scheduled jobs and its watcher daemon only when the preprod is set up — they act on the torrent
#     client prod shares and write into the preprod's roots. The preconditions are
#     judged by scripts/preprod_preconditions.py with the staging venv's python (the
#     code just installed): the overlay and secrets file exist, the overlay loads in
#     `staging` (its data dir's .tm-environment reads `staging`), every root is marked
#     .tm-preprod-root and mounted. Any missing one is printed and the jobs stay off.
#
# PM2 merges an app's file env into its stored env on `--update-env`: a key the file no
# longer sets survives every restart. The staging web once ran with
# PERSONALSCRAPER_WEB_ROLE (read-only); while its stored env still carries it, the web
# is deleted first so it starts from the file's env alone.
#
# Run from the staging clone's root.
#
# Usage:  ./scripts/start-preprod.sh <python>
#   <python>  the staging venv's interpreter.
#   TM_PREPROD_CONFIG / TM_PREPROD_ENV_FILE override the overlay dir and secrets file
#   (defaults: the preprod apps' PERSONALSCRAPER_CONFIG / PERSONALSCRAPER_ENV_FILE).
#
set -euo pipefail

PYTHON="${1:?usage: start-preprod.sh <python>}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PREPROD_CONFIG="${TM_PREPROD_CONFIG:-$HOME/.torrentmate/config-staging}"
PREPROD_ENV_FILE="${TM_PREPROD_ENV_FILE:-$HOME/.torrentmate/.env-staging}"
# The preprod's PM2 apps — exactly those of ecosystem.config.js whose env says
# PERSONALSCRAPER_ENV=staging (tests/indexer/test_ecosystem.py holds them equal).
PREPROD_WEB="torrentmate-web-staging"
PREPROD_JOBS="personalscraper-preprod-follow-detect,personalscraper-preprod-search,personalscraper-preprod-grab,personalscraper-preprod-seed-sweep,personalscraper-preprod-health-check,personalscraper-preprod-index-full,personalscraper-preprod-purge,personalscraper-preprod-watch"

# ── The retired read-only role: delete the web while its stored env carries it ──
stored_role="$(pm2 jlist 2>/dev/null | "$PYTHON" -c '
import json, sys
try:
    apps = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for app in apps:
    if app.get("name") == sys.argv[1]:
        env = app.get("pm2_env") or {}
        if "PERSONALSCRAPER_WEB_ROLE" in (env.get("env") or {}) or "PERSONALSCRAPER_WEB_ROLE" in env:
            print("yes")
' "$PREPROD_WEB" || true)"
if [ "$stored_role" = "yes" ]; then
  printf '→ %s still carries PERSONALSCRAPER_WEB_ROLE in its stored env — deleting it so it starts from ecosystem.config.js alone\n' "$PREPROD_WEB"
  if ! out="$(pm2 delete "$PREPROD_WEB" 2>&1)"; then
    printf '⚠ pm2 delete %s failed — the read-only role may survive this deploy:\n%s\n' "$PREPROD_WEB" "$out" >&2
  fi
fi

# ── The preconditions of the scheduled jobs ────────────────────────────────────
apps="$PREPROD_WEB,$PREPROD_JOBS"
if ! missing="$("$PYTHON" scripts/preprod_preconditions.py "$PREPROD_CONFIG" "$PREPROD_ENV_FILE" 2>&1)"; then
  printf '\n⚠ PREPROD JOBS NOT STARTED — a precondition does not hold:\n%s\n   Only %s is (re)started.\n\n' \
    "$(printf '%s\n' "$missing" | sed 's/^/   - /')" "$PREPROD_WEB" >&2
  apps="$PREPROD_WEB"
fi

# ── Start-or-restart ───────────────────────────────────────────────────────────
# startOrRestart (not restart): the first staging deploy must START the apps if they
# were never launched; --update-env picks up their env from this clone's file.
if ! out="$(pm2 startOrRestart ecosystem.config.js --only "$apps" --update-env 2>&1)"; then
  printf '⚠ pm2 startOrRestart --only %s failed:\n%s\n' "$apps" "$out" >&2
fi
