# Phase 17 — The Médiathèque and the sheet are read-only, but for Admin

**Amended 2026-09-27** (renumbered from the first drawing's phase 16): `library.write` is now SPLIT into
`library.delete` and `library.rescrape` (§ 1.2 — the granularity ruling 23's preprod list needs: it forbids
deletion alone, and one combined right could not express that). The selection/delete flow reads `.delete`; the
sheet's « Re-scraper » reads `.rescrape`. Both Admin-default, both absent for every other role. Re-estimated at
**9** (unchanged — a split right, not new surface).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `wc -l frontend/maquette/design/src/features/library/delete-dialog.ts frontend/maquette/design/src/features/library/library-head.tsx frontend/maquette/design/src/features/media/media-verbs.ts` → **193, 163, 141**; the selection bar REPLACES the tab bar on `lib` (`slotReplacesTabBar`, `app/navigation.ts`).
- `git grep -l -E "deleteLibraryItems|rescrapeMedia" -- frontend/maquette/design/src ':!*.d.ts' ':!mocks/*'` → `features/library/delete-dialog.ts`, `live.ts`, `queries.ts`, `features/media/media-verbs.ts`, `harness/publish.ts`: the two operations of `library.write` and where they are offered.
- `library.write` is the Operator's alone (DESIGN § 1.2): nothing is missing from a library the account can read whole, so nothing is explained (§ 3.0).
- **Points ≈ 9.** the selection and delete flow gated, ≈ 12 lines (2) + the sheet's « Re-scraper » act gated, ≈ 8 lines (2) + two states — `lib-read-only`, `sheet-read-only` (2) + R-L18-n with its mutations (3).

**DESIGN § 3.6.** For the Member, the guest and the rights-less account the library draws no selection and no delete and the sheet no « Re-scraper »; the refusal half is phase 4's guard on `deleteLibraryItems` and `rescrapeMedia`. **Note**: because the selection bar replaces the tab bar, a library with no selection affordance must not leave the bar hidden — the opening measure reads `slotReplacesTabBar` under the model.

## Red today

**R-L18-n — the library, read-only**: for the Member, the guest and the rights-less: no selection, no delete on the library, no « Re-scraper » on the sheet; forced `deleteLibraryItems` / `rescrapeMedia` answer `403`; for the Operator both exist.

**Red against `main`**: every account can select and delete.

## Move

The two gates, the states.

## Mutation

With the commit made first: leave the selection bar for the Member → R-L18-n falls; offer « Re-scraper » on the sheet → falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** for the Operator's states. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the library and the sheet are read-only for every account but the Operator`
