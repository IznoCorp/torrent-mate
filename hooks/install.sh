#!/usr/bin/env bash
# Configure git to use hooks/ as the hook directory for this clone.
# This avoids overwriting any existing .git/hooks/ files and lets multiple
# project hooks coexist (one per file under hooks/).
#
# Note: core.hooksPath is per-clone (lives in .git/config). It does NOT
# affect other clones or other repos.

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

INSTALL_CRON=0

usage() {
  cat <<EOF
Usage: hooks/install.sh [--install-cron] [--help]

Configures this clone to use hooks/ via git core.hooksPath.

Options:
  --install-cron  Also install the 6-month coverage audit cron entry.
  --help          Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install-cron)
      INSTALL_CRON=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "install.sh: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

# Refuse to run outside a git repo — without a .git/ the call to
# ``git config --local`` below would silently write nothing (or fail with
# an opaque error). Surface the real cause up-front instead.
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "install.sh: not inside a git repository (run 'git init' first or clone the repo)." >&2
  exit 1
fi

current=$(git config --local core.hooksPath || true)
if [ "$current" = "hooks" ] || [ "$current" = "hooks/" ]; then
  echo "core.hooksPath already set to hooks/ — nothing to do."
else
  git config --local core.hooksPath hooks
  echo "Configured: git config core.hooksPath hooks"
fi

# Verify hook scripts are executable; install.sh and docs are skipped.
for hook in "$REPO_ROOT"/hooks/*; do
  [ -f "$hook" ] || continue
  case "$(basename "$hook")" in
    install.sh) continue ;;
    *.md|*.txt) continue ;;
  esac
  if [ ! -x "$hook" ]; then
    chmod +x "$hook"
    echo "chmod +x $(basename "$hook")"
  fi
done

install_cron() {
  local crontab_bin="${PERSONALSCRAPER_CRONTAB_CMD:-crontab}"
  local begin="# personalscraper coverage audit begin"
  local end="# personalscraper coverage audit end"
  local cron_line="0 9 1 1,7 * cd \"$REPO_ROOT\" && ./scripts/coverage_audit_report.sh"
  local current filtered next

  if ! command -v "$crontab_bin" >/dev/null 2>&1; then
    echo "install.sh: crontab command not found; install manually from docs/features/test-coverage/HOWTO.md." >&2
    return 1
  fi

  current=$(mktemp)
  filtered=$(mktemp)
  next=$(mktemp)
  trap 'rm -f "$current" "$filtered" "$next"' RETURN

  if ! "$crontab_bin" -l > "$current" 2>/dev/null; then
    : > "$current"
  fi

  awk -v begin="$begin" -v end="$end" '
    $0 == begin {skip=1; next}
    $0 == end {skip=0; next}
    !skip {print}
  ' "$current" > "$filtered"

  cat "$filtered" > "$next"
  if [ -s "$next" ] && [ "$(tail -c 1 "$next")" != "" ]; then
    printf '\n' >> "$next"
  fi
  {
    printf '%s\n' "$begin"
    printf '%s\n' "$cron_line"
    printf '%s\n' "$end"
  } >> "$next"

  "$crontab_bin" "$next"
  echo "Installed coverage audit cron entry:"
  echo "  $cron_line"
}

if [ "$INSTALL_CRON" -eq 1 ]; then
  install_cron
fi

echo "Hooks installed. Test: edit a tests/integration/test_design_*.py file and commit."
