#!/usr/bin/env bash
# scripts/phase-gate.sh — Interactive helper to ship a phase-gate commit cleanly.
#
# Usage:
#   ./scripts/phase-gate.sh <phase_number>
#
# Workflow:
#   1. Find the previous gate commit (git log grep) to derive SHA range.
#   2. Show commit summary in range (count + subjects).
#   3. Run drift-detect.py --json and surface PLAN_DEV_COVERAGE issues.
#   4. Propose IMPL.md + ACCEPTANCE.md edits.
#   5. Prompt user for confirmation.
#   6. Apply edits + git add + git commit.
#   7. Print new gate SHA.
#
# Idempotence: exits 0 with "already gated" message when IMPL.md already has
# [x] gate with a SHA for this phase.

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT="$(git rev-parse --show-toplevel)"
IMPL_MD="${REPO_ROOT}/IMPLEMENTATION.md"
ACCEPTANCE_MD="${REPO_ROOT}/docs/features/tech-debt/ACCEPTANCE.md"
DRIFT_DETECT="${REPO_ROOT}/scripts/drift-detect.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "  $*"; }

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

[[ $# -ge 1 ]] || die "Usage: $0 <phase_number>"
PHASE_NUM="$1"
[[ "$PHASE_NUM" =~ ^[0-9]+$ ]] || die "phase_number must be a plain integer (e.g. 5)"

# ---------------------------------------------------------------------------
# 0. Idempotence check — already gated?
# ---------------------------------------------------------------------------

echo ""
echo "=== phase-gate.sh — Phase ${PHASE_NUM} ==="
echo ""

already_gated_sha=""
while IFS= read -r line; do
    # Match table row starting with | PHASE_NUM |
    if echo "$line" | grep -qE "^\|\s*${PHASE_NUM}\s*\|"; then
        # Row has [x] and a backticked SHA → already gated.
        if echo "$line" | grep -qi '\[x\]'; then
            sha_candidate=$(echo "$line" | grep -oE '`[0-9a-f]{7,40}`' | head -1 | tr -d '`' || true)
            if [[ -n "$sha_candidate" ]]; then
                already_gated_sha="$sha_candidate"
            fi
        fi
    fi
done < "$IMPL_MD"

if [[ -n "$already_gated_sha" ]]; then
    echo "Phase ${PHASE_NUM} is already gated (IMPL.md row has [x] with SHA \`${already_gated_sha}\`)."
    echo "Nothing to do."
    exit 0
fi

# ---------------------------------------------------------------------------
# 1. Find the previous gate commit SHA to derive the commit range.
# ---------------------------------------------------------------------------

prev_gate_sha=""
prev_gate_num=""

while IFS= read -r line; do
    sha="${line%% *}"
    subject="${line#* }"
    if echo "$subject" | grep -qE "^chore\(tech-debt\): phase [0-9]+ gate"; then
        gate_n=$(echo "$subject" | grep -oE 'phase [0-9]+' | head -1 | sed 's/phase //')
        if [[ "$gate_n" -lt "$PHASE_NUM" ]]; then
            # git log is newest-first; take the first hit (= most recent prev gate).
            if [[ -z "$prev_gate_sha" ]]; then
                prev_gate_sha="$sha"
                prev_gate_num="$gate_n"
            fi
        fi
    fi
done < <(git -C "$REPO_ROOT" log --pretty=format:"%h %s")

if [[ -n "$prev_gate_sha" ]]; then
    SHA_RANGE="${prev_gate_sha}..HEAD"
    info "Previous gate: phase ${prev_gate_num} at ${prev_gate_sha}"
    info "Commit range : ${SHA_RANGE}"
else
    SHA_RANGE=""
    info "No previous gate commit found — using full git log."
fi

echo ""

# ---------------------------------------------------------------------------
# 2. Enumerate commits in range.
# ---------------------------------------------------------------------------

echo "--- Commits in range ---"

if [[ -n "$SHA_RANGE" ]]; then
    commits_raw=$(git -C "$REPO_ROOT" log --pretty=format:"%h %s" "${SHA_RANGE}" 2>/dev/null || true)
else
    commits_raw=$(git -C "$REPO_ROOT" log --pretty=format:"%h %s" 2>/dev/null || true)
fi

if [[ -z "$commits_raw" ]]; then
    echo "No commits found for phase ${PHASE_NUM}. Nothing to gate."
    exit 0
fi

commit_count=$(echo "$commits_raw" | wc -l | tr -d ' ')
echo "  ${commit_count} commit(s):"
echo "$commits_raw" | head -20 | while IFS= read -r c; do
    echo "    $c"
done
if [[ "$commit_count" -gt 20 ]]; then
    echo "    ... ($(( commit_count - 20 )) more)"
fi

last_shas=$(echo "$commits_raw" | head -5 | awk '{print $1}' | tr '\n' ' ')
echo ""
info "Latest SHAs: ${last_shas}"

# Gate description: first non-gate commit subject in range.
gate_description=$(echo "$commits_raw" | awk '{$1=""; sub(/^ /,""); print}' \
    | grep -v "^chore(tech-debt): phase" | head -1)
[[ -z "$gate_description" ]] && gate_description="phase ${PHASE_NUM} work"

echo ""

# ---------------------------------------------------------------------------
# 3. Run drift-detect.py --json and parse output.
# ---------------------------------------------------------------------------

echo "--- drift-detect.py --json ---"

drift_json=""
if command -v python3 >/dev/null 2>&1 && [[ -f "$DRIFT_DETECT" ]]; then
    drift_json=$(python3 "$DRIFT_DETECT" --json 2>/dev/null || true)
fi

if [[ -n "$drift_json" ]]; then
    drift_errors=$(DRIFT_JSON="$drift_json" python3 -c "
import json, os
data = json.loads(os.environ.get('DRIFT_JSON','{}'))
print(data.get('error_count', 0))
" 2>/dev/null || echo "0")
    echo "  drift errors total : ${drift_errors}"

    # Parse PLAN_DEV_COVERAGE findings.
    dev_coverage_output=$(DRIFT_JSON="$drift_json" python3 -c "
import json, os
data = json.loads(os.environ.get('DRIFT_JSON','{}'))
for f in data.get('findings', []):
    if f.get('check') == 'PLAN_DEV_COVERAGE' and f.get('severity') == 'error':
        dev = f.get('context', {}).get('dev', '?')
        phase = f.get('context', {}).get('phase', '?')
        desc = f.get('context', {}).get('desc', '')
        print(f'DEV #{dev} (phase {phase}): {desc}')
" 2>/dev/null || true)

    if [[ -n "$dev_coverage_output" ]]; then
        echo ""
        echo "  PLAN_DEV_COVERAGE drifts:"
        while IFS= read -r drift_line; do
            echo "    WARNING: $drift_line"
        done <<< "$dev_coverage_output"
    else
        echo "  No PLAN_DEV_COVERAGE drifts detected."
    fi
else
    echo "  drift-detect skipped (python3 or script unavailable)."
fi

echo ""

# ---------------------------------------------------------------------------
# 4. Propose ACCEPTANCE.md updates.
# ---------------------------------------------------------------------------

echo "--- ACCEPTANCE.md candidates ---"

# Extract ACC-NN tokens from commit subjects in range.
acc_candidates=()
while IFS= read -r commit_line; do
    while IFS= read -r acc_token; do
        [[ -n "$acc_token" ]] && acc_candidates+=("$acc_token")
    done < <(echo "$commit_line" | grep -oE 'ACC-[0-9]+[A-Z]?' | sort -u)
done <<< "$commits_raw"

# Remove duplicates.
if [[ ${#acc_candidates[@]} -gt 0 ]]; then
    mapfile -t acc_candidates < <(printf '%s\n' "${acc_candidates[@]}" | sort -u)
fi

acc_to_flip=()
if [[ ${#acc_candidates[@]} -gt 0 ]] && [[ -f "$ACCEPTANCE_MD" ]]; then
    for acc_id in "${acc_candidates[@]}"; do
        # Check if this ACC section already has a status marker.
        # Read from the heading until the next heading (### ).
        section_has_marker=false
        in_section=false
        while IFS= read -r aline; do
            if echo "$aline" | grep -qE "^### ${acc_id}[[:space:]—]"; then
                in_section=true
                continue
            fi
            if $in_section; then
                if echo "$aline" | grep -qE '^###'; then
                    break
                fi
                if echo "$aline" | grep -qE '✅|❌|🟡|\[SHIPPED'; then
                    section_has_marker=true
                    break
                fi
            fi
        done < "$ACCEPTANCE_MD"

        if $section_has_marker; then
            info "${acc_id}: already has status marker — skip"
        else
            acc_to_flip+=("$acc_id")
            info "${acc_id}: MISSING status marker — will flip ✅"
        fi
    done
fi

if [[ ${#acc_to_flip[@]} -eq 0 ]]; then
    echo "  No ACCEPTANCE.md updates proposed."
fi
echo ""

# ---------------------------------------------------------------------------
# 5. Prompt user.
# ---------------------------------------------------------------------------

echo "--- Proposed gate commit ---"
echo "  Message: chore(tech-debt): phase ${PHASE_NUM} gate — ${gate_description}"
echo ""
echo "  IMPL.md   : row ${PHASE_NUM} → set [x] gate \`<NEW_SHA>\`"
if [[ ${#acc_to_flip[@]} -gt 0 ]]; then
    echo "  ACCEPTANCE: flip ${#acc_to_flip[@]} marker(s) to ✅ : ${acc_to_flip[*]}"
fi
echo ""

if [[ -t 0 ]]; then
    read -r -p "Apply updates and create gate commit? [y/N] " response
    response="${response,,}"
    if [[ "$response" != "y" && "$response" != "yes" ]]; then
        echo "Aborted."
        exit 0
    fi
else
    echo "(Non-interactive mode — proceeding automatically)"
fi

echo ""

# ---------------------------------------------------------------------------
# 6a. Edit IMPL.md: update phase N row status to [x] gate `__GATE_SHA__`.
# ---------------------------------------------------------------------------

echo "--- Editing IMPL.md ---"

IMPL_MD_PATH="$IMPL_MD" PHASE_NUM_EDIT="$PHASE_NUM" python3 - <<'PYEOF'
import re, os

impl_path = os.environ["IMPL_MD_PATH"]
phase_num = os.environ["PHASE_NUM_EDIT"]

with open(impl_path, encoding="utf-8") as fh:
    lines = fh.readlines()

# Table row whose first column == phase_num.
row_re = re.compile(r"^\|\s*" + re.escape(phase_num) + r"\s*\|")
# Backtick SHA pattern — detects an existing gated row.
sha_re = re.compile(r"`[0-9a-f]{7,40}`")
changed = False
new_lines = []
for line in lines:
    if row_re.match(line):
        parts = line.rstrip("\n").split("|")
        # parts: ['', num, phase_title, file, effort, status, '']
        if len(parts) >= 6:
            status_cell = parts[5]
            has_sha = bool(sha_re.search(status_cell))
            # Update when there's no backtick SHA yet (even if [x] is present).
            if not has_sha:
                parts[5] = " [x] gate `__GATE_SHA__` "
                new_line = "|".join(parts) + "\n"
                new_lines.append(new_line)
                changed = True
                continue
    new_lines.append(line)

if changed:
    with open(impl_path, "w", encoding="utf-8") as fh:
        fh.writelines(new_lines)
    print(f"  IMPL.md: phase {phase_num} row updated (SHA placeholder inserted)")
else:
    print(f"  IMPL.md: no change needed for phase {phase_num} (already has backtick SHA)")
PYEOF

# ---------------------------------------------------------------------------
# 6b. Edit ACCEPTANCE.md: flip selected markers to ✅
# ---------------------------------------------------------------------------

if [[ ${#acc_to_flip[@]} -gt 0 ]]; then
    echo ""
    echo "--- Editing ACCEPTANCE.md ---"
    for acc_id in "${acc_to_flip[@]}"; do
        ACCEPTANCE_MD_PATH="$ACCEPTANCE_MD" PHASE_NUM_PY="$PHASE_NUM" ACC_ID_PY="$acc_id" python3 - <<'PYEOF'
import re, os

acceptance_path = os.environ.get("ACCEPTANCE_MD_PATH", "")
acc_id = os.environ.get("ACC_ID_PY", "")
phase_num = os.environ.get("PHASE_NUM_PY", "?")

if not acc_id:
    print("  ACCEPTANCE.md: no ACC_ID — skipped")
    raise SystemExit(0)

with open(acceptance_path, encoding="utf-8") as fh:
    content = fh.read()

heading_re = re.compile(
    r"(^### " + re.escape(acc_id) + r"[ \t—].*$)",
    re.MULTILINE,
)
m = heading_re.search(content)
if m:
    insert_pos = m.end()
    status_line = f"\n\n**Status**: ✅ — Shipped in phase {phase_num} gate."
    new_content = content[:insert_pos] + status_line + content[insert_pos:]
    with open(acceptance_path, "w", encoding="utf-8") as fh:
        fh.write(new_content)
    print(f"  ACCEPTANCE.md: {acc_id} status marker inserted")
else:
    print(f"  ACCEPTANCE.md: {acc_id} heading not found — skipped")
PYEOF
    done
fi

echo ""

# ---------------------------------------------------------------------------
# 6c. git add + git commit (with placeholder SHA in IMPL.md)
# ---------------------------------------------------------------------------

echo "--- Creating gate commit ---"

files_to_stage=("$IMPL_MD")
[[ -f "$ACCEPTANCE_MD" ]] && files_to_stage+=("$ACCEPTANCE_MD")

git -C "$REPO_ROOT" add "${files_to_stage[@]}"

commit_msg="chore(tech-debt): phase ${PHASE_NUM} gate — ${gate_description}"
git -C "$REPO_ROOT" commit -m "$commit_msg"

new_gate_sha=$(git -C "$REPO_ROOT" rev-parse --short HEAD)
echo ""
info "Gate commit created: ${new_gate_sha}"

# ---------------------------------------------------------------------------
# 7. Back-fill real SHA into IMPL.md and amend.
# ---------------------------------------------------------------------------

echo ""
echo "--- Back-filling SHA in IMPL.md ---"

IMPL_MD_PATH="$IMPL_MD" NEW_GATE_SHA="$new_gate_sha" python3 - <<'PYEOF'
import os, pathlib

# Locate IMPL.md from env or derive from cwd.
impl_path = os.environ.get("IMPL_MD_PATH", "")
if not impl_path:
    impl_path = str(pathlib.Path.cwd() / "IMPLEMENTATION.md")

new_sha = os.environ.get("NEW_GATE_SHA", "")
if not new_sha:
    print("  IMPL.md: NEW_GATE_SHA not set — cannot replace placeholder")
    raise SystemExit(1)

with open(impl_path, encoding="utf-8") as fh:
    content = fh.read()

if "__GATE_SHA__" in content:
    updated = content.replace("__GATE_SHA__", new_sha)
    with open(impl_path, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print(f"  IMPL.md: __GATE_SHA__ replaced with {new_sha}")
else:
    print("  IMPL.md: no __GATE_SHA__ placeholder found — nothing replaced")
PYEOF

git -C "$REPO_ROOT" add "$IMPL_MD"
git -C "$REPO_ROOT" commit --amend --no-edit

final_sha=$(git -C "$REPO_ROOT" rev-parse --short HEAD)

echo ""
echo "=== Phase ${PHASE_NUM} gate committed ==="
echo "  Final SHA  : ${final_sha}"
echo "  Full SHA   : $(git -C "$REPO_ROOT" rev-parse HEAD)"
echo "  Message    : ${commit_msg}"
echo ""
echo "Done."
