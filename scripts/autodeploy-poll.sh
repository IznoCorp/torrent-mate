#!/usr/bin/env bash
#
# autodeploy-poll.sh — branch-driven continuous deployment (TorrentMate).
#
# Watches origin and redeploys a clone when the branch it tracks advances:
#   prod    : ~/deploy/torrentmate   ⟵ main     → scripts/deploy.sh
#   staging : ~/staging/torrentmate  ⟵ staging  → scripts/deploy-staging.sh
#
# The operator's CD model, mirroring KanbanMate: a push to `main` redeploys
# prod, a push to `staging` redeploys staging. Runs as the PM2 app
# `torrentmate-autodeploy`, looping every AUTODEPLOY_INTERVAL seconds (60 by
# default). `--once` runs a single pass, which is what a test or CI wants.
#
# Clone paths are overridable through TM_PROD_CLONE / TM_STAGING_CLONE.
#
# SSH remotes are REQUIRED — silent and non-interactive. HTTPS+GCM would open
# a credentials window on every pass. Every git network operation is bounded
# by `timeout`: a server can accept the TCP connection and never answer.
#
set -euo pipefail

PROD_CLONE="${TM_PROD_CLONE:-$HOME/deploy/torrentmate}"
STAGING_CLONE="${TM_STAGING_CLONE:-$HOME/staging/torrentmate}"

# The ceiling, in seconds, on any git network operation — without it a remote
# that accepts the connection and never answers hangs the loop for good.
GIT_NET_TIMEOUT="${TM_GIT_NET_TIMEOUT:-60}"

stamp() { date "+%Y-%m-%d %H:%M:%S"; }

# redeploy_if_advanced <clone> <branch> <strategy> <deploy_script>
#
#   strategy = "pull"  → git pull --ff-only origin <branch>
#                        (prod: `main` only moves forward — strict fast-forward)
#            = "reset" → git reset --hard origin/<branch>
#                        (staging: the clone FOLLOWS the remote, which a
#                         feature branch may rebase or force-push; a
#                         fast-forward would fail on a diverged history)
#
# Fail-soft: any error — a missing clone, the network, the script — is logged
# and returns without propagating, so the calling loop carries on.
redeploy_if_advanced() {
  local clone="$1" branch="$2" strategy="$3" deploy="$4"

  cd "$clone" 2>/dev/null || { echo "[$(stamp)] no such clone: $clone — skipped"; return 0; }

  # Refreshes the remote refs, under the time bound.
  timeout "$GIT_NET_TIMEOUT" git fetch --prune --quiet origin "$branch" 2>/dev/null \
    || { echo "[$(stamp)] $clone: git fetch origin $branch failed (network?) — pass skipped"; return 0; }

  local cur rem
  cur="$(git rev-parse HEAD 2>/dev/null)" \
    || { echo "[$(stamp)] $clone: HEAD unreadable — pass skipped"; return 0; }
  rem="$(git rev-parse "origin/$branch" 2>/dev/null)" \
    || { echo "[$(stamp)] $clone: origin/$branch not found — pass skipped"; return 0; }

  if [ "$cur" = "$rem" ]; then
    echo "[$(stamp)] $clone: $branch up to date (${cur:0:8})"
    return 0
  fi

  echo "[$(stamp)] $clone: $branch advanced ${cur:0:8} -> ${rem:0:8} — deploying"

  # Stand on the right branch — this is what makes a clone's first run work.
  git checkout -q "$branch" 2>/dev/null || git checkout -q -B "$branch" "origin/$branch" 2>/dev/null

  case "$strategy" in
    pull)
      # main only moves forward, so a strict fast-forward. After the pull HEAD
      # equals origin/main, which is what deploy.sh's own guard asks for.
      if ! timeout "$GIT_NET_TIMEOUT" git pull --ff-only --quiet origin "$branch"; then
        echo "[$(stamp)] $clone: git pull --ff-only origin $branch failed — pass skipped"
        return 0
      fi
      ;;
    reset)
      # staging follows the remote strictly. The deploy scripts refuse a dirty
      # tree, so a clone never carries local work there is anything to lose.
      if ! git reset -q --hard "origin/$branch"; then
        echo "[$(stamp)] $clone: reset --hard origin/$branch failed — pass skipped"
        return 0
      fi
      ;;
    *)
      echo "[$(stamp)] $clone: unknown strategy '$strategy' — pass skipped"
      return 0
      ;;
  esac

  # Deployment: every line is stamped, for the PM2 log.
  if [ ! -f "$deploy" ]; then
    echo "[$(stamp)] $clone: no deploy script at $deploy — pass skipped"
    return 0
  fi
  if bash "$deploy" 2>&1 | sed "s/^/[$(stamp)] /"; then
    echo "[$(stamp)] $clone: $branch deployment finished (${rem:0:8})"
  else
    echo "[$(stamp)] $clone: $deploy failed — pass skipped"
  fi
  return 0
}

# ── the design host, which is neither of the two clones ──────────────────────
#
# `torrentmate-design` serves `serve.py` out of the DEV checkout, which this
# poller never updates — so this is not a deployment. It repairs one asymmetry:
# that host re-reads its MARKUP from the source on every request and loads its
# PYTHON once, at boot. Editing `serve.py` therefore changes what the login
# form SENDS without changing what the process READS, and the two disagree in
# silence. Measured on 2026-08-18: renaming the form's fields locked the
# operator out with nothing in the logs, while the page served was correct.
#
# The trigger is the FILE'S DATE against the process's start, never a git
# event: an editor save, a branch switch and a pull all break it the same way.
# `serve.py` imports nothing but the standard library, so it is the only file
# loaded cold, and therefore the only one to watch.
DESIGN_APP="${TM_DESIGN_APP:-torrentmate-design}"

# Last-modified time, in seconds, read through `python3` — which this function
# already depends on. `stat` does NOT have one interface: to GNU's `stat`, `-f`
# means « filesystem », so `stat -f %m || stat -c %Y` never reaches its
# fallback — the first half SUCCEEDS, printing a block of filesystem facts, and
# the comparison below is handed text. Its test said so: the host restarted on
# every pass.
file_mtime() {
  python3 -c 'import os, sys; print(int(os.stat(sys.argv[1]).st_mtime))' "$1" \
    2>/dev/null || echo 0
}

restart_design_if_stale() {
  command -v pm2 >/dev/null 2>&1 || return 0

  local listing
  listing="$(pm2 jlist 2>/dev/null)" \
    || { echo "[$(stamp)] $DESIGN_APP: pm2 jlist failed — pass skipped"; return 0; }

  # « <script path> <start, in seconds> », or nothing when the app is absent,
  # stopped, or when the output is not JSON this can read.
  local reading
  reading="$(printf '%s' "$listing" | python3 -c '
import json, sys
name = sys.argv[1]
try:
    apps = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for app in apps:
    if app.get("name") != name:
        continue
    env = app.get("pm2_env") or {}
    if env.get("status") != "online":
        sys.exit(0)
    path, started = env.get("pm_exec_path"), env.get("pm_uptime")
    if path and started:
        print(path, int(started) // 1000)
' "$DESIGN_APP" 2>/dev/null)" || return 0
  [ -n "$reading" ] || return 0

  local script started mtime
  script="${reading% *}"
  started="${reading##* }"
  [ -f "$script" ] || { echo "[$(stamp)] $DESIGN_APP: no such file: $script — pass skipped"; return 0; }
  mtime="$(file_mtime "$script")"

  # Strictly later: restarting on equality would restart on every pass, for good.
  if [ "$mtime" -le "$started" ]; then
    return 0
  fi

  echo "[$(stamp)] $DESIGN_APP: $script changed after the process booted — restarting"
  if pm2 restart "$DESIGN_APP" >/dev/null 2>&1; then
    echo "[$(stamp)] $DESIGN_APP: restarted"
  else
    echo "[$(stamp)] $DESIGN_APP: pm2 restart failed — pass skipped"
  fi
  return 0
}

one_pass() {
  redeploy_if_advanced "$PROD_CLONE"    main    pull  "$PROD_CLONE/scripts/deploy.sh"
  redeploy_if_advanced "$STAGING_CLONE" staging reset "$STAGING_CLONE/scripts/deploy-staging.sh"
  restart_design_if_stale
}

# The design-host check on its own: this is how its test drives it, without
# running a deployment at all.
if [ "${1:-}" = "--design-only" ]; then
  if ! restart_design_if_stale; then echo "[$(stamp)] design check: a non-fatal error"; fi
  exit 0
fi

if [ "${1:-}" = "--once" ]; then
  # `if !` turns errexit off inside one_pass, so a pass does all of its work
  # rather than leaving early on the first internal error.
  if ! one_pass; then echo "[$(stamp)] single pass: a non-fatal error"; fi
  exit 0
fi

INTERVAL="${AUTODEPLOY_INTERVAL:-60}"
echo "[$(stamp)] autodeploy poller up (every ${INTERVAL}s): deploy<-main, staging<-staging"
while true; do
  # Fail-soft per cycle: a failed pass must NEVER kill the loop. `if ! one_pass`
  # neutralises errexit inside the function, so a failed cycle is logged and
  # the next one runs.
  if ! one_pass; then
    echo "[$(stamp)] cycle failed — carrying on"
  fi
  sleep "$INTERVAL"
done
