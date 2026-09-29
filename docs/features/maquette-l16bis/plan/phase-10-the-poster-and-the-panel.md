# Phase 10 — The poster and the panel

**STOP C: DECIDED 2** (2026-09-29, PR #637 — DESIGN § 5): an unlinked entry's left is the media card's own
non-medium side (the folder icon and its word), the same card anatomy as every other row — not nothing.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "data-mediasheet\|data-panel" frontend/maquette/design/src/features/acquisition/card-markup.ts`
  → lines **218–229** (poster → sheet, body → panel, the folder side); `grep -n "export type CardSide"
  frontend/maquette/design/src/ui/card-markup.ts` → line **46** (a side is required — kept required, DECIDED 2).
- **Points ≈ 12.** R-L16bis-e 3; the poster (linked) and its fallback (≈ 10 lines) 1; the torrent's panel —
  facts and actions, the generic blocks only, subject `torrent:<infoHash>:<tracker>` (≈ 45 lines new) 4; « Voir la
  fiche » / « Identifier » / « Aucun dossier à identifier. » and « Retirer de qBittorrent » as the panel's actions
  (the L16 verb) 1; states `torrent-card-unlinked`, `torrent-card-no-artwork`, `torrent-panel`,
  `torrent-panel-unlinked`, `torrent-panel-unlinked-no-folder`, `torrent-panel-partial` — 6 at ½ 3.
- **Readers.** `harness/paths_to_sheets.py` (NE-DOIT-PAS-9) reads a torrent's path to its sheet on the title —
  re-aimed OUT LOUD onto the poster; `harness/trackers_removal.py` opens the removal from `torrents/remove` —
  re-aimed onto the panel's action (the swipe's is phase 11's).

## Red today

R-L16bis-e over `torrent-panel`: a tap on the card body opens nothing (`data-panel` absent).

## Move

1. Linked: the poster opens the sheet; the body opens the panel. Unlinked: the folder side (DECIDED 2), the body
   opens the panel; the panel says how to identify, or that nothing can be.
2. L17's place: the panel's actions and facts end with nothing reserved in words — L17 adds its own.

## Mutation

Open the panel from the poster → the poster hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every « Torrents » state (the poster), declared by script; the six new states. **Midpoint after this phase.**

## Commit

`feat(maquette-l16bis): a torrent's poster opens its medium, its card opens its panel`
