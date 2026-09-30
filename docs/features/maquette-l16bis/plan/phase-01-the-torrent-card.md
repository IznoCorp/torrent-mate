# Phase 1 — The torrent card: its facts, its poster and panel, its swipe (S4, S5, S6)

**Opening measure** (taken on `9234341fc`; re-taken at the real opening, on `main` after the train):
`grep -cv '^\s*$' frontend/maquette/design/src/features/trackers/torrents-tab.tsx` → **196**;
`grep -n "export const cardTitle" frontend/maquette/design/src/ui/variants/card.ts` → **37** (`nowrap … ellipsis`);
the contract's `Download` → 16 fields, none of `addedAt`, `swarmSeeds`, a rate or a volume (DESIGN § 0.1 item 7);
`frontend/maquette/design/src/mocks/seeds/downloads.json` → 7 entries, all linked, longest name 80.

## What changes

1. **The data first** (DESIGN § 2.1, § 2.3): `Download` gains `addedAt`, `swarmSeeds`, `swarmLeechers`,
   `downloadedBytes`, `uploadedBytes`, `downloadRate`, `uploadRate`, each nullable, each description saying what the
   engine HAS and what it is asked for (T3); `compare-contracts.py --write`, then `--check`; the types regenerated.
   The seven entries' figures read ONCE, read-only, from the operator's qBittorrent (`/api/v2/torrents/info`,
   `--connect-timeout 10 --max-time 30`), the date in the fixture register; a figure the client does not give stays
   `null`. The poses `poseLongName` (the 132-character real name), `poseUnlinked`, `poseEntryState(state)`,
   `poseOneEntry`, each declared a derivation.
2. **A torrent is a media card** (S4): the `factRow` of `features/trackers/torrents-tab.tsx:51–120` → `cardMarkup`;
   the name WHOLE on line 1 (the card title's `wrap` value); line 2 the state chip (eight words, eight tones), the
   size, the ratio; line 3 down / up in DECIDED 1's three states (volumes by default; the byte-progress fill and the
   download rate while downloading; the upload rate alone while uploading), the sources (« sources inconnues » for
   `null`, never « 0 »), the date added; then L16's marks. `data-part="torrents/row"`, `data-entry`, `data-tracker`
   kept on the root.
3. **Its taps** (S4, S5; DECIDED 2): linked, the poster opens the medium's sheet — the film's for a film, the
   series' for an episode; unlinked, the folder side; the body opens the torrent's bottom panel (`ui/panel` facts and
   actions only, subject `torrent:<infoHash>:<tracker>`): every fact said when absent, « Voir la fiche » or
   « Identifier » / « Aucun dossier à identifier. », « Retirer de qBittorrent » (L16's verb and three confirmations).
4. **Its swipe** (S6; DECIDED 9): the card in `swipeRowMarkup`, the right drawer « Retirer » opening the SAME
   confirmation; no left drawer until L17. The row's text « Retirer » goes; the variants this orphans are deleted
   here (`torrentTitle`, `torrentHead`, `torrentChipLine`, `torrentRemove`).

## Acceptance — red first on the old code, then green

- **R-L16bis-d** (the card says it all, whole) — red on `torrent-card-long-name` (`scrollWidth > clientWidth`) and
  `torrent-card-no-popularity`; **R-L16bis-e** (the taps) — red on `torrent-panel` (no `data-panel`);
  **R-L16bis-f** (the swipe only through the confirmation) — red on `torrent-swipe-remove`.
- Re-aimed OUT LOUD, their successor named: `trackers_page.py`, `trackers_removal.py`, `trackers_roster.py`,
  `trackers_alert.py`, `follow_offered.py`, `paths_to_sheets.py` (the title → `card/title`; the path to the sheet →
  the poster; the removal → the panel's action, the swipe a second door).
- Named states (DESIGN § 3, S4–S6): every S4, S5 and S6 id, `torrent-card-film` and `torrent-panel-episode`
  included.
- Walked by finger at 369 px: the poster → the sheet → Retour → « Torrents »; « Identifier » → the resolution
  screen → Retour; a swipe → the confirmation → « Annuler ».
- `python3 scripts/compare-contracts.py --check`, `python3 scripts/check-mock-seeds.py`, read by OUTPUT.

## Commit

`feat(maquette-l16bis): a torrent is a media card — its name whole, its facts, its poster, its panel, its swipe`
