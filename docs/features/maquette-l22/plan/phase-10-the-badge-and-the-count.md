# Phase 10 — The badge and the count

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `sed -n 339,342p frontend/maquette/design/src/features/acquisition/queries.ts` → `acquisitionBadge()` =
  `takeable.length + blocked.length`; `acquisition-tabs.tsx` draws the same sum on « En cours ». `git grep -n 'acquisitionBadge\|takeable' -- 'frontend/maquette/harness/*.py' | wc -l`
  → **31 lines in 9 files** (`acted_surface_redraws.py`, `actions.py`, `audit.py`, `audit2.py`, `busy.py`,
  `journey_verbs.py`, `page_host.py`, `seeds_at_rest.py`, `take.py`).
- **Found (2026-09-26) — a reader of the behaviour this phase reverses.** `harness/audit2.py:244` (**R16**, « the badge is
  the sum it claims to be ») asserts, on `acq-now-idle` and `acq-now-loaded`, that BOTH the bar's badge and the first
  tab's count equal `takeable + blocked`. Left as it is, it falls the moment the badge changes — or is « fixed » by
  weakening it. **R-L22-b IS R16's re-aim**, written red first and said in the commit (DESIGN § 5.1). `actions.py:27`
  reads the badge but asserts only that the card moved.
- **Points ≈ 6.** The badge derivation and the tab count, 4 lines edited 1; R-L22-b (R16 re-aimed, with its mutation) 3;
  the tab-count half of R16 and `actions.py`'s read 1; the derivation re-read from `todo-tab.tsx`'s own count 1.

Ruling 10: the bottom bar's badge counts « À traiter » alone. **`takeable` stops reaching the bar** — a number the
operator sees moves (DESIGN § 3.1). « En cours »'s own count is what it drew minus what left it.

## Red today

**R-L22-b — the count in the badge** (R16 re-aimed): the bar's Acquisition badge equals the number on the « À traiter » tab
equals the number of cards in it, on `acq-todo-loaded`; on `acq-todo-empty` the badge is ABSENT, not `0`; « En cours »'s
tab count equals what it draws.

**Red against `main`**: the badge counts `takeable` too, and R16 as it stands asserts that sum.

## Move

`acquisitionBadge()` counts « À traiter »'s cards (one derivation, read by the bar, the drawer and the tab —
`app/navigation.ts` points at it); `acquisition-tabs.tsx` draws the count on « À traiter » and drops `blocked` from « En cours »'s.

## Mutation

With the commit made first: make the badge count `takeable` too (the old derivation) → R-L22-b falls.

## Register

—

## Oracle: states that diverge, declared by name

Every state that draws the count on « En cours »'s tab or the bar's Acquisition badge — `acq-now-*`, `acq-follows-*`,
`acq-discover*` — accepted with « L22 § 3.1: the counts follow ruling 10 ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; the nine files above are re-run by name.

## Commit

`feat(maquette-l22): the bar's badge counts « À traiter » alone`
