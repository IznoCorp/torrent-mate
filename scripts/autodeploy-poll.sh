#!/usr/bin/env bash
#
# autodeploy-poll.sh — branch-bound continuous deployment.
#
# Watches origin and redeploys a clone when its tracked branch advances:
#   prod    : ~/deploy/kanban-mate   ⟵ main     → scripts/deploy.sh
#   staging : ~/staging/kanban-mate  ⟵ staging  → scripts/deploy-staging.sh
#
# Push to `staging` → the staging env redeploys; push to `main` → prod redeploys
# (operator CD model, 2026-06-21). Run as the PM2 app `kanban-autodeploy`; loops
# every AUTODEPLOY_INTERVAL (default 60s). `--once` = single pass.
#
# REQUIRES SSH remotes (silent / non-interactive) — HTTPS+GCM would pop a
# credential dialog every pass.
#
set -uo pipefail

DEPLOY_CLONE=/Users/izno/deploy/kanban-mate
DEPLOY_VENV=/Users/izno/deploy/venv/bin
STAGING_CLONE=/Users/izno/staging/kanban-mate
STAGING_VENV=/Users/izno/staging/venv/bin

stamp() { date "+%Y-%m-%d %H:%M:%S"; }

redeploy_if_advanced() {
  local clone="$1" branch="$2" venvbin="$3" deploy="$4"
  cd "$clone" 2>/dev/null || { echo "[$(stamp)] missing clone $clone"; return; }
  git remote update --prune origin >/dev/null 2>&1 \
    || { echo "[$(stamp)] $clone: remote update failed (network?)"; return; }
  local cur rem
  cur="$(git rev-parse HEAD 2>/dev/null)" || return
  rem="$(git rev-parse "origin/$branch" 2>/dev/null)" \
    || { echo "[$(stamp)] $clone: no origin/$branch"; return; }
  [ "$cur" = "$rem" ] && return  # already up to date
  echo "[$(stamp)] $clone: $branch advanced ${cur:0:8} -> ${rem:0:8} — deploying"
  git checkout -q "$branch" 2>/dev/null
  if ! git pull -q --ff-only origin "$branch"; then
    echo "[$(stamp)] $clone: ff-only pull failed (diverged) — skipping"; return
  fi
  PATH="$venvbin:$PATH" bash "$deploy" 2>&1 | sed "s/^/[$(stamp)] /"
}

one_pass() {
  redeploy_if_advanced "$DEPLOY_CLONE"  main    "$DEPLOY_VENV"  "$DEPLOY_CLONE/scripts/deploy.sh"
  redeploy_if_advanced "$STAGING_CLONE" staging "$STAGING_VENV" "$STAGING_CLONE/scripts/deploy-staging.sh"
}

if [ "${1:-}" = "--once" ]; then one_pass; exit 0; fi

INTERVAL="${AUTODEPLOY_INTERVAL:-60}"
echo "[$(stamp)] autodeploy poller up (every ${INTERVAL}s): deploy<-main, staging<-staging"
while true; do
  one_pass
  sleep "$INTERVAL"
done
