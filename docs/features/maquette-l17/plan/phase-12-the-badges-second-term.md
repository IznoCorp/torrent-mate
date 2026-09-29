# Phase 12 — The badge counts failures

**OPEN 8 = A, unconditional: failures only.** The operator ruled that « the refused cross-seeds » join the badge
(L16 OPEN 3 = B); F22 narrows what a « refused cross-seed » IS for the count: the two failure families of § 2.2
(« the attempt failed », « the engine could not finish »), plus a reserved slot for a future upload/creation
failure (round 8 Q18 = B) — never the ordinary mismatches, never « sans correspondance ». **M5 confirms the count
leaves on a state change alone, no « seen » gesture** — the first drawing already read this correctly.

**Opening measure (2026-09-27, on `1d1282567` — `trackersBadge` is L16's, already re-drawn on `5e5ecd052`):**

- **Commands.** `sed -n 70,95p frontend/maquette/design/src/app/tab-bar.tsx` → the bar draws `row.badge ? row.badge()
  : 0` with `tabBarBadge()`; the file is **94** non-blank lines and « KNOWS NOTHING of what a badge counts ».
  `docs/features/maquette-l16/DESIGN.md@f3d8fed01` § 4.5 → `trackersBadge` (L16's file) counts FOUR components already: the
  threshold, the breach, the refused identifier, the unseen broken obligation. **This phase adds a FIFTH — the
  cross-seed failure — not a second**, and the demand's OWN field (`crossSeed.failed`, phase 1) is already narrowed
  to the two counted families, so the function needs no client-side kind filter of its own (F22's own cost
  correction: the first cut's ≈9-point « client filter » estimate is dropped).
- **Points ≈ 9.** `trackersBadge` edited (the fifth term) ≈ 8 lines edited 1½; the state `bar-trackers-refused` — the
  bar with a badge only a cross-seed failure justifies, under its own scenario of the mock's state (a seed variant)
  2; R-L17-g, reading `crossSeed.failed` as already-narrowed and holding that an ordinary mismatch or a
  « sans correspondance » row never moves it, 3; R-L16-d re-aimed at the sum of FOUR, now five, components 1½ → 8,
  9 by rounding.
- **Found.** L16's own `bar-trackers-alert` cannot serve as this state: its badge is justified by the ratio alert;
  only a state where NOTHING ELSE speaks proves the cross-seed failure counts on its own.

## Red today

**R-L17-g — the badge's failure term** (DESIGN § 5): on `bar-trackers-refused`, the Trackers tab's number equals the
trackers under threshold plus the obligations in breach plus the refused identifiers plus the cross-seed FAILURES
(the two counted families only), and moves when a seeded failure's state changes. Red: the tab counts four terms.

## Move

1. `trackersBadge` reads the summary's `crossSeed.failed` as its fifth term.
2. `bar-trackers-refused` in `harness/states/frame.ts` beside L22's `bar-todo-badge` and L16's `bar-trackers-alert`.
3. R-L16-d re-aimed, out loud: the tab's count against the entry's, with the sum of five — its mutation re-run.

## Mutation

Commit first: drop the term → R-L17-g falls; count an ordinary mismatch → falls; count « sans correspondance » →
falls; require a « seen » gesture to clear a resolved failure → the M5 hold falls.

## Register

—

## Oracle: states that diverge, declared by name

None by the oracle — the badge's number is text and the tab's rectangle does not move (DESIGN § 4.1). R-L17-g holds
it.

## Gate

Per INDEX « Gates »; `--a11y` on `bar-trackers-refused`.

## Commit

`feat(maquette-l17): the Trackers tab counts the cross-seed failures, and only the failures`
