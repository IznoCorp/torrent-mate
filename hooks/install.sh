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

echo "Hooks installed. Test: edit a tests/integration/test_design_*.py file and commit."
