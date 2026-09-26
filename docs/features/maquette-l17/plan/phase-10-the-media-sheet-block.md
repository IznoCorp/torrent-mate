# Phase 10 — The media sheet's block

**Reads OPEN 1 (the block's gate) — not ruled at this writing.** **This phase and phase 11 exist only under reading A** (the block drawn at L17,
gated on a value the mock serves). Under reading B (held until L18) both leave the plan (−22 points) and the block is drawn by L18 on its model;
the map's DOIT-14 row then reads `partly` at L17's close. This phase draws the block; **phase 11 draws its gate** — the block's drawing and its
absence are never one commit.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `sed -n 1,42p frontend/maquette/design/src/routes/media-sheet.tsx` → the route composes the follows into the screen
  (`MediaScreenProperties = { readFollows }`): two features never import each other (invariant 7). `grep -cve '^[[:space:]]*$'` →
  `features/media/media-screen.tsx` **330**, `media-library-facts.tsx` **245**, `routes/media-sheet.tsx` **42**. `sed -n 1,12p
  frontend/maquette/design/src/features/media/media-screen.tsx` → the sheet's fixed order (« hero → trailer → synopsis → cast → library state (+
  seasons) → identifiers → actions »). `git grep -n 'registerBlock' -- frontend/maquette/design/src` → `panel-seasons.tsx:285`,
  `settings/panel-field.tsx:191`, `settings/panel-secret-field.tsx:54` — **bottom-panel blocks, not sheet blocks** (DESIGN fact 12). The named
  states: `grep -o '"mediasheet-[a-z-]*"' frontend/maquette/design/src/harness/states/media.ts` → `mediasheet-series`, `mediasheet-movie` among six; the
  region `screen-media/body` (`frontend/maquette/regions.json`). `grep -n 'crossReference' frontend/maquette/design/src/features/system/locks.tsx`.
- **Points ≈ 11.** `features/trackers/media-cross-seed.tsx` ≈ 55 lines new 5½ (analogue `features/media/media-cast.tsx` → 115 lines for a whole block; this one is
  a list of tracker rows); the slot in `media-screen.tsx` (a render-function prop and its placement, ≈ 6 lines edited) 1½; `routes/media-sheet.tsx` (≈ 8 lines
  edited) 1½; `fr.json` ≈ 6 lines ½; the state `media-cross-seed` re-using phase 2's seed 1; R-L17-b re-aimed at the block (its third hold) 1 → 11.
- **Found.** The block reads the SAME rows as the roster, filtered to the title (one derivation); a title that is not owned draws no block and says
  why in one line (§ 8); each tracker's block leads to that tracker's page by `crossReference()`; **`features/media` imports nothing from `features/trackers`** —
  the route composes.

## Red today

**R-L17-b — one derivation**, third hold: the block's state per tracker equals the section's row for the same pair. Red against `main`: no block.

## Move

1. The block in `features/trackers/media-cross-seed.tsx`; the media screen's slot and the route's composition; `data-part="media/cross-seed"`,
   `media/cross-seed-tracker`.
2. `media-cross-seed` in `harness/states/media.ts` (61 non-blank lines today) or in the trackers states file — measured at the opening.
3. **The block is drawn ungated for the mock's account in this phase**; the gate is phase 11's.

## Mutation

Commit first: read the state from a constant → R-L17-b falls; draw one block for all trackers instead of one per tracker → the per-tracker hold falls.

## Register

—

## Oracle: states that diverge, declared by name

`mediasheet-series`, `mediasheet-movie` on `screen-media/body` (a block on an owned title) — accepted with « L17 § 3.5: the per-tracker block ».
Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on `media-cross-seed`; `python3 scripts/check-no-french.py`.

## Commit

`feat(maquette-l17): a title says where it cross-seeds, tracker by tracker`
