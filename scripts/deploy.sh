#!/usr/bin/env bash
#
# deploy.sh — the ONLY sanctioned way to build + serve TorrentMate (PROD).
#
# Mirrors KanbanMate's deploy model (operator rule):
#
#     ON NE DÉPLOIE QUE `main`. Si c'est déployé, c'est sur `main`.
#     Pour déployer, on met sur `main` d'abord.
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

fail() { printf '\n❌ DÉPLOIEMENT REFUSÉ: %s\n' "$*" >&2; exit 1; }

# ── Guard 1: must be on `main` ────────────────────────────────────────────────
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || fail "branche '$branch' ≠ main. On ne déploie QUE main."

# ── Guard 2: working tree must be clean (no uncommitted code can be served) ────
if [ -n "$(git status --porcelain)" ]; then
  git status --short >&2
  fail "arbre de travail non propre — commit ou stash d'abord. On ne déploie JAMAIS de code non commité."
fi

# ── Guard 3: local main must equal origin/main (no un-pushed / diverged code) ──
timeout 30 git fetch --quiet origin main || fail "git fetch origin main a échoué (réseau ?)."
local_sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse origin/main)"
[ "$local_sha" = "$remote_sha" ] \
  || fail "main local ($local_sha) ≠ origin/main ($remote_sha). Fais 'git pull --ff-only origin main' d'abord."

# ── Guard 4: the prod venv must exist (per-clone isolation) ───────────────────
[ -x "$VENV/bin/pip" ] \
  || fail "venv prod introuvable: $VENV (attendu $VENV/bin/pip). Crée-le d'abord (python -m venv \"$VENV\") ou exporte TM_VENV."

printf '✓ main propre et synchronisée @ %s — build du SPA…\n' "$local_sha"

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
"$VENV/bin/pip" install -e ".[dev]" >/dev/null

# ── Restart the PM2 app (fail-soft if not defined on this box yet) ────────────
if ! pm2 restart torrentmate-web >/dev/null 2>&1; then
  printf 'ℹ pm2 restart torrentmate-web a échoué — app PM2 non définie ? (pm2 start ecosystem.config.js && pm2 save)\n' >&2
fi

# ── Post-check: /api/health is public → expect 200 ────────────────────────────
code="$(curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)"
if [ "$code" = "200" ]; then
  printf '\n✅ Déployé (prod): %s\n   health %s → 200 · commit tamponné dans personalscraper/web/static/BUILD_COMMIT\n' \
    "$local_sha" "$HEALTH_URL"
else
  printf '\n⚠ Déployé (prod): %s — mais health %s a répondu "%s" (attendu 200).\n   Vérifie: pm2 logs torrentmate-web\n' \
    "$local_sha" "$HEALTH_URL" "$code" >&2
fi
