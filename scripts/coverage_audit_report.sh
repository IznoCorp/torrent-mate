#!/usr/bin/env bash
# Generates a dated coverage audit report at
# docs/features/test-coverage/audit-YYYY-MM-DD.md.
#
# Schedule (mirrors docs/features/test-coverage/HOWTO.md "6-month maintenance"):
#   0 9 1 1,7 * "$HOME/dev/PersonnalScaper/scripts/coverage_audit_report.sh"
# (Path is quoted so a $HOME containing spaces or symlinks doesn't break
# the cron line. The script cd's to its own repo root internally.)
# The output is committed manually only when it surfaces actionable findings —
# expired skip_audit entries, fail_under regression, or new orphan sections.

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

# Single-instance lock — prevents a manual run racing with the cron run
# (which would otherwise corrupt the same-day collision counter below
# via TOCTOU). flock blocks until the previous run releases; -n converts
# it to a fast-fail, which is the safer default for a long-running audit.
LOCKFILE="${TMPDIR:-/tmp}/personalscraper_coverage_audit.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  echo "audit: another coverage_audit_report.sh is already running (lock=$LOCKFILE); aborting." >&2
  exit 1
fi

DATE=$(date +%Y-%m-%d)
OUT="docs/features/test-coverage/audit-${DATE}.md"

# Same-day collision (manual re-run after a cron run, etc.) — preserve the
# previous report by suffixing -N. We don't silently overwrite. The flock
# above guarantees we are the only writer, so the find-free-slot loop is
# race-free.
counter=0
target="$OUT"
while [ -e "$target" ] && [ "$counter" -lt 100 ]; do
  counter=$((counter + 1))
  target="${OUT%.md}-${counter}.md"
done
OUT="$target"

# Atomic write: build into a tmp file, mv into place at the end. Avoids
# leaving a half-written report visible to a watcher.
TMP="${OUT}.tmp.$$"
PYTEST_LOG=$(mktemp -t coverage_audit_pytest.XXXXXX)
AUDIT_LOG=$(mktemp -t coverage_audit_design.XXXXXX)
MAP_LOG=$(mktemp -t coverage_audit_map.XXXXXX)
trap 'rm -f "$TMP" "$PYTEST_LOG" "$AUDIT_LOG" "$MAP_LOG"' EXIT

# Track the worst unexpected exit across sections so the script returns
# non-zero (cron supervisors notice) even though the report still gets
# written. Each section has a "tolerance" cap: exit codes at or below the
# cap are expected (e.g. exit 1 = findings); above the cap is a crash.
worst_rc=0

record() {
  local cap=$1 logfile=$2 label=$3
  shift 3
  local rc=0
  "$@" > "$logfile" 2>&1 || rc=$?
  if [ "$rc" -gt "$cap" ]; then
    echo "audit: ${label} unexpected exit ${rc} (cap=${cap}); see report and ${logfile}" >&2
    if [ "$rc" -gt "$worst_rc" ]; then
      worst_rc=$rc
    fi
  fi
  return 0
}

# pytest exit codes: 0=ok, 1=test failures, 2=interrupt, 3=internal,
# 4=usage, 5=no tests collected. Tolerate up to 5; anything higher is
# a runtime crash that the operator must see.
record 5 "$PYTEST_LOG" pytest \
  python3 -m pytest tests/ --ignore=tests/e2e -q --no-header -n auto \
    --cov=personalscraper --cov-branch --cov-report=term

# audit_design_coverage.py: exit 1 on findings is expected.
record 1 "$AUDIT_LOG" audit_design_coverage \
  python3 scripts/audit_design_coverage.py --strict-skip

# update_feature_map.py --check: exit 1 on drift is expected.
record 1 "$MAP_LOG" update_feature_map \
  python3 scripts/update_feature_map.py --check

{
  echo "# Coverage audit — $DATE"
  echo
  echo "## Coverage report"
  echo
  echo '```'
  tail -50 "$PYTEST_LOG"
  echo '```'
  echo
  echo "## Design coverage (--strict-skip)"
  echo
  echo '```'
  cat "$AUDIT_LOG"
  echo '```'
  echo
  echo "## Map freshness"
  echo
  echo '```'
  cat "$MAP_LOG"
  echo '```'
} > "$TMP"

mv "$TMP" "$OUT"

if [ "$worst_rc" -gt 0 ]; then
  echo "Wrote $OUT (with crash exit ${worst_rc} — investigate)"
  exit "$worst_rc"
fi

echo "Wrote $OUT"
