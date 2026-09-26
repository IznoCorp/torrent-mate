# Phase 5 — One ladder, two readers

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** Three lengths answer « where is this medium »: `PipelineStrip` (`components.schemas.PipelineStrip`, 5),
  `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/journey-stages.json'))))"`
  → **5**, `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/pipeline.json'))['steps']))"`
  → **9**. The seeds that carry a `strip`: `blocked.json`, `moving.json`, `in-flight.json`, `stuck.json`,
  `stuck-loaded.json` (`grep -l '"strip"' frontend/maquette/design/src/mocks/seeds/*.json`) — **14 rows** (1 + 5 + 3 + 2 + 3).
  `features/acquisition/panel-journey.ts` 112 lines (`STAGE_PIP`, one literal `RELEASE`). `fr.json`
  `surfaces.card.stages` = 5 labels. `git grep -c strip -- frontend/maquette/design/src/features/acquisition/card-markup.ts`
  → 3. Harness reader of the journey sheet's dots: `acted_surface_redraws.py` (R157). Named states that draw a strip:
  the seeds above reach `acq-now-idle`, `acq-now-loaded`, `sheet-journey`, and the `arr-*` cards (measured by running
  the oracle at the phase, not by this list).
- **Points ≈ 14.** The ladder seed (ten rungs, derived from `journey-stages.json` and the nine steps of `pipeline.json`)
  4; `panel-journey.ts` reading ten rows ≈ 15 lines 3; the acquisition card markup reading the ladder 1; the rungs'
  names as `fr.json` keys 1; the new rule with its mutation 3; two states 2.

Ruling 4: ONE ladder, from the wish to Plex. The card's strip and the journey sheet's rows are two READERS of one
seed (§13 — one derivation per question); the strip retires from the acquisition queue's cards (it stays on
`readStaging`'s cards until the page dies — Arrivées keeps working through phase 22).

## Red today

**R-L22-f — one ladder** (DESIGN § 5):

- the card's ladder draws the journey's rungs in the journey's ORDER, and its current rung equals the journey sheet's;
- at 390 px, on `acq-card-rungs`: ten cells, no horizontal overflow, and the **current rung's NAME is drawn whole** (not
  truncated — § 12) on line 2;
- `acq-card-blocked` shows the reason in full under a `blocked` rung.

**Red against `main`**: the card carries five positions read from `QueueCard.strip`, the journey five stages from a second
seed, and no state holds ten rungs.

## Move

1. The seed and the handler answer ten rungs with a state each (`done` · `now` · `waiting` · `blocked` · `aside` ·
   `pending`), from ONE source; `readJourney` answers it; the acquisition card markup reads the same source.
2. `panel-journey.ts` draws ten rows. Its `RELEASE` literal is a demand (the journey names the release it followed), left
   as it is and noted.
3. The strip draws ten unlabelled cells; line 2 names the current rung (DESIGN § 3.2). The rungs' names live in `fr.json`
   (they adjust to the drawing — OPEN 4).
4. Named states `acq-card-rungs` (ten cards, one on each rung) and `acq-card-blocked`, in `harness/states/tunnel.ts`.

## Mutation

With the commit made first: make the card read the old five-position strip → R-L22-f falls (the agreement hold); swap two
rungs in the seed → it falls again (the order hold).

## Register

—

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded`, `sheet-journey`, and the `arr-*` cards' states whose card is drawn by the acquisition
markup — each accepted with « L22 § 3.2: ten cells and one named rung replace five labelled steps ». **The Arrivées page
keeps its own five-cell strip** and must not move: any `arr-*` divergence beyond a shared list card is STOP A. New states
are recorded, not compared.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`; `python3 scripts/compare-contracts.py --check`.

## Commit

`feat(maquette-l22): one ladder from the wish to Plex, read by the card and the journey sheet`
