#!/usr/bin/env bash
#
# deploy.sh — the ONLY sanctioned way to build + serve TorrentMate (PROD).
#
# Mirrors KanbanMate's deploy model (operator rule):
#
#     ONLY `main` IS DEPLOYED. If it is deployed, it is on `main`.
#     To deploy something, it goes onto `main` first.
#
# Run this INSIDE the prod clone (~/deploy/torrentmate, tracks `main`) with the
# prod venv (TM_VENV). Why the guards: the Vite SPA build (frontend/,
# emptyOutDir) is gitignored and mirrored into personalscraper/web/static/. A
# build from a dirty or non-main tree would serve non-committed code AND wipe the
# previous build. This script makes that impossible — it refuses unless the tree
# is a clean `main` in sync with origin/main — then stamps the exact commit it
# served (BUILD_COMMIT + baked into the SPA bundle) so "what is live" is always
# verifiable via GET /api/version.
#
# Usage:  ./scripts/deploy.sh
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && git rev-parse --show-toplevel)"
cd "$REPO"

# Per-clone venv (isolation from the dev editable install — avoids the
# stale-editable-finder incident class). Override with TM_VENV if relocated.
VENV="${TM_VENV:-$HOME/deploy/torrentmate-venv}"
PORT=8710
HEALTH_URL="http://127.0.0.1:${PORT}/api/health"

fail() { printf '\n❌ DEPLOYMENT REFUSED: %s\n' "$*" >&2; exit 1; }

# ── Guard 0: config-home migration must have run if pins point there ──────────
# If this clone's ecosystem.config.js pins PERSONALSCRAPER_CONFIG to the
# canonical .torrentmate/config, the migration MUST have been run — a boot
# without the canonical config dir is a silent no-op (no library.db, no state).
# If the pins still point at the old dev config path, this guard is a no-op
# (pre-merge deploys and deploys on hosts that have not yet migrated are
# unaffected).
if grep -q '.torrentmate/config' ecosystem.config.js 2>/dev/null; then
  [ -d "/Users/izno/.torrentmate/config" ] \
    || fail "config-home migration not done — refusing to deploy (run scripts/migrate-config-home.sh)"
fi

# ── Guard 1: must be on `main` ────────────────────────────────────────────────
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || fail "branch '$branch' is not main. ONLY main is deployed."

# ── Guard 2: working tree must be clean (no uncommitted code can be served) ────
if [ -n "$(git status --porcelain)" ]; then
  git status --short >&2
  fail "working tree not clean — commit or stash first. Uncommitted code is NEVER deployed."
fi

# ── Guard 3: local main must equal origin/main (no un-pushed / diverged code) ──
timeout 30 git fetch --quiet origin main || fail "git fetch origin main failed (network?)."
local_sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse origin/main)"
[ "$local_sha" = "$remote_sha" ] \
  || fail "main local ($local_sha) ≠ origin/main ($remote_sha). Fais 'git pull --ff-only origin main' d'abord."

# ── Guard 4: the prod venv must exist (per-clone isolation) ───────────────────
[ -x "$VENV/bin/pip" ] \
  || fail "prod venv not found: $VENV (expected $VENV/bin/pip). Create it first (python -m venv \"$VENV\") or export TM_VENV."

printf '✓ main clean and in sync @ %s — building the SPA…\n' "$local_sha"

# ── Build: reproducible from source only; bake the served SHA into the bundle ─
# TM_BUILD_COMMIT is read by vite.config.ts (define __BUILD_COMMIT__), so the
# installed PWA knows its own commit and can detect a redeploy (DESIGN §5.4).
(
  cd frontend
  timeout 600 npm ci --no-audit --no-fund
  TM_BUILD_COMMIT="$local_sha" npm run build
)

# ── Install SPA: mirror the fresh Vite build into the served static dir ───────
# --delete purges stale hashed assets from a previous build; .gitkeep (the dir's
# git placeholder) and BUILD_COMMIT (rewritten just below) are protected.
mkdir -p personalscraper/web/static
rsync -a --delete \
  --exclude='.gitkeep' --exclude='BUILD_COMMIT' \
  frontend/dist/ personalscraper/web/static/

# ── Stamp: record exactly which commit is now live (GET /api/version reads it) ─
printf '%s\n' "$local_sha" > personalscraper/web/static/BUILD_COMMIT

# ── Reinstall the backend into the prod venv (per-clone isolation) ────────────
"$VENV/bin/pip" install -e . >/dev/null || fail "pip install -e . failed (broken venv? missing dependencies?)"

# ── Start-or-restart the PM2 app (fail-soft) ──────────────────────────────────
# startOrRestart (not restart): the FIRST post-merge autodeploy must START the
# prod app if it was never launched on this box — a bare `pm2 restart` would
# fail-soft and leave prod down after the merge. Uses this clone's own tracked
# ecosystem.config.js (absolute-path entry) and --update-env to pick up .env.
if ! pm2 startOrRestart ecosystem.config.js --only torrentmate-web --update-env >/dev/null 2>&1; then
  printf 'ℹ pm2 startOrRestart torrentmate-web failed — ecosystem.config.js missing, or the app misdeclared?\n' >&2
fi

# ── Post-check: /api/health is public → expect 200 ────────────────────────────
# Retry loop: pm2 restart is async — the new process may not be listening yet.
# Up to 15 attempts × 2 s = 30 s total before declaring failure.
health_ok=false
for i in $(seq 1 15); do
  code="$(curl --connect-timeout 5 --max-time 10 -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)"
  if [ "$code" = "200" ]; then
    health_ok=true
    break
  fi
  [ "$i" -lt 15 ] && sleep 2
done
if ! $health_ok; then
  printf '\n❌ Deployed (prod): %s — but health %s answered "%s" after 15 tries (30 s).\n   Check: pm2 logs torrentmate-web\n' \
    "$local_sha" "$HEALTH_URL" "$code" >&2
  exit 1
fi

# ── Post-check 2 (R27): the RUNNING process serves THIS build ─────────────────
# /api/version caches BUILD_COMMIT AT BOOT — an old process (a pm2 restart that
# failed) would keep serving the OLD sha even with a fresh file on disk. The
# route is session-guarded, so a short-lived JWT is forged from WEB_JWT_SECRET
# (the clone's .env) with the venv's python (PyJWT, the web extra). Tooling
# absent (no PyJWT, or no secret) → a fail-soft warning; a MISMATCH or a
# timeout → a hard failure.
VERSION_URL="http://127.0.0.1:${PORT}/api/version"
tm_token="$("$VENV/bin/python" - "$REPO" 2>/dev/null <<'PYEOF' || true
import os, re, sys, time
from pathlib import Path

import jwt  # PyJWT — ships with the web extra in the prod venv

repo = Path(sys.argv[1])
secret = next(
    (
        line.split("=", 1)[1].strip().strip('"').strip("'")
        for line in (repo / ".env").read_text().splitlines()
        if line.startswith("WEB_JWT_SECRET=")
    ),
    "",
)
config_dir = Path(os.environ.get("PERSONALSCRAPER_CONFIG", str(Path.home() / ".torrentmate" / "config")))
web_cfg = (config_dir / "web.json5").read_text()
match = re.search(r'username:\s*"([^"]+)"', web_cfg)
if not secret or match is None:
    raise SystemExit(1)
now = int(time.time())
claims = {"sub": match.group(1), "iat": now, "exp": now + 120}
print(jwt.encode(claims, secret, algorithm="HS256"))
PYEOF
)"

if [ -z "$tm_token" ]; then
  printf '⚠ version post-check skipped (no JWT can be forged: PyJWT/WEB_JWT_SECRET/config absent) — health checked alone.\n' >&2
else
  served_sha=""
  for i in $(seq 1 10); do
    served_sha="$(curl --connect-timeout 5 --max-time 10 -s -H "Cookie: tm_session=${tm_token}" "$VERSION_URL" \
      | "$VENV/bin/python" -c 'import json,sys; print(json.load(sys.stdin).get("build_commit",""))' 2>/dev/null || true)"
    [ "$served_sha" = "$local_sha" ] && break
    [ "$i" -lt 10 ] && sleep 2
  done
  if [ "$served_sha" != "$local_sha" ]; then
    printf '\n❌ Deployed (prod): %s — but the running process serves build_commit="%s".\n   The pm2 restart probably failed (the old process is still alive). Check: pm2 logs torrentmate-web\n' \
      "$local_sha" "$served_sha" >&2
    exit 1
  fi
fi

printf '\n✅ Deployed (prod): %s\n   health %s → 200 · /api/version serves this commit · stamped into personalscraper/web/static/BUILD_COMMIT\n' \
  "$local_sha" "$HEALTH_URL"
