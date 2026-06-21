#!/usr/bin/env bash
#
# install-git-guards.sh — activate the committed git guards in THIS clone.
#
# Points core.hooksPath at the versioned hooks/ dir so the reference-transaction
# branch-deletion guard runs. Idempotent. Run ONCE per clone (the deploy clone
# AND each dev clone). Safe: the repo ships no commit/push hooks here, so this
# only ADDS the branch-deletion guard.
#
set -euo pipefail
repo="$(git rev-parse --show-toplevel)"
chmod +x "$repo/hooks/"* 2>/dev/null || true
git -C "$repo" config core.hooksPath "$repo/hooks"
echo "✓ core.hooksPath → $repo/hooks"
echo "  Garde anti-suppression de branche (non-poussée/non-mergée) ACTIVE pour ce clone."
