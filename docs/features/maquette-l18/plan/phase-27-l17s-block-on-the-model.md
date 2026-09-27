# Phase 27 — L17's administrator block, on the model

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** **Its size depends on L17's OPEN 1, unruled on this head** (`git show origin/docs/maquette-l17-design:docs/features/maquette-l17/DESIGN.md | grep -n 'OPEN 1' | head -3`): A — L17 drew the block behind an `admin` fact on `readAccount` and a second mock identity, and this phase re-aims the gate onto the model and deletes L17's stand-in (**9**); B — L17 held the block, and **this lot draws it** on the model (**13 + 9**, cut at the opening into 27 — the block, per L17's S5 — and 27-bis — its gate).
- `sed -n 299,318p` of L17's design → « `features/trackers/media-cross-seed.tsx` … composed into the media screen by `routes/media-sheet.tsx` … `media-cross-seed` and `media-cross-seed-hidden` ». **Neither file exists on this head.**
- L17's own finding, recorded: no account carries a role in either contract on this head (`readAccount` = 3 fields); the backend's `/auth/me` answers `{username}`. Phase 1 changes that.
- **Points ≈ 9** (reading A: 9 · reading B: 22). The base counted here: `media-cross-seed.tsx`'s gate re-aimed onto the model, ≈ 8 lines (2) + L17's stand-in `admin` fact and its second identity deleted, ≈ 15 lines (3) + `media-cross-seed-hidden` driven on the six identities (1) + R-L18-w with its mutations (3).

**DESIGN § 3.6.** L17's rule R-L17-f, proved on the six identities of § 2.2: the block is drawn for the Operator, ABSENT from the DOM for the others (not disabled, not empty); the route the block reads answers `403` for a forced call. **One authorisation path** — a stand-in left beside the model is the second mechanism § 17 point 3 forbids.

## Red today

**R-L18-w — the administrator block on the model**: shown to the Operator, absent from the DOM for the others; the forced route answers `403`.

**Red against `main`**: on this head the block does not exist; at this phase's opening the state of L17's OPEN 1 decides what is red.

## Move

The gate re-aimed, the stand-in deleted (A) — or the block drawn (B).

## Mutation

With the commit made first: show the block to the Member → R-L18-w falls.

## Register

—

## Oracle: states that diverge, declared by name

`media-cross-seed-hidden` is L17's state, re-driven. **None** otherwise. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`refactor(maquette-l18): the cross-seed block is gated by the rights model, not by a stand-in`
