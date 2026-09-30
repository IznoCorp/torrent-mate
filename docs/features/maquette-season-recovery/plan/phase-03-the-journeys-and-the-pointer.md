# Phase 3 — The journeys and the pointer (S4, the season card's journey)

**Opening measure** (taken on `9234341fc`; re-taken at the real opening):
`grep -n 'address: "journey:"' frontend/maquette/design/src/features/acquisition/panel-journey.ts` → **90** (per
title); `grep -n "journey: {" -A10 frontend/maquette/design/src/app/addressed-panels.ts` → the reopen by title;
`grep -n "fillLandingDoor" frontend/maquette/design/src/features/acquisition/verbs.ts` → **135** (the dial read as a
TAB alone); the model to adapt: `grep -n "split(DIAL_SEPARATOR)" frontend/maquette/design/src/features/trackers/verbs.ts`.

## What changes

1. **A journey per acquisition** (DECIDED 1): the journey addressed `journey:<title>|S03`, `journey:<title>|S03E07`
   — producer, reopen, the read's parameter; the follow panel's « Voir le parcours » opens the running recovery's
   journey if there is one, else the most recent.
2. **The season's journey lists what it absorbed** (DECIDED 3): each absorbed episode with its state
   (« S03E07 — téléchargement déjà en cours »), each a path to its own journey.
3. **The pointer** (S4; DECIDED 2): the absorbed episode's journey draws its `note` (« Cet épisode est couvert par la
   récupération de la saison 3. ») and its primary action « Voir la carte de la saison »; the landing door reads
   `<tab>:<acquisition>` — the tab from where the season card IS (« En cours », or « À traiter » when stopped), that
   card scrolled into view, focused and highlighted. The landing is a link inside a page: it STACKS (§ 16).
4. **The ended target**: « La saison 3 est arrivée en médiathèque. » and « Voir la fiche ».

## Acceptance — red first on the old code, then green

- **R-season-recovery-c** — red on `absorbed-journey-pointer` (no note, no action) and on
  `absorbed-journey-pointer-blocked` (a fixed « En cours » landing).
- Named states: every S4 id, `season-card-journey`, `season-recovery-absorbed-downloading`; the oracle accepts the
  journey states by name.
- Walked by finger at 369 px: the journey → « Voir la carte de la saison » → the tab, the card highlighted → Retour
  → the journey's page; the same from `absorbed-journey-pointer-blocked`; the ended pointer → the sheet.

## Commit

`feat(maquette-season-recovery): a journey per acquisition, and an absorbed episode's journey points to its season's card`
