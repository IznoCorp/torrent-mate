# Phase 8 — The torrent card

**No STOP C.**

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -cv '^\s*$' frontend/maquette/design/src/features/trackers/torrents-tab.tsx` → **196**;
  `grep -n "export const cardTitle" frontend/maquette/design/src/ui/variants/card.ts` → line **37**,
  `whitespace-nowrap … text-ellipsis`; `grep -cv '^\s*$' frontend/maquette/design/src/ui/variants/card.ts` → **155**;
  the longest real name **132** (DESIGN § 0.1 item 6).
- **Points ≈ 14.** R-L16bis-d, its « whole name » half, 3; the row → `cardMarkup` in the list (≈ 40 lines edited,
  the `factRow` composition removed) 4; the `wrap` value on the card title (2 lines) 1; the marks (tracker, ratio,
  obligation chips, deadline) carried into the card's lines 2; `torrent-card-long-name` at 369 and 390 px
  (`poseLongName`) 2; `torrents-one` 1; the report 1.
- **Readers.** `torrents/row` is read by `trackers_page.py`, `trackers_removal.py`, `trackers_roster.py`,
  `trackers_alert.py`, `follow_offered.py`, `paths_to_sheets.py`; `torrents/title` by `follow_offered.py` and
  `trackers_roster.py`. **The card keeps `data-part="torrents/row"` on its root and `data-entry` / `data-tracker`**;
  `torrents/title` becomes the card's `card/title` — the two holds re-aimed OUT LOUD, their successor named.

## Red today

R-L16bis-d over `torrent-card-long-name`: the title clipped — `scrollWidth > clientWidth`.

## Move

1. One card per entry; the name on line 1, whole; § 12's line 2 order (state first — phase 9 adds its word).
2. The title's `wrap` breaks anywhere (a release name has no spaces); the poster's box does not grow with it.

## Mutation

Put `text-ellipsis` back on the torrent's title → the whole-name hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every « Torrents » state, declared by script (the row became a card); the two new ones.

## Commit

`feat(maquette-l16bis): a torrent is a card, its file name whole`
