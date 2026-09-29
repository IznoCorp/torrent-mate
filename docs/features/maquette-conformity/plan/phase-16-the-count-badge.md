# Phase 16 — The count badge (D.1 #8)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "tabBarBadge|drawerEntryCount|segmentCount" -g '*.ts' -g '*.tsx' frontend/maquette/design/src`
  → `ui/variants/frame.ts:133, 318`, `ui/variants/controls.ts:418` (moved by phase 6 — re-taken); uses at
  `app/tab-bar.tsx:87`, `app/menu-badge.tsx:38`, `app/drawer.tsx:150`, the tab bars; `grep -cv '^\s*$'
  frontend/maquette/design/src/ui/variants/frame.ts` → **397 / 400** (STOP D near: lines move OUT).
- **Points ≈ 10.** One badge variant with a `placement` (corner / inline) (≈ 15 lines, 3); three callers (1);
  `drawerEntryCount` and `segmentCount` die (1); R-conformity-k (3); the RESUME (1); the frame.ts count held (1).
- **Readers.** `badges_observed.py`, `trackers_alert.py`, `trackers_policy.py`, `audit2.py`, `actions.py`,
  `set_aside_is_later.py`, `four_tabs.py` — the parts are kept.

## Red today

R-conformity-k on `menu-system-badge`, `drawer-navigation`, `acq-todo-loaded`: the three badges share size, fill and
type — falls.

## Mutation

Restore `segmentCount` on the tabs → falls by name.

## Oracle: states that diverge, declared by name

Every state drawing a tab count or the drawer (built by script). If a tab's count changes size beyond the report's
« one drawing », STOP A.

## Commit

`refactor(maquette-conformity): one count badge, the bar's, placed at a corner or inline`
