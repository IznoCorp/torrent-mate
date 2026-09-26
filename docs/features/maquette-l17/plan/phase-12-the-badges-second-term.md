# Phase 12 — The badge's second term

**Reads OPEN 8 (which refusals the badge counts) — not ruled at this writing.** The operator ruled that « the refused cross-seeds » join the badge (L16 OPEN 3 = B);
what a refusal IS for the count is the question. **Reading A — failures only**: the function filters on the kind of trouble (DESIGN § 2.2), ≈ 6 lines more and one seed
case (a mismatch that does NOT count): **9 points**. **Reading B — every refusal in « erreur de cross-seed »**: the function counts the summary's `refused` as it is:
**8 points as drawn below**. In both the count is DERIVED from the state and leaves when the pair's state changes; no « seen » gesture is drawn.

**Opening measure (2026-09-27, on `46806a88d` — `trackersBadge` is L16's and does not exist on this head):**

- **Commands.** `sed -n 70,95p frontend/maquette/design/src/app/tab-bar.tsx` → the bar draws `row.badge ? row.badge() : 0` with `tabBarBadge()`; the file is **94** non-blank
  lines and « KNOWS NOTHING of what a badge counts »; `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/app/navigation.ts` → **210**.
  `docs/features/maquette-l16/plan/phase-10-alert-on-bar.md` → `trackersBadge` is exported by `features/trackers/queries.ts` (≈ 12 lines new in L16) and counts the trackers under
  threshold AND the obligations in breach (OPEN 3 = B). `python3 -c` over the mock's rows once phase 2 exists → the number of pairs in « erreur » by kind.
- **Points ≈ 8.** `trackersBadge` edited (the second term) ≈ 8 lines edited 1½; the state `bar-trackers-refused` — the bar with a badge only a refusal justifies, which needs its own
  scenario of the mock's state (a seed variant) 2; R-L17-g 3; R-L16-e re-aimed at the sum of three 1 → 7½, 8 by rounding.
- **Found.** L16's `bar-trackers-alert` cannot serve as this state: its badge is justified by the alert; only a state where NOTHING ELSE speaks proves the refusal counts.

## Red today

**R-L17-g — the badge's second term** (DESIGN § 5): on `bar-trackers-refused`, the Trackers tab's number equals the trackers under threshold plus the obligations in breach plus the
refusals OPEN 8 counts, and moves when a seeded refusal moves. Red: the tab counts two terms.

## Move

1. `trackersBadge` reads the summary's `crossSeed.refused` (and, under A, the kind).
2. `bar-trackers-refused` in `harness/states/frame.ts` beside L22's `bar-todo-badge` and L16's `bar-trackers-alert`.
3. R-L16-e re-aimed, out loud: the tab's count against the row's, with the sum of three — its mutation re-run.

## Mutation

Commit first: drop the term → R-L17-g falls; count every skipped check as a refusal → falls; count a resolved refusal (its pair back to « actif ») → the leave hold falls.

## Register

—

## Oracle: states that diverge, declared by name

None by the oracle — the badge's number is text and the tab's rectangle does not move (DESIGN § 4.1). R-L17-g holds it.

## Gate

Per INDEX « Gates »; `--a11y` on `bar-trackers-refused`.

## Commit

`feat(maquette-l17): the Trackers tab counts the refused cross-seeds`
