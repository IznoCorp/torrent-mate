# Phase 10 — The ratio alert on the bar

The alert's fourth reader: **a badge on the Trackers tab** of the bottom bar (organisation ruling 12 —
every thing speaks where it lives, and the tab that carries it takes a badge). And, because the badge
must move without a refetch, the stream's ratio and obligation events are claimed by this feature.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `sed -n 70,95p frontend/maquette/design/src/app/tab-bar.tsx` → the bar draws
  `row.badge ? row.badge() : 0` and the badge with `tabBarBadge()`; `app/tab-bar.tsx` « KNOWS NOTHING
  of what a badge counts. The row points at a function the feature exports » (its own header).
  `app/live-updates.ts` imports `<feature>LiveRules` per feature and spreads them — no `trackers`.
  **`acquisitionLiveExemptions`** (`features/acquisition/live.ts:130`) names `RatioMeasured`,
  `SeedObligationRecorded`, `SeedObligationSatisfied`, `SeedObligationBreached`, `CrossSeedInjected`,
  `CrossSeedRejected` and `TrackerAuthFailed`, with a `because` saying the ratio and cross-seed events
  « belong to surfaces that have no page yet »; `git grep -n RatioMeasured -- frontend/maquette` → that
  list only. `frontend/maquette/harness/fanout.py` is R91, whose per-rule hold reads each rule's event
  types against the query cache. `frontend/maquette/design/src/features/system/live.ts` → 118
  non-blank lines (the analogue of a feature's own live file).
- **Points ≈ 10.** `trackersBadge` — the function the feature exports, summing the three components
  (≈ 15 new, reading `alertOf` across every tracker) 1½; the row's `badge:` line in `app/navigation.ts`
  (1 edited) ⅕; **`features/trackers/live.ts`** — the rules for `RatioMeasured` and the three
  `SeedObligation*` events, each refreshing the summary and obligations reads and nothing else
  (≈ 35 new) 3½; its registration in `app/live-updates.ts` (2 new) ⅕; the four names removed from
  `acquisitionLiveExemptions`, its `because` rewritten to the cross-seed and auth events that remain
  (≈ 10 edited) 2; **R91 re-aimed** (its per-rule and exemption holds read the new rules) 1; **R-L16-d
  re-aimed** — the fourth reader, the tab's count against the entries' — 1; the state
  `bar-trackers-alert` re-using phase 8's seed 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** Close in shape to the prior re-read's own phase 10 (11,
  « new by the design, ruling 12 gives it its badge, the rest is the first drawing's own gap »): this
  redraw's badge sums THREE components instead of two (round 9 Q1's identifier), costing one point
  more in the function, offset by the bar reading four buttons already established in phase 2 (no
  re-derivation of the equal-share rule needed here, unlike a reading that had left it for this
  phase).

A BEHAVIOUR change on the frame's own region: the bar's fourth button gains its badge, and a ratio or
obligation event now refreshes the page's reads.

## The proof FIRST

R-L16-d re-aimed (the label was bound in phase 2); R91 re-aimed.

- **What it drives.** On a state where a tracker is under its threshold, read the bar; then deliver a
  `RatioMeasured` event (the mock's stream) that puts it above.
- **What it reads.** The Trackers tab's count equals the sum of every entry and row already read (one
  derivation, four readers total across phases 8 and 9), and moves with the event in the render that
  follows, with no refetch of any other query (R91: exactly what it should refresh, and nothing else).
- **Red today.** The tab carries no badge and no rule claims the event — both fail against `main` for
  that reason (and, on the branch, against phase 8, which draws three readers but no fourth).
- **Mutation.** `scripts/mutate.sh` disagrees the tab's count from the entries' (a stale copy) — the
  agreement must fall; and drops one event type from the rule — R91 must fall, naming it.

## The move

- **`features/trackers/queries.ts`** exports `trackersBadge`; **`app/navigation.ts`** — the row's
  `badge: trackersBadge`. The frame names the feature once and never its counter (`app/tab-bar.tsx`).
- **`features/trackers/live.ts`** — `trackersLiveRules`, registered in `app/live-updates.ts`;
  **`features/acquisition/live.ts`** — the four ratio/obligation names leave `acquisitionLiveExemptions`,
  and the `because` no longer says « no page yet » of them.
- **`harness/states/frame.ts`** — `bar-trackers-alert`, **beside `drawer-navigation`** (D8's oracle
  proves only #nav's own box — F58: this state is never anchored beside L22's `bar-todo-badge`, a
  different lot's row that this ruling never made it a copy of).

## Mutation

Two, as above, each committed and restored separately.

## Register

§ 18's alert clause reads `served` (the in-app half; push stays a filed demand) once this phase lands;
the contract's « events are claimed by a rule » clause of L16's « Done when » reads served. Reported
by phase 16.

## Oracle: states that diverge, declared by name

**None expected on the tabs.** `bar-trackers-alert` is NEW. **The bar is on every state that draws
it** (`shell/bottom-bar`): the badge appears ONLY when at least one of the three components is true,
so a state whose seed puts none under it stays at zero; a state whose seed does gains the badge —
accepted, named, with the reason « L16 phase 9: the Trackers tab carries its badge ». Any divergence
off that region is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `bar-trackers-alert`.

## Commit

`feat(maquette-l16): the Trackers tab carries the ratio alert on the bar, and the stream is claimed`
