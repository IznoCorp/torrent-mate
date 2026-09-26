# Phase 8 — The fourth tab exists, and fits

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `acquisition-tabs.tsx` 54 lines, a `tabs` array of three; `page.tsx` 49 lines, a three-way branch on
  `state.acqTab`; `screens.acquisition` holds 100 keys (`tabNow`, `tabFollows`, `tabDiscover`, `blocked` = « À traiter »
  already). `git grep -n 'acqTab\|acqtab' -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine' ':!frontend/maquette/design/src/harness' | wc -l`
  → **13 site-lines**; `git grep -l 'acqtab\|data-acqtab\|acqTab' -- 'frontend/maquette/harness/*.py' | wc -l` → **14 rule files**
  read the tab value. **The segmented control TRUNCATES silently**: `ui/variants/controls.ts:410-411`, `segmentTab`
  carries `whitespace-nowrap overflow-hidden text-ellipsis`, so a label too long for its share is cut with an ellipsis,
  never overflowing — a rule that reads page overflow would never see it.
- **Points ≈ 8.** The tab bar and page branch ≈ 9 lines 2; a new file for the tab's body (its empty state) 2; four
  `fr.json` keys 0 (folded); the new rule with its mutations 3; one state 1.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: `acquisition-tabs.tsx`
  54 lines, `page.tsx` 49 lines, `screens.acquisition` 100 keys, 13 site-lines, 14 rule files, `segmentTab` still
  `whitespace-nowrap overflow-hidden text-ellipsis` — identical. **Points 8 → 8; OPEN 1 (ruled) moved the drawing, not the
  cost**: the row reads « Suivis · En cours · À traiter · Découvrir », so the three tabs that exist REORDER (`tabs` is `now`,
  `follows`, `discover` today) in the same lines this phase edits. The harness names a tab by its value
  (`[data-acqtab="follows"]`), never by position, with ONE site that reads the DOM order — `journey.py:117-118`, « the first
  tab whose value is not `now` » — which answers `follows` under both orders. R-L22-e gains the order as a hold and a
  mutation, inside its 3.

Ruling 10: « À traiter » is a fourth tab, with its count. **This phase adds the tab and proves it fits; its body is the
empty state** (phase 9 fills it), and its count is zero. Nothing is redirected to it yet, and the `blocked` section still
lives in « En cours ». **The order of the four is ruled (OPEN 1): « Suivis · En cours · À traiter · Découvrir »**, the
operator's own words; the default-tab rule (phase 13) is untouched by it and may open the third tab.

## Red today

**R-L22-e — four labels at 390 px**: at the real phone width the four tabs' labels and counts are NOT truncated
(`scrollWidth ≤ clientWidth` per label — the ellipsis is invisible to a page-overflow test), the control does not overflow
horizontally, the « ⋮ » control stays reachable, and every target meets the touch minimum; **and the four read, in the DOM, in the
ruled order** « Suivis » · « En cours » · « À traiter » · « Découvrir ».

**Red against `main`**: three tabs, so the fourth label does not exist to be read, and « En cours » comes first.

## Move

The tab row and the page branch take `todo`; `todo-tab.tsx` draws the empty state (DOIT-7: never an empty screen); the
named state `acq-todo-empty`.

## Mutation

With the commit made first: lengthen a label past the budget → R-L22-e falls; drop a tab's `min-w-0` → it falls; swap two tabs
in the row → the order hold falls.

## Register

—

## Oracle: states that diverge, declared by name

Every state that draws Acquisition's tab bar — `acq-now-*`, `acq-follows-*`, `acq-discover*`, and the `acq-add-*` /
`acq-identify` screens behind which it stands — on `acquisition/tabs`, each accepted with « L22 § 3.1: a fourth tab, and the row's new order ».
Any state that does not draw the bar is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` over `acq-todo-empty`.

## Commit

`feat(maquette-l22): « À traiter » is a fourth tab of Acquisition and its four labels fit at 390 px`
