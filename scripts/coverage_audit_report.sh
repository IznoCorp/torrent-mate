#!/usr/bin/env bash
# Generates a dated coverage audit report to
# docs/features/test-coverage/audit-YYYY-MM-DD.md.
#
# Run via cron every 6 months (1st January, 1st July). The output file is
# inspected manually and committed if it surfaces actionable findings —
# expired skip_audit entries, fail_under regression, or new orphan sections.

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

DATE=$(date +%Y-%m-%d)
OUT="docs/features/test-coverage/audit-${DATE}.md"

{
  echo "# Coverage audit — $DATE"
  echo
  echo "## Coverage report"
  echo
  echo '```'
  python3 -m pytest tests/ --ignore=tests/e2e -q --no-header -n auto \
    --cov=personalscraper --cov-branch --cov-report=term 2>&1 | tail -50
  echo '```'
  echo
  echo "## Design coverage (--strict-skip)"
  echo
  echo '```'
  # --strict-skip promotes expired skip_audit entries to errors so we
  # see them in the report even when CI's --strict run still passes.
  python3 scripts/audit_design_coverage.py --strict-skip 2>&1 || true
  echo '```'
  echo
  echo "## Map freshness"
  echo
  echo '```'
  python3 scripts/update_feature_map.py --check 2>&1 || true
  echo '```'
} > "$OUT"

echo "Wrote $OUT"
