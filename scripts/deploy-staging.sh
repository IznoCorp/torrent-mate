#!/usr/bin/env bash
#
# deploy-staging.sh — build `staging` in THIS (staging) clone and restart the
# staging TorrentMate UI.
#
# The git flow (docs/features/git-flow/DESIGN.md): `staging` moves only through
# scripts/promote.sh, by fast-forward from `main`, when a user story is complete
# — it is no longer a playground a feature branch is checked out on. This
# script serves `staging` alone, clean and equal to origin/staging; the stamp
# records "branch @ sha" so what is live on staging is always verifiable via
# GET /api/version.
#
# S1 is read-only, so staging against the real config/data is safe (KanbanMate
# "no test board" rule).
#
# Run this INSIDE the staging clone with the staging venv (TM_STAGING_VENV).
#
# Usage:  ./scripts/deploy-staging.sh
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && git rev-parse --show-toplevel)"
cd "$REPO"

# Per-clone staging venv (isolation from the dev editable install and from the
# prod clone). Override with TM_STAGING_VENV if relocated.
VENV="${TM_STAGING_VENV:-$HOME/staging/torrentmate-venv}"
PORT=8711
HEALTH_URL="http://127.0.0.1:${PORT}/api/health"

fail() { printf '\n❌ STAGING DEPLOYMENT REFUSED: %s\n' "$*" >&2; exit 1; }

# ── Guard 1: only ever serve committed code (dirty tree refused) ──────────────
if [ -n "$(git status --porcelain)" ]; then
  git status --short >&2
  fail "working tree not clean — commit first (only committed code is tested)."
fi

# ── Guard 2: must be `staging`, equal to origin/staging ───────────────────────
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "staging" ] || fail "branch '$branch' is not staging. ONLY staging is deployed here."
timeout 30 git fetch --quiet origin staging || fail "git fetch origin staging failed (network?)."
sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse origin/staging)"
[ "$sha" = "$remote_sha" ] \
  || fail "local staging ($sha) ≠ origin/staging ($remote_sha). Run 'git pull --ff-only origin staging' first."

# ── Guard 3: the staging venv must exist (per-clone isolation) ────────────────
[ -x "$VENV/bin/python" ] \
  || fail "staging venv not found: $VENV (expected $VENV/bin/python). Create it first (python -m venv \"$VENV\") or export TM_STAGING_VENV."

# ── Guard 4b: uv must be reachable and the lock must exist and match pyproject.toml (checked BEFORE the build wipes anything) ──
# The backend is installed from uv.lock, never re-resolved from pyproject.toml. PM2's PATH may lack
# Homebrew's bin, hence the explicit fallback; override with TM_UV.
UV="${TM_UV:-$(command -v uv || true)}"
if [ -z "$UV" ] && [ -x /opt/homebrew/bin/uv ]; then UV=/opt/homebrew/bin/uv; fi
{ [ -n "$UV" ] && [ -x "$UV" ]; } || fail "uv not found (install it, or export TM_UV=/path/to/uv)."
[ -f uv.lock ] || fail "uv.lock missing — the backend installs from the lock."
"$UV" lock --check >/dev/null 2>&1 \
  || fail "uv.lock is out of date with pyproject.toml (run 'uv lock' and commit it)."

printf '→ build staging: %s @ %s — building the SPA…\n' "$branch" "$sha"

# ── Build: reproducible from source only; bake the served identity into the bundle ─
# TM_BUILD_COMMIT is read by vite.config.ts (define __BUILD_COMMIT__) so the SPA
# knows its own identity and detects a staging redeploy (DESIGN §5.4). Bake the
# EXACT same "branch @ sha" string that is stamped into BUILD_COMMIT below, so the
# PWA's baked __BUILD_COMMIT__ matches GET /api/version byte-for-byte — otherwise
# every load compares "sha" (baked) against "branch @ sha" (served) and reports a
# perpetual phantom update.
(
  cd frontend
  timeout 600 npm ci --no-audit --no-fund
  TM_BUILD_COMMIT="$branch @ $sha" npm run build
)

# ── Install SPA: mirror the fresh Vite build into the served static dir ───────
# --delete purges stale hashed assets; .gitkeep and BUILD_COMMIT are protected.
mkdir -p personalscraper/web/static
rsync -a --delete \
  --exclude='.gitkeep' --exclude='BUILD_COMMIT' \
  frontend/dist/ personalscraper/web/static/

# ── Stamp: "branch @ sha" so staging's /api/version shows the branch context ──
printf '%s @ %s\n' "$branch" "$sha" > personalscraper/web/static/BUILD_COMMIT

# ── Reinstall the backend (from the lock) into the staging venv (per-clone isolation) ─────────
# --locked: install exactly uv.lock (fails if it disagrees with pyproject.toml, never re-resolves);
# the sync is exact, so a package outside the lock is removed from the venv. No `dev` extra here.
UV_PROJECT_ENVIRONMENT="$VENV" "$UV" sync --locked --python "$VENV/bin/python" >/dev/null \
  || fail "uv sync --locked failed (lock out of date with pyproject.toml? broken venv?)"

# ── Start-or-restart the staging PM2 app (fail-soft) ──────────────────────────
# startOrRestart (not restart): the first staging autodeploy must START the app
# if it was never launched. Uses this clone's own ecosystem.config.js entry and
# --update-env to pick up .env changes.
if ! pm2 startOrRestart ecosystem.config.js --only torrentmate-web-staging --update-env >/dev/null 2>&1; then
  printf 'ℹ pm2 startOrRestart torrentmate-web-staging failed — ecosystem.config.js missing, or the app misdeclared?\n' >&2
fi

# ── Post-check: /api/health on the staging port → expect 200 ──────────────────
# Retry loop (mirrors deploy.sh): startOrRestart is async and the app rebuilds
# the full AppContext (provider registry, …) on boot — the port may not be
# listening for a few seconds. Up to 15 attempts × 2 s = 30 s before failing.
health_ok=false
for i in $(seq 1 15); do
  code="$(curl --connect-timeout 5 --max-time 10 -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)"
  if [ "$code" = "200" ]; then
    health_ok=true
    break
  fi
  [ "$i" -lt 15 ] && sleep 2
done
if $health_ok; then
  printf '\n✅ staging deployed: %s @ %s\n   health %s → 200 · UI on 127.0.0.1:%s (REAL board, canonical config)\n' \
    "$branch" "$sha" "$HEALTH_URL" "$PORT"
else
  printf '\n⚠ staging deployed: %s @ %s — but health %s answered "%s" after 15 tries (30 s).\n   Check: pm2 logs torrentmate-web-staging\n' \
    "$branch" "$sha" "$HEALTH_URL" "$code" >&2
fi
