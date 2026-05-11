# Phase 11 — Maintenance: 6-month audit + automation

**Type**: maintenance
**Effort**: S (~1 h)
**Entry**: Phase 10 done. `fail_under = 90`. CI green with hard `design-gaps` and diff-coverage.
**Exit**:

- Cron entry on the maintainer's machine for a 6-month audit.
- `scripts/coverage_audit_report.sh` that produces a dated report.
- Open-questions section of DESIGN.md updated with post-implementation decisions.

## Task 11.1 — Create the 6-month audit script

**Files created**: `scripts/coverage_audit_report.sh`

````bash
#!/usr/bin/env bash
# Generates a dated coverage audit report to docs/features/test-coverage/audit-YYYY-MM-DD.md.
# Run via cron every 6 months. Output is committed manually.
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
  echo "## Design coverage"
  echo
  echo '```'
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
````

`--strict-skip` is the audit mode that promotes "expired skip_audit entry" warnings to errors — surfaces drift in `skip_audit` after the entries' `expires` date passes.

- [ ] **Step 1**: Write the script.
- [ ] **Step 2**: `chmod +x scripts/coverage_audit_report.sh`.
- [ ] **Step 3**: Run it once to verify it produces a sensible report.
- [ ] **Step 4**: Commit (don't commit the audit-YYYY-MM-DD.md output yet).

```
feat(test-coverage): add 6-month audit report script
```

## Task 11.2 — Schedule the audit

`hooks/install.sh` is updated to optionally install a launchd plist (macOS) or a crontab entry (Linux) for the audit. Implementation detail — outside the strict project scope but documented in HOWTO.md.

- [ ] **Step 1**: Add an `--install-cron` flag to `hooks/install.sh` that, when passed, installs a 6-month cron entry.
- [ ] **Step 2**: Document in `HOWTO.md` the manual cron entry as fallback:
  ```
  # 1st of January and July at 09:00 — coverage audit
  0 9 1 1,7 * cd $HOME/dev/PersonnalScaper && ./scripts/coverage_audit_report.sh
  ```
- [ ] **Step 3**: Commit.

```
feat(test-coverage): cron-based 6-month audit (manual install)
```

## Task 11.3 — Update DESIGN.md Open Questions with retrospective answers

**Files modified**: `docs/features/test-coverage/DESIGN.md` (Open Questions section)

After 6 cycles, answer Q1, Q2, Q3 with measured data:

- Q1 (diff-coverage timing): "Enabled in Phase 8 alongside `design-gaps` hard error. Caught X regressions in cycles 5-6."
- Q2 (`-n auto` for `make test`): "Kept `-n auto` for both. No data race observed across N CI runs."
- Q3 (90 % vs 85 % end target): "Reached 90 %. Final cycle effort matched the projection in Phase 9."

- [ ] **Step 1**: Update DESIGN.md with measured retrospective.
- [ ] **Step 2**: Commit:

```
docs(test-coverage): retrospective answers to Open Questions
```

## Task 11.4 — Phase 11 gate (final feature gate)

- [ ] All scripts in place.
- [ ] HOWTO.md complete.
- [ ] `IMPLEMENTATION.md` reflects all 11 phases done.
- [ ] One last `make check` + `make gate` for good measure.
- [ ] Final milestone commit:

```
chore(test-coverage): phase 11 gate — feature complete, 90% achieved
```
