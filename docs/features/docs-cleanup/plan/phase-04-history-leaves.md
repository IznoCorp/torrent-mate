# Phase 4 — History leaves the tree

**Delivers:** `docs/archive/`, `docs/superpowers/`, `docs/analysis/`, the residue of
`docs/features/maquette-l10-ter/` and `docs/features/tech-debt-2/` deleted; every living citation
of a deleted FILE rewritten to `` `path@SHA` ``; every living citation of a deleted DIRECTORY
rewritten by hand to the file that matters; arm 2 wired. Green at the end: the guard, and
`git ls-files` over the three trees printing `0`.

**Files:**

- Delete (git rm -r): the five trees above.
- Modify: `BUGS.md`, `IMPLEMENTATION.md`, `CLAUDE.md`, `docs/reference/frontend-architecture.md`,
  `docs/reference/feature-lifecycle.md`, `docs/reference/libraries.md`,
  `frontend/maquette/README.md`, `scripts/check-docs-cited-paths.py` (`main()`).
- Left as written (spec § 3, « on purpose »): every file under `docs/production/`.

**Interfaces:**

- Consumes: `SHA` from phase 0; phase 1's `arm_no_history_in_tree()`.
- Produces: `main()` running arms 1, 2 and 3.

---

### Task 4.1: Delete

- [ ] **Step 1: Confirm nothing under the trees is still needed live**

`api-unify/DESIGN.md` left in phase 2, `MODEL.md` and `SURVEY.md` in phase 3. Check:

```bash
cd /Users/izno/dev/PersonalScraper-steward
git ls-files docs/archive/features/api-unify docs/features/maquette-l10-ter
```

Expected: `api-unify/` lists no `DESIGN.md`; `maquette-l10-ter/` lists `BRIEF.md`,
`DEFINITION.md`, `HANDOVER.md`, `QUESTIONS.md`, `REPORT.md` only.

- [ ] **Step 2: Remove**

```bash
git rm -r -q docs/archive docs/superpowers docs/analysis docs/features/maquette-l10-ter docs/features/tech-debt-2
git ls-files docs/archive docs/superpowers docs/analysis docs/features/maquette-l10-ter docs/features/tech-debt-2 | wc -l    # 0
git status --short | grep -c '^D'
```

Expected: `0`, and a deletion count equal to phase 0's « the archive's size now » plus 6.

### Task 4.2: Cite by commit

- [ ] **Step 1: Every FILE citation in a living document, mechanically**

```bash
SHA=$(cat "$SCRATCH/sha.txt")
LIVING="BUGS.md IMPLEMENTATION.md CLAUDE.md docs/reference/frontend-architecture.md docs/reference/feature-lifecycle.md docs/reference/libraries.md docs/reference/frontend-steward.md docs/reference/product-intent-map.md frontend/maquette/README.md"
for file in $LIVING; do
  sed -i '' -E "s#\`(docs/(archive|superpowers|analysis)/[A-Za-z0-9_./-]+\.(md|json|json5|py|txt|sh|mjs|ts|tsx|js|css|html|yml|yaml))\`#\`\1@${SHA}\`#g" "$file"
done
grep -c "@${SHA}\`" $LIVING | grep -v ':0$'
```

Expected: counts close to phase 0's per-file numbers (files, not directories). A path already
followed by `@` is not touched twice — the pattern requires a closing backtick right after the
extension.

- [ ] **Step 2: Every DIRECTORY citation and every un-backticked one — by hand, each one read**

```bash
grep -n -E 'docs/(archive|superpowers|analysis)/' $LIVING | grep -v "@${SHA}" | cut -c1-200
```

For each hit, decide from the sentence:

- A directory cited as a whole (`docs/archive/features/maquette-l08/`, « the per-wave plans are in
  `docs/superpowers/plans/` ») → name the file that matters, `@SHA`
  (`docs/archive/features/maquette-l08/DESIGN.md@SHA`; « the per-wave plans are in
  `docs/superpowers/plans/`, read with `git show SHA:docs/superpowers/plans/<file>` »), or, when
  the sentence only says WHERE things used to be, rewrite it to say they are in history.
- A path outside backticks (`docs/reference/feature-lifecycle.md` line 117:
  `(see docs/archive/features/tech-debt/audit/11-global-synthesis.md §out-of-scope)`) → backtick
  it and add `@SHA`.
- A shell command that reads the tree (`BUGS.md`: `` `ls docs/archive/features/ | tr … | grep maquette` ``)
  → it is evidence of what was true when written; leave it as written inside a sentence that is
  already past tense, or prefix the command with `git show SHA:` when it must still run.
- `IMPLEMENTATION.md`'s « the L06 spec is parked, not lost — `docs/superpowers/roadmap/maquette-l06/specs/` »:
  find it first — `git log --all --oneline -S 'maquette-l06' -- docs/superpowers | head`, then
  `git log --all --oneline -- 'docs/archive/features/maquette-l06/*spec*'`. Rewrite the sentence to
  the file found, `@SHA` (or `@<the commit that holds it>` if it was never on `main` at `SHA`), or
  to « the L06 spec was never committed anywhere this repository can show; what it settled is in
  this file's L06 paragraphs » if nothing is found. This is the spec's finding 1; phase 5 files it.

```bash
grep -n -E 'docs/(archive|superpowers|analysis)/' $LIVING | grep -v "@${SHA}" | grep -v 'git show' | wc -l
```

Expected: `0`.

- [ ] **Step 3: The lifecycle's § 6 dies here, its § 7 pointers go to history**

`docs/reference/feature-lifecycle.md` § 6 (« Cross-Feature DESIGN Drift », the banner rule)
becomes:

```markdown
## 6. A superseded design is history

A design that a later feature invalidates is not annotated: it left the tree when its wave
merged, and `docs/reference/` is the only authority on the present. What a reader must know
about the change is in the reference document the later feature updated. Reading an old design
is `git show <sha>:<path>`; the citation form is `docs/reference/documentation-model.md` § 2.
```

Its two citations of `docs/archive/superpowers/specs/2026-04-22-implement-skills-refactor-design.md`
are now `@SHA` (step 1 did it); leave them.

- [ ] **Step 4: `libraries.md` and the maquette README**

`docs/reference/libraries.md` line 48 (`docs/archive/legacy-alpha/guessit-evaluation.md`) and
`frontend/maquette/README.md` line 248 (the 2026-08-10 spec) were rewritten by step 1. Read both
sentences once: they must still make sense with a commit in them.

### Task 4.3: Wire arm 2, prove, commit

- [ ] **Step 1: `main()` runs all three arms**

```python
    violations = arm_cited_paths() + arm_no_history_in_tree() + arm_production_manifest()
```

- [ ] **Step 2: Prove every `@SHA` citation resolves — the guard does it, and three by hand**

```bash
python3 scripts/check-docs-cited-paths.py
python3 scripts/check-docs-cited-paths.py 2>&1 | grep -c 'does not hold\|not one commit'    # 0
for citation in $(grep -ohE '`docs/[^`]+@[0-9a-f]+`' BUGS.md IMPLEMENTATION.md docs/reference/frontend-architecture.md | tr -d '`' | sort -u | head -3); do
  echo "== $citation"; git show "${citation#*@}:${citation%@*}" | grep -m1 '^# '
done
```

Expected: the guard prints `[history]: 0 tracked path(s)` and `clean`; the three `git show` print
each file's first heading. Keep this output for the pull request body (phase 6).

- [ ] **Step 3: The other readers**

```bash
python3 scripts/check-implementation-state.py | tail -1
python3 scripts/check-bug-register.py | tail -1
python3 scripts/check-no-french.py | tail -1 | cut -c1-60
python3 -m pytest tests/scripts -q 2>&1 | tail -1
```

Expected: all green. `check-bug-register.py`'s `--next` no longer needs `BUGS-CLOSED.md` to
change: it stays.

- [ ] **Step 4: Read the diff of the living files**

Run: `git diff -- $LIVING | grep -E '^[-+]' | grep -v -E '^(\+\+\+|---)' | cut -c1-160`
Expected: every rewritten line still reads as a sentence; no citation lost its path.

- [ ] **Step 5: Commit**

```bash
git add -A docs BUGS.md IMPLEMENTATION.md CLAUDE.md frontend/maquette/README.md scripts/check-docs-cited-paths.py
git commit -m "refactor(docs-cleanup): history leaves the tree — docs/archive, docs/superpowers, docs/analysis are read from git, cited by commit"
```
