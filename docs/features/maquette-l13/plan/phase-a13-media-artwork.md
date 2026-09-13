# Phase a·13 — « Média »: artwork and cast

A CONVERSION: the media screen reads `sheet.hero`, `sheet.castPortraits` and `trailerVideo` from the
sheet the mock already serves, and `HERO_IMAGES`, `CAST` and `trailerIds` die (DESIGN § 5.1; § 3,
row 18).

## The proof FIRST

- **The oracle**: zero divergence on every media-screen state: the hero, the trailer, and the cast
  with and without portraits. Any other divergence is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - RE-AIMED, each with its count unchanged and said in its docstring:
    - `audit2.py`, `screen_addresses.py` and `transition.py`, where they read `HERO_IMAGES`;
    - `screen_addresses.py`, where it reads `trailerIds`.
  - Each re-aimed rule now reads the served sheet, meaning the answer of `readMediaSheet`.
  - `CAST` has no harness reader. Its proof is the oracle on the cast states.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exit 0 with the three families marked
  `converted` in `frontend/maquette/fixture-register.json`. The byte-level arms are run here
  (DESIGN § 5.1) and their output goes in the report.

## The move

- **The media screen reads the sheet.**
  - `features/media/media-screen.tsx` reads `sheet.hero`, which is already served and not yet read,
    in place of `HERO_IMAGES`.
  - The trailer is read from `trailerVideo` alone: it is already read first, so the `trailerIds`
    fallback goes.
  - The poster comes from `sheet.poster`, which ends a·11's last `POSTERS` reader.
- **The cast reads the sheet.** `features/media/media-cast.tsx` reads `sheet.castPortraits` in place
  of `CAST`.
- **Deleted from `legacy.js`**: `HERO_IMAGES`, `CAST` and `trailerIds`. Their members also leave the
  media reference type (`features/media/reference.ts`) and `lib/engine-drawing.ts`.
- **Residue classes.** The media hero and cast classes still styled only by `legacy.css` (`noinfo`
  on the hero and the cast, and whatever the scan of DESIGN § 2.6 lists on
  `features/media/media-hero.tsx` and `features/media/media-cast.tsx`) become variants in
  `features/media/variants.ts`. Their rules are deleted in this commit, except `noinfo` while
  `features/media/season-list.tsx` still emits it (a·14).
- **The poster box.** `check-poster-box.py` stays at its floor, because the cast portrait's box
  (named in `scripts/markup_dressing.py`) is carried by the variant.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition, `check-mock-seeds.py` exits 0 and the residue ceiling is
re-recorded after the shrink. STOP D if a state draws a hero, a trailer or a portrait that the
served sheet does not carry.

## Commit

`refactor(maquette-l13): the media screen reads its artwork and cast from the served sheet`
