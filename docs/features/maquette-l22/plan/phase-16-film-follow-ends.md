# Phase 16 — A film's follow ends alone

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `python3 -c "import json;from collections import Counter;print(Counter(r['kind'] for r in json.load(open('frontend/maquette/design/src/mocks/seeds/follows.json'))))"`
  → `Counter({'show': 9, 'movie': 5})` — **five real followed films** to prove the rule on. `readFollows` at
  `mocks/handlers/acquisition.ts` (`/api/acquisition/followed`, the list « Suivis » draws); the live rule that keeps it fresh:
  `features/acquisition/live.ts` (`FOLLOWED_KEY`). `features/acquisition/follows-tab.tsx` is 282 lines (ceiling 400).
  `git grep -l 'acq-follows' -- 'frontend/maquette/harness/*.py' | wc -l` → **37 files** name the follows states.
  **The ladder's last rung has no source in the maquette today** (`git grep -ci plex` over the contract and the mocks → no
  match) until phase 1's demand B and phase 5's ladder; this phase is the first to READ it.
- **Points ≈ 10.** The mock ends a followed film's follow when its ladder reaches « vérifié dans Plex » (a move in the
  follows handler ≈ 15 lines edited 3); the live rule re-reads the follows on that event 1; the five film rows checked
  against the seed 1; R-L22-m with its mutations 3; one state (`acq-follows-film-confirming`) 1; the follows readers
  re-run, none expected to fall 1.

Ruling 3: a film's follow ends by itself when the film is CONFIRMED in the library (Plex match validated, §4) and leaves
« Suivis » without a trace there; a series' follow never ends by itself. **Drawn here, in its own phase; the media
sheet's half (« acquis le … », release, requester) is NOT drawn** — DESIGN § 3.5 gives the reason and phase 25 names the
debt.

## Red today

**R-L22-m — a film's follow ends alone**, on the five followed films: present in « Suivis » until the ladder reaches
« vérifié dans Plex », absent after (no trace in « Suivis »); a followed series is there after; NOT ended at the rung before.

**Red against `main`**: a followed film stays in « Suivis » forever.

## Move

The follows handler ends a film's follow at the last rung; `acq-follows-film-confirming` holds a followed film one event
away from it.

## Mutation

With the commit made first: end the follow one rung early → R-L22-m falls; end a series' follow too → it falls.

## Register

—

## Oracle: states that diverge, declared by name

Only the state this phase adds. Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; the follows rules re-run by name.

## Commit

`feat(maquette-l22): a followed film leaves « Suivis » when Plex confirms it`
