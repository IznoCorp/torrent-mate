# Phase 9 — « À traiter » holds its cards

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `sed -n 84,98p frontend/maquette/design/src/features/acquisition/now-tab.tsx` → the `blocked` section
  (« À traiter » inside « En cours », foot « Résoudre → », `data-resolution`), 13 lines. `git grep -l -E '"blocked"|data-resolution' -- 'frontend/maquette/harness/*.py' | wc -l`
  → **6 rule files** read the blocked family or its foot. The reason vocabulary
  (`features/acquisition/decision-vocabulary.ts` after phase 2): 4 tokens (`below_threshold`, `mid_band`, `ambiguous`,
  `manual`) with their tones; `screens.resolution.reason.*` holds their words. `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/mocks/seeds/pipeline-runs.json'));print(sum(s.get('errorCount',0) for r in d for s in r['steps']))"`
  → **0** errored steps in the ten real runs; `git grep -ci plex` over the seeds → no match.
- **Points ≈ 14.** `now-tab.tsx`: the `blocked` section leaves ≈ 13 lines deleted 3; `todo-tab.tsx`'s three sections ≈
  50 lines written 5; the queue read of the blocked family and the arrival stuck rows 1; the sections' words as `fr.json`
  keys 1; the new rule with its mutations 3; one state (`acq-todo-loaded`) 1.
- **Found (2026-09-26) — STOP D at this opening.** DESIGN § 3.3 draws three sections; **two of them have no real row**:
  no errored step, no Plex mismatch exists in any seed. The phase re-takes these figures, reports them to the steward
  with the commands above, and does NOT improvise a seed (§13, « no invented data »). The steward's word decides between
  (a) re-casting a real stuck row under another reason, shown as a derivation, and (b) drawing the two sections from
  their states with the seeds marked `x-unseeded`. **The « to resolve » section has real rows and is drawn either way.**

Ruling 7: « À traiter » holds what only his hand unblocks, and it is drawn as the language « En cours » already speaks
(a pip per section, a counter that IS its own link, a section with no card not drawn at all). The `blocked` section
LEAVES « En cours » for it.

## Red today

**R-L22-h — « À traiter » holds only what his hand unblocks**, on `acq-todo-loaded`: every card in the tab is `blocked` in
one of the three kinds; a card `aside` and a card `waiting` are NOT in it and ARE in « En cours » with their reasons.

**Red against `main`**: no such tab body; the blocked cards live in « En cours ».

## Move

1. `todo-tab.tsx` draws the three sections; each card's foot is « Résoudre → » (to resolve; the Plex-mismatch section
   adds nothing beyond it — OPEN 9), or « Relancer » (`requeueJourney`) and « Abandonner » (OPEN 10) on a tunnel error.
2. `now-tab.tsx` loses its `blocked` section. **Its cross-reference (`data-go="arr"`) stays until phase 19**: it still
   counts what is stuck, which is true.
3. The named state `acq-todo-loaded`; `acq-now-idle` and `acq-now-loaded` lose the `blocked` section.

## Mutation

With the commit made first: put an `aside` card in the tab → R-L22-h falls; put a `blocked` card in « En cours » → it falls.

## Register

B-515's subject (the Arrivées error retry) is read here for the new tab in phase 11, not in this phase.

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded` on `acquisition/body` (the section leaves), each accepted with « L22 § 3.3: the `blocked`
section leaves for its own tab ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l22): « À traiter » holds what only his hand unblocks`
