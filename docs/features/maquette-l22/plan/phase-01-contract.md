# Phase 1 — The contract (D7)

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **63** operations. `sed -n 20,29p docs/reference/frontend-backend-demands.md` → required and missing **16**,
  different shape **47**, different status **11**, path spelled differently **15**, pre-formatted fields **25**,
  backend-only **18**. `python3 scripts/compare-contracts.py --check` → exit 0 (« matches the computed diff »);
  `python3 scripts/check-mock-seeds.py` → exit 0 (« clean », 15 payload modules, 395 literals, 0 uncovered).
  `git grep -ci requester -- frontend/maquette/contract/openapi.json frontend/maquette/design/src` → no match;
  `git grep -ci reclassif -- …` → no match (neither the field nor the operation exists).
  `PipelineStrip`: `minItems` = `maxItems` = 5; `journey-stages.json` 5 rows; `pipeline.json` 9 steps.
  The sort's non-media destinations are configuration: `grep -n 'file_type' config.example/patterns.json5` → eight
  staging directories: two media (`movies`, `tvshows`), **five non-media** (`ebooks`, `audio`, `apps`, `android`,
  `autres`) and `temp`, the ingest entry, which has no type. Handlers: `readAcquisitionQueue` at `mocks/handlers/acquisition.ts:276` (359 non-blank lines in the file),
  `readJourney` at :344; the staging routes in `mocks/handlers/staging.ts` (121); `decisions.ts` (112).
- **Points ≈ 12.** Four operations edited or declared (the queue read 1, the journey read 1 — optional fields only —,
  `reclassifyStagedMedia` new 2, the read of the non-media destinations new 2 → 6); two mock handlers moved and one added
  (the queue composes the arrival family from the staging seeds and the account 2, the reclassify route 2, the
  destinations read 1) = 5; the `fixture-register.json` / `x-seeded-from` row for the new family 1; regenerating the
  register and the types is mechanical. **Mean stated once, in `plan/INDEX.md`.**
- **Found (2026-09-26).** The seed builder L20's plan cites (`build-mock-seeds.py`) no longer exists: the seeds are edited
  by hand and `check-mock-seeds.py` (its `schema` and `provenance` arms) is the guard. And **nothing in the contract or
  the mocks names Plex** (`git grep -ci plex -- frontend/maquette/contract/openapi.json frontend/maquette/design/src/mocks/handlers`
  → no match): the ladder's last rung has no source until demand B lands.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** Every command above re-run: 63 operations, required
  and missing 16, `compare-contracts.py --check` exit 0, `check-mock-seeds.py` clean (15 payload modules, 395 literals, 0
  uncovered), `requester` and `reclassif` no match, `PipelineStrip` 5, 5 seed stages, 9 pipeline steps — identical, the tree did
  not move. **Points 12 → 12: no ruling moved this phase, and one was kept OUT of it.** OPEN 9's operation (demand E,
  `resolvePlexMatch`) would add a declared operation (2) and a mock route (2) — 16, over measure 19's ceiling — so phase 10 files
  it as its first act, where its card is drawn. OPEN 11 (the requester line only) adds no reassign operation here.

Every surface of this lot calls an operation the maquette's contract does not declare as the lot needs it. This phase
settles all of it, and it is FIRST because `scripts/compare-contracts.py --check` refuses the three artefacts apart and
because the demands are what make the design's proposals decisions rather than discoveries (DESIGN § 6.2).

## First, bind the rule numbers

    git remote update origin >/dev/null && grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1

Re-take it against this branch's base at the moment this phase runs, then bind `R-L22-a` … `R-L22-u` (DESIGN § 5) to
consecutive free numbers and write the mapping into the report. **A number taken from the design without re-measuring is
a collision.**

## Red today

**No rule in this phase, and that is stated rather than skipped.** A contract is not a behaviour: what holds it is
`scripts/compare-contracts.py --check`, the generated `contract/types.d.ts` and `scripts/check-mock-seeds.py`. The rules
that read these operations are written in phases 2 to 25, each beside the surface that calls it.

## Move

1. `frontend/maquette/contract/openapi.json`:
   - **`readAcquisitionQueue`** — a card carries WHO asked and WHERE it came from (a requested medium, an arrival); the
     answer gains a family for the arrivals nobody requested. **No surface reads the new family in this phase** —
     phase 6 does — so nothing moves. Demand A.
   - **`readJourney`** — each stage may carry a rung token and, where it is blocked, a reason token; the list stays
     five long until phase 5. Demand B (its full one-ladder shape is written when the ladder lands).
   - **`reclassifyStagedMedia`** — declared, with its answer and its inverse, and **a read of the non-media
     destinations the sort files into** (seeded from the five above, `x-seeded-from` the config's staging directories).
     Demand C.
   The operationIds are proposals (DESIGN § 6.2) and adjust; **demand D (`readAccount`'s rights) is L18's and is NOT filed
   here** — a rights read of any size is the model the non-goals forbid.
2. `frontend/maquette/design/src/mocks/handlers/` — what each MOVES (D7): the queue handler composes the arrival family
   from the staging seeds and `account.json` (requester = the account; a direct add when the title matches no follow,
   read from `follows.json`) — **no data literal in the handler** (the `handlers` arm refuses one); the reclassify route
   in `staging.ts` removes the folder from staging and from the arrival family, and its inverse puts it back.
3. `fixture-register.json` and the operation's `x-seeded-from` / `x-unseeded`: one row for the new family, so the
   `provenance` arm stays clean.
4. Regenerate and read what came out:

       python3 scripts/compare-contracts.py --write
       python3 scripts/compare-contracts.py --check
       npm --prefix frontend/maquette/design run generate-contract-types

   **Read the counters and put them in the report, before and after** (« required and missing » must move from 16).

## Mutation

None (no rule). The proof that the mock MOVES is phase 6's, which is the first surface to read it.

## Register

— (the demands A–C are the output; the lot files them here by editing the contract).

## Oracle: states that diverge, declared by name

**None.** No surface reads the new family, and the journey's seed is unchanged. Any divergence is STOP A.

## Gate

`sh scripts/heavy.sh --class browser l22 frontend/maquette/harness/run.sh --contracts` (announced to the steward before
and after); `python3 scripts/check-mock-seeds.py`; `python3 scripts/compare-contracts.py --check`.

## Commit

`feat(maquette-l22): the contract of arrivals as cards, the ladder and the reclassification`
