#!/usr/bin/env bash
# check-merge-ready.sh — mechanical SCRIPT-transition gate (Review→Merge, run by the
# daemon via KANBAN_REPO+KANBAN_BRANCH; §15.5-15.7) AND an agent-facing readiness
# check (DESIGN §8).
#
# Asserts that:
#   1. A pull request exists and is OPEN.
#   2. All review threads are resolved (or the PR is approved with no outstanding
#      unresolved threads — GitHub's mergeable state CLEAN or BLOCKED only by approval).
#   3. All required CI checks are green.
#
# Read-only: this script never merges, pushes, or rewrites history (DESIGN §10 —
# merge is human-only). It only reports whether a human MAY merge.
#
# Environment variables:
#   KANBAN_REPO    (required) owner/repo, e.g. "IznoCorp/demo"
#   KANBAN_BRANCH  (required unless KANBAN_PR set) branch name
#   KANBAN_PR      (optional) PR number
#
# Exit codes:
#   0  Reviews resolved/approved AND CI green → safe for a human to merge
#   1  Reviews pending / CI not green / PR not found

set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

: "${KANBAN_REPO:?KANBAN_REPO must be set (owner/repo)}"

# ----- 1. Resolve PR number ------------------------------------------------
if [[ -z "${KANBAN_PR:-}" ]]; then
  : "${KANBAN_BRANCH:?KANBAN_BRANCH or KANBAN_PR must be set}"
  echo "Looking up PR for branch: $KANBAN_BRANCH (repo: $KANBAN_REPO)"
  pr_json=$(gh pr view "$KANBAN_BRANCH" \
              --repo "$KANBAN_REPO" \
              --json number,state,url,reviewDecision,mergeStateStatus 2>&1) || {
    echo "FAIL: no open PR found for branch '$KANBAN_BRANCH'." >&2
    echo "      (gh pr view output: $pr_json)" >&2
    exit 1
  }
else
  pr_json=$(gh pr view "$KANBAN_PR" \
              --repo "$KANBAN_REPO" \
              --json number,state,url,reviewDecision,mergeStateStatus 2>&1) || {
    die "could not fetch PR #$KANBAN_PR"
  }
fi

pr_number=$(echo  "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['number'])")
pr_url=$(echo     "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
pr_state=$(echo   "$pr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
review_decision=$(echo "$pr_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reviewDecision') or '')")
merge_state=$(echo "$pr_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mergeStateStatus') or '')")

echo "PR #$pr_number ($pr_state) — $pr_url"
echo "  reviewDecision:  $review_decision"
echo "  mergeStateStatus: $merge_state"

if [[ "$pr_state" != "OPEN" ]]; then
  echo "FAIL: PR #$pr_number is not OPEN (state=$pr_state)." >&2
  exit 1
fi

# ----- 2. Reviews check ----------------------------------------------------
# reviewDecision: APPROVED → all approvals satisfied, no pending required reviews
# CHANGES_REQUESTED / REVIEW_REQUIRED → not ready
# "" (empty) → no review requirement configured → OK
if [[ "$review_decision" == "CHANGES_REQUESTED" ]]; then
  echo "FAIL: PR has outstanding change requests (reviewDecision=CHANGES_REQUESTED)." >&2
  exit 1
fi
if [[ "$review_decision" == "REVIEW_REQUIRED" ]]; then
  echo "FAIL: PR still requires at least one review (reviewDecision=REVIEW_REQUIRED)." >&2
  exit 1
fi

# Check for unresolved review threads via the reviews JSON
threads_json=$(gh pr view "$pr_number" \
                 --repo "$KANBAN_REPO" \
                 --json reviews 2>/dev/null) || threads_json='{"reviews":[]}'

# JSON fed via env var (not stdin) — heredoc overrides the pipe, so stdin = python3 program not data
unresolved=$(_KM_JSON="$threads_json" python3 - << 'PYEOF'
import os, json
data = json.loads(os.environ["_KM_JSON"])
reviews = data.get("reviews") or []
# Pending / commented (not approved / dismissed) reviews indicate outstanding discussions
not_done = [r for r in reviews if r.get("state") not in ("APPROVED", "DISMISSED")]
for r in not_done:
    author = r.get("author", {}).get("login", "?") if isinstance(r.get("author"), dict) else "?"
    print(f"  - {author}: {r.get('state','?')}")
PYEOF
)

if [[ -n "$unresolved" ]]; then
  echo "FAIL: there are unresolved review threads:" >&2
  echo "$unresolved" >&2
  exit 1
fi

echo "Reviews: OK (reviewDecision=$review_decision)"

# ----- 3. CI checks --------------------------------------------------------
echo "Checking CI for PR #${pr_number}…"
# Use ``bucket`` (gh's normalised roll-up), NOT ``conclusion``: ``gh pr checks --json`` does not
# expose a ``conclusion`` field, so requesting it makes gh exit non-zero on every call and the gate
# would ALWAYS fail (engine bug, gh 2.x — mirrors the check-pr-ready.sh fix).
checks_json=$(gh pr checks "$pr_number" \
                --repo "$KANBAN_REPO" \
                --json name,bucket,state 2>&1) || {
  echo "FAIL: could not retrieve checks for PR #$pr_number." >&2
  exit 1
}

# JSON fed via env var (not stdin) — heredoc overrides the pipe, so stdin = python3 program not data
failing=$(_KM_JSON="$checks_json" python3 - << 'PYEOF'
import os, json
checks = json.loads(os.environ["_KM_JSON"])
bad = [c for c in checks if c.get("bucket") in ("fail", "cancel")]
for c in bad:
    print(f"  - {c.get('name','?')}: bucket={c.get('bucket','?')} state={c.get('state','?')}")
PYEOF
)

# JSON fed via env var (not stdin) — heredoc overrides the pipe, so stdin = python3 program not data
pending=$(_KM_JSON="$checks_json" python3 - << 'PYEOF'
import os, json
checks = json.loads(os.environ["_KM_JSON"])
pending = [c for c in checks if c.get("bucket") == "pending"]
for c in pending:
    print(f"  - {c.get('name','?')}: bucket={c.get('bucket','?')} state={c.get('state','?')}")
PYEOF
)

if [[ -n "$failing" ]]; then
  echo "FAIL: failing CI checks:" >&2
  echo "$failing" >&2
  exit 1
fi

if [[ -n "$pending" ]]; then
  echo "FAIL: pending CI checks (still running):" >&2
  echo "$pending" >&2
  exit 1
fi

total=$(echo "$checks_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
echo "OK: PR #$pr_number — reviews resolved + $total CI checks green. Ready for a human to merge."
exit 0
