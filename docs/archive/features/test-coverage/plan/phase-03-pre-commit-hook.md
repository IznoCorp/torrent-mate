# Phase 3 — Pre-commit hook (via `core.hooksPath`)

**Type**: infra
**Effort**: S (~1 h)
**Entry**: Phase 2 gate done.
**Exit**:

- `hooks/pre-commit` script regenerates feature maps when `test_design_*.py` files are staged.
- `hooks/install.sh` configures `git config core.hooksPath hooks/` instead of writing a single symlink.
- Existing `.claude/hooks/` (block_ai_attribution, block_curl_without_timeout, block_background_pipeline) are preserved.

## Why `core.hooksPath` and not a symlink

The original plan proposed `ln -sf ../../hooks/pre-commit .git/hooks/pre-commit`. This would silently overwrite anything the user had at `.git/hooks/pre-commit`, including (most importantly) any Claude-managed hook chain. The project uses `.claude/hooks/` extensively for guard rails (`block_ai_attribution.py`, etc.) — losing those would unblock AI-attribution slips and other guard violations.

`git config core.hooksPath hooks/` redirects all git hook lookups to `hooks/` for _this clone only_ (it lives in `.git/config`, not `~/.gitconfig` and not the tracked repo). The hooks in `hooks/` can be a chain of multiple files (one per hook type, one per concern). Contributors who want their own additional hooks add a sibling file in `hooks/` instead of fighting over `.git/hooks/`.

## Task 3.1 — Create `hooks/pre-commit`

**Files created**: `hooks/pre-commit`

```bash
#!/usr/bin/env bash
# Pre-commit hook: when test_design_*.py files are staged, regenerate the
# affected feature_map files and stage them.
#
# Install: hooks/install.sh
# Bypass: git commit --no-verify (CI will catch the drift via update_feature_map.py --check)

set -euo pipefail

# Are any test_design_*.py files staged?
STAGED_DESIGN_TESTS=$(
  git diff --cached --name-only --diff-filter=ACM \
    | grep 'test_design_.*\.py$' \
    || true
)

if [ -z "$STAGED_DESIGN_TESTS" ]; then
  exit 0
fi

echo "pre-commit: design-contract tests staged, regenerating feature maps..."
python3 scripts/update_feature_map.py

# git status --porcelain (NOT git diff) — captures both modified AND new
# (untracked) map files. git diff would miss new codename files.
UPDATED=$(git status --porcelain tests/feature_map/ | awk '{print $2}' || true)
if [ -n "$UPDATED" ]; then
  echo "pre-commit: staging updated/new map files:"
  echo "$UPDATED" | while read -r f; do
    [ -n "$f" ] || continue
    git add "$f"
    echo "  + $f"
  done
fi

echo "pre-commit: feature maps up to date."
```

- [ ] **Step 1**: Write the script.
- [ ] **Step 2**: `chmod +x hooks/pre-commit`.

## Task 3.2 — Create `hooks/install.sh`

**Files created**: `hooks/install.sh`

```bash
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

# Idempotent: only sets if not already pointing at hooks/.
current=$(git config --local core.hooksPath || true)
if [ "$current" = "hooks" ] || [ "$current" = "hooks/" ]; then
  echo "core.hooksPath already set to hooks/ — nothing to do."
else
  git config --local core.hooksPath hooks
  echo "Configured: git config core.hooksPath hooks"
fi

# Verify all hook scripts are executable.
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
```

- [ ] **Step 1**: Write the script.
- [ ] **Step 2**: `chmod +x hooks/install.sh`.
- [ ] **Step 3**: Run `hooks/install.sh` — must succeed, idempotent on second run.
- [ ] **Step 4**: Verify `git config --local core.hooksPath` returns `hooks`.

## Task 3.3 — Document the install step

**Files modified**: `CLAUDE.md` (Quick Start section), `README.md` (Contributing section).

Add a one-liner under "Setup":

> ```bash
> ./hooks/install.sh   # one-time per clone — sets core.hooksPath to hooks/
> ```

- [ ] **Step 1**: Edit `CLAUDE.md` and `README.md`.
- [ ] **Step 2**: Commit.

```
docs(test-coverage): document hooks/install.sh in Setup
```

## Task 3.4 — Smoke test the hook

- [ ] **Step 1**: Create `tests/integration/test_design_smoke.py` with a single dummy function carrying `Design:` + `Contract:` markers (no assertion — just a `pass`).
- [ ] **Step 2**: `git add tests/integration/test_design_smoke.py && git commit -m "test: smoke pre-commit"`.
- [ ] **Step 3**: Verify the commit included `tests/feature_map/<codename>.json` (auto-generated and auto-staged by the hook).
- [ ] **Step 4**: `git reset HEAD~1 --soft && git checkout -- tests/integration/test_design_smoke.py tests/feature_map/` to undo.

## Task 3.5 — Phase 3 gate

- [ ] `make check` green.
- [ ] `core.hooksPath` set on the dev's clone.
- [ ] `.claude/hooks/*` still present (`ls .claude/hooks/`).
- [ ] Commit:

```
chore(test-coverage): phase 3 gate — pre-commit hook done
```
