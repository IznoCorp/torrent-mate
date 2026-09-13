# Phase a·10 — « Médiathèque »

A CONVERSION: the tile, the library row, the swipe row, the gallery and the kind chips' strip become components,
`tileHTML`, `libRowHTML` and `swipeHTML` are deleted, and `LIBRARY` dies because its three readers ask the cache
instead (DESIGN § 2.5, § 2.6, § 5.1; § 3, rows 16 and 18).

## The proof FIRST

- **The oracle**: zero divergence on every library state, and on the follows grid and the discover cards, which call
  `tileHTML` too. Any other divergence is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and no movement.
  `library_sort.py`, `gallery.py` and the selection rules read the same tiles.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exit 0 after `LIBRARY` is marked `converted` in
  `frontend/maquette/fixture-register.json`. The classification arm then no longer finds the declaration in the
  engine.
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.
- `python3 scripts/check-poster-box.py` exit 0. The `.tile .p` box declaration moves into the tile variant.
- **B-336 does NOT change.** The strip converts with its visible scrollbar exactly as it is, and c·4 repairs it.

## The move

- **Components in `ui/`, each under 400 non-blank lines**:
  - the tile: `tile`, `tilebadge`, `nm`, `off`, `p`, `fr`, `sel`;
  - the library row: `selrow`, `rowtxt`, `row`;
  - the swipe row: `swipe`, `actions`, `side`, `right`;
  - the gallery: `gallery`.
- **Variants.** The library's variants go in a feature `variants.ts` beside the library feature (new file).
  Primitives go in `ui/variants/`.
- **The kind chips' strip.** B-336 locates it in the engine's library head, not in
  `features/library/library-head.tsx`, so the phase re-takes where it is drawn before moving it.
- **Every caller of `tileHTML`, `libRowHTML` and `swipeHTML` switches**:
  - `features/library/library-list.tsx`, `features/library/page.tsx`, `features/library/incomplete-lens.tsx` and
    `features/library/reference.ts`;
  - the acquisition callers `features/acquisition/follows-tab.tsx` and `features/acquisition/discover-cards.ts`.

  The components live in `ui/`, so no feature imports another (invariant 7). The three helpers are then deleted, and
  so are their `lib/engine-drawing.ts` members.
- **The `data-*` names on tiles stay as they are.** `data-tile`, `data-selected-title`, `data-mediasheet` and
  `data-panel` are emitted identically, because L13b's verbs (b·6, b·3, b·7) read them.
- **`LIBRARY` dies.** Its three readers ask the library query's cache: `mediaNamedBy` (still in the engine until
  b·6), `knownMedium` (`app/addressed-panels.ts` (new file, a·3), a·3), and `features/acquisition/follow-facts.ts`.
  The engine copy already ignores mock deletes (DESIGN § 5.1). A state where the cache and the copy answered
  differently shows up in the oracle and is named, and a divergence the phase cannot name is STOP B.

  **Amended 2026-09-13 by phase a·3 (steward's ruling).** `knownMedium` is not in `app/addressed-panels.ts` as code:
  the engine still defines it over `follows()`, `INCOMPLETE` and `LIBRARY` and hands it in through
  `installKnownMedium`. This phase moves it and switches it to the cache, and it DECIDES, in its report, whether the
  cache's narrower answer is a behaviour change to file — a title known on any page today is known then only where
  its listing page is cached — or whether a·6's `ids` on every list item makes the predicate unnecessary. `INCOMPLETE`
  has no phase of this plan that names its death: it is `knownMedium`'s second fixture, so this phase takes it or
  says which one does. The words above that put `knownMedium` in `app/addressed-panels.ts` « a·3 » are VOID.
- **`legacy.css` rules** of the classes above are deleted in this commit, except the ones an acquisition emitter
  still wears, which wait for a·11 and are named: the `.swipe, .sugwrap, .deck` group, `act`, `pause`, `remove`,
  `resume`, and the gallery emitted by `discover-feed.ts`. `linkbtn` already has its variant and stays until a·18
  (see a·7).
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in
  the same commit.

## Gate

Per INDEX « Gates ». In addition, `check-mock-seeds.py` exits 0 with `LIBRARY` converted. STOP D if a reader of
`LIBRARY` has no cache answer.

## Commit

`refactor(maquette-l13): the library draws its tiles, rows and swipe rows as components and the engine's library copy dies`
