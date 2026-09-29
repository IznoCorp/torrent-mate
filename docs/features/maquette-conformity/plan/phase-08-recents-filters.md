# Phase 8 — « Récents » gets the category filters (the operator's surface decision)

**Decided 2026-09-29** (the operator, relayed by the orchestrator, order 69), verbatim: « Mediathèque sur l'onglet
recents, on peut aussi mettre les filtres Tout/Films/séries. » « Récents » gets the SAME filters as the category lens
— the same component, the same remembered choice, counts of its own if counts show. « Incomplets » is NOT included
unless the operator says so. **Kind: behaviour** — the visible change accepted BY NAME. Right after the tabs phase,
which rebuilds the same head.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `sed -n 122,136p frontend/maquette/design/src/features/library/library-head.tsx` → the pills
  (`filterPill`, `CATS`, `data-cat`, `aria-pressed`) drawn only when `state.libLens === "cat"` (**:124**);
  `rg -n "readLibraryRecent" -g '*.ts' frontend/maquette/design/src/mocks/handlers` → `/api/library/recent` answers
  `recent.json` (**12** rows) with no category; whether « Récents » is filtered by the SAME `libCat` read from the
  store, and whether each recent row carries its category, is read at the opening.
- **Points ≈ 10.** The pills drawn for `recent` too (≈ 4 lines, 1); the recent list filtered by `libCat` (≈ 8 lines,
  2); the counts of « Récents », per category, from the rows drawn (≈ 6 lines, 1); a named state `lib-recent-films`
  (the filter applied on « Récents ») (1); R-conformity-s (3); the RESUME (1); mutation (1).
- **Readers.** `filters.py` (« filters filter, and their parts sum to the whole »), `library_membership.py`,
  `selection_survives_the_listing.py` (the listing writers — a new writer counted, office).

## Red today

R-conformity-s on `lib-recent`: the category pills are drawn, one pressed, and a pressed « Films » leaves only films
whose count equals the pill's — falls (no pill).

## Mutation

Draw the pills only for the category lens again → falls by name.

## Oracle: states that diverge, declared by name

`lib-recent` and the new `lib-recent-films` — accepted by name.

## Commit

`feat(maquette-conformity): « Récents » is filtered by category like the library's lens`
