# Phase 16 — The virtual window

**A phase the first drawing did not carry, cut out of phase 6 at this re-cut's opening (F24).** Under OPEN 5 = A and
round 10 Q5 = A, the mark now lists a row for every OTHER eligible tracker, including the ones that were never
searched or found nothing — **the mark grows with the library**, not only with what the engine has acted on. Phase
6 measured over the 15-point ceiling once this cost was counted honestly, so it is drawn here, its own commit,
never folded silently into phase 6's own render.

**Opening measure (2026-09-27, on `1d1282567` — the mark is phase 6's):**

- **Commands.** `sed -n 1,60p frontend/maquette/design/src/ui/virtual-rows.tsx` — the fixed-size virtual-window
  component already exists in this codebase (`personalscraper` maquette, a prior lot's own precedent); this phase
  REUSES it rather than building a second one. `grep -rn 'virtual-rows' frontend/maquette/design/src` → its existing
  callers, the geometry each one declares (row height, overscan). `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/features/trackers/torrents-cross-seed.tsx` (phase 6's file, re-measured at this
  phase's own opening) — the size past which a screenful is exceeded on the phone's real width (390 px, DOIT-9).
- **Points ≈ 9.** The mark's row list wrapped in `ui/virtual-rows.tsx`'s fixed-size mode ≈ 20 lines edited 2; the
  geometry declared (row height, from the SAME chip-and-date layout every row already draws, so no new measurement
  is invented) ≈ 8 lines new 1; **whether phase 7's opened-refusal row (a taller, multi-line form) fits the SAME
  fixed height or needs its own reserved slot** is measured here and reported, never assumed 1½; R117 (the codebase's
  own virtual-window rule) or a new rule re-aimed at the mark's rows, with its own mutation, 3; the seed's own row
  count, re-measured against a screenful at 390 px (fact: DOIT-9) 1½ → 9.
- **Found.** The mark's OWN scroll never escapes the Torrents tab's own page scroll (D1's own discipline, unchanged
  by a virtual window); the window's geometry is DECLARED, not read by a rectangle proof (the oracle records no
  divergence for it, DESIGN § 4.1).

## Red today

The existing virtual-window rule (bound at phase 4, re-aimed here) reads: every row of the mark, however many the
library holds, renders as an HTML string inside a fixed-size geometry, and the DOM never carries more rows than the
window's own overscan. Red before this phase: the mark renders every row unwindowed.

## Move

1. Wrap the mark's row list in `ui/virtual-rows.tsx`, declaring its geometry.
2. Measure phase 7's opened-refusal row against the SAME fixed height; report the finding (fits, or needs its own
   reserved slot) rather than silently choosing.
3. Re-aim the virtual-window rule at the mark's own rows, seen red first.

## Mutation

Commit first: render the full row list unwindowed past a screenful → falls; let an opened refusal's taller form
overflow the fixed geometry silently (no reserved slot, no reported finding) → falls.

## Register

—

## Oracle: states that diverge, declared by name

None — a virtual window's geometry is declared, never read by a rectangle proof (DESIGN § 4.1 says so before this
phase does).

## Gate

Per INDEX « Gates »; the re-aimed virtual-window rule under `--contracts`.

## Commit

`feat(maquette-l17): the cross-seed mark's rows render in a fixed-size window once they pass a screenful`
