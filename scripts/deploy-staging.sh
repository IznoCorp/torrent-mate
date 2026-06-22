#!/usr/bin/env bash
#
# deploy-staging.sh — build the CURRENT branch of THIS (staging) clone and
# restart the staging UI. The non-main playground.
#
# Unlike scripts/deploy.sh (prod, main-only), staging serves whatever branch is
# checked out here — so you can test a not-yet-merged feature remotely. It points
# at the REAL prod root (~/.kanban-km): the prod daemon does the real work, so a
# card move / config edit made in the staging UI applies FOR REAL on the prod
# board. There is no test board (operator rule, 2026-06-21).
#
# Safety rests on one design rule (see docs/reference/repo-safety.md): a feature
# must keep the on-disk state/config format BACKWARD-COMPATIBLE, so the feature
# build (staging) and the prod daemon (main) read/write the same files safely.
#
# Run this INSIDE the staging clone, with the staging venv active.
#
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && git rev-parse --show-toplevel)"
cd "$REPO"

# Obligation de commit: only ever serve committed code.
if [ -n "$(git status --porcelain)" ]; then
  git status --short
  echo "❌ arbre non propre — commit d'abord (on ne teste que du code commité)." >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
sha="$(git rev-parse HEAD)"
[ "$branch" != "main" ] && echo "ℹ staging sert une branche non-main: $branch (c'est le but)."
printf '→ build staging : %s @ %s\n' "$branch" "$sha"

( cd web && npm ci && npm run build )
printf '%s @ %s\n' "$branch" "$sha" > src/kanbanmate/webui/BUILD_COMMIT

pip install -e . >/dev/null 2>&1
pm2 restart kanban-staging-config >/dev/null 2>&1 || true

printf '\n✅ staging déployé : %s @ %s\n   UI sur 127.0.0.1:8797 — board RÉEL (~/.kanban-km)\n' "$branch" "$sha"
