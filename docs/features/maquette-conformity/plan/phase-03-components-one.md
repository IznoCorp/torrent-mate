# Phase 3 — Components I, in `ui/`: the tabs, the chevron, the count badge, the segmented choice's text size

**Why first.** Four needs are drawn by several modules today (the conformity reading § B.1); the surfaces that follow
consume the ONE component, so the component exists before its consumers. Nothing a surface draws moves here except
where the component already has callers.

## What changes

1. **`ui/tabs.tsx` — `Tabs`** (D.1 #1, L16-bis DESIGN § 1.1 as specified, DECIDED 7): built from Acquisition's bar
   as it stands (`features/acquisition/acquisition-tabs.tsx:34–56`) — tabs `{ id, label, count?, badge? }`, the
   selected id, the `data-*` its taps write (the caller names it), an optional trailing control (« ⋮ »). It owns
   `role="tablist"`, `role="tab"`, `aria-selected`, the 44 px floor INSIDE `segmentTab` (a class edit, no line added
   to `ui/variants/controls.ts`, **397 / 400**). No consumer yet: the three bars convert in their surface phase.
2. **The one fold chevron** (D.1 #3, DECIDED 4): `ui/variants/surfaces.ts:407`'s `▸` / `▾` becomes the seasons' `›`
   in a 20 px chip turning a quarter (`features/media/variants.ts:226–231`); a `season` variant of `Disclosure`
   carries the uppercase summary. **Visible**: every existing `Disclosure` wears the new chevron — accepted by name.
3. **One count badge** (D.1 #8): `tabBarBadge` (`ui/variants/frame.ts:133`) gains a `placement` (`corner` /
   `inline`); `drawerEntryCount` (`:318`) and `segmentCount` (`controls.ts:418`) are re-declared as its placements
   in the same move, so no caller changes and `frame.ts` (**397 / 400**) loses lines, never gains.
4. **`viewSwitch` gains a `text` size** (D.1 #14, OPEN 4 = A) beside its icon size; `segmentSmall` is not touched
   here (its three uses convert with their surfaces: Acquisition 7, the frame 10).

## Acceptance — how we know it is done

- `Tabs`, the chevron, the badge's placements and the `text` size exist in `ui/`, each with its `variants.test.ts`
  case; `python3 scripts/check-component-once.py` clean; `grep -cv '^\s*$'` on `controls.ts` and `frame.ts` ≤ 397.
- The oracle diverges ONLY on the states drawing a `Disclosure` (built by script: a `summary` in the region) and on
  the states whose badges change geometry — each declared by name; any other divergence is STOP A.
- `run.sh --rules` on the rules reading those parts: `follow_seasons.py`, `season_family.py`, `badges_observed.py`,
  `four_tabs.py`, plus R-conformity-a on the states the oracle names.

## Commit

`feat(maquette-conformity): components I — one tab bar, one chevron, one badge, a text-sized segmented choice`
