# maquette-l13 — the design and the plan of L13, the engine's death, prepared ahead of its wave

You prepare **L13 — The engine's residue** (`docs/reference/frontend-architecture.md` § 4, entry
`#### L13`, which is the CONTRACT and is not restated here; its « Done when » has four clauses and
two inheritances, and the four « Carried here by … » blocks are part of the contract). You **measure,
decide and plan; you do not implement**: this wave produces `docs/features/maquette-l13/DESIGN.md`
and `docs/features/maquette-l13/plan/` (INDEX.md + one file per phase), nothing under
`frontend/maquette/design/src/`, no rule, no mock, no code. The lot is NEXT by the operator's seventh
measure of 2026-09-12 (« L13 — la mort du moteur — en priorité après les vagues en vol »; the plan's
§ 4 records the re-order beside the 2026-09-02 re-cut, and `IMPLEMENTATION.md` § « Where the frontend
work stands » names it in its « Next » row). Its implementer will read your two documents from `main`
and execute the plan, so they are written for a session that has none of your context — every figure
with its command, every decision with its reason and with what it makes void, every phase with the
proof that closes it.

Branch `docs/maquette-l13-design`, worktree `/Users/izno/dev/worktrees/wave-l13-design` (cut from
`origin/main` at `5eafd3cfc`), one pull request opened READY with the label `no-version-bump`
(prose only — the version does not move), squash merge on the steward's verification once the
operator has read the architecture decisions. You are the only writer there. `IMPLEMENTATION.md`,
`BUGS.md` and the plan are not yours: the steward writes the rows and amends the plan from your
DESIGN.md § « What the plan gets wrong, measured ».

## Why a design phase for a lot that draws nothing

L13 deletes a file of 31 802 lines and everything that rests on it. It is not a surface to draw; it
is the largest ARCHITECTURE decision left in the plan, and the operator's method (2026-09-12) is
explicit: big lots land fast and surface corrections come cheap afterwards, **architecture is the
one place where getting it right BEFORE landing still matters**. So the design's job is to turn the
contract's four clauses into decided homes, a measured order and a cut the operator can read in ten
minutes and rule on. The measurements you start from are in `INVENTORY.md` beside this file (taken
by the steward's read-only reading on 2026-09-13, at `5eafd3cfc`); re-run every command you rely on
— the file is a starting point, not a source.

## What « designed » means here

For each thing that dies or moves, the design says, with a command behind every figure:

1. **What it is** — the lines it spans today, who reads it (product code, the harness, a guard, a
   baseline), and the rule or guard that holds it today.
2. **Its home, or its death.** Where the surviving half goes (which file, under which invariant of
   the plan's § 3, under the 400-line ceiling of `check-frontend-boundaries.py --arm size`, with
   invariant 7's import rules between features), or that it dies with the engine and nothing takes
   its place — and what each reader does then.
3. **The proof.** Which existing rule keeps its hold count unchanged across the move (the
   conversion proof: the oracle green, `harness-hold-counts.py --compare` with `failed` 0 and no
   hold lost), or — for the behaviour changes the contract carries (B-290's two shapes, B-275's
   mirror) — the NEW rule, what it reads, how it is seen red first, and the mutation that fells it.
   A conversion phase carries no behaviour repair and a behaviour phase carries no conversion
   (`docs/reference/frontend-steward.md` § « What a review costs », rule 1) — that is why they are
   separate phases, and the plan says which is which.
4. **What loses its subject** — the guard, the baseline, the arm, the vocabulary section, the
   README sentence, the register row — and the commit that removes it, in the same phase as the
   thing it read. Machinery nobody can justify becomes machinery nobody dares delete: the plan's
   § 7.1 and `CLAUDE.md` both carry that sentence, and this lot is where it bites hardest.

The homes the plan has ALREADY decided, which you apply and do not re-litigate (cite them; a design
that finds one wrong says so in § « What the plan gets wrong, measured » with the command):

- The ladder's HANDLER goes to **one `app/layers.ts`** — the ranked registrations, the back handler,
  `closeLayers`, `hideLayers` — the engine calling it through the seam until the engine is gone
  (`docs/reference/frame-model.md` § 2 Part 4: « the ranking is frame; the move is behaviour »; the
  drawer and the dialog registered in L15 — VERIFY that they did, `frame-model.md` and
  `app/layer-registry.ts`). B-229 (the dialog's rung), B-290 (the two shapes), B-275 (the panel's
  return) are decided THERE, and B-290's arbitration is written out — two shapes become one, and a
  rule COUNTS the entries crossed on the way back.
- The harness's driving seams — `__go`, `__states`, `__queries`, `__relay`, `__mocks` — live in **a
  harness module of the prototype's own build** that dies at switchover with `harness.css`
  (contract, and `IMPLEMENTATION.md`'s sentence on `harness.css`: it IS in the maquette's own build
  and in no production build). `engine/states.js` (786 non-blank lines, B-352) goes with them. You
  decide WHERE that module sits (`design/src/harness/`, or beside `harness.css` under `styles/` is
  not a home for code — say which and why), how the switchover excludes it (read
  `frontend/maquette/harness/switchover.py` — it already lists what moves), and what the 91
  non-driving `window.__` seams the harness reads become: each is EITHER a product seam that keeps
  a definition in the shell (`__panel`, `__store`, `__screens`, `__bridge`, `__address` are the
  shell's already — INVENTORY § 1.4), OR a probe the harness installs itself, OR a residue that dies
  with its rule re-aimed. A table, one row per seam, is the deliverable.
- The five surface-opening verbs and the delegation's frame verbs move to **L21's verb registry**
  (`lib/verbs.ts`, `app/feature-verbs.ts` — read how the mock-layer micro-wave, #592, added
  `feature-verbs.ts` with one import per feature); the delegation block (693 lines, 64 names,
  INVENTORY § 3) dies when its last name has a registered handler. Decide the order in which the
  64 leave (by feature, so each phase is one feature's verbs and its rules), and which three are
  DATA rather than verbs (`index`, `ep`, `selectedTitle`).
- The nine fixture families (26 375 lines, INVENTORY § 4) die with the DRAWING that reads them
  (`sheetFor`, `allSettings`, `cardHTML`, `tileHTML`, `posterBox`, `seasonsOf`, `ownedFor`). The
  mock layer already answers the declared contract from `mocks/` (#592: « the mock answers the
  declared code »): the design says, family by family, whether its data is ALREADY answered by a
  mock handler (then the family dies), or must become a fixture under `mocks/` (then in what shape
  — a generated JSON under the size arm's « generated file » exemption, or a typed module under the
  ceiling — and what `check-frontend-boundaries.py` says about it), or is dead data nobody draws
  (then it dies with nothing). `SHEETS_RAW` alone is 20 538 lines: its answer decides the shape of
  the lot, so it comes first in your reading.
- `refonte.html` (120 lines of ledger inside an empty `@layer` envelope) is deleted; R72 is
  renegotiated with its two surviving holds mutation-tested (`regions.json` already records the
  mutation of record for hold (a)); the ledger gets a home that outlives it — say which document,
  and cite it by commit in the plan's L07 entry the way the documentation model prescribes
  (`docs/reference/documentation-model.md`: history is read with `git show`, not kept in the tree).
  Fourteen files hold the path as a literal (INVENTORY § 6): every one is named in the phase that
  deletes the file, with what it does instead.
- `legacy.css` (2 207 lines, 148 classes, 956 declarations, 238 rules at a zero-slack ceiling) dies
  with the engine's markup: each class either has a variant already (`ui/variants/*.ts` — the arm
  `check-css-tokens.py` and R80's probe say what still shadows what) or belongs to markup that dies
  in the same phase. Its guard `check-legacy-css-residue.py`, its ceiling file, R80, the
  `comment-references-baseline.json` row, and the FRENCH DEBT section of
  `scripts/code-vocabulary.txt` (`CLAUDE.md` § Language: « When the engine goes, that section goes
  with it ») all lose their subject in the same phase.
- The dead `#screen` layer and the mount-node placement that rests on it (B-232, `app/shell.tsx:305–307`)
  go, and the two harness readers of `.screen.open` (`screens.py`, `bridge.py`) are re-aimed with
  their counts unchanged; `__startEngine` (263 lines) and `__releasePage` go when the shell boots
  itself — what `boot_order.py` and `bridge.py` hold f′ then read is written down.

## The cut is an arbitration for the OPERATOR, and you send it in your first two hours

Before the plan, send the steward ONE message: what the lot weighs (the figures, once), and **two
readings of its cut** — (A) ONE wave, one branch, one squash, N phases chained, one reader round at
the end (the office's shape for a lot; cost: a pull request of tens of thousands of deleted lines
read once, a long branch that merges `main` under it for weeks, and the operator's Mac walk at the
end only); (B) L13 split into two to four SUB-LOTS in the plan's own § 4 — e.g. L13a the harness
module and the ladder (frame), L13b the verbs and the delegation, L13c the fixture families and the
drawing, L13d the styles, the fragment and the guards — each a wave with its own squash, its own
reader round (measure 2: one round per lot), its own Mac walk, in a fixed order (cost: three or four
merges and gestures; the register's rows re-owned per sub-lot; and the plan's § 0 rule re-reads
« L13 » as four entries). What each costs, **one recommendation**, and the ORDER inside whichever
reading (what must go first because everything else reads it — the harness module, so every later
phase keeps `__go` — and what can go last). Then CONTINUE on your recommended reading; if the ruling
differs, re-cut the plan — write it so the cut touches the INDEX and the phase boundaries, not the
phases' content. Any other question with two defensible answers (the fixture families' shape, the
harness module's place, whether `screens.py`'s `.screen.open` selector stays) is put to the steward
the same way, batched, never one at a time, and never blocks the rest.

## The plan

`plan/INDEX.md` in L21's shape (read it: `git show 2ffdc4ba3:docs/features/maquette-l21/plan/INDEX.md`
and one phase, `git show 2ffdc4ba3:docs/features/maquette-l21/plan/phase-02-season-grab.md`; and
L20's, on `main`, `docs/features/maquette-l20/plan/INDEX.md`, for a plan written by a design wave):
« the phases chain, they do not pause », the governing rule (for a CONVERSION phase: the oracle
and the hold counts unchanged, `failed` read first; for a BEHAVIOUR phase: the rule first, seen red
against the engine while the engine's branch still exists — the strongest form), the STOPs (B: an
oracle divergence on a state the phase did not touch; C: the pull request; D: a measurement that
contradicts a decided home), the table of phases with what each lands, what it deletes (lines, by
command), what it re-aims and which register rows it closes (the 24 open rows whose body names L13,
INVENTORY § 10, each assigned to a phase or explicitly re-owned with the reason), the ordering and
its reason. One kind of change per phase; the harness module first (every later phase is proved
through `__go`); the guards and baselines die in the phase that kills what they read, never in a
closing sweep; the closing phase re-reads the register, the README's stale « 54 » (87 states today),
`frame-model.md`'s « today → target » lines and `frame-survey.md`, and says what each now reads.
Each phase file: the proof first (what it reads, how it is seen to fall), the move (files created
or deleted — ceiling 400 non-blank lines per file, the engine's own GRANDFATHERED count shrinking
by the phase's figure and `frontend_size_ledger.py` re-recorded in the same commit), the gate, the
commit message. Figures are written ONCE in the design; the plan cites the design.

## What you read before acting, in order

1. `docs/reference/product-intent.md` (French, the constitution) — §15, §16, NE-DOIT-PAS-7, §13.
2. `docs/reference/frontend-architecture.md` § 0, § 2 whole (D1, D1b, D4, D5, D7, D8, D10, D-L06-4),
   § 3, § 4's L07, L09, L12, L15, L19, L21 entries (what each left to L13, and how L19 measured),
   L13 (yours), § 5 (the instruments' debts block — which are L13's), § 6, § 7.1.
3. `docs/reference/frame-model.md` whole and `docs/reference/frame-survey.md` whole — the survey's
   line numbers have moved; re-run its commands.
4. `docs/features/maquette-l13/INVENTORY.md` (beside this file) — then re-run its commands.
5. `frontend/maquette/README.md` whole; `frontend/maquette/harness/switchover.py` (what the
   switchover already knows to move), `frontend/maquette/regions.json` R72 and R80,
   `scripts/frontend_size_ledger.py`, `scripts/check-legacy-css-residue.py`,
   `scripts/check-frontend-boundaries.py` (its arms), `scripts/code-vocabulary.txt` (the banner).
6. `BUGS.md` bodies of B-229, B-232, B-275, B-290, B-327, B-352, B-366, B-465 and the sixteen others
   INVENTORY § 10 lists; B-383 (« said, not done » — the class no phase of yours may join).
7. The maquette as it stands: `frontend/maquette/design/src/app/` (shell.tsx, history-bridge.ts,
   layer-registry.ts, panel-host.ts, feature-verbs.ts, engine-redraw.ts, engine-data.ts),
   `engine/seams.ts` (what the engine still publishes), `engine/states.js` (the state table),
   `lib/verbs.ts`, `mocks/` (index.ts, handlers/, scenario.ts, declared-status.ts), `ui/variants/`.
8. `docs/reference/documentation-model.md` (where the ledger's home may live).
9. Optional: `http://127.0.0.1:8712/` is `tm-design` (pm2, the main checkout's build) — read it in a
   browser to see what the engine still draws; never rebuild or restart it.

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    pwd && git branch --show-current && git status --short
    grep -n "^#### L13" docs/reference/frontend-architecture.md
    grep -o "| \*\*Next\*\*[^|]*| [^.]\{0,60\}" IMPLEMENTATION.md
    wc -l frontend/maquette/design/src/engine/legacy.js frontend/maquette/design/src/engine/states.js frontend/maquette/design/src/styles/legacy.css frontend/maquette/design/refonte.html
    python3 scripts/check-frontend-boundaries.py --arm size; echo "exit $?"
    python3 scripts/check-legacy-css-residue.py; echo "exit $?"
    grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)" frontend/maquette/design/src/engine/legacy.js
    grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
    ls frontend/maquette/design/src/app/ frontend/maquette/design/src/mocks/
    git check-ignore -v docs/features/maquette-l13/BRIEF.md; echo "exit $? (1 = not ignored, expected)"

## Non-goals

- No file under `frontend/maquette/design/`, `frontend/maquette/harness/`, `personalscraper/`,
  `scripts/`; no rule written, no mock, no seed, no i18n edit, no deletion — the implementer does
  those from your plan.
- No edit to `docs/reference/frontend-architecture.md`, `IMPLEMENTATION.md`, `BUGS.md`,
  `frame-model.md`, `frame-survey.md`, `product-intent-map.md`: a design that finds a directive
  wrong says so in DESIGN.md § « What the plan gets wrong, measured » with the command, and the
  steward amends it.
- No redrawing of any validated surface (§15: what is in the maquette is validated); the engine's
  nine drawing sites become components that draw the SAME thing, proved by the oracle.
- No heavy run: you build nothing and drive no browser; the one exception is reading `tm-design`
  in a browser. `npm ci` is not needed for this wave. This branch touches only `docs/`: push it
  with `--no-verify` — the pre-push hook's suite reads nothing you change — and SAY SO in the
  push report, with `git diff --name-only origin/main | grep -v '^docs/'` shown empty; run
  `python3 scripts/check-docs-cited-paths.py` and `python3 scripts/check-no-french.py` before the
  push (exit codes in the report).
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

Commits: `docs(maquette-l13): …`, one per document (DESIGN, INDEX, each phase), conventional, no
attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg` refuses it).
`git ls-remote --heads origin docs/maquette-l13-design` read after the push. Pull request READY,
label `no-version-bump`, title `docs(maquette-l13): the design and the plan of the engine's death`,
body: the cut and its ruling, the homes table (one line per thing that dies or moves), the phases,
the register rows assigned, what the plan gets wrong if anything. Report to the orchestrator: on the
handshake (readings + gauge), on the cut arbitration, on the push (head sha, PR number), with the
gauge each time. Do not stop between documents to report one done.

## Resource envelope — the machine is shared (2026-09-13)

At most two agents run beside the steward on this 8-core, 16 GB host (the operator's sixth measure
of 2026-09-12). This wave is prose: it starts no browser, no build, no test run. What still binds:

- **Every command runs synchronously in the tool call that waits for it**, long output to a FILE
  (`> /tmp/l13-design-<step>.log 2>&1`), the exit code read in the same call; never `| tail -N` on
  a long command, never a turn ended « waiting for » anything.
- **Search safety** (`CLAUDE.md`): every `rg`/`grep -r` carries a type filter (`--type py`,
  `-g '*.ts'`, `--include='*.js'`…); never `rg` a directory bare. **Never `cd` into
  `frontend/maquette/design/src`** (B-384): absolute paths from your worktree root.
- If you ever need a run under a lock (you should not): `sh scripts/heavy.sh --class rule l13-design <command>`
  for anything touching the served copy, and `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder` for
  any pytest — announced to the steward one line before and one after. Read the lock with
  `sh scripts/heavy.sh --held`, never the directory.
- **Kill what you start, prove it with `ps`** before every report.
- Context: run `/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.28.3/skills/context-gauge/scripts/context-gauge.sh`
  as the LAST call before every report and paste its `context_percent=` and `source=` lines; past
  60 %, finish the document in progress, commit and push a resume note in your folder, and stop.
- Tier **deep** (the map binds every tier to opus; no tier of this project is ever Sonnet), chosen
  because the deliverable is an architecture decision nothing downstream re-checks but the operator's
  reading and the steward's. Your session was spawned with NO MCP server; none is needed.
