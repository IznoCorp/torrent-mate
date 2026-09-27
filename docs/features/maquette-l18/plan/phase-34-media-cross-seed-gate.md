# Phase 34 — The media-sheet block's gate

**New phase, split from the first drawing's phase 27 by F25's re-pricing (≈ 27 points total).** Phase 33 drew the
block; this phase gates it on `trackers.view` (§ 1.2's own granularity note — the same right that opens the
Trackers page, reused rather than split, since both show the same cross-seed state from a different entry point)
and carries L17's own holds into R-L18-w.

**Opening measure — re-take at this phase's own opening:**

- **Points ≈ 13.** the gate itself — `trackers.view` read from the model, the block ABSENT from the DOM for a
  non-holder (≈ 8 lines, 2) + `readMediaCrossSeed` refused `403` when forced (1) + R-L18-w — proved on the SIX
  seed identities of § 2.2, carrying L17's own R-L17-b (the roster line's count matches the section's rows) and
  R-L17-k (the block's key) as inherited holds rather than re-derived ones (5) + `media-cross-seed-hidden` driven
  for the five non-`trackers.view` identities (2) + the mutation set — show the block to a non-holder → falls;
  drop the `403` on a forced call → falls (3).
- **What to cut if the opening measure exceeds 15.** Drop the L17-hold carry-over to a dated line rather than a
  proved mutation, and record the gap for the steward — not expected at this size.

**DESIGN § 3.6, § 5 (R-L18-w), F25.** « L18's state table owns both `media-cross-seed` and `media-cross-seed-hidden`.
R-L18-w carries R-L17-f's holds, the block's refresh key, and the block holds of R-L17-b and R-L17-k » — this
phase is where that carrying happens, on the model rather than on L17's own dropped stand-in.

## Red today

The block, drawn in phase 33, renders for every identity today (no gate yet); `readMediaCrossSeed` answers 200 to
a forced call from every identity.

## Move

The gate; the six-identity proof; the carried holds.

## Mutation

With the commit made first: show the block to a non-`trackers.view` identity → R-L18-w falls; let a forced
`readMediaCrossSeed` answer 200 for a non-holder → the refusal half falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** — Admin's own view is unchanged by gating (it already held the right). Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the media-sheet block gated on trackers.view, proved on all six identities`
