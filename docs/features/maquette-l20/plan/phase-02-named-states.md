# Phase 2 — The named states leave the engine's ledger

**A mechanical prerequisite, and it is a phase because it has its own gate.** This lot declares 26
named states (DESIGN § 5), and the file that holds them may not grow.

## What was measured, and it blocks everything after it

    grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/states.js
    sed -n '94,98p' scripts/frontend_size_ledger.py

`engine/states.js` reads **786** non-blank lines and the ledger records it at **786**, grandfathered
to « L13 — the scenario table goes with the engine it drives ». `scripts/check-frontend-boundaries.py`
**refuses the count going UP** — that is B-306, discharged by L19 in #558 precisely because a
grandfathered file had grown 77 lines under a decision titled « dies by subtraction » while the arm
printed clean. Its message is explicit: « a grandfathered file is one that may not be EXTENDED ».

Twenty-six states at the shape that file uses — Système's four take twenty lines for four
(`sed -n '580,599p' frontend/maquette/design/src/engine/states.js`) — is on the order of a hundred
and thirty lines. **Even two would be refused.** So the states do not go there.

## The move

- **New file** `design/src/states/system.ts` — the named states of the Système surface, in the same
  `[id, label, run]` shape, typed. It is a top-level directory beside `mocks/`, `contract/`,
  `i18n/` and `engine/`, which is the shape this tree already has for a kind of artefact that
  belongs to no feature: **the state table is the HARNESS's own fixture**, and `engine/states.js`
  says so in its own comment.
- **Système's four existing states MOVE into it** — `system`, `system-outage`, `system-loading`,
  `system-error` — and this lot's 26 are declared beside them. That is D5 « surface by surface »
  applied to the table, and it ADVANCES L13 rather than working around it.
- `engine/states.js` imports the module and spreads it into its own table: **+2 lines against −20**,
  so the file SHRINKS and `scripts/frontend_size_ledger.py`'s `GRANDFATHERED` record for
  `engine/states.js` is **re-recorded DOWNWARD in this commit** — which is the direction the arm
  asks for and the only one it accepts.
- Nothing is added to `legacy.js`. `window.__recordStates` is called once, as today, with the one
  composed table.

**The alternative was examined and refused, and it is written down so it is not re-proposed.**
`window.__recordStates(table)` does `STATES = table` (`legacy.js:8683`), so a second caller WIPES the
first; making it accumulate is a one-line change inside the engine that alters the seam's semantics
for every existing caller. It adds no line and would pass the ledger, but it is a BEHAVIOUR change to
the harness's driving seam, made in a lot whose subject is elsewhere, to save a two-line import. The
composition route costs two lines and changes nothing anyone else depends on.

## The rule

**No new rule, and the reason is that the existing one is the right instrument.**
`frontend/maquette/harness/states.py` drives every id `window.__states()` answers and asserts each
renders content, has no horizontal overflow at 390 px and raises no JS error. Its hold COUNT is
therefore the proof this phase is looking for:

- before: it drives **87** ids;
- after this phase: still **87** — the four moved out are still answered, and this lot's 26 are
  declared but not yet drawable, so they are added to the module in the phase that draws them.

**That is the discipline, and it is deliberate**: a state id declared before its surface exists
would make `states.py` fail on « renders nothing », which is the pass it is supposed to enforce. So
phase 2 moves the HOME; each later phase adds its own ids to `states/system.ts` with the surface
that answers them, and phase 9 reads the final count.

⚠ **The count is read, not assumed.** `python3 scripts/harness-hold-counts.py --compare` with
`failed` read FIRST (B-291), and a count that moved in this phase is a finding: nothing here draws
anything.

## Gate

`run.sh --contracts` under the shared lock, announced; `states.py` driving 87 ids as before;
`python3 scripts/check-frontend-boundaries.py` reading `engine/states.js` **below** its record and
the record re-recorded to match. The oracle: **zero divergence everywhere** — no surface changed and
no state's behaviour did.

## Commit

`refactor(maquette-l20): the Système surface's named states leave the engine's table`
