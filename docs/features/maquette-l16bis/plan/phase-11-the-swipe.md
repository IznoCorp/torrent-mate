# Phase 11 — The swipe

**STOP C: DECIDED 9** (2026-09-29, PR #637 — DESIGN § 5): the cross-seed side is ABSENT before L17 — nothing is drawn
that does nothing.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "swipeRowMarkup(" -A6 frontend/maquette/design/src/features/acquisition/follows-tab.tsx`
  → the follow row's two drawers (**153–159**); `grep -n "export function openRemoveConfirm"
  frontend/maquette/design/src/features/trackers/remove-verb.ts` → the confirmation's one door;
  `grep -cv '^\s*$' frontend/maquette/design/src/lib/swipe-arbitration.ts` → **226** (read, not edited).
- **Points ≈ 8.** R-L16bis-f 3; each card wrapped in `swipeRowMarkup`, its right drawer « Retirer »
  (`tone: remove`, the trash icon) calling the SAME verb as the panel's action (≈ 12 lines) 2; the text « Retirer »
  of the row deleted 1; `torrent-swipe-remove` 1; the three L16 confirmations reached from the swipe, by a finger walk
  1. The left drawer is not drawn (DECIDED 9) — L17 adds it.
- **Readers.** `harness/trackers_removal.py` (R-L16-c's holds) opens the confirmation — its finger walk gains the
  swipe as a second door, never replacing the panel's.

## Red today

R-L16bis-f over `torrent-swipe-remove`: no drawer — the card does not travel.

## Move

1. The drawer's action opens the confirmation; nothing leaves before « Confirmer », read on the network.
2. One row open at a time — the arbitration's rule, unchanged.

## Mutation

Call `removeDownload` from the drawer without the confirmation → the network hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every « Torrents » state (the swipe row's box), declared by script; the new states.

## Commit

`feat(maquette-l16bis): a swipe offers the removal, always through its confirmation`
