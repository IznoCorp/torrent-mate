# Phase 9 — The media sheet and the seasons (the sheet, the follow sheet's seasons)

## What changes

1. **A fact's state is the chip at its row's end** (D.1 #6): « ● oui / non » after a `keyValueRow`
   (`features/media/media-library-facts.tsx:118–122, 127–132, 155–160, 217–220`) → the chip; « actif / non suivi »
   joins the one on/off pair of phase 5.
2. **The empty place is `emptyNote`** (D.1 #10): `noInfo` (`season-list.tsx:231, 243, 247, 251`,
   `media-details.tsx:148`, `media-hero.tsx:177`, `media-cast.tsx:109`); a `noInfo` wrapping a skeleton is a LOADING
   place and stays, said.
3. **The season fold is `Disclosure`, variant `season`** (D.1 #3): the raw `<details>` of `season-list.tsx:256` and
   `panel-seasons.tsx:143`; `seasonDisclosure` dies. `season-list.tsx` is **390 / 400**: lines move out.
4. **The season marks are the chip** (D.1 #5): `queuedMark` (info), `seasonShortfall` (warning — and an air date
   becomes text, `:321`), `trailerSource` (neutral); the parts `season/queued`, `season/asked`, `season/missing` stay.
5. **The episode dots are `statusDot`** (D.1 #7, OPEN 9 = A), `upcoming` included; `episodeDot` dies; the episode
   cells' text colours take the `*-text` tokens.
6. **The legend is drawn over the media sheet's season list** (D.1 #9, order 57: an absent legend is a defect), only
   the codes present — the `ui` legend of phase 4.
7. **Tokens** (D.1 #16): the inline `marginTop` / `marginBottom` spacing of `media-details.tsx`, `media-cast.tsx`,
   `media-screen.tsx`, `media-library-facts.tsx`, `season-list.tsx` → the section's steps; the monospace inline
   style (`media-library-facts.tsx:165–170`) → `factKey`.

## Acceptance — red first

- R-conformity-d (new, `harness/state_chips.py`): every state pill on `followsheet-gaps`, `mediasheet-series` and
  `run-detail` is a `.chip`; R-conformity-g (new, `harness/fact_state.py`): on `mediasheet-movie` / `-series` the
  ownership row's state is the chip at its end; R-conformity-l (new, `harness/legends.py`): every dot tone drawn on
  `mediasheet-series` and `followsheet-gaps` has its legend entry; R-conformity-h (phase 5's)
  extended: on `mediasheet-no-trailer` the empty part is `emptyNote`.
- Re-aimed by name: `season_family.py`, `follow_seasons.py`, `queued_ask_mark.py`, `queued_by_hand.py`,
  `season_grab.py`, `audit.py` (`no-info`).
- The oracle accepts by name: the chips, the dots, the legend on the sheet, the fold.

## Commit

`feat(maquette-conformity): the media sheet — facts as chips, one fold, one dot, its legend`
