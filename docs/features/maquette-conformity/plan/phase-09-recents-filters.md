# Phase 9 — « Récents » and « Incomplets » get the category filters (the operator's surface decisions)

**Decided 2026-09-29** (the operator, relayed by the orchestrator, order 69), verbatim: « Mediathèque sur l'onglet
recents, on peut aussi mettre les filtres Tout/Films/séries. » « Récents » gets the SAME filters as the category lens
— the same component, the same remembered choice, counts of its own if counts show. **« Incomplets » too** — Q20 = A
(rulings file § Q20): the same filter bar, the same component, the same remembered choice. **Kind: behaviour** — the visible change accepted BY NAME. Right after the tabs phase,
which rebuilds the same head.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `sed -n 122,136p frontend/maquette/design/src/features/library/library-head.tsx` → the pills
  (`filterPill`, `CATS`, `data-cat`, `aria-pressed`) drawn only when `state.libLens === "cat"` (**:124**);
  `rg -n "readLibraryRecent" -g '*.ts' frontend/maquette/design/src/mocks/handlers` → `/api/library/recent` answers
  `recent.json` (**12** rows) with no category; whether « Récents » is filtered by the SAME `libCat` read from the
  store, and whether each recent row carries its category, is read at the opening.
- **Points ≈ 13.** The pills drawn for `recent` and `inc` too (≈ 4 lines, 1); both lists filtered by `libCat` (≈ 14
  lines, 3); their counts per category, from the rows drawn (≈ 8 lines, 1); named states `lib-recent-films` and
  `lib-incomplete-films` (2); R-conformity-s over both lenses (3); the RESUME (1); mutation (1); whether
  `incomplete-shows.json` rows carry a category (they are shows: « Films » then reads EMPTY — said by the empty note,
  never a hidden pill) read at the opening (1).
- **Readers.** `filters.py` (« filters filter, and their parts sum to the whole »), `library_membership.py`,
  `selection_survives_the_listing.py` (the listing writers — a new writer counted, office).

## Red today

R-conformity-s on `lib-recent` and `lib-incomplete`: the category pills are drawn, one pressed, and a pressed « Films » leaves only films
whose count equals the pill's — falls (no pill).

## Mutation

Draw the pills only for the category lens again → falls by name.

## Oracle: states that diverge, declared by name

`lib-recent`, `lib-incomplete` and the new `lib-recent-films`, `lib-incomplete-films` — accepted by name.

## Commit

`feat(maquette-conformity): « Récents » and « Incomplets » are filtered by category like the library's lens`
