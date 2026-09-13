# Phase b·10-ter — The pipeline's status is the layer's

A BEHAVIOUR phase, added on 2026-09-13 by ruling 74, placed after b·10-bis and BEFORE b·11 because `legacy.js` cannot
die while its `data-pipe` branch still writes the `pipe` store key — and that write cannot move to a feature as it
stands: `scripts/check-state-ownership.py` refuses a component writing server state (its component ceiling is 0, and it
STAYS 0).

## What converts

- The `pipe` store key (`idle` / `running` / `queued`) becomes the layer's answer: `usePipeline()` over
  `/api/pipeline/status`, which the mock layer already serves.
- The `data-pipe` verb, registered in `features/arrivals/`, asks the layer: `runPipeline` (`POST /api/pipeline/run`) for
  `start`, `killPipeline` (`POST /api/pipeline/kill`) for `stop`; its three sentences are fr.json's.
- Readers re-aimed: `features/arrivals/page.tsx:102` and `:122` (the running / queued banners), `app/arrival.ts:29`
  (the initial value leaves the store).
- The three named states that drive it (`arr-idle`, `arr-running`, `arr-queued`) drive the layer's answer instead of
  `applyState({ pipe })`, their readings unchanged.

## The proof FIRST

- The rules that hold `data-pipe` (`arrivals.py`, `page_host.py`) run green before and after, counts unchanged; the
  queued answer (DOIT-4) is held by the layer's own reply.
- Red: the verb's layer call removed on purpose, the holding rule falls naming the pipeline state that did not move.
- The oracle: any divergence on the three arrivals states is NAMED before the gate, or it is STOP B.

## Deleted

- `legacy.js`'s `data-pipe` branch and its toasts; the `pipe` key from `app/arrival.ts` and the store's type;
  `scripts/frontend_size_ledger.py` re-recorded DOWNWARD.

## Commit

`feat(maquette-l13b): the pipeline's status and its run are the layer's`
