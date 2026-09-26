# Phase 24 — The live rule Système was borrowing

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `sed -n 105,112p frontend/maquette/design/src/features/system/queries.ts` → `usePipelineState` reads
  `["/api/pipeline/status"]`. `grep -n 'PIPELINE_KEY\|pipeline/status' frontend/maquette/design/src/features/arrivals/live.ts frontend/maquette/design/src/features/system/live.ts`
  → the key and the rule that refreshes it (`PipelineStarted`, `PipelineEnded`, `PipelinePaused`, `PipelineResumed`,
  `StepStarted`, `StepCompleted`, `StepErrored`) live ONLY in `arrivals/live.ts`; `system/live.ts`'s rules refresh the
  schedulers, the history and the locks. `app/live-updates.ts:29,79` registers the arrivals table.
  `python3 scripts/check-live-relay.py` reads the tables (its poll arm holds NE-DOIT-PAS-8).
- **Points ≈ 5.** The rule moved into `features/system/live.ts` ≈ 12 lines written 1; the same rule removed from the
  arrivals table 1; R-L22-r with its mutation 3.

DESIGN § 1.1's finding. The levers' state would freeze at its last read the day the page's table died, and no rule about
Arrivées would ever say so. **The move is made BEFORE the deletion**, with the arrivals table still registered, so the hold
is written red first and green after, never « green because the page still carries it ».

## Red today

**R-L22-r — the levers stay live**: Système's levers draw the pipeline's state, and it MOVES when `PipelineStarted`,
`PipelinePaused` and `PipelineEnded` arrive through the mock relay — read while Arrivées' table still exists AND after the
rule left it.

**Red against `main`** in the sense that matters: the rule is written first with the status rule REMOVED from
`arrivals/live.ts` and NOT yet added to `system/live.ts` — the lever stops moving and the hold falls; then the rule is added
and the hold passes. (Against unmodified `main` it passes, because Arrivées carries the rule for Système: the phase says so
in its report rather than pretending a red that does not exist.)

## Move

Add the rule (with its `because:` sentence) to `features/system/live.ts`; remove it from `features/arrivals/live.ts`.

## Mutation

With the commit made first: leave the rule out of `features/system/live.ts` → R-L22-r falls.

## Register

—

## Oracle: states that diverge, declared by name

**None.** Any divergence is STOP A.

## Gate

Per INDEX « Gates »; `python3 scripts/check-live-relay.py`.

## Commit

`fix(maquette-l22): Système owns the live rule that keeps its levers current`
