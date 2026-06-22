#!/usr/bin/env bash
#
# agent-stage-deploy.sh — the ONE sanctioned staging-deploy path for orchestrated
# review agents (operator decision, 2026-06-22).
#
# The universal agent deny-list (adapters/perms.py) bans force-push for EVERY
# permission profile — a blunt safety so an autonomous agent can never rewrite
# history or clobber a branch. Deploying a feature to staging, however, requires
# overwriting the `staging` branch (a disposable playground that is force-updated
# on every test). This script encapsulates that single, SCOPED exception:
#
#   * it force-pushes ONLY the current branch onto the `staging` branch,
#   * it REFUSES to run on main/master/staging (so it can never touch the default
#     branch — the merge-is-human invariant is untouched),
#   * everything it does is staging-only and reversible.
#
# Because an agent invokes it as `bash scripts/agent-stage-deploy.sh` (broad-Bash
# is allowed by the dev profile), the internal `git push --force-with-lease` runs
# as a subprocess the agent's permission layer never sees — by design: the trust
# boundary is THIS reviewed, target-pinned script, not an arbitrary agent push.
#
# It deploys the pushed branch to the staging UI via scripts/deploy-staging.sh and
# prints the served bundle hash so the caller can confirm + quote it in a comment.
#
# Run it from the worktree of the branch you want on staging.
#
set -euo pipefail

STAGING_CLONE="$HOME/staging/kanban-mate"
STAGING_VENV="$HOME/staging/venv"
STAGING_URL="https://km-staging.iznogoudatall.xyz"

branch="$(git rev-parse --abbrev-ref HEAD)"
case "$branch" in
  main | master | staging | HEAD | "")
    echo "❌ refus: '$branch' n'est pas une branche de feature déployable (jamais main/staging)." >&2
    exit 2
    ;;
esac

if [ ! -d "$STAGING_CLONE/.git" ]; then
  echo "❌ clone staging introuvable: $STAGING_CLONE" >&2
  exit 3
fi

echo "→ refresh origin + push $branch → staging (force-with-lease, cible figée 'staging')"
git remote update --prune origin
# Target is HARDCODED to the staging branch; --force-with-lease guards against a
# racing staging update (lease is the freshly-updated origin/staging).
git push origin "HEAD:staging" --force-with-lease

echo "→ deploy the staging clone ($STAGING_CLONE)"
cd "$STAGING_CLONE"
git remote update --prune origin
git reset --hard origin/staging
PATH="$STAGING_VENV/bin:$PATH" bash scripts/deploy-staging.sh

served="$(curl -s --connect-timeout 5 --max-time 20 "$STAGING_URL/" | grep -o 'index-[A-Za-z0-9_-]*\.js' | head -1 || true)"
echo ""
echo "✅ STAGING DEPLOYED"
echo "   branch: $branch"
echo "   url:    $STAGING_URL"
echo "   bundle: ${served:-unknown}"
