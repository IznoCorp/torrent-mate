# Phase 8 — B-371: the path a hand takes

The lot's last repair, and the only one that subtracts from the engine. **B-371 is not a drawing —
it is a PATH that does not exist.** DOIT-4's « En file » pastille is drawn, R138 passes on it, and
no person can make it appear.

Two pipeline notions and nothing joins them:

    grep -rn "runPipeline\|/api/pipeline/run" frontend/maquette/design/src --include=*.ts --include=*.tsx
    grep -n "closest.dataset.pipe" frontend/maquette/design/src/engine/legacy.js

The layer's `pipelineState` is written only by the mock handlers for `POST /api/pipeline/{run,pause,
resume,kill}`, and **no surface calls any of them**. The engine's interface store `pipe` is written
by Arrivées' « Lancer le pipeline » at `legacy.js:9207`, which **touches no network at all**. The
hand moves the second; the pastille reads the first.

## The rule FIRST, red against the engine's own branch

`frontend/maquette/harness/queued_by_hand.py` — new, label **R-L20-h**. One walk, and **no `__go`
appears anywhere in it** — that absence IS the rule's subject:

1. Arrivées, at rest. « Lancer le pipeline » found and pressed **by a finger**, hit-tested.
2. **The run OPERATION is answered** — read on the network. *The store write the engine does today
   answers nothing, which is exactly what this hold names.*
3. A season with a hole is asked for, on a surface a finger can reach.
4. **The « En file » pastille is PRESENT** — `data-part="season/queued"`, the mark R138 already
   reads, reached this time by a walk a person could repeat.

**Seen red how**: against `main` hold 2 fails with an empty network record and hold 4 fails because
`pipelineState` never left `IDLE`. No mutation is needed — **the defect is on `main` and the rule
names it**, which is the strongest form this repository asks for.

**Mutation after the move**: revert `data-pipe`'s handler to the store write; hold 2 falls and hold
4 follows it. Restore.

## The move

- `mocks/handlers/pipeline.ts`'s `runPipeline` takes the backend's shape at last (phase 1 deferred
  it here): **409 for a second PIPELINE run** — §6's strict duplicate — and queued only when a
  MAINTENANCE run holds the lock.
- **New file** `features/arrivals/pipeline-verbs.ts` — `registerVerb("pipe", …)` on `lib/verbs.ts`,
  calling `runPipeline` / `killPipeline` and letting the store's `pipe` DERIVE from the layer's
  answer. **Invariant 4 applied to the one field that broke it**: server state is never copied into
  client state.
- **The engine's branch is SUBTRACTED** in this commit (`legacy.js:9207`'s `if
  (closest.dataset.pipe)`), and `scripts/frontend_size_ledger.py` is re-recorded **downward** in the
  same commit. D5: every engine edit is a subtraction or a call through a seam; a line added that is
  neither is the defect.
- `features/arrivals/page.tsx` is **not extended** — it is one of L14's grandfathered four. The verb
  is a new file beside it.

**`arr-queued`'s precondition MOVES, and that is named rather than discovered** (DESIGN § 3.2 point
3): from « ask twice » to « ask while a maintenance run holds the lock ». R138 arranges busy-ness
through the same field and is re-read here, not re-written. **A fixture or precondition change is an
input to every rule that reads the surface it feeds** — B-369 is the entry that cost a wave exactly
this — so this phase runs the FULL suite, not the contracts tier, before it commits.

## Gate

The **full** suite under the shared lock, announced to the steward before and after:

    HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh l20 \
      frontend/maquette/harness/run.sh > /tmp/l20-phase7-suite.log 2>&1; echo "exit $?"

Read the file, not a tail. R-L20-h green, its mutation named; R138 still green and **its hold count
unchanged** — a repair that moved a count moved a rule's subject. The oracle: `arr-queued`'s drawing
does not change, so **ZERO divergence is the expectation there; a divergence is a finding, not an
acceptance**, because a precondition change that alters a pixel means the drawing depended on the
wrong fact.

## Commit

`fix(maquette-l20): starting the pipeline by hand reaches the pipeline, and the queued mark with it`
