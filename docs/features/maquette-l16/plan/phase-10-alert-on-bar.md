# Phase 10 — The alert on the bar

The alert's fourth reader: **a badge on the Trackers tab** of the bottom bar (organisation ruling 12 — every thing speaks where it lives, and the tab
that carries it takes a badge). And, because the badge must move without a refetch, the stream's ratio events are claimed by this feature.

**Reads OPEN 1 and OPEN 3 (DESIGN § 5) — ruled on 2026-09-26: OPEN 1 = A, OPEN 3 = B, so the phase is 11** (the obligations read too). The readings stay below for the record. What each
reading costs THIS phase:

- **OPEN 1 — A** (the row is in the bar from phase 2): as drawn, **10**. **OPEN 1 — B** (the row is in the drawer until L17): the badge is drawn by
  the frame's own sum over the rows the bar does not hold — the menu button carries it (L22's phase 20 wrote that derivation) — so the row's `badge:`
  line is the same and the state is `menu-badge-trackers` instead of `bar-trackers-alert`: **10**.
- **OPEN 3 — A** (the trackers under their threshold): as drawn. **OPEN 3 — B** (also the obligations in breach): `trackersBadge` reads the obligations
  too, ≈ 6 lines new and one more seed case: **+1 (11)**.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `sed -n 70,95p frontend/maquette/design/src/app/tab-bar.tsx` → the bar draws `row.badge ? row.badge() : 0` and the badge with `tabBarBadge()`
  (`data-part="shell/tab-badge"`); `app/tab-bar.tsx` is 94 non-blank lines and « KNOWS NOTHING of what a badge counts. The row points at a function the
  feature exports » (its own header). `app/live-updates.ts` (116 non-blank lines) imports `<feature>LiveRules` per feature (lines 28–33) and spreads them
  (lines 78–83) — no `trackers`. **`acquisitionLiveExemptions`** (`features/acquisition/live.ts:130`, the file is 148 non-blank lines) names `RatioMeasured`,
  `SeedObligationRecorded`, `SeedObligationSatisfied`, `SeedObligationBreached`, `CrossSeedInjected`, `CrossSeedRejected` and `TrackerAuthFailed`, with a
  `because` saying the ratio and cross-seed events « belong to surfaces that have no page yet »; `git grep -n RatioMeasured -- frontend/maquette` → that list
  only. `frontend/maquette/harness/fanout.py` is R91 (486 non-blank lines), whose per-rule hold reads each rule's event types against the query cache.
  `frontend/maquette/design/src/features/system/live.ts` → 118 non-blank lines (the analogue of a feature's own live file).
- **Points ≈ 10.** `trackersBadge` — the function the feature exports, reading the summary read (≈ 12 new) 1; the row's `badge:` line in `app/navigation.ts` (1
  edited) ⅕; **`features/trackers/live.ts`** — the rules for `RatioMeasured` and the three `SeedObligation*` events, each refreshing the summary and
  obligations reads and nothing else (≈ 35 new) 3½; its registration in `app/live-updates.ts` (2 new) ⅕; the four names removed from
  `acquisitionLiveExemptions`, its `because` rewritten to the cross-seed and auth events that remain (≈ 10 edited) 2; **R91 re-aimed** (its per-rule and
  exemption holds read the new rules) 1; **R-L16-e re-aimed** — the fourth reader, the tab's count against the row's — 1; the state `bar-trackers-alert`
  re-using phase 9's seed 1.
- **Re-measured (2026-09-26, on `dafe29ec1`).** No row of the first drawing: this phase is **new**. Two causes, said apart. **Ruling 12** gives the alert its
  tab badge (≈ 3 of the 10: the function, the row's line, the re-aimed rule, the state). **The first drawing's own gap** gives the rest (≈ 7): the
  contract's « Done when » says the stream's ratio events are claimed by a rule (R91's fan-out) and « this lot's `live.ts` does » (`frontend-architecture.md`
  § 4, L16 objective), and no phase of the first drawing wrote `features/trackers/live.ts` or touched the exemption that names those events as belonging
  to a page that had none.

A BEHAVIOUR change on the frame's own region: the bar's third button gains its badge, and a ratio event now refreshes the page's reads.

## The proof FIRST

R-L16-e re-aimed (the label was bound in phase 9); R91 re-aimed.

- **What it drives.** On a state where a tracker is under its threshold, read the bar; then deliver a `RatioMeasured` event (the mock's stream) that puts it
  above.
- **What it reads.** The Trackers tab's count equals what the roster's badge and the detail's block draw (one derivation, four readers), and moves with
  the event in the render that follows, with no refetch of any other query (R91: exactly what it should refresh, and nothing else).
- **Red today.** The tab carries no badge and no rule claims the event — both fail against `main` for that reason (and, on the branch, against phase 9,
  which draws three readers).
- **Mutation.** `scripts/mutate.sh` disagrees the tab's count from the row's (a stale copy) — the agreement must fall; and drops one event type from the
  rule — R91 must fall, naming it.

## The move

- **`features/trackers/queries.ts`** exports `trackersBadge`; **`app/navigation.ts`** — the row's `badge: trackersBadge`. The frame names the feature once
  and never its counter (`app/tab-bar.tsx`).
- **`features/trackers/live.ts`** — `trackersLiveRules`, registered in `app/live-updates.ts`; **`features/acquisition/live.ts`** — the four ratio names leave
  `acquisitionLiveExemptions`, and the `because` no longer says « no page yet » of them.
- **`harness/states/frame.ts`** — `bar-trackers-alert`, beside L22's `bar-todo-badge`.

## Mutation

Two, as above, each committed and restored separately.

## Register

§ 18's alert clause reads `served` (the in-app half; push stays a filed demand) once this phase lands; the contract's « events are claimed by a rule »
clause of L16's « Done when » reads served. Reported by phase 15.

## Oracle: states that diverge, declared by name

**None expected on the roster and the detail.** `bar-trackers-alert` is NEW. **The bar is on every state that draws it** (`shell/bottom-bar`): the badge
appears ONLY when a tracker is under its threshold, so every state whose seed puts none under it stays at zero; a state whose seed does gains the badge on
`shell/bottom-bar` — accepted, named, with the reason « L16 phase 10: the Trackers tab carries its badge ». Any divergence off that region is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `bar-trackers-alert`.

## Commit

`feat(maquette-l16): the Trackers tab carries the ratio alert, and the stream's ratio events are claimed`
