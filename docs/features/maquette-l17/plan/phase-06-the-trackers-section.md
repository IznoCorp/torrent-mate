# Phase 6 — The tracker's section

**Reads OPEN 5 (a pair with nothing found).** OPEN 5 = A (a fifth word): the section also lists the pairs the engine looked at and found nothing
for — the list grows with the library and the section needs a virtual window if it passes a screenful (`ui/virtual-rows.tsx` exists); **+1
point, at the ceiling and over it: cut at the opening (the empty state moves to phase 7)**. OPEN 5 = B: only the pairs the engine acted on or was
stopped for are listed; the empty state says « aucune correspondance trouvée » as a sentence.

**Opening measure (2026-09-27, on `46806a88d` — the detail screen does not exist on this head; figures are from L16's plan):**

- **Commands.** `ls frontend/maquette/design/src/features/trackers` → none; `docs/features/maquette-l16/plan/phase-04-detail-head.md` and `phase-05-detail-lists.md`
  place the detail in `features/trackers/tracker-screen.tsx` (≈ 45 lines for the head, then the obligations and the active torrents — the file
  is grown, not the section's home; **the section is a file of its own**, `features/trackers/tracker-cross-seed.tsx`, so the 400-line ceiling of
  invariant 6 is never the question). The analogue: `features/system/run-list.tsx` → 176 non-blank lines, `features/settings/panel-field.tsx` → 182.
  `sed -n 1,40p frontend/maquette/design/src/ui/state-surfaces.tsx` — `SkeletonLine` and `SurfaceError`, the two states every surface needs.
  `sed -n 60,80p frontend/maquette/design/src/ui/variants/surfaces.ts` — the `chip` tones.
- **Points ≈ 15.** The section's component ≈ 45 lines new 4½; its query hook ≈ 10 lines new 1; the `fr.json` keys ≈ 8 lines 1; four states —
  `tracker-cross-seed`, `-empty`, `-loading`, `-error` — 4; R-L17-b re-aimed at the section (its second hold: the section's rows and the roster's count
  agree) 1; **R-L17-k, one read per visit (NE-DOIT-PAS-8)** 3. **AT the ceiling: if it opens over, R-L17-k moves to phase 7.**
- **Found.** Each row's title leads to its sheet by provider ID (NE-DOIT-PAS-9); a torrent with no identity leads to the resolution, never to a
  dead link. The row carries the date the state took and its origin, and offers NOTHING the engine does not allow (§ 17 point 1).

## Red today

**R-L17-k — one read per visit** (DESIGN § 5): opening the roster, a tracker's detail and (phase 10) a title's block makes each operation ONE call,
and a wait on the page makes none (`window.__mocks.answered()`). Red: the section does not exist.

## Move

1. `features/trackers/tracker-cross-seed.tsx`, mounted in `tracker-screen.tsx` after the obligations and the active torrents; its query in
   `features/trackers/queries.ts`. `data-part`: `tracker/cross-seed`, `tracker/cross-seed-row`, `tracker/cross-seed-state`,
   `tracker/cross-seed-origin`; `data-region="tracker/cross-seed"`.
2. The four states in `harness/states/trackers.ts` (or `harness/states/cross-seed.ts` when the file would pass 400 — measured at the opening).
3. R-L17-k written first, seen red; R-L17-b re-aimed.

## Mutation

Commit first: add a refetch interval to the section's query → R-L17-k falls; render the count from a constant → R-L17-b falls; render a state as the
raw enum value → R-L17-a falls.

## Register

—

## Oracle: states that diverge, declared by name

L16's `tracker-detail` and its variants (a section after the lists) — accepted with « L17 § 3.3: the cross-seed section ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on the four states.

## Commit

`feat(maquette-l17): a tracker's page lists what cross-seeds on it, one word per torrent`
