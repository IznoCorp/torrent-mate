# Phase 0 — The window

**Delivers:** the branch on today's `origin/main`, the wave's `SHA` fixed, the spec's counts
refreshed against the tree as it is at the window, and proof that every guard is green BEFORE
anything moves — so a red guard later is attributable to this wave.

**Files:** none created. Modifies nothing tracked.

**Interfaces:**

- Produces: the shell variable `SHA` (eight hex characters, `origin/main` after the merge) that
  phases 4 and 5 write into every `@sha` citation, and the scratch file
  `$SCRATCH/counts.txt` phases 2–4 compare their grep results against.

---

### Task 0.1: Refuse to start outside the window

- [ ] **Step 1: Check L12 has merged and its post-merge gesture is done**

```bash
cd /Users/izno/dev/PersonalScraper-steward
git remote update origin >/dev/null 2>&1 || true
git log --oneline origin/main | grep -E 'maquette-l12' | head -3
git show origin/main:IMPLEMENTATION.md | grep -E '^\| \*\*(In flight|Last landed)\*\*' | cut -c1-160
git ls-tree -d --name-only origin/main docs/archive/features/ | grep maquette-l12
gh pr list --state open --limit 10
```

Expected: at least one `main` subject carries `(#NNN)` with `maquette-l12`; the « In flight » row
reads `none`; « Last landed » names L12; `docs/archive/features/maquette-l12` is listed; no open
pull request other than #539 (this wave's draft). If any of the four is false, STOP — the window
is not open, and moving documentation under a lot in flight is the failure the spec's decision 5
exists to prevent.

- [ ] **Step 2: Check no harness is running on this machine**

Use `ListAgents`, then `SendMessage` to any live implementing session: « the steward takes the
harness for the docs-cleanup wave; tell me if you are mid-run ». Wait for the answer before
phase 2's `make check`.

### Task 0.2: Bring the branch to today's main and fix the SHA

- [ ] **Step 1: Merge, never rebase**

```bash
cd /Users/izno/dev/PersonalScraper-steward
git status --short          # must be empty
git merge --no-edit origin/main
git log --oneline -3
```

Expected: a merge commit or a fast-forward; no conflict (the spec commit adds two files nothing
else touches).

- [ ] **Step 2: Fix the wave's SHA and record it**

```bash
SHA=$(git rev-parse --short=8 origin/main); echo "$SHA"
SCRATCH=/private/tmp/claude-501/-Users-izno-dev-PersonalScraper/b5f0d053-c6b6-4635-9e16-446a78dab9f7/scratchpad
mkdir -p "$SCRATCH"; echo "$SHA" > "$SCRATCH/sha.txt"
git cat-file -e "$SHA:docs/archive/features/maquette-l07/DESIGN.md" && echo "holds L07 design"
git cat-file -e "$SHA:docs/archive/features/maquette-l12/DESIGN.md" && echo "holds L12 design"
```

Expected: both `holds` lines print. Every phase's shell starts with
`SHA=$(cat "$SCRATCH/sha.txt")`.

### Task 0.3: Refresh the spec's counts against this tree

- [ ] **Step 1: Recount every end the spec § 3 lists**

```bash
cd /Users/izno/dev/PersonalScraper-steward
{
echo "## directives → leaving trees"
for pat in 'docs/archive/' 'docs/superpowers/' 'docs/analysis/' 'docs/features/maquette-l10-ter/'; do
  echo "--- $pat"
  grep -c -F "$pat" BUGS.md IMPLEMENTATION.md CLAUDE.md docs/reference/frontend-architecture.md docs/reference/frontend-steward.md docs/reference/product-intent-map.md docs/reference/feature-lifecycle.md docs/reference/libraries.md frontend/maquette/README.md | grep -v ':0$'
done
echo "## Design: markers per document"
grep -rhoE 'Design: docs/[^#[:space:]]+' --include='*.py' tests | sort | uniq -c | sort -rn
echo "## code prose citing a present document"
grep -rn -E 'docs/reference/(architecture|commands|config-overlay-layout|event-bus|external-ids-flow|grab-core|indexer-json-shapes|indexer|insights|logging|maintenance|pipeline-internals|promises|runbook-post-merge|scraping|storage|trailers|web-ui)\.md' --include='*.py' --include='*.ts' --include='*.tsx' personalscraper tests scripts frontend/maquette | grep -v 'Design:' | cut -d: -f1 | sort | uniq -c
echo "## the archive's size now"
git ls-files docs/archive docs/superpowers docs/analysis | wc -l
} > "$SCRATCH/counts.txt"; cat "$SCRATCH/counts.txt"
```

Expected: the numbers match the spec § 3 except where L12 added lines (its archive, its row in
`IMPLEMENTATION.md`, possibly new register entries citing `docs/archive/features/maquette-l12/`).
Write the differences down: phase 4 rewrites what THIS list says, not what the spec counted on
2026-08-31.

- [ ] **Step 2: Prove the guards are green before anything moves**

```bash
cd /Users/izno/dev/PersonalScraper-steward
python3 scripts/check-docs-cited-paths.py | tail -1
python3 scripts/update_feature_map.py --check && echo "maps fresh"
python3 scripts/audit_design_coverage.py --strict | tail -1
python3 scripts/audit-cli-coverage.py | tail -1
python3 scripts/check-no-french.py | tail -1 | cut -c1-80
```

Expected: every line green. A red line here is not this wave's — file it, do not fix it here,
and decide with the operator whether the window stays open.

- [ ] **Step 3: Take the next free register numbers**

```bash
python3 scripts/check-bug-register.py --next
```

Expected: `B-NNN (highest written: …)`. Note the number: phase 5 files three entries from it
(the spec § 5), consecutive. Re-run it at phase 5 before writing — another branch may have taken
one meanwhile.

No commit in this phase: nothing tracked changed except the merge.
