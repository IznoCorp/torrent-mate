# Phase 9 — The pointer

**STOP C: OPEN 1 and OPEN 2** (DESIGN § 5). Written for A and A: the absorbed episode has its own journey, and its
pointer lands on the tab holding the season's card, that card in view. Under OPEN 2 = B the action opens the season's
journey directly (≈ 5 points less, no landing adaptation); under OPEN 1 = B there is no episode journey to carry the
pointer and this phase draws it on the release picker alone (merged into phase 10).

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `grep -n "fillLandingDoor" -A3 frontend/maquette/design/src/features/acquisition/verbs.ts` → line
  **135**, the dial read as a TAB alone; `grep -n "^export function landingTab" frontend/maquette/design/src/features/acquisition/tab-memory.ts`
  → **50**; the model to adapt: `grep -n "split(DIAL_SEPARATOR)" frontend/maquette/design/src/features/trackers/verbs.ts`
  → **40** (`trackers:<name>`).
- **Points ≈ 14.** R-season-recovery-c with its mutations 3; Acquisition's landing door reads `<tab>:<acquisition>`,
  the named card scrolled into view and focused after the tab is drawn 3; the journey's `note` and its primary action
  (`data-go` + `data-dial`, the tab chosen from where the season card IS — the derivation's own answer) 2; the ended
  target (« La saison 3 est arrivée en médiathèque. », « Voir la fiche ») 1; states `absorbed-journey-pointer`,
  `absorbed-journey-pointer-blocked`, `absorbed-journey-pointer-ended`, and `season-recovery-absorbed-downloading`
  (OPEN 3 = A: the season's journey names the episode whose torrent still runs, a path each way) 4; the report 1.
- **Readers.** `harness/deferred_reason.py` lands on `trackers:c411` — the SAME shape on another page, unchanged;
  every hold reading `acqTab` after a landing (`grep -ln "acqTab" frontend/maquette/harness/*.py` at the opening).

## Red today

R-season-recovery-c on `absorbed-journey-pointer`: the journey of « Silo » · « S03E07 » draws its stages and no
pointer.

## Move

1. A landing is an arrival (§ 16): one entry; the tab inside it is not a second.
2. Copy in `fr.json`: `panels.journey.absorbedBy`, `panels.journey.seeSeasonCard`, `panels.journey.absorbedEnded`.
3. The walk by FINGER, cold and from the previous state, at the seven widths of order 85; Retour replays the path.

## Mutation

Land on a fixed « En cours » → falls at `absorbed-journey-pointer-blocked`; drop the note → falls; scroll no card
into view → falls on the viewport hold.

## Register

None.

## Oracle: states that diverge, declared by name

The three `absorbed-journey-*` ids and `season-recovery-absorbed-downloading` are new; no existing state moves.

## Commit

`feat(maquette-season-recovery): an absorbed episode's journey points to its season's card`
