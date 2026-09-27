# Phase 33 — The media-sheet's cross-seed block, drawn fresh

**Amended 2026-09-27, rewritten** (renumbered from the first drawing's phase 27): **L17 OPEN 1 is RULED B, firm**
(round 8 question 1: « le bloc « cross-seed » de la fiche média, réservé à l'administrateur, attend L18 et son
modèle de droits »). The first drawing's conditional « reading A / reading B » is GONE — L17 drew nothing of the
block (its own § 3.5, § 7.1 confirm: no route, no state, no gate on `origin/main` at `709dbb3e9`), so there is no
stand-in to re-aim and no second identity to delete. **This lot draws the block from nothing**, taking over L17's
own first-drawing demand C (`readMediaCrossSeed`) per **F25**. **Re-priced at ≈ 27 points total (F25), too large
for one 15-point phase — cut into this phase (the block itself) and a sibling (34, its gate and R-L18-w's proof)**.

**Opening measure — re-take at this phase's own opening, against `origin/main` (L17 landed as #617, `709dbb3e9`):**

- **Commands.** `ls frontend/maquette/design/src/features/trackers/` (post-L16/L17) — confirm no `media-cross-seed.tsx`
  exists; `git show 709dbb3e9:docs/features/maquette-l17/DESIGN.md | sed -n '377,384p'` — L17's own § 3.5 says
  « Nothing of it is drawn here: no route, no state, no gate », confirming this phase starts from zero, not from
  a stand-in.
- **Points ≈ 14.** `features/trackers/media-cross-seed.tsx` — the block itself, drawn from L17's own intended shape
  (its § 3.5's citation of what the FIRST drawing proposed before L17 dropped it): per-tracker rows, the section's
  own vocabulary (« cross-seed », round 9 Q10), composed into the media screen by `routes/media-sheet.tsx` (≈ 60
  new lines, 6) + `readMediaCrossSeed`'s mock route and handler (2, demand C) + the block's own refresh key,
  carried from L17's original citation (F25) rather than re-derived (1) + two named states,
  `media-cross-seed` (needing a new seed row) and `media-cross-seed-hidden` (2) + the demand filed in the
  contract, register regenerated (2) + a sentence naming what the block shows (1).
- **What to cut if the opening measure exceeds 15.** Drop the block's own refresh key to a follow-up line in
  phase 34 rather than build it twice (−1); the section's per-tracker row count is bounded by the library's own
  trackers, so no pagination is drawn here regardless of size.

**DESIGN § 3.6, § 6.2 (demand C).** The block shows, per tracker the medium's file(s) touch, its cross-seed state
— reusing L16/L17's own vocabulary (« actif », « stoppé », « sans correspondance », etc., § 19's six-word list) —
composed into the media sheet below the existing content. **Its gate is drawn in phase 34**, on the model: this
phase draws the block AS IF gated (Admin's own view, since the resting maquette is Admin's, R-L18-a), and phase
34 proves the OTHER five identities never see it.

## Red today

`readMediaCrossSeed` does not exist; the media sheet has no cross-seed section; no route on this head.

## Move

`features/trackers/media-cross-seed.tsx`; `routes/media-sheet.tsx`'s composition; the mock route; the two named
states; the contract demand.

## Mutation

**Nothing to mutate yet** — the gate (phase 34) is what a right-based mutation bites on; this phase proves the
block RENDERS for Admin with the mock's data, not that it is absent for anyone.

## Register

—

## Oracle: states that diverge, declared by name

`media-cross-seed`, `media-cross-seed-hidden` are new. **None** otherwise. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the media sheet's cross-seed block, drawn from L17's own dropped proposal`
