# Phase 7 — Acquisition (En cours, À traiter, Suivis, the add screen, the resolution screen)

## What changes

1. **The requester line drawn at zero width** (a defect the rule found — `cut · card/requester` at every width):
   its mechanism READ in the browser at the opening and logged in the RESUME; the repair; its `BUGS.md` line (order
   57: escaped from / why / family repaired by the responsive rule's `cut` arm).
2. **Its tab bar is `ui` `Tabs`** (D.1 #1): `acquisition-tabs.tsx` consumes it; `fingerTab`, `fingerMore` die.
3. **The add screen's segmented choices are `viewSwitch({ size: "text" })`** (OPEN 4 = A,
   `add-screen.tsx:256, 344`); `segmentSmall` stays only for the drawer until phase 10, then dies there.
4. **« Choisir » is `actionButton({ kind: "panelAction", tone: "primary" })` at 44 px** (OPEN 8 = A):
   `candidatePick` dies (`features/acquisition/variants.ts:221`, `resolution-cards.tsx:118`).
5. **The identify notice is the toned notice** (OPEN 3 = A, `add-screen.tsx:213–221`), no `role="alert"`, no inline
   colour.
6. **« Par identifiant » is `Disclosure`** (D.1 #3, `add-screen.tsx:337`, `features/acquisition/variants.ts:44–50`).
7. **`muted` → `neutral`** (`follow-vocabulary.ts:19, 105`, D.1 #5); the section head re-typed at
   `follows-tab.tsx:252` → `sectionInnerMarkup`; tokens: `add-screen.tsx:185–190, 381` (9 and 16 off-scale).

## Acceptance — red first

- R-conformity-a: `cut · card/requester` leaves the owed list, green on every Acquisition state.
- R-conformity-b (new, `harness/one_tab_bar.py`): the bars share height ≥ 44, composition and count drawing — on
  `acq-follows-list` here, extended to `lib-grid` (8) and `trackers-page` (11).
- R-conformity-o (new, `harness/segmented_choice.py`): every segmented choice is `viewSwitch`'s drawing.
- R-conformity-p (new, `harness/primary_action.py`): on `acq-resolution-tie` the pick is the `ui` action button,
  ≥ 44 px (the save's hold joins it from phase 6).
- Re-aimed by name: `resolution_card.py`, `four_tabs.py`, `add_screen_opens_fresh.py`.
- The oracle accepts by name: the requester now visible, the pick, the notice, the chevron.

## Midpoint (after this phase)

`--contracts` and the full responsive sweep (Chromium + WebKit), once; their real falls repaired before phase 8.

## Commit

`feat(maquette-conformity): Acquisition — the requester seen, one tab bar, one pick button, its notice`
