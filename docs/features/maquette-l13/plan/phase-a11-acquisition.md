# Phase a·11 — Acquisition

A CONVERSION. « Maintenant », « Suivis », the « Découvrir » deck and its suggestion card, and the add screen all
draw through components. `cardHTML`, `posterBox` and `POSTERS` leave the engine, lists read the `poster` field
declared in a·6, and the format helpers move to the feature (DESIGN § 2.5, § 2.6, § 5.1; § 3, rows 16 and 18).

## The proof FIRST

- **The oracle**: zero divergence on every acquisition state and on the add screen. Any other divergence is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - `poster.py` is RE-AIMED: it reads the poster through the list's `poster` field, not through the engine's table.
    Its count is unchanged, said in its docstring.
  - `deck.py`, `drag.py` and `gestures.py` read the same cards and keep their counts. The gestures themselves are
    still the engine's until b·8.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exit 0 with `POSTERS` marked `converted` in
  `frontend/maquette/fixture-register.json`. The seed `posters.json` stays, and the lists now serve it as `poster`
  (DESIGN § 5.1).
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.
- `python3 scripts/check-poster-box.py` exit 0, with the poster box declared by the variant.
- **R80 (amended 2026-09-13, from a·8).** The pairs a·8 added — `.chip` and its five tones with `chip()`,
  `.pfall` with `posterFallback()` — go in the phase that removes the LAST engine builder writing their
  class: each pair removed here is named in the commit body, and `PAIRS_FLOOR` is lowered to the measured count.

## The move

- **Switched to `ui/card.tsx` (new file, a·9) (a·9), the tile and the swipe row (a·10)**:
  - `features/acquisition/now-tab.tsx`, `features/acquisition/follows-tab.tsx`,
    `features/acquisition/discover-cards.ts`, `features/acquisition/discover-feed.ts`,
    `features/acquisition/discover-tab.tsx` and `features/acquisition/add-screen.tsx`;
  - their `dangerouslySetInnerHTML` sites.
- **Deleted.** With its last callers gone, `cardHTML` is deleted, and so is `posterBox` with the last engine
  builder. The `lib/engine-drawing.ts` members go with them.
- **Variants go in `features/acquisition/variants.ts`**:
  - the deck and its card: `dcard`, `deck`, `deckbody`, `dhint`, `l`, `r`, `cap`, `m`, `why`, `p`, `.dcard .t`;
  - the suggestion card: `sugwrap`, `sugback`, `gone`, `out`;
  - `cadence`;
  - the swipe actions `act`, `pause`, `remove` and `resume`;
  - `segmini`, with the drawer's own use of it (`app/drawer.tsx`) converted in the same commit.
- **Dragging keeps drawing the same.** The class `dragging`, which the engine's gesture block puts on cards (the
  engine keeps it until b·8), is carried by a class-qualified utility in the variant.
- **Posters.** `POSTERS` leaves the engine, and every list reads `poster`. The phase re-takes its remaining readers
  before deleting it: `ui/panel/index.tsx` and `features/media/media-screen.tsx` (the latter converts in a·13
  through `sheet.poster`, per DESIGN § 5.1). A reader with no field is STOP D.
- **Format helpers.** They move out of the engine and sit beside the feature that uses them: `dateFR`, `plages`,
  `initials`, `baseTitle` and `richText`, among the names DESIGN § 2.5 lists. A helper two features use goes to
  `lib/` as a pure function (invariant 7). The phase re-takes their callers first.
- **Rules left waiting from a·7, a·9 and a·10**, whose last emitter is here, are deleted now:
  - the card classes `cardHTML` still emitted;
  - the `.swipe, .sugwrap, .deck` group, the gallery, and the bare `empty` and `endmark` writes.
- **Engine-internal `loading`.** Its component emitter is `features/acquisition/discover-tab.tsx`, which carries a
  variant, and the rule stays while the engine's pull block still writes the class (b·8).
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in
  the same commit.

## Gate

Per INDEX « Gates ». In addition, `check-mock-seeds.py` and `check-poster-box.py` exit 0.

## Commit

`refactor(maquette-l13): acquisition draws its cards through components and lists carry their poster`

## Amendment — 2026-09-13 (ruling 45, a·11's STOP D)

**`POSTERS` does NOT leave the engine at a·11**, and the phase above contradicted its successor: « Posters »
says the table leaves here, while `phase-a13-media-artwork.md:28` says a·13's `sheet.poster` « ends a·11's last
`POSTERS` reader ». Three readers have no `poster` field, which « A reader with no field is STOP D » refuses to
guess past: `features/arrivals/resolution-cards.tsx:100` (a release candidate — `DecisionCandidate` carries only
`withoutPoster`), `resolution-cards.tsx:161` (a decision's choice — `DecisionChoice` carries none) and
`features/media/media-screen.tsx:48-50`.

What a·11 does instead, and what this makes void above:
- Every LIST reads `poster` (`QueueCard`, `Follow`, `Suggestion`, `SearchResult`, `IncompleteShow`,
  `LibraryRow`), through `posterArtwork()` in `lib/engine-drawing.ts`; the panel head reads the `source` its
  producer passes (`panel-follow.ts`, from `follow.poster`). `posterArtworkFor()` keeps the by-title form for
  the two resolution readers ONLY.
- `cardHTML`, `posterBox` and `stripHTML` die, as written. The table, its `__referentiel` member and its window
  export STAY; `POSTERS` is NOT marked `converted` in `fixture-register.json`. Its death is a·13's.
- `poster.py` is NOT re-aimed: it reads no table (`grep -n "POSTERS\|__referentiel" harness/poster.py` finds a
  comment only). Its count cannot move for a reason this phase gives it.
- The format helpers: `baseTitle` and `initials` go to `lib/titles.ts`, `dateLabel` and `numberRanges` to
  `features/media/format.ts`, `richTextMarkup` to `features/acquisition/rich-text.ts`. The engine loses
  `initials`, `plages`, `richText` and `STRIP_LABELS`; it KEEPS `baseTitle`, which its own verbs call, and
  `dateFR` with its `__referentiel` member, which `harness/pop.py` and `harness/season_family.py` read beside
  `sheetFor` — both are re-aimed at a·14, with `sheetFor`.
- `swipeAction` goes to `ui/variants/rows.ts`, not to this feature's variants: `features/library/library-rows.ts`
  writes the same removal action, and a feature may not import another (invariant 7).
