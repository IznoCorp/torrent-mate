# Phase a·14 — « Média »: seasons and identity

A CONVERSION with two halves. The season tree draws through variants, and every crossing reads the `ids` field
declared in a·6. As a result `SHEETS_RAW`, `OWNED`, `sheetFor`, `titleForProviderId`, `addressIdsFor` and `ownedFor`
die (DESIGN § 5.1, § 5.2; § 3, rows 15 and 18).

## The proof FIRST

- **The oracle**: zero divergence on every media, seasons-panel, episode-popover and follow-panel state. Any other
  divergence is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
- **Harness readers, RE-AIMED to the served answers** (`readMediaSheet`, `readMediaSeasons`, the list's `ids`). Each
  keeps its count, said in its docstring:
  - `addressIdsFor`: `audit2.py`, `panel.py`, `priming.py`, `season_family.py`, `screen_addresses.py`,
    `url_state.py`;
  - `sheetFor`: `audit.py`, `audit2.py`, `follow_has_sheet.py`, `followed_sheet_act.py`, `pop.py`, `priming.py`,
    `season_grab_unfollowed.py`, `transition.py`, `season_family.py`, `screen_addresses.py`;
  - `ownedFor`: `audit2.py`, `priming.py`;
  - `titleForProviderId`: `audit2.py`, `transition.py`.

  INDEX's row names five of these files. The measured list above is the one the phase re-takes before moving
  anything.
- **R156 (`follow_has_sheet.py`) keeps its hold.** It asks the served sheet instead of the engine's resolver. It
  stays a GATE; it is not B-366's repair (c·7).
- **`window.SEASONS`** (read by `busy.py`, `followed_sheet_act.py`, `message_over_layers.py`, `priming.py`,
  `season_grab_unfollowed.py`, `queued_ask_mark.py`, `season_family.py`, `season_grab.py`, `seeds_at_rest.py`) is a
  constant under 100 lines: it dies with its last reader, and each rule is re-aimed to the seed the mock layer
  answers `readMediaSeasons` from, through `window.__mocks` (DESIGN § 4.2). The phase re-takes the reader list
  first; each re-aimed file keeps its count.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exit 0 with `SHEETS_RAW` and `OWNED` marked `converted`.

## The move

- **Identity readers.** Every reader switches to `ids` on the list item, or to the served sheet:
  - `features/media/panel-seasons.tsx`, `features/media/popover-episode.ts`, `features/acquisition/follow-facts.ts`
    and `features/media/queries.ts`, for sheet presence and episodes;
  - `features/media/media-screen.tsx`, for the sheet and the title;
  - `app/history-bridge.ts` and `features/media/media-verbs.ts`, for the address ids.
- **Owned episodes.** `features/media/season-list.tsx` and `features/media/panel-seasons.tsx` read
  `readMediaSeasons.owned` in place of `ownedFor`.
- **The season tree becomes variants in `features/media/variants.ts`.** Every file stays under 400 non-blank lines,
  and the rules are deleted in this commit. The classes:
  - `season`, `ep`, `eprow`, `epdot`, `eps`, `en`, `et`, `ed`, `sfr`, `legend`;
  - `sw-info`, `sw-muted`, `sw-success`, `sw-upcoming`, `sw-waiting`, `sw-warning`;
  - `miss`, `missing`, `acquiring`, `announced`, `in_library`, `pending`, `to_grab`, `unverified`;
  - `noinfo`.
- **Deleted from `legacy.js`**: `SHEETS_RAW`, `OWNED`, `SHEETS_IDX`, `sheetFor`, `titleForProviderId`,
  `addressIdsFor` and `ownedFor`. Their members also leave the media reference type and `lib/engine-drawing.ts`.
- **`popover`.** It keeps living in the engine until its verb leaves (b·3), and asks the cache.
- **The size ledger.** This is the largest subtraction of the lot (DESIGN § 2.2). `scripts/frontend_size_ledger.py`
  is re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition: `check-mock-seeds.py` exits 0; the residue ceiling is re-recorded; and the
re-aimed file list, with one count per file, goes in the report. STOP D if a title keyed crossing has no `ids`.

## Commit

`refactor(maquette-l13): every media crossing reads the provider identity and the engine's sheet table dies`

## Amendment — 2026-09-13 (ruling 50: the phase lands as two commits)

**a·14.1** — the season tree to variants (`season-list.tsx`, `panel-seasons.tsx` with `sw-*` and `legend`,
`popover-episode.ts`), their `legacy.css` rules deleted, and `SEASONS` dies with its harness readers re-aimed to the
seed the mock layer answers `readMediaSeasons` from. A pure drawing conversion: oracle zero, the ledger down.

**a·14.2** — the identity crossings: `SHEETS_RAW`, `OWNED`, `SHEETS_IDX`, `sheetFor`, `titleForProviderId`,
`addressIdsFor`, `ownedFor`, their product readers and their harness readers. It opens on a STOP D over two questions
this file does not settle, and implements nothing before they are ruled:

- **(a)** `features/media/queries.ts`'s `placeholderData` IS `reference.sheetFor(title)`, and R119 (`priming.py`'s
  INTERCEPT) thins it by wrapping `__referentiel.sheetFor`. With the resolver dead, « what the tap knew » needs
  another source (the tapped list item? the list read's cache?), and R119's thinning seam must move with it — a
  mechanism choice, not a reader switch.
- **(b)** `features/media/media-screen.tsx`'s title comes from `titleForProviderId` BEFORE the read lands
  (`data-key`, `aria-label`, the hero's title in flight); the served `MediaSheet.title` arrives only with the read.
  Whence the title in flight is the same question.
