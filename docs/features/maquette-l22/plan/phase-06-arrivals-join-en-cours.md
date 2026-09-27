# Phase 6 — Arrivals join « En cours »

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n mediumCardMarkup -- frontend/maquette/design/src | cut -d: -f1 | sort | uniq -c` → 13 call sites
  in 5 files (`now-tab.tsx` 6, `follows-tab.tsx` 2, `add-screen.tsx` 2, `discover-cards.ts` 2, `card-markup.ts` 1).
  `now-tab.tsx` is 137 non-blank lines, five sections (`takeable`, `blocked`, `inflight`, `notfound`, `doneToday`) and
  a cross-reference button (lines 104–121, `data-go="arr"`). `git grep -l useAcquisitionQueue -- frontend/maquette/design/src`
  → 4 files. The arrival rows to place: `moving.json` 5, `settled.json` 2, `settled-loaded.json` 7, `stuck.json` 2,
  `stuck-loaded.json` 3 — **19 rows**, of which the five stuck ones have `ids` = `null`. `features/acquisition/queries.ts`
  is 326 lines (ceiling 400): the new code lands in a new file. `now-tab.tsx`'s `AcquisitionQueue` type is
  `lib/queue.ts:42`.
- **Points ≈ 14.** `now-tab.tsx` re-slotting ≈ 20 lines 4; the queue types and the read 2; a new file for the
  arrival-card flavour (a card without identity, the `waiting` rung's reason) ≈ 25 lines 3; the new rule with its
  mutation 3; two states 2.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: 13 `mediumCardMarkup`
  call sites in 5 files (`now-tab.tsx` 6, `follows-tab.tsx` 2, `add-screen.tsx` 2, `discover-cards.ts` 2, `card-markup.ts` 1),
  `now-tab.tsx` 137 non-blank lines, `queries.ts` 326 lines, 19 arrival rows — identical. **Points 14 → 14; OPEN 3 (ruled A)
  moved what this phase says, not what it costs**: the arrival family is drawn by « En cours » and « À traiter » ONLY, never by
  « Suivis ». `follows-tab.tsx` reads `useFollows` alone (line 50), so no arrival card can reach it by construction, and R-L22-l
  (phase 17) holds the absence against a later change. The cards read « n sur 8 » on phase 5's ladder (OPEN 4).

Ruling 2: an arrival is an acquisition card. The cards of phase 1's new family now DRAW: `moving` → « En vol » while it
moves, `settled` → « Rangé aujourd'hui » (Arrivées called it « Arrivé dans les 24 h »), `stuck` → the `blocked`
section, which still bears the name « À traiter » inside « En cours » until phase 9 gives it a tab of its own.
**Arrivées still exists and still draws the same rows from `readStaging`**: one source, two readers, until phase 33.

## Red today

**R-L22-g — a card without identity** (DESIGN § 5): the card born of the game folder (« Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto »)
exists in acquisition — the folder's name for a title, no poster, `data-nonmedia`, the ladder resting on « identifié »
with `blocked` and its reason IN FULL, **no sheet link and no « Suivre »**, and a way to the candidates screen
(NE-DOIT-PAS-9's exception).

**Red against `main`**: no acquisition card exists for it.

## Move

1. `now-tab.tsx` reads the arrival family and slots each card by its rung; the folder icon and `data-nonmedia` come from
   the existing card markup (`ui/card.tsx`'s `CardFolder`).
2. Named states: `acq-card-no-identity` (from the seed's game folder) and `acq-card-waiting` (a card `waiting` behind a
   maintenance run, with its « en file » reason — the `waiting` cell state phase 4 added).
3. `acq-now-idle` and `acq-now-loaded` are RE-SEEDED; nothing is added to the queue's contract beyond phase 1.

## Mutation

With the commit made first: give the folder card a sheet link → R-L22-g falls; drop its reason → it falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded` (and `arr-idle`, `arr-loaded` — the same rows drawn by their second reader), each
accepted with « L22 § 3.3: the arrivals join « En cours » ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l22): the arrivals are cards in « En cours », a folder without identity included`
