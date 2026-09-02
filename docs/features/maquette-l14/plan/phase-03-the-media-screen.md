# Phase 3 — The media screen · **conversion**

**Owns**: `features/media/media-screen.tsx` 796 → under 400. **Constitution**: §15, §16, DOIT-11
(the address stays `/media/$provider/$id`).

## What changes

Six files beside the screen, each carrying the code, the comments and the imports it needs and
nothing else:

| File                      | Carries                                                                                                                                                                                                                                                                |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sheet-fields.ts`         | `SheetEpisode`, `CatalogSeason`, `MediaSheetFields`, `SeasonRow`, and the `Follow` slice — types only                                                                                                                                                                  |
| `season-list.tsx`         | `SeasonList` whole                                                                                                                                                                                                                                                     |
| `media-hero.tsx`          | the `heroWrap … heroNote` block and the trailer row (or its no-info) — the element carrying `data-part="hero"` is the SAME element, so `screen-banner` keeps its one owner                                                                                             |
| `media-cast.tsx`          | the heading, the director/creator row and the cast strip (or its no-info) — the `img` moves here, and `scripts/markup_dressing.py`'s `BARE_ALLOWED` key for `("features/media/media-screen.tsx", "img")` is re-keyed to this file in the same commit, reason unchanged |
| `media-library-facts.tsx` | the « Bibliothèque » heading, its facts panel (three branches) and the `SeasonList` call                                                                                                                                                                               |
| `media-information.tsx`   | the « Informations » panel and the `sheetActions` block                                                                                                                                                                                                                |

`media-screen.tsx` keeps: the params, `useStoreContent(version)`, the follows read, the two
queries, the derivations (`sorted`, `own`, `aired`, `pct`, `owns`, `followed`, `catalog`,
`catalogEp`, `prov`, `url`, `artwork`, `trailer`), `artworkFor`, the section, the bar, and the
composition of the six. `data-region="screen-media/body"` stays on the body `<div>` the screen
draws. Props are the derived values, typed from `sheet-fields.ts`.

`GRANDFATHERED["features/media/media-screen.tsx"]` is removed in the same commit.

## Deviations, recorded here rather than discovered later

- **`media-information.tsx` is `media-details.tsx`.** `check-no-french.py`'s vocabulary arm
  refuses « Information » — it is not a word this codebase's names are built from — and the guard
  is right: the block is the medium's identifiers and its actions, which « details » names.
- The design's § 2 estimate for this cut was seven files at ~190 lines for the screen; it landed
  at six plus the screen, and the screen ends the wave at 214 after phase 4 writes into it.

## Definition of done

- `grep -cve '^\s*$' frontend/maquette/design/src/features/media/media-screen.tsx` → **< 400**
  (estimate ~190); no new file over 250.
- `grep -rn -E 'data-part="hero"|screen-media/body' frontend/maquette/design/src/features/media` →
  one emitter each.
- `python3 scripts/check-frontend-boundaries.py --arm size` → 4 at or over the ceiling.
- The oracle: zero divergence across the six media states. **R115** (`harness/transition.py`) green —
  it reads `screen-banner` and `screen-body` by name; **R116** and **R26** green.
- `python3 scripts/check-markup-contracts.py` green (arm 6 reads the re-keyed `img` site).
- `run.sh --contracts` green; `npm run check` green.
- One commit: `refactor(maquette-l14): the media screen — six files beside it, nothing moved`.
