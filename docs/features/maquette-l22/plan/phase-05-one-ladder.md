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
- **Points ≈ 15.** The ladder seed (eight rungs and the three steps « trié · enrichi · rangé » that « rangé » carries as
  detail, derived from `journey-stages.json` and the nine steps of `pipeline.json`) 4; `panel-journey.ts` reading eight rows
  and the three details ≈ 20 lines 4; the acquisition card markup reading the ladder 1; the rungs' names as `fr.json` keys 1;
  the new rule with its mutations 3; two states 2.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: `PipelineStrip` 5,
  `journey-stages.json` 5, `pipeline.json` 9 steps, 14 seed rows carrying a `strip`, `panel-journey.ts` 112 lines (105 non-blank),
  `surfaces.card.stages` 5 labels, `card-markup.ts` 3 `strip` lines — identical. **Points 14 → 15, moved by OPEN 4 (reading
  B: eight rungs, the journey sheet keeps the three merged steps in detail)**: the sheet gains detail rows under one rung
  (+1). **What to cut if the opening measure exceeds 15**: the sheet's detail under « rangé » becomes its own phase; the
  card's eight cells and the sheet's eight rows stay here.

Ruling 4, and OPEN 4 (ruled B): ONE ladder of EIGHT rungs, from the wish to Plex — « trié · enrichi · rangé » are one rung,
« rangé », and the card reads « n sur 8 ». The card's strip and the journey sheet's rows are two READERS of one
seed (§13 — one derivation per question); the strip retires from the acquisition queue's cards (it stays on
`readStaging`'s cards until the page dies — Arrivées keeps working through phase 34).

## Red today

**R-L22-f — one ladder** (DESIGN § 5):

- the card's ladder draws the journey's rungs in the journey's ORDER, and its current rung equals the journey sheet's; the
  sheet opens « rangé » into its three steps from the SAME source (no list of its own);
- at 390 px, on `acq-card-rungs`: eight cells, no horizontal overflow, and the **current rung's NAME is drawn whole** (not
  truncated — § 12) on line 2;
- `acq-card-blocked` shows the reason in full under a `blocked` rung.

**Red against `main`**: the card carries five positions read from `QueueCard.strip`, the journey five stages from a second
seed, and no state holds eight rungs.

## Move

1. The seed and the handler answer eight rungs — « rangé » carrying its three steps as detail — with a state each (`done` · `now` · `waiting` · `blocked` · `aside` ·
   `pending`), from ONE source; `readJourney` answers it; the acquisition card markup reads the same source.
2. `panel-journey.ts` draws eight rows, and under « rangé » its three steps. Its `RELEASE` literal is a demand (the journey names the release it followed), left
   as it is and noted.
3. The strip draws eight unlabelled cells; line 2 names the current rung (DESIGN § 3.2). The rungs' names live in `fr.json`
   (the names adjust to the drawing; the number is ruled — OPEN 4, B).
4. Named states `acq-card-rungs` (eight cards, one on each rung) and `acq-card-blocked`, in `harness/states/tunnel.ts`.

## Mutation

With the commit made first: make the card read the old five-position strip → R-L22-f falls (the agreement hold); swap two
rungs in the seed → it falls again (the order hold); give the sheet a list of its own for the three steps → it falls a third
time (the one-source hold).

## Register

—

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded`, `sheet-journey`, and the `arr-*` cards' states whose card is drawn by the acquisition
markup — each accepted with « L22 § 3.2: eight cells and one named rung replace five labelled steps ». **The Arrivées page
keeps its own five-cell strip** and must not move: any `arr-*` divergence beyond a shared list card is STOP A. New states
are recorded, not compared.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`; `python3 scripts/compare-contracts.py --check`.

## Commit

`feat(maquette-l22): one ladder from the wish to Plex, read by the card and the journey sheet`
