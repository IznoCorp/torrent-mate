# Phase 9 — « À traiter » holds its cards

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `sed -n 84,98p frontend/maquette/design/src/features/acquisition/now-tab.tsx` → the `blocked` section
  (« À traiter » inside « En cours », foot « Résoudre → », `data-resolution`). `git grep -l -E '"blocked"|data-resolution' -- 'frontend/maquette/harness/*.py' | wc -l`
  → **6 rule files** read the blocked family or its foot. The reason vocabulary
  (`features/acquisition/decision-vocabulary.ts` after phase 2): 4 tokens (`below_threshold`, `mid_band`, `ambiguous`,
  `manual`) with their tones; `screens.resolution.reason.*` holds their words. `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/mocks/seeds/pipeline-runs.json'));print(sum(s.get('errorCount',0) for r in d for s in r['steps']))"`
  → **0** errored steps in the ten real runs. `git grep -n 'requeueJourney' -- frontend/maquette/design/src/mocks/handlers`
  → `acquisition-verbs.ts:242` (the « Relancer » operation is declared and mocked).
- **Points ≈ 13.** `now-tab.tsx`: the `blocked` section leaves ≈ 15 lines deleted 3; `todo-tab.tsx`'s two sections ≈ 35 lines
  written 4; the queue read of the blocked family and the arrival stuck rows 1; the sections' words as `fr.json` keys 1; the new
  rule with its mutations 3; one state (`acq-todo-loaded`) 1.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run — 6 rule files, 0 errored
  steps, `requeueJourney` mocked; the `blocked` section reads **15 non-blank lines at 84–98** (the first drawing wrote 13), which
  is 3 points at 1 per 5 either way. **Points 14 → 13, and this phase was CUT**: the first drawing carried three sections and
  both acts of the tunnel-error card, at 14; OPEN 9 (ruled B) adds a verb on the Plex match, with its contract operation and its
  mock, and OPEN 10 (ruled B) adds a quarantine with its confirmation and its state. Together they take the phase far past
  measure 19's 15, so they leave it: **phase 10 draws the Plex-match section and its two verbs, phase 11 draws « Abandonner »**
  (INDEX, « Why twenty-seven phases »). A card is never drawn with a foot that does nothing, so this phase draws only the two
  sections whose acts EXIST today.
- **Found (2026-09-26) — STOP D at this opening.** DESIGN § 3.3 draws « À traiter » in three sections; **the tunnel-error one has
  no real row**: no errored step exists in any seed (0, above). The phase re-takes this figure, reports it to the steward with
  the command, and does NOT improvise a seed (§13, « no invented data »). The steward's word decides between (a) re-casting a
  real stuck row under another reason, shown as a derivation, and (b) drawing the section from its state with the seed marked
  `x-unseeded`. **The « to resolve » section has real rows and is drawn either way.**

Ruling 7: « À traiter » holds what only his hand unblocks, and it is drawn as the language « En cours » already speaks
(a pip per section, a counter that IS its own link, a section with no card not drawn at all). The `blocked` section
LEAVES « En cours » for it.

## Red today

**R-L22-h — « À traiter » holds only what his hand unblocks**, on `acq-todo-loaded`: every card in the tab is `blocked` in
one of the kinds drawn so far (two here, to resolve and tunnel error; phase 10 adds the Plex match and re-reads the rule); a
card `aside` and a card `waiting` are NOT in it and ARE in « En cours » with their reasons.

**Red against `main`**: no such tab body; the blocked cards live in « En cours ».

## Move

1. `todo-tab.tsx` draws the two sections; each card's foot is « Résoudre → » (to resolve) or « Relancer » (`requeueJourney`,
   on a tunnel error). **« Abandonner » is not drawn here** (phase 11) and neither is the Plex-match section (phase 10): a
   card is never drawn with a foot that does nothing.
2. `now-tab.tsx` loses its `blocked` section. **Its cross-reference (`data-go="arr"`) stays until phase 29**: it still
   counts what is stuck, which is true.
3. The named state `acq-todo-loaded`; `acq-now-idle` and `acq-now-loaded` lose the `blocked` section.

## Mutation

With the commit made first: put an `aside` card in the tab → R-L22-h falls; put a `blocked` card in « En cours » → it falls.

## Register

B-515's subject (the Arrivées error retry) is read here for the new tab in phase 13, not in this phase.

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded` on `acquisition/body` (the section leaves), each accepted with « L22 § 3.3: the `blocked`
section leaves for its own tab ». Any other divergence is STOP A. `acq-todo-loaded` is NEW and recorded, not compared; phases 10
and 11 change it and name it.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l22): « À traiter » holds what only his hand unblocks`
