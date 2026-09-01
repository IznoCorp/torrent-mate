# Phase 5 — The directives change in the same move

**Delivers:** every directive that described the old model now describes the new one — `CLAUDE.md`
(§ Language, the reference index, the archive sentence), the plan's § 1 and § 5 (gesture four and
its exemption), `IMPLEMENTATION.md` (this wave's rows, the spec pointer), the office (the model is
the steward's to hold), the `README.md` signpost, `.gitignore`'s two dead lines, the register's
three findings, the version bump. Green at the end: `make check` and `run.sh --contracts`.

**Files:**

- Modify: `CLAUDE.md`, `docs/reference/frontend-architecture.md`, `IMPLEMENTATION.md`,
  `docs/reference/frontend-steward.md`, `README.md`, `.gitignore`, `BUGS.md`,
  `personalscraper/__init__.py`.

**Interfaces:**

- Consumes: `SHA`; the register numbers from `check-bug-register.py --next` (re-run now).

---

### Task 5.1: `CLAUDE.md`

- [ ] **Step 1: § Language — the exception list**

Replace the two bullets « **Operator-facing docs stay French** … » and « `docs/archive/` is frozen
history — never translated, never restyled. » with:

```markdown
- **One document stays French, by name**: `docs/reference/product-intent.md`, the constitution,
  dictated by the operator and amended by the operator alone. The documents describing the
  version in production (`docs/production/`, `README.md`) keep the language they were written
  in — they are frozen and die at the switchover; the next version's operator documents are born
  in English. The rule, the three families and their fates:
  `docs/reference/documentation-model.md`.
```

And in the sentence above the list, the parenthesis `(`docs/`, `BUGS.md`, `CHANGELOG.md`,
`ROADMAP.md`, `IMPLEMENTATION.md`, this file)` loses `ROADMAP.md` (it is in production now).

- [ ] **Step 2: The reference index**

Above the table's first row, add one paragraph:

```markdown
**Three families, one rule** — `docs/reference/documentation-model.md`: a row pointing into
`docs/production/` describes the version IN PRODUCTION, frozen, dying at the switchover; a row
pointing into `docs/reference/` describes the next version or what is true whatever the version.
History is not in the tree: a path cited as `` `path@sha` `` is read with `git show sha:path`.
```

Add the row, first in the table:

```markdown
| **The documentation model — which version a document may describe, where it lives, how history is cited (BINDING)** | `docs/reference/documentation-model.md` |
```

The two rows pointing at `docs/archive/features/registry/DESIGN.md@SHA` and
`docs/archive/features/config-home/DESIGN.md@SHA` (phase 4 rewrote the paths) stay as rows:
their subjects are still real questions. Delete the closing line « Also check archived alpha
versions under `docs/archive/legacy-alpha/` and archived features under `docs/archive/features/`. »
and put in its place:

```markdown
Everything a merged wave wrote is in git, not in the tree: `git log --all --oneline -- <path>`
finds the commit, `git show <sha>:<path>` reads it.
```

- [ ] **Step 3: The maquette section's sentence about the archive gesture**

`grep -n 'docs/archive' CLAUDE.md` — any remaining mention outside an `@SHA` citation is
rewritten to the new gesture (« deleted at merge, cited by commit »). Then:

```bash
python3 scripts/check-no-french.py | tail -1 | cut -c1-60
grep -n 'scripts/check-no-french.py` (fifteen arms' CLAUDE.md | wc -l
```

Expected: green, and `1` — the self-description sentence is intact.

### Task 5.2: The plan (`docs/reference/frontend-architecture.md`)

- [ ] **Step 1: § 1's two mentions of `docs/superpowers/`**

Line ~37 « Write the wave's plan under `docs/superpowers/plans/` » →
« Write the wave's plan under `docs/features/<codename>/plan/` ». The table row
``| `docs/superpowers/specs/` · `plans/` | the scope and the steps of ONE wave |`` →
``| `docs/features/<codename>/DESIGN.md` · `plan/` | the scope and the steps of ONE wave — deleted at merge, cited by commit |``.

- [ ] **Step 2: § 5, gesture four**

Replace the whole paragraph beginning « **And a fourth: ARCHIVE the wave's design and plan** » and
ending « …has the count above to argue with. » with:

```markdown
**And a fourth: DELETE the wave's folder and cite it by commit** — `docs/features/<codename>/`
leaves the tree (`git rm -r`), and every citation of a file in it that a living document still
needs is rewritten to `` `path@sha` `` in the same step, `sha` being `origin/main` at that moment
(`docs/reference/documentation-model.md` § 2; the guard's history arm refuses the folder coming
back under `docs/archive/`). A file the wave wrote that has become a durable reference — a model,
a survey, a rule — is not left in the folder as an exception: it moves to `docs/reference/` under
a name that says what it is, with its citations. Added on 2026-08-26 by B-083 as an ARCHIVE step,
after the third wave out of eight where the gesture slipped; turned into a deletion on 2026-08-31
when `docs/archive/` left the tree, because a second copy of history in the tree was 224 000 lines
a reader could open by mistake. The operator arbitrated a step here rather than a guard — the
check is cheap to imagine and this list is not, on the evidence, cheap to remember.
```

- [ ] **Step 3: § 6 — the trap about the archive, if any**

`grep -n -i 'archive' docs/reference/frontend-architecture.md | grep -v "@${SHA}"` — read each
hit; a sentence saying « `docs/archive/` is frozen history that a lot may not amend » becomes
« history is in git and a lot may not rewrite it ».

- [ ] **Step 4: Prove**

```bash
python3 scripts/check-intent-map.py | tail -1
python3 scripts/check-docs-cited-paths.py | tail -1
```

### Task 5.3: `IMPLEMENTATION.md`

- [ ] **Step 1: This wave's row — NOT A LOT**

Under « Where the frontend work stands », set the « In flight » row to:

```markdown
| **In flight** | **docs-cleanup — the documentation model's first application**, PR **#539**, `chore/docs-cleanup`. **NOT A LOT**: a directives wave, the steward's, between L12 and L13; it moves no maquette source. Spec: `docs/features/docs-cleanup/DESIGN.md`; the rule it applies: `docs/reference/documentation-model.md`. |
```

(The post-merge gesture moves it to a « Between L12 and L13 » row, like L07-bis and L10-bis.)

- [ ] **Step 2: The spec pointer and the wave log**

Line ~32 `**Spec:** \`docs/superpowers/specs/2026-08-10-…@SHA\``(phase 4 rewrote it) — add
« (in history) » after it. Line ~517 « The full record of each wave … is in`docs/superpowers/shell-mobile-wave-log.md@SHA`; the per-wave plans are in … » — phase 4 rewrote
the sentence; read it once more here.

- [ ] **Step 3: Prove**

Run: `python3 scripts/check-implementation-state.py | tail -1`
Expected: clean — the row names an OPEN pull request; the guard accepts it until #539 lands.

### Task 5.4: The office, the README, `.gitignore`

- [ ] **Step 1: The office** — `docs/reference/frontend-steward.md`, under « ## The office », one
      paragraph at the end:

```markdown
**The documentation model is the steward's to hold.** `docs/reference/documentation-model.md`
says which version a document may describe and where it lives; the steward's audit reads a
landed wave against it — its folder deleted, its citations by commit, nothing born in
`docs/production/` — and `scripts/check-docs-cited-paths.py`'s three arms are the instrument.
```

- [ ] **Step 2: The README signpost** — first line after `# TorrentMate` and its badges:

```markdown
> This document describes the version **in production**, which the next version replaces — the
> constitution of that next version is `docs/reference/product-intent.md`, and which document
> describes which version is `docs/reference/documentation-model.md`.
```

English, on purpose: it is the model speaking, not the manual.

- [ ] **Step 3: `.gitignore`** — delete the comment fragment `(see docs/features/config-home/DESIGN.md)`
      from line ~150 (keep the rest of the comment) and delete line ~170
      `docs/features/provider-ids/plan/DEVIATIONS.md`.

### Task 5.5: The register — three findings, one recount

- [ ] **Step 1: Take the numbers**

Run: `python3 scripts/check-bug-register.py --next`
Expected: `B-NNN`. The three entries below take `NNN`, `NNN+1`, `NNN+2`.

- [ ] **Step 2: Three rows in the open table** (after the last `| B-… |` row), and three bodies in
      the « Open » section in the register's form (title, what, why no rule saw it, the proof line in
      `<sub>`):

```markdown
| B-NNN | `IMPLEMENTATION.md` cited a « parked » L06 spec at a directory no commit ever held | by audit | `fixed #539` |
| B-NNN+1 | 38 `Design:` markers name `docs/features/…` paths that left the tree, and the design-gaps pair passes over them | by audit | `open` |
| B-NNN+2 | `.gitignore` cited two `docs/features/…` files that no longer exist | by audit | `fixed #539` |
```

Bodies (fill the sha and the found file from phase 4's task 4.2 step 2):

```markdown
**B-NNN — the « parked » L06 spec was cited at a directory that never existed.** `IMPLEMENTATION.md`
said « the L06 spec is parked, not lost — `docs/superpowers/roadmap/maquette-l06/specs/` », and
`git log --all -- docs/superpowers/roadmap/maquette-l06` is empty: no commit on any branch has held
that directory. The cited-paths guard is blind to a directory by design (a directory is a set; the
file that matters is cited on its own line), so the sentence sat green. Found by the docs-cleanup
inventory; rewritten in #539 to <the file found, `@sha`, or « lost »>.

<sub>`git log --all --oneline -- docs/superpowers/roadmap/maquette-l06 | wc -l` → 0</sub>

**B-NNN+1 — 38 `Design:` markers point at paths that left the tree, and nothing says so.**
`grep -rhoE 'Design: docs/[^#[:space:]]+' --include='*.py' tests | sort | uniq -c` shows 16 for
`docs/features/api-unify/DESIGN.md`, 13 for `torrent-fetch`, 5 for `watch-seed`, 2 for
`scraper`, 1 each for `webui-ux/plan/phase-04-scraping.md` and `test-coverage` — features archived
long ago. `update_feature_map.py --check` and `audit_design_coverage.py --strict` are green over
them: a marker whose path resolves to no map file is not an error to either. A guard green over
what it does not read (B-085 species). Left as found by #539, which moved the 78 live markers;
the fix is the design-gaps pair refusing a marker whose path `git ls-files` does not hold.

<sub>`grep -rhoE 'Design: docs/features/[^#[:space:]]+' --include='*.py' tests | sort | uniq -c`</sub>

**B-NNN+2 — two dead `docs/features/` paths in `.gitignore`.** Line 150's comment cited
`docs/features/config-home/DESIGN.md` and line 170 ignored
`docs/features/provider-ids/plan/DEVIATIONS.md`; neither file is in the tree. Harmless and
misleading; removed in #539.

<sub>`git ls-files docs/features/config-home docs/features/provider-ids | wc -l` → 0</sub>
```

- [ ] **Step 3: The B-085 counter** — in « ## Guards green over what they do not read », add this
      wave's row in the table's form: `docs-cleanup` · found by the wave: 1 (B-NNN+1) · found by
      readers: 0 · Total = previous total + 1.

- [ ] **Step 4: Prove**

Run: `python3 scripts/check-bug-register.py | tail -1`
Expected: clean.

### Task 5.6: The version, the gates, the commit

- [ ] **Step 1: Bump**

```bash
grep -n '__version__' personalscraper/__init__.py
```

Raise the patch component by one (`0.98.N` → `0.98.N+1`, whatever `N` is at the window).

- [ ] **Step 2: The two tiers, announced first**

```bash
make check 2>&1 | tail -3
frontend/maquette/harness/run.sh --contracts 2>&1 | tail -5
```

Expected: both green; `run.sh` prints its guard count and no fallen rule.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/reference/frontend-architecture.md IMPLEMENTATION.md docs/reference/frontend-steward.md README.md .gitignore BUGS.md personalscraper/__init__.py
git commit -m "docs(docs-cleanup): the directives describe the model — gesture four deletes and cites by commit, the index knows three families, three findings filed"
```
