# Phase 6 — One `Tabs`, built from Acquisition's bar (D.1 #1)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n 'role="tablist"' -g '*.tsx' frontend/maquette/design/src` → **3** bars:
  `features/acquisition/acquisition-tabs.tsx:34` (THE REFERENCE, L16-bis DECIDED 7), `features/library/library-head.tsx:41`
  (no 44 px floor), `features/trackers/page.tsx:32`; `rg -n "fingerTab|fingerMore|trackersTab = cva"` → the floor
  declared in two features; `grep -cv '^\s*$' frontend/maquette/design/src/ui/variants/controls.ts` → **397 / 400**.
- **Points ≈ 14.** `ui/tabs.tsx` ≈ 50 lines new (5); three callers converted ≈ 30 lines edited (6); `fingerTab`,
  `trackersTab` die, the floor INTO `segmentTab` (1); the tablist arm of `scripts/check-component-once.py` with its
  test (the operator's 17:17 order and order 80 — authorised despite measure 1) (2, shared with phase 7's file).
- **Readers.** `four_tabs.py`, `trackers_page.py`, `audit2.py`, `set_aside_is_later.py`, `now_holds_in_flight.py`
  (`segment/count`), `scroll.py`, `selection.py`, `page_host.py`, `touch.py` (`segment`) — the parts are kept.

## The component (L16-bis DESIGN § 1.1, as specified there)

`ui/tabs.tsx`, knowing no domain: tabs `{ id, label, count?, badge? }`, the selected id, the `data-*` its taps write
(the caller names it), an optional trailing control (Acquisition's « ⋮ »). It owns `role="tablist"`, `role="tab"`,
`aria-selected`, the size — the 44 px floor INSIDE `segmentTab` (a class edit, no new line in `controls.ts`). The
landing rule stays `lib/tab-memory.ts`.

## Red today

R-conformity-b over `acq-follows-list`, `lib-grid`, `trackers-page`: the three bars share height (≥ 44), composition
(`tablist` / `tab` / `aria-selected`) and the count drawing — falls on `lib-grid` (no floor). The tablist arm: **3**
hits outside `ui/`.

## The one visible change

Médiathèque's tabs gain the 44 px floor.

## Mutation

Drop the floor from `segmentTab` → R-conformity-b falls by name; add a `role="tablist"` in a feature → the arm falls.

## Oracle: states that diverge, declared by name

Every `lib` state whose page draws the tab bar (built by script); Acquisition and Trackers: none.

## Commit

`refactor(maquette-conformity): one tab component, Acquisition's bar — Médiathèque gains the finger floor`
