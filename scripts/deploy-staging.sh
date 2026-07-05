#!/usr/bin/env bash
#
# deploy-staging.sh — build the CURRENT branch of THIS (staging) clone and
# restart the staging TorrentMate UI. The non-main playground.
#
# Unlike scripts/deploy.sh (prod, main-only), staging serves whatever branch is
# checked out here (~/staging/torrentmate) — so a not-yet-merged feature can be
# validated remotely on tm-staging.iznogoudatall.xyz. It still refuses a dirty
# tree: only committed code is ever served, and the stamp records "branch @ sha"
# so what is live on staging is always verifiable via GET /api/version.
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

fail() { printf '\n❌ DÉPLOIEMENT STAGING REFUSÉ: %s\n' "$*" >&2; exit 1; }

# ── Guard 1: only ever serve committed code (dirty tree refused) ──────────────
if [ -n "$(git status --porcelain)" ]; then
  git status --short >&2
  fail "arbre non propre — commit d'abord (on ne teste que du code commité)."
fi

# ── Guard 2: the staging venv must exist (per-clone isolation) ────────────────
[ -x "$VENV/bin/pip" ] \
  || fail "venv staging introuvable: $VENV (attendu $VENV/bin/pip). Crée-le d'abord (python -m venv \"$VENV\") ou exporte TM_STAGING_VENV."

branch="$(git rev-parse --abbrev-ref HEAD)"
sha="$(git rev-parse HEAD)"
[ "$branch" != "main" ] && printf 'ℹ staging sert une branche non-main: %s (comportement voulu).\n' "$branch"
printf '→ build staging : %s @ %s — build du SPA…\n' "$branch" "$sha"

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

# ── Reinstall the backend into the staging venv (per-clone isolation) ─────────
"$VENV/bin/pip" install -e . >/dev/null || fail "pip install -e . a échoué (venv cassé ? dépendances manquantes ?)"

# ── Start-or-restart the staging PM2 app (fail-soft) ──────────────────────────
# startOrRestart (not restart): the first staging autodeploy must START the app
# if it was never launched. Uses this clone's own ecosystem.config.js entry and
# --update-env to pick up .env changes.
if ! pm2 startOrRestart ecosystem.config.js --only torrentmate-web-staging --update-env >/dev/null 2>&1; then
  printf 'ℹ pm2 startOrRestart torrentmate-web-staging a échoué — ecosystem.config.js absent ou app mal définie ?\n' >&2
fi

# ── Post-check: /api/health on the staging port → expect 200 ──────────────────
code="$(curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)"
if [ "$code" = "200" ]; then
  printf '\n✅ staging déployé : %s @ %s\n   health %s → 200 · UI sur 127.0.0.1:%s (board RÉEL, config canonique)\n' \
    "$branch" "$sha" "$HEALTH_URL" "$PORT"
else
  printf '\n⚠ staging déployé : %s @ %s — mais health %s a répondu "%s" (attendu 200).\n   Vérifie: pm2 logs torrentmate-web-staging\n' \
    "$branch" "$sha" "$HEALTH_URL" "$code" >&2
fi
