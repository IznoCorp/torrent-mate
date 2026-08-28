# Phase 9 — Média — the sheet, the matrix, the popover

**The largest family in the file lives here**: `SHEETS_RAW` is **20 538 lines** of episode
catalogue — 58 % of `legacy.js` on its own. With `OWNED` (1 383), `SEASONS`, `SYNOPSIS` (672),
`CAST` and `HERO_IMAGES`, this phase is the single biggest subtraction of the lot.

**`epState` leaves the engine here**, and it is the reason phase 2 exists: 8 branches, 3
assertions in one browser rule today. It becomes a pure function in this feature with a test per
branch, asserted against the seeds.

**§13's « une seule dérivation par question » is this phase's constitutional stake.** « Where is
this episode? » is answered on the sheet, on the season matrix and in the popover. One
derivation, read by all three, or they will diverge and the operator will see two truths.

**B-030 is open and is NOT this phase's to close**: 87 of 345 sheets carry no genre and no cast.
It is a defect of the maquette's DATA, the operator has excluded it from batch closure, and the
seeds carry it faithfully — which is correct.

## What every surface phase carries

Four things, and none is optional:

1. **Its reads go through the cache**, never through `window.__referentiel`.
2. **Its mutations carry an optimistic path and a rollback**, or a written reason why one cannot
   exist. An action answers the finger before the network does — this is the largest single lever
   on how native the interface feels, and no animation later repairs a tap that waits for a round
   trip (DOIT-4).
3. **Its share of the fixture dies in the same commit** (D5). The engine is touched only by
   subtraction; its part is removed, never rewritten.
4. **A rule that bites**, mutation-tested: break the behaviour on purpose, see the rule fall and
   name the right defect, restore.

## The gate

`frontend/maquette/harness/run.sh --contracts`, then `--oracle`. Run **after** the phase, not
after a commit inside it.

## Done when

- `grep -rn "__referentiel" <this surface's files>` → 0.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`, or every divergence named,
  understood and accepted with its reason (D-L09-7). Never « the data changed ».
- The invariant-4 arm's count has fallen by this surface's share, and the arm says so.
