# Phase 5 — One tab component

**STOP C: OPEN 7.** Under reading B this phase leaves the lot (the conformity train builds the component); under A it
runs as written.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `git grep -n 'role="tablist"' -- 'frontend/maquette/design/src/*.tsx'` → **3**
  (`acquisition-tabs.tsx:34`, `library-head.tsx:41`, `trackers/page.tsx:32`); `grep -cv '^\s*$'
  frontend/maquette/design/src/ui/variants/controls.ts` → **397** of 400; `grep -n "fingerTab\|trackersTab ="
  frontend/maquette/design/src/features/*/variants.ts` → the two re-declared floors.
- **Points ≈ 11.** R-L16bis-j 3 (on Trackers; the other two bars are the train's); the `ui` `Tabs` component
  (≈ 45 lines new) 5; the 44 px floor moved INTO `segmentTab` (1 line) and `trackersTab` deleted 1; Trackers' page
  on it (≈ 20 lines edited) 1; the report 1.
- **Readers.** `harness/four_tabs.py`, `page_host.py`, `touch.py`, `scroll.py`, `selection.py` read
  `data-part="segment"` — the component keeps the part names; `harness/trackers_page.py` reads
  `data-trackers-tab` — kept (the caller names its data attribute).

## Red today

R-L16bis-j over `trackers-page`: the strip is not the component's (`data-part="tabs"` absent).

## Move

1. `Tabs` in `ui/`, knowing no domain: tabs `{id, label, count?, badge?}`, the selected id, the caller's data
   attribute, an optional trailing control; `role`s and `aria-selected` owned.
2. The floor in `segmentTab` lifts Médiathèque's bar to 44 px too: its states diverge, declared.
3. Trackers onto it; Acquisition and Médiathèque stay composed until the train.

## Mutation

Give Trackers' tab its own height beside the component → falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every state drawing Médiathèque's lens bar (the floor), declared by script; `trackers-page`.

## Commit

`feat(maquette-l16bis): one tab component, the Trackers page first on it`
