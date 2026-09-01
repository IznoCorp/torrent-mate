# Phase 3 — The frame's model and survey become reference documents

**Delivers:** `docs/reference/frame-model.md` and `docs/reference/frame-survey.md`, every citation
of `docs/features/maquette-l10-ter/MODEL.md` / `SURVEY.md` and every bare `MODEL.md` / `SURVEY.md`
in a living document rewritten, the plan's twenty-four references intact. The rest of the L10-ter
folder waits for phase 4.

**Files:**

- Move: `docs/features/maquette-l10-ter/MODEL.md` → `docs/reference/frame-model.md`,
  `docs/features/maquette-l10-ter/SURVEY.md` → `docs/reference/frame-survey.md`.
- Modify: `docs/reference/frontend-architecture.md`, `docs/reference/product-intent-map.md`,
  `docs/reference/frontend-steward.md` (if it cites them), `CLAUDE.md`, `BUGS.md`,
  `IMPLEMENTATION.md`, the two moved files (they cite each other), and any `docs/features/*`
  file still in the tree that cites them.

**Interfaces:**

- Produces: the two paths above, cited bare (they are tracked) by every living document.

---

### Task 3.1: Move, then enumerate every citation

- [ ] **Step 1: Move**

```bash
cd /Users/izno/dev/PersonalScraper-steward
git mv docs/features/maquette-l10-ter/MODEL.md docs/reference/frame-model.md
git mv docs/features/maquette-l10-ter/SURVEY.md docs/reference/frame-survey.md
```

- [ ] **Step 2: Enumerate before rewriting — living files only**

```bash
grep -rnE 'maquette-l10-ter/(MODEL|SURVEY)\.md|`(MODEL|SURVEY)\.md`' --include='*.md' CLAUDE.md BUGS.md IMPLEMENTATION.md docs/reference docs/features frontend/maquette/README.md | cut -c1-140
```

Expected: the plan (around 24), `CLAUDE.md` (1 row), `BUGS.md` (2–3), `IMPLEMENTATION.md` (2),
`product-intent-map.md` (1), the two moved files (2), possibly `docs/features/docs-cleanup/`
(this plan — leave it: it is a wave's file and dies at merge). Anything under
`docs/features/maquette-l10-ter/` is deleted in phase 4 and is not rewritten.

### Task 3.2: Rewrite

- [ ] **Step 1: The full paths**

```bash
for file in CLAUDE.md BUGS.md IMPLEMENTATION.md docs/reference/frontend-architecture.md docs/reference/product-intent-map.md docs/reference/frontend-steward.md docs/reference/frame-model.md docs/reference/frame-survey.md; do
  sed -i '' -E 's#docs/features/maquette-l10-ter/MODEL\.md#docs/reference/frame-model.md#g; s#docs/features/maquette-l10-ter/SURVEY\.md#docs/reference/frame-survey.md#g' "$file"
done
```

- [ ] **Step 2: The bare names — where they are not « beside the file you are reading »**

A bare `` `MODEL.md` `` in the plan meant « the file in L10-ter's folder »; it now names a file that
is not beside the plan. Rewrite bare names to the tracked path in the same files:

```bash
for file in CLAUDE.md BUGS.md IMPLEMENTATION.md docs/reference/frontend-architecture.md docs/reference/product-intent-map.md docs/reference/frontend-steward.md docs/reference/frame-model.md docs/reference/frame-survey.md; do
  sed -i '' -E 's#`MODEL\.md`#`docs/reference/frame-model.md`#g; s#`SURVEY\.md`#`docs/reference/frame-survey.md`#g' "$file"
done
grep -rn -E '`(MODEL|SURVEY)\.md`|maquette-l10-ter/(MODEL|SURVEY)' CLAUDE.md BUGS.md IMPLEMENTATION.md docs/reference | cut -c1-120
```

Expected: nothing left except inside command lines that READ history — e.g. `BUGS.md`'s
`git show d3892d18:docs/features/maquette-l10-ter/MODEL.md`, which is already the `@sha` idea in
another syntax and stays as written (it reads a commit, not the tree). Re-read each remaining hit
and leave only those.

- [ ] **Step 3: The `CLAUDE.md` index row**

The row « The frame's model — its thirteen parts … » now reads
`` `docs/reference/frame-model.md` · `docs/reference/frame-survey.md` `` in its second cell. Check
by eye; the `sed` above did it.

- [ ] **Step 4: The plan's exemption paragraph is now false — phase 5 rewrites it**

Do not touch § 5's gesture-four paragraph here; phase 5 rewrites the whole gesture. Only its paths
changed.

### Task 3.3: Prove and commit

- [ ] **Step 1: The guards that read these files**

```bash
python3 scripts/check-docs-cited-paths.py | tail -1
python3 scripts/check-intent-map.py | tail -1
python3 scripts/check-implementation-state.py | tail -1
python3 scripts/check-no-french.py | tail -1 | cut -c1-60
git diff --stat | tail -1
```

Expected: all clean. The `grep -o "maquette-l10-ter\|MODEL\.md\|SURVEY\.md" … | wc -l` command
quoted inside the plan's gesture paragraph now counts differently — that paragraph is rewritten
in phase 5.

- [ ] **Step 2: Read the diff, not the count**

Run: `git diff | grep -E '^[-+]' | grep -v -E '^(\+\+\+|---)' | cut -c1-160`
Expected: every `-` line has a `+` twin differing only in the path; no line lost a word.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md BUGS.md IMPLEMENTATION.md docs/reference
git commit -m "refactor(docs-cleanup): the frame's model and survey are reference documents — frame-model.md, frame-survey.md"
```
