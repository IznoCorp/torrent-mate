#!/usr/bin/env bash
# check-pr-ready.sh — mechanical SCRIPT-transition gate (InProgress→PRCI, run by the
# daemon via KANBAN_REPO+KANBAN_BRANCH; §15.5-15.7) AND an agent-facing readiness
# check (DESIGN §8).
#
# Asserts that:
#   1. A pull request exists for KANBAN_BRANCH (or KANBAN_PR if pre-resolved).
#   2. All required CI checks are green (no failing or pending checks).
#
# Read-only: this script never merges, pushes, or rewrites history (DESIGN §10 —
# merge is human-only). It only inspects PR + CI state via `gh`.
#
# Environment variables:
#   KANBAN_REPO    (required) owner/repo, e.g. "IznoCorp/demo"
#   KANBAN_BRANCH  (required unless KANBAN_PR set) branch name
#   KANBAN_PR      (optional) PR number — skips the lookup when already known
#
# Exit codes:
#   0  PR exists and CI is fully green
#   1  PR missing, CI not green, or a command failed

set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

: "${KANBAN_REPO:?KANBAN_REPO must be set (owner/repo)}"

# ----- 1. Resolve PR number ------------------------------------------------
if [[ -z "${KANBAN_PR:-}" ]]; then
  : "${KANBAN_BRANCH:?KANBAN_BRANCH or KANBAN_PR must be set}"
  echo "Checking for PR on branch: $KANBAN_BRANCH (repo: $KANBAN_REPO)"
  pr_json=$(gh pr view "$KANBAN_BRANCH" \
              --repo "$KANBAN_REPO" \
              --json number,state,url,headRefName 2>&1) || {
    echo "FAIL: no open PR found for branch '$KANBAN_BRANCH'." >&2
    echo "      (gh pr view output: $pr_json)" >&2
    exit 1
  }
  pr_number=$(echo "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['number'])")
  pr_url=$(echo    "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
  pr_state=$(echo  "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
else
  pr_number="$KANBAN_PR"
  pr_json=$(gh pr view "$pr_number" \
              --repo "$KANBAN_REPO" \
              --json number,state,url 2>&1) || die "could not fetch PR #$pr_number"
  pr_url=$(echo   "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
  pr_state=$(echo "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
fi

echo "PR #$pr_number ($pr_state) — $pr_url"

if [[ "$pr_state" != "OPEN" ]]; then
  echo "FAIL: PR #$pr_number is not OPEN (state=$pr_state)." >&2
  exit 1
fi

# ----- 2. Check CI status --------------------------------------------------
echo "Checking CI checks for PR #${pr_number}…"
# Capture both the output and the exit code WITHOUT aborting (set -e): `gh pr checks` exits
# non-zero in two distinct cases we must tell apart — a real error vs "no checks reported" (a
# repo with NO CI configured on the branch). The zero-checks policy (defect 9) treats the latter
# as GREEN-with-warning (a checkless repo must not strand the campaign in PR/CI forever), while a
# genuine error (auth/network) still FAILs. ``set +e`` around the capture: under ``set -e`` a
# command-substitution assignment whose command fails ABORTS the script before we can inspect the
# exit code, so the zero-checks branch would never run.
set +e
checks_json=$(gh pr checks "$pr_number" \
                --repo "$KANBAN_REPO" \
                --json name,state,conclusion 2>&1)
checks_rc=$?
set -e
if [[ $checks_rc -ne 0 ]]; then
  # "no checks reported" (no CI on the branch) → PASS with a recap note (zero-checks policy).
  if echo "$checks_json" | grep -qi "no checks reported"; then
    echo "OK: PR #$pr_number — no CI checks are configured on this branch (zero-checks policy: " \
         "treated as green). Note: enable required checks for real gating." >&2
    exit 0
  fi
  echo "FAIL: could not retrieve checks for PR #$pr_number." >&2
  echo "      (gh pr checks output: $checks_json)" >&2
  exit 1
fi

# Parse: any check that is not successful is a problem
# JSON fed via env var (not stdin) — heredoc overrides the pipe, so stdin = python3 program not data
failing=$(_KM_JSON="$checks_json" python3 - << 'PYEOF'
import os, json
checks = json.loads(os.environ["_KM_JSON"])
bad = [c for c in checks if c.get("conclusion") not in ("SUCCESS", "SKIPPED", "NEUTRAL", None) or c.get("state") == "FAILURE"]
for c in bad:
    print(f"  - {c.get('name','?')}: state={c.get('state','?')} conclusion={c.get('conclusion','?')}")
PYEOF
)

# JSON fed via env var (not stdin) — heredoc overrides the pipe, so stdin = python3 program not data
pending=$(_KM_JSON="$checks_json" python3 - << 'PYEOF'
import os, json
checks = json.loads(os.environ["_KM_JSON"])
# A check with no conclusion yet is still running
pending = [c for c in checks if c.get("state") in ("IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED")]
for c in pending:
    print(f"  - {c.get('name','?')}: {c.get('state','?')}")
PYEOF
)

if [[ -n "$failing" ]]; then
  echo "FAIL: the following CI checks are NOT green:" >&2
  echo "$failing" >&2
  exit 1
fi

if [[ -n "$pending" ]]; then
  echo "FAIL: the following CI checks are still pending:" >&2
  echo "$pending" >&2
  exit 1
fi

total=$(echo "$checks_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
echo "OK: PR #$pr_number — all $total CI checks are green."
exit 0
