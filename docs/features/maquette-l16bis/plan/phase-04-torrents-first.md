# Phase 4 — « Torrents » first

**No STOP C.** Amends L16 OPEN 4 = C, by the operator (2026-09-29 16:4x): the first tab is « Torrents ».

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "tabMemory(" frontend/maquette/design/src/features/trackers/verbs.ts` → line **18**,
  first tab `"trackers"`; `grep -n "trackersTab" frontend/maquette/design/src/app/arrival.ts` → line **27**,
  `"trackers"`; `grep -n "trackersTab: \"trackers\"" frontend/maquette/design/src/harness/states/trackers.ts | wc -l`
  → the states that pose the tab by hand.
- **Points ≈ 5.** R-L16bis-a 3; two values 1; the report 1.
- **Readers.** `harness/trackers_page.py` (the landing hold, L16 phase 2) reads « Trackers » on a cold entry — re-aimed
  OUT LOUD, its successor R-L16bis-a; `harness/deferred_reason.py` lands on `trackers:c411` — a NAMED landing,
  unchanged.

## Red today

R-L16bis-a over a cold `/trackers`: « Trackers » selected — `aria-selected` on `data-trackers-tab="trackers"`.

## Move

1. The first tab `torrents`, in the memory and in the opening state.
2. The memory's key is unchanged: an operator who opened « Trackers » last keeps landing on it.

## Mutation

The first tab back to `trackers` → the cold-entry hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

`trackers-page` (now « Torrents »); `trackers-page-remembered` and `trackers-landing-named` are new.

## Commit

`feat(maquette-l16bis): the Trackers page opens on « Torrents »`
