# Phase 8 — Médiathèque (the library page)

## What changes

1. **A title is never cut** (§ 12, B.5 R2 — the constitution: « Rien d'essentiel n'est tronqué ») — a `ui` change
   whose picture moves wherever a card, a tile or a cast name is drawn: `cardTitle`, `cardSubtitle`
   (`ui/variants/card.ts:37, 40`), `tileTitle` (`ui/variants/tile.ts:52`, R8) and `castCaption`
   (`features/media/variants.ts:137–139`, R9) wrap; the title takes its whole line. The virtual window's row pitch
   (`ui/virtual-rows.tsx`, `ui/window-geometry.ts`) is MEASURED on a wrapped card, never assumed. `BUGS.md` line
   (order 57, family « a title is never cut »).
2. **Its tab bar is `ui` `Tabs`** (D.1 #1) — the ONE visible change of that conversion: Médiathèque's tabs gain the
   44 px floor (`library-head.tsx:41–53`).
3. **« Récents » and « Incomplets » get the category filters** (the operator's surface decision, and Q20 = A): the
   pills of `library-head.tsx:124` drawn for the `recent` and `inc` lenses too — the same component, the same
   remembered `libCat`, counts of their own from the rows drawn; « Films » on « Incomplets » (shows only) reads
   EMPTY and says so by the empty note. Named states `lib-recent-films`, `lib-incomplete-films`.
4. **The Incomplets count line** (D.1 #6): its `statusDot` + inline `b` and `marginLeft: 12` (`page.tsx:51–54, 89`)
   → `countLine`'s own count part; the residue class `linkbtn` checked and removed.

## Acceptance — red first

- R-conformity-a: `cut · card/title`, `card/subtitle`, `tile/title`, `cast` and `cut · segment`, `segment/count`
  leave the owed list, green on every state that draws them (the cards are Acquisition's too: its states included).
- R-conformity-b extended to `lib-grid`; R-conformity-s (new, `harness/lens_filters.py`): on `lib-recent` and
  `lib-incomplete` the pills are drawn, one pressed, and a pressed « Films » leaves only films, its count equal to the
  rows drawn.
- Re-aimed by name: `virtual.py`, `scroll_keeps_place.py`, `cards.py`, `filters.py`, `library_membership.py`.
- The oracle accepts by name: every state whose titles wrap (built by script), the library tabs' floor, the pills on
  the two lenses.

## Commit

`feat(maquette-conformity): Médiathèque — titles whole, one tab bar, the category filters on every lens`
