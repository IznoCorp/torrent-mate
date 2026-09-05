# maquette-schedulers — B-308, the seventh scheduler, and the hold-count baseline

You open a **micro-wave**, decided by the operator on 2026-09-05 (« micro-vague pour B-308 avant
L21 »): one register entry, one instrument's record, no lot. It runs BEFORE L21 because the full rule
suite has been red on `main` since #557 for a reason that is nobody's lot, and every wave to come
would inherit « one red, it is known » — the habit B-277 names. Branch `fix/maquette-schedulers`,
one pull request, squash merge, the version bumps.

**What B-308 is.** `frontend/maquette/harness/machine.py` reads the operator's live PM2 list and the
backend's scheduler registry against what the Système page draws, and reads **6 drawn vs 7 real**
since `personalscraper-index-full` was scheduled (#557, `4c0e274a7`). The interface has to describe
what the machine runs (§13: real data), and the row it lacks is the full index scan. Read the entry
whole in `BUGS.md` before anything else — it says why nothing caught it and what the finding is
beyond the missing row.

## What you read before acting

1. `CLAUDE.md`; `docs/reference/documentation-model.md`; `docs/reference/frontend-architecture.md`
   § 0, D5 (the engine is subtracted from — and the size ledger REFUSES it growing: B-306, discharged
   at L19), D7 (mocks are seeded from the contract and the running backend's shapes), § 3 invariants
   6, 7, 10, 11, § 5 (the proof, the post-merge gesture, B-291 in the instruments' debts block).
2. `BUGS.md`: B-308 (yours), B-291 (the recorder writes a baseline over a failed rule without a word
   — read `failed` FIRST), B-277 (a fall under load), B-306 (the ledger that refuses `legacy.js` up).
3. `IMPLEMENTATION.md` § « Where the frontend work stands » — L19 is the last landed, its gesture
   (#561) deliberately did NOT re-record `frontend/maquette/hold-counts-baseline.json`, and says why.
4. `docs/reference/frontend-steward.md` § « What a review costs, and the five rules » — they bind
   your review from round one, small as this wave is.

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    grep -o "| \*\*In flight\*\*[^|]*| [^.]\{0,60\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    TM_HARNESS_JOBS=1 sh scripts/heavy.sh <you> python3 frontend/maquette/harness/machine.py 2>&1 | tail -3
    pm2 jlist | python3 -c "import sys,json; print(sorted(a['name'] for a in json.load(sys.stdin) if a['name'].startswith('personalscraper-')))"
    grep -n "const SCHEDULERS" frontend/maquette/design/src/engine/legacy.js
    grep -rn "SCHEDULERS\|maintenance/schedulers" frontend/maquette/design/src/features/system frontend/maquette/design/src/mocks frontend/maquette/design/src/app/engine-data.ts
    grep -n "engine/legacy.js" scripts/frontend_size_ledger.py
    python3 scripts/harness-hold-counts.py --help

Read on 2026-09-05 at `aec70c308`: `machine.py` red on « as many schedulers drawn as PM2
schedules — 6 drawn vs 7 real »; `SCHEDULERS` is a 67-line fixture at `legacy.js:4979` with a derived
`SCHEDULERS_DOWN`, read by `features/system/queries.ts` through `/api/maintenance/schedulers`
(`useSystemRead`) and by `features/system/reference.ts`; the ledger records `legacy.js` at **31 645**
and refuses it upward; `--next` says **B-323**.

## The four things the plan does not tell you

### 1. You cannot add the row where it lives, and that is the design

The fixture is in the engine, and the ledger refuses `legacy.js` growing by one line (B-306, with the
mutation that proves it). D5 says the engine dies by subtraction. So the seventh scheduler is NOT a
line added to `SCHEDULERS`: **the family leaves the engine** — it moves to where the mock answers
`/api/maintenance/schedulers` (under `mocks/`, seeded from the running backend's shape, D7 — read
the shape from the real endpoint on the operator's machine: `personalscraper` exposes it, and the
maquette's contract under `frontend/maquette/contract/` names it), the system feature reads the mock
as it already does, and `SCHEDULERS` / `SCHEDULERS_DOWN` and their `window` republication go. The
ledger's record for `legacy.js` is re-recorded DOWNWARD in the same commit (the arm prints the new
count; a growth is refused, a shrink must be written). Net: the engine loses ~70 lines, the mock gains
the seven rows it should have carried since L08.

### 2. The oracle will move, and that is accepted under B-308's name

A seventh row on Système is a surface change: `make maquette-oracle` will read divergences on the
`sys-*` states' regions. Each divergence is accepted with B-308 as the reason (D8, « accepted with
reasons »), and the reference is re-recorded ONCE on the final head: `make maquette-oracle` then
`python3 frontend/maquette/oracle.py --record` (§ 5 gives the two commands and why the first is not
optional). The 390 px states must show no overflow with seven rows (`harness/states.py`).

### 3. The rule that bites is the one that is red today — and one more

`machine.py` is the rule: green with seven drawn, and it must FALL if the mock draws six again
(mutate the mock's list, see it red naming the missing name, restore). It reads the LIVE PM2 list, so
it is a full-suite rule and not a contracts-tier one, and it cannot hold on a runner — say so in the
report rather than moving it. The one more: a rule that the drawn schedulers are the BACKEND's list
is not this wave's (it is a demand on the contract, D7); but write in B-308's body that the fixture
and the machine are one contract with two ends and only one end has a guard — the entry already says
it, keep it true.

### 4. Then the baseline, and `failed` first

With `machine.py` green the full suite has no red rule left (verify: the 92 rules + yours). Then, and
only then, `python3 scripts/harness-hold-counts.py --record frontend/maquette/hold-counts-baseline.json`
under the lock (`TM_HARNESS_JOBS=2 sh scripts/heavy.sh <you> …`), and READ `failed` in the totals
BEFORE you commit the file: it must be **0**. The movements since the recorded baseline at
`64c43d0e7` are L19's (eight changed, five new, every one upward — REPORT.md@9fa13da57 § 10 lists
them) plus yours; write them in the pull request. This closes the obligation L19's gesture left open
(`IMPLEMENTATION.md`, « Last landed », last sentence) — rewrite that sentence to say it is done, with
the commit.

## What you do not do

- **You do not add a line to `legacy.js`** — the ledger refuses it, and D5 forbids it.
- **You do not draw anything but the seventh row** (its shape is the six others').
- **You do not touch the delegation, the producers, L21's verbs, or any other register entry.**
- **You do not quarantine `machine.py`** — the operator chose the repair.
- **You do not stop between steps**; the only stop is a divergence on a state that is not Système's.

## The gates

Per commit: the contract rules and cheap guards (`run.sh --contracts`, 27 guards). Before the pull
request: the full suite (`frontend/maquette/harness/run.sh`, expected **no failure**), `--a11y` 0, the
oracle re-recorded once, `make check` at 0 failed / 0 errors, the hold-count baseline with
`failed: 0`. The machine is an instrument: every heavy run wrapped in `TM_HARNESS_JOBS=2 sh
scripts/heavy.sh <you> <command>`, kill what you start, delete what you build, prove with `ps`.

## How you deliver

Branch `fix/maquette-schedulers`, one pull request, English title and body, the version bumped
(patch). Write the « In flight » row when the pull request opens (number first, then version).
B-308 reads `fixed #<n>` by rule 3 (the script, the mutation, the run). Then message the steward —
its exact address is in your invocation — and the steward launches ONE independent reader
(head against a control of `main`, walking Système at 390 px with seven rows and running
`machine.py` alone); you alone write. The operator gives the merge word. Your folder leaves the tree
at the post-merge gesture, cited by the squash.
