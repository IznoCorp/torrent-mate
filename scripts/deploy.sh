#!/usr/bin/env bash
#
# deploy.sh — the ONLY sanctioned way to build + serve KanbanMate.
#
# Enforces the deployment invariant (operator rule, 2026-06-21):
#
#     ON NE DÉPLOIE QUE `main`. Si c'est déployé, c'est sur `main`.
#     Pour déployer, on met sur `main` d'abord.
#
# Why this exists: the web SPA build (src/kanbanmate/webui/) is gitignored and
# Vite builds it with emptyOutDir=true. A `npm run build` run from a dirty or
# non-main working tree therefore deploys non-committed code AND wipes the
# previous build — exactly how a batch of UI work was lost on 2026-06-21.
# This script makes that impossible: it refuses to build unless the working
# tree is clean `main`, fully in sync with origin/main, then stamps the exact
# commit it served so "what is live" is always verifiable.
#
# Usage:  ./scripts/deploy.sh
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && git rev-parse --show-toplevel)"
cd "$REPO"

fail() { printf '\n❌ DÉPLOIEMENT REFUSÉ: %s\n' "$*" >&2; exit 1; }

# ── Guard 1: must be on `main` ───────────────────────────────────────────────
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || fail "branche '$branch' ≠ main. On ne déploie QUE main."

# ── Guard 2: working tree must be clean (no uncommitted code can be served) ───
if [ -n "$(git status --porcelain)" ]; then
  git status --short >&2
  fail "arbre de travail non propre — commit ou stash d'abord. On ne déploie JAMAIS de code non commité."
fi

# ── Guard 3: local main must equal origin/main (no un-pushed / diverged code) ─
timeout 30 git fetch --quiet origin main || fail "git fetch origin main a échoué (réseau ?)."
local_sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse origin/main)"
[ "$local_sha" = "$remote_sha" ] \
  || fail "main local ($local_sha) ≠ origin/main ($remote_sha). Fais 'git pull --ff-only origin main' d'abord."

printf '✓ main propre et synchronisée @ %s — build du SPA…\n' "$local_sha"

# ── Build: reproducible from source only (Vite emptyOutDir → webui/) ──────────
( cd web && npm ci && npm run build )

# ── Stamp: record exactly which commit is now live ───────────────────────────
printf '%s\n' "$local_sha" > src/kanbanmate/webui/BUILD_COMMIT

# ── Reinstall the editable package + restart the PM2 apps ────────────────────
pip install -e . >/dev/null
for app in kanban kanban-km kanban-km-serve kanban-km-config; do
  pm2 restart "$app" >/dev/null 2>&1 || true
done
pm2 save >/dev/null 2>&1 || true

printf '\n✅ Déployé: %s\n   (commit servi tamponné dans src/kanbanmate/webui/BUILD_COMMIT)\n' "$local_sha"
