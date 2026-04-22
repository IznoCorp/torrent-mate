# Branch + PR Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add branch creation and PR workflow to the implementation skills (`implement-version`, `implement-phase`, `archive-version`)

**Architecture:** Extend `github-curl` with `pr-create` and `pr-merge` subcommands (REST POST/PUT), then modify each skill's SKILL.md to integrate branching and PR steps at the right points in the workflow.

**Tech Stack:** Bash (gh-api.sh), Python (gh-parse.py), Markdown (skill files)

---

## File Map

| File                                        | Action | Purpose                                                                                |
| ------------------------------------------- | ------ | -------------------------------------------------------------------------------------- |
| `.claude/skills/github-curl/gh-api.sh`      | Modify | Add `rest_post`, `rest_put` helpers + `pr-create`, `pr-merge`, `pr-status` subcommands |
| `.claude/skills/github-curl/gh-parse.py`    | Modify | Add `pr-url`, `pr-merge-status` parsers                                                |
| `.claude/skills/github-curl/SKILL.md`       | Modify | Document new subcommands                                                               |
| `.claude/skills/implement-version/SKILL.md` | Modify | Add branch creation + config injection after archiving                                 |
| `.claude/skills/implement-phase/SKILL.md`   | Modify | Add last-phase PR creation logic                                                       |
| `.claude/skills/archive-version/SKILL.md`   | Modify | Add PR verification/merge + local branch cleanup                                       |

---

### Task 1: Add PR subcommands to gh-api.sh

**Files:**

- Modify: `.claude/skills/github-curl/gh-api.sh:28-38` (add helpers)
- Modify: `.claude/skills/github-curl/gh-api.sh:200-237` (add subcommands + dispatch)

- [ ] **Step 1: Add `rest_post` and `rest_put` helpers after `rest_get` (line 33)**

```bash
# ── Helper: REST POST ─────────────────────────────────────────
rest_post() {
  local endpoint="$1"
  local body="$2"
  curl -s -X POST -H "$AUTH_HEADER" -H "$ACCEPT_HEADER" -H "$CONTENT_HEADER" "$API$endpoint" -d "$body"
}

# ── Helper: REST PUT ──────────────────────────────────────────
rest_put() {
  local endpoint="$1"
  local body="$2"
  curl -s -X PUT -H "$AUTH_HEADER" -H "$ACCEPT_HEADER" -H "$CONTENT_HEADER" "$API$endpoint" -d "$body"
}
```

- [ ] **Step 2: Add `cmd_pr_create` subcommand before the dispatch block**

```bash
cmd_pr_create() {
  # Usage: gh-api.sh pr-create <title> <body> [base]
  local title="${1:?Usage: gh-api.sh pr-create <title> <body> [base]}"
  local body="${2:?Usage: gh-api.sh pr-create <title> <body> [base]}"
  local base="${3:-main}"
  local head
  head=$(git branch --show-current)
  local payload
  payload=$(python3 -c "
import json, sys
print(json.dumps({
    'title': sys.argv[1],
    'body': sys.argv[2],
    'head': sys.argv[3],
    'base': sys.argv[4]
}))
" "$title" "$body" "$head" "$base")
  rest_post "/repos/$OWNER/$REPO/pulls" "$payload"
}
```

- [ ] **Step 3: Add `cmd_pr_merge` subcommand**

```bash
cmd_pr_merge() {
  # Usage: gh-api.sh pr-merge <pr_number> [merge|squash]
  local pr_num="${1:?Usage: gh-api.sh pr-merge <pr_number> [merge|squash]}"
  local method="${2:-merge}"
  local payload
  payload=$(python3 -c "
import json, sys
print(json.dumps({'merge_method': sys.argv[1]}))
" "$method")
  rest_put "/repos/$OWNER/$REPO/pulls/$pr_num/merge" "$payload"
}
```

- [ ] **Step 4: Add `cmd_pr_status` subcommand**

```bash
cmd_pr_status() {
  # Usage: gh-api.sh pr-status <pr_number>
  local pr_num="${1:?Usage: gh-api.sh pr-status <pr_number>}"
  rest_get "/repos/$OWNER/$REPO/pulls/$pr_num"
}
```

- [ ] **Step 5: Register new subcommands in the dispatch case block**

Add these entries to the `case "$SUBCOMMAND"` block:

```bash
  pr-create)         cmd_pr_create "$@" ;;
  pr-merge)          cmd_pr_merge "$@" ;;
  pr-status)         cmd_pr_status "$@" ;;
```

And add to the usage text:

```
  pr-create <title> <body> [base]  Create PR from current branch (REST POST)
  pr-merge <pr_number> [method]    Merge PR (method: merge|squash, default: merge)
  pr-status <pr_number>            Get PR details (state, merged, etc.)
```

- [ ] **Step 6: Verify gh-api.sh syntax**

Run: `bash -n ".claude/skills/github-curl/gh-api.sh"`
Expected: no output (syntax OK)

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/github-curl/gh-api.sh
git commit -m "feat(github-curl): add pr-create, pr-merge, pr-status subcommands"
```

---

### Task 2: Add PR parsers to gh-parse.py

**Files:**

- Modify: `.claude/skills/github-curl/gh-parse.py:305-320` (add commands + register)

- [ ] **Step 1: Add `cmd_pr_url` function before the COMMANDS dict**

```python
def cmd_pr_url(data):
    """Extract PR URL from pr-create or pr-status response."""
    err = check_errors(data)
    if err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(3)
    if isinstance(data, dict):
        print(data.get("html_url", ""))
    elif isinstance(data, list) and data:
        print(data[0].get("html_url", ""))
    else:
        print("")
```

- [ ] **Step 2: Add `cmd_pr_merge_status` function**

```python
def cmd_pr_merge_status(data):
    """Check PR merge status from pr-status response.

    Prints: 'merged', 'open', or 'closed'.
    """
    err = check_errors(data)
    if err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(3)
    if isinstance(data, dict):
        if data.get("merged"):
            print("merged")
        else:
            print(data.get("state", "unknown"))
    else:
        print("unknown")
```

- [ ] **Step 3: Register new commands in the COMMANDS dict**

```python
    "pr-url": cmd_pr_url,
    "pr-merge-status": cmd_pr_merge_status,
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import py_compile; py_compile.compile('.claude/skills/github-curl/gh-parse.py', doraise=True)"`
Expected: no output (syntax OK)

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/github-curl/gh-parse.py
git commit -m "feat(github-curl): add pr-url and pr-merge-status parsers"
```

---

### Task 3: Update github-curl SKILL.md documentation

**Files:**

- Modify: `.claude/skills/github-curl/SKILL.md`

- [ ] **Step 1: Add new subcommands to the `gh-api.sh Subcommands` table**

Add these rows:

```markdown
| `pr-create <title> <body> [base]` | Title, body, base branch (default: main) | Create PR from current branch |
| `pr-merge <pr> [method]` | PR number, merge method (merge\|squash) | Merge a PR |
| `pr-status <pr>` | PR number | Get PR state (open/closed/merged) |
```

- [ ] **Step 2: Add new subcommands to the `gh-parse.py Subcommands` table**

Add these rows:

```markdown
| `pr-url` | `pr-create` or `pr-status` | PR HTML URL |
| `pr-merge-status` | `pr-status` | "merged", "open", or "closed" |
```

- [ ] **Step 3: Add usage example in the Usage section**

```markdown
# Create PR

PR_JSON=$(bash "$SKILL_DIR/gh-api.sh" pr-create "feat: my feature" "## Summary\n- Added X")
PR_URL=$(echo "$PR_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-url)
PR_NUM=$(echo "$PR_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-number)

# Merge PR

bash "$SKILL_DIR/gh-api.sh" pr-merge "$PR_NUM" "merge"

# Check merge status

STATUS_JSON=$(bash "$SKILL_DIR/gh-api.sh" pr-status "$PR_NUM")
echo "$STATUS_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-merge-status
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/github-curl/SKILL.md
git commit -m "docs(github-curl): document pr-create, pr-merge, pr-status"
```

---

### Task 4: Modify `/implement-version` skill

**Files:**

- Modify: `.claude/skills/implement-version/SKILL.md`

- [ ] **Step 1: Replace the entire `## Process` section with the new workflow**

The new section 2 ("Launch Brainstorming") stays the same. Insert a new section between archive and brainstorming:

````markdown
### 2. Create Branch

After successful archiving (or if this is the first version with no archive needed):

1. **Ask conventional commit type** — prompt the user:

   > Type de commit conventionnel ? (feat, chore, fix, docs, tests…)

2. **Ask feature name** — prompt the user:

   > Nom de la feature pour la branch ?

   Slugify the answer: lowercase, replace spaces with hyphens, strip special chars.

3. **Ask merge strategy** — prompt the user:

   > Stratégie de merge pour la PR ? (auto-merge / auto-squash / manual)

4. **Create the branch:**

   ```bash
   git checkout -b {type}/{name}
   ```
````

If branch already exists → ask user: switch to existing branch (`git checkout {type}/{name}`) or pick a new name.

5. **Inject config into `IMPLEMENTATION.md`** — the file was just created by `/archive-version` (or create it now for first version). Add/fill these fields in the metadata block at the top:

   ```markdown
   **Branch:** `{type}/{name}`
   **PR merge:** auto-merge | auto-squash | manual
   **PR:** _(created after last phase)_
   ```

6. **Commit:**

   ```bash
   git add IMPLEMENTATION.md
   git commit -m "init: branch {type}/{name}"
   ```

````

- [ ] **Step 2: Renumber the brainstorming section from `### 2` to `### 3`**

The brainstorming section stays identical, just renumbered to `### 3. Launch Brainstorming`.

- [ ] **Step 3: Update the `## What this skill does NOT do` section**

Add:

```markdown
- Does not push the branch — pushing happens in `/implement-phase` when the PR is created
- Does not create the PR — that happens automatically at the end of the last phase
````

- [ ] **Step 4: Verify the skill file is valid markdown**

Read the file back and check for broken formatting, mismatched headings, or syntax issues.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/implement-version/SKILL.md
git commit -m "feat(implement-version): add branch creation and config injection"
```

---

### Task 5: Modify `/implement-phase` skill

**Files:**

- Modify: `.claude/skills/implement-phase/SKILL.md`

- [ ] **Step 1: Add PR creation logic after step 5 (Phase review gate)**

Insert a new step 6 after the existing phase review gate:

````markdown
6. **Last-phase PR creation** (only if ALL phases are done):

   After the phase review gate, check `IMPLEMENTATION.md`: if every phase row has `[x]` or `✅`, this was the last phase.

   a. **Read branch config** from `IMPLEMENTATION.md`:
   - `**Branch:**` → branch name (e.g., `feat/library-maintenance`)
   - If no `**Branch:**` field → skip PR creation (legacy project, no branch workflow)

   b. **Check if PR already exists** — if `**PR:**` already contains a URL (not the placeholder), skip PR creation (idempotent).

   c. **Push the branch:**

   ```bash
   git push -u origin {type}/{name}
   ```

   d. **Create PR via `/github-curl`:**

   ```bash
   SKILL_DIR=".claude/skills/github-curl"
   PR_JSON=$(bash "$SKILL_DIR/gh-api.sh" pr-create "{type}: {description}" "{body}" "main")
   PR_URL=$(echo "$PR_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-url)
   PR_NUM=$(echo "$PR_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-number)
   ```

   - **Title:** `{type}: {description}` — conventional commit format, description extracted from design spec heading
   - **Body:** auto-generated markdown with:
     - Summary of all completed phases (from `IMPLEMENTATION.md`)
     - Link to the design spec file

   e. **Update `IMPLEMENTATION.md`** — replace the PR placeholder:

   ```markdown
   **PR:** {PR_URL}
   ```

   f. **Commit + push:**

   ```bash
   git add IMPLEMENTATION.md
   git commit -m "docs: add PR link to IMPLEMENTATION.md"
   git push
   ```
````

- [ ] **Step 2: Verify the skill file is valid markdown**

Read the file back and check formatting.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/implement-phase/SKILL.md
git commit -m "feat(implement-phase): add PR creation on last phase completion"
```

---

### Task 6: Modify `/archive-version` skill

**Files:**

- Modify: `.claude/skills/archive-version/SKILL.md`

- [ ] **Step 1: Add PR handling section between pre-flight checks and version detection**

Insert a new section `### 1b. PR Verification and Merge` after the existing pre-flight checks:

````markdown
### 1b. PR Verification and Merge

**Skip this entire section if `IMPLEMENTATION.md` has no `**Branch:**` field** (legacy project without branch workflow).

1. **Read config from `IMPLEMENTATION.md`:**
   - `**Branch:**` → branch name
   - `**PR merge:**` → `auto` or `manual`
   - `**PR:**` → PR URL (extract PR number from URL)

2. **Verify PR exists:**

   ```bash
   SKILL_DIR=".claude/skills/github-curl"
   STATUS_JSON=$(bash "$SKILL_DIR/gh-api.sh" pr-status "$PR_NUM")
   STATUS=$(echo "$STATUS_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-merge-status)
   ```
````

If PR not found → error: "No PR found at {PR_URL}. Run the last /implement-phase first."

3. **Execute merge strategy:**

   **If `auto`:**
   - Ask user: "Merge commit ou squash merge ?"
   - Merge via `/github-curl`:

     ```bash
     bash "$SKILL_DIR/gh-api.sh" pr-merge "$PR_NUM" "merge"   # or "squash"
     ```

   - Switch to main:

     ```bash
     git checkout main
     git pull
     ```

   **If `manual`:**
   - Check PR status (from step 2 above)
   - If status is not `merged` → error: "PR not merged yet. Merge it manually then re-run /archive-version."
   - If `merged`:

     ```bash
     git checkout main
     git pull
     ```

````

- [ ] **Step 2: Add branch cleanup to section 4 (Execution), after the commit**

Add after the existing `git add` + `git commit` step:

```markdown
7. **Branch cleanup** (only if `**Branch:**` field existed):

   ```bash
   git branch -d {type}/{name}
````

Remote branch is **not** deleted (preserved for history).

If delete fails (branch not fully merged) → warning only, do not block archiving.

````

- [ ] **Step 3: Update the summary display (section 3) to show PR info**

Add to the summary block:

```markdown
PR:
  - Strategy: {auto|manual}
  - Status: {merged|open|to be merged}
  - Action: {merge via API|verify already merged|skip (no PR)}

Post-archive:
  - Delete local branch: {type}/{name}
````

- [ ] **Step 4: Verify the skill file is valid markdown**

Read the file back and check formatting.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/archive-version/SKILL.md
git commit -m "feat(archive-version): add PR verification, merge, and branch cleanup"
```

---

### Task 7: Final integration commit

- [ ] **Step 1: Verify all 6 files are consistent**

Read all modified files and cross-check:

- `IMPLEMENTATION.md` field names match across all 3 skills (`**Branch:**`, `**PR merge:**`, `**PR:**`)
- `/github-curl` subcommand names in skill files match `gh-api.sh` dispatch block
- Parser subcommand names match `gh-parse.py` COMMANDS dict

- [ ] **Step 2: Update github-curl SKILL.md description to mention PR creation/merge**

Update the frontmatter `description` to include:

```yaml
description: |
  Use when making GitHub API calls from the Claude Code sandbox. Provides sandbox-safe
  scripts that replace gh api / gh api graphql (which fail due to Go TLS issues).
  WHEN: Any GitHub API interaction (PRs, review threads, comments, thread resolution, PR creation, PR merging).
  WHEN NOT: When gh cli works (outside sandbox) or for non-GitHub API calls.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/github-curl/SKILL.md
git commit -m "chore: final consistency check across branch-pr workflow skills"
```
