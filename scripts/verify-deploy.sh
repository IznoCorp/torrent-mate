#!/usr/bin/env bash
#
# verify-deploy.sh — drift detector. READ ONLY.
#
# Answers one question: "is what is LIVE exactly origin/main, served from a
# clean main clone?" Catches the failure mode early (before any loss):
#   - the deploy clone is on a branch other than main
#   - the deploy clone has uncommitted changes
#   - the served build (BUILD_COMMIT stamp) ≠ origin/main HEAD
#
# Exit 0 = no drift; exit 1 = drift detected (and described on stderr).
# Wire into cron / `kanban doctor` / the kanban-monitor sweep.
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && git rev-parse --show-toplevel)"
cd "$REPO"
status=0

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ]; then
  echo "⚠ clone de déploiement hors-main (branche '$branch')"; status=1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "⚠ clone de déploiement SALE — modifications non commitées présentes :"
  git status --short
  status=1
fi

timeout 30 git fetch --quiet origin main 2>/dev/null || echo "⚠ fetch origin/main échoué (offline ?) — comparaison sur l'état local"

live="$(cat src/kanbanmate/webui/BUILD_COMMIT 2>/dev/null || echo '∅(non-tamponné)')"
main_sha="$(git rev-parse origin/main 2>/dev/null || git rev-parse main 2>/dev/null || echo '?')"

if [ "$live" = "$main_sha" ]; then
  echo "✓ live=$live == origin/main — aucun écart"
else
  echo "⚠ DÉRIVE: build servi=$live ≠ origin/main=$main_sha"
  status=1
fi

exit "$status"
