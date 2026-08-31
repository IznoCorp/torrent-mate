# Phase 6 — The proofs, and the pull request

**Delivers:** the spec § 7's definition of done, executed and pasted into PR #539's body; the
three mutations each seen red and restored; the diff re-read; the draft turned into a pull request
ready for the operator's word. Nothing in this phase changes a tracked file except restoring what
a mutation broke.

**Files:** none modified at the end. PR #539 (`chore/docs-cleanup`) — body rewritten, label
`no-version-bump` removed, draft status lifted.

---

### Task 6.1: The counts the spec promised

- [ ] **Step 1: The trees**

```bash
cd /Users/izno/dev/PersonalScraper-steward
git ls-files docs/archive docs/superpowers docs/analysis | wc -l                       # 0
git ls-files docs/production | wc -l                                                  # 23
python3 -c "import json; print(len(json.load(open('scripts/production-docs-manifest.json'))['files']))"   # 23
git ls-files docs | wc -l
git ls-files 'docs/*.md' | wc -l
```

Record the last two: the spec said 53 documents plus `_samples/` plus the open wave's folder.

- [ ] **Step 2: The guard, in full**

Run: `python3 scripts/check-docs-cited-paths.py`
Expected: six directive lines, `[history]: 0 tracked path(s)`, `[production]: 23 file(s), manifest
names 23, 0 born, 0 gone`, `clean`. Paste the output.

### Task 6.2: Three mutations — break, see the fall, restore (commit first: the tree is committed)

- [ ] **Step 1: Arm 2 — a file reborn under a history tree**

```bash
git status --short | wc -l           # 0 before mutating
mkdir -p docs/archive && echo "reborn" > docs/archive/reborn.md && git add -f docs/archive/reborn.md
python3 scripts/check-docs-cited-paths.py; echo "exit=$?"
git rm -q -f docs/archive/reborn.md && rmdir docs/archive 2>/dev/null; git status --short | wc -l
```

Expected: `exit=1`, the message names `docs/archive/reborn.md` under « history »; the tree is
clean again.

- [ ] **Step 2: Arm 3 — a birth in production**

```bash
echo "# born" > docs/production/born.md && git add -f docs/production/born.md
python3 scripts/check-docs-cited-paths.py; echo "exit=$?"
git rm -q -f docs/production/born.md; git status --short | wc -l
```

Expected: `exit=1`, the message names `docs/production/born.md` as « not in the manifest »; clean.

- [ ] **Step 3: Arm 1 — a commit that does not hold the path**

Pick one `@sha` citation in `BUGS.md`, replace its sha by `0000000` (seven zeros — a syntactically
valid abbreviation that is not a commit), run, restore:

```bash
CITATION=$(grep -ohE '`docs/[^`]+@[0-9a-f]+`' BUGS.md | head -1); echo "$CITATION"
BROKEN=$(printf '%s' "$CITATION" | sed -E 's/@[0-9a-f]+`/@0000000`/')
python3 - "$CITATION" "$BROKEN" <<'PY'
import sys, pathlib
p = pathlib.Path("BUGS.md"); s = p.read_text(encoding="utf-8")
assert s.count(sys.argv[1]) >= 1
p.write_text(s.replace(sys.argv[1], sys.argv[2], 1), encoding="utf-8")
PY
python3 scripts/check-docs-cited-paths.py; echo "exit=$?"
git checkout -- BUGS.md; git status --short | wc -l
```

Expected: `exit=1`, « not one commit » naming the citation; clean. Then a second variant: a REAL
commit that predates the file — take `SHA_OLD=$(git rev-list --max-parents=0 HEAD | head -1)` (the
root commit), substitute it the same way, expect « does not hold the path », restore.

### Task 6.3: Three `git show`, the diff, the gates

- [ ] **Step 1: Read three citations from history**

```bash
for citation in $(grep -ohE '`docs/[^`]+@[0-9a-f]+`' IMPLEMENTATION.md docs/reference/frontend-architecture.md CLAUDE.md | tr -d '`' | sort -u | head -3); do
  echo "== $citation"; git show "${citation#*@}:${citation%@*}" | grep -m1 '^# '
done
```

Expected: three headings. Paste them.

- [ ] **Step 2: Re-read the whole diff against `origin/main`, by kind**

```bash
git diff --stat origin/main...HEAD | tail -1
git diff origin/main...HEAD -- CLAUDE.md IMPLEMENTATION.md BUGS.md docs/reference README.md .gitignore | grep -E '^[-+]' | grep -v -E '^(\+\+\+|---)' | wc -l
git diff origin/main...HEAD -- personalscraper tests scripts frontend .github | grep -E '^[-+]' | grep -v -E '^(\+\+\+|---)' | grep -v -E 'docs/(production|reference)/' | cut -c1-160
```

Read the third command's output line by line: it is every code-side change that is NOT a path
rewrite — it must be exactly the guard, its tests, the override table's new key and comment, the
manifest, the CI filter block, the version. Anything else is a defect of this wave.

- [ ] **Step 3: The gates, once more, on the final tree**

```bash
make check 2>&1 | tail -3
frontend/maquette/harness/run.sh --contracts 2>&1 | tail -3
python3 -c "import personalscraper; print(personalscraper.__version__)"
```

### Task 6.4: The pull request

- [ ] **Step 1: Push**

Run: `git push --no-verify origin chore/docs-cleanup 2>&1 | tail -1`

- [ ] **Step 2: The body, the label, the status**

```bash
gh pr edit 539 --remove-label no-version-bump
gh pr edit 539 --body-file "$SCRATCH/pr-body.md"
gh pr ready 539
gh pr checks 539 --watch 2>&1 | tail -8
```

`$SCRATCH/pr-body.md` holds, in this order: the five decisions (from the spec § 0); the counts of
task 6.1; the guard's full output; the three mutations with their messages; the three `git show`
headings; the diff summary of task 6.3 step 2; the `SHA` every citation names, in one sentence:
« every path that ever lived under `docs/archive/`, `docs/superpowers/` and `docs/analysis/`
exists at `SHA` »; the six `.claude/` files the operator's skills must change, untouched here; the
three register entries filed; the version. End with the session link the harness asks for in
pull-request bodies.

- [ ] **Step 3: Wait for CI, then hand it to the operator**

Expected: every check green, including `harness-contracts` (the `maquette` filter fires: the
mocks' comments and the harness comment changed), `design-gaps`, `version-bump`, the `python` job.
The pull request is merged on the operator's word — a documentation move of this size is theirs to
release. After the merge: the post-merge gesture of the plan's § 5 as it stands that day (this
wave's own gesture four included — `docs/features/docs-cleanup/` leaves the tree, cited by the
squash commit), the worktree removed, the steward's memory brought to resume state.
