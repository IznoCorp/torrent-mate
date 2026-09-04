# Phase 18 — B-300: the restart is confirmed

## **This is a BEHAVIOUR phase. It is alone in its commit, and its rule is seen RED first.**

## Objective

`legacy.js:9590` sets `redemarrage = true` on a setting's save, and the `dataset.restart` branch
drops the flag and toasts « Service redémarré ». **There is no confirmation.**

**§17 is the clause**: a restart cuts the service for every account of the household — the case
NE-DOIT-PAS-6's spirit covers even though nothing is destroyed. Production confirms first.

## What changes

- The confirmation is `ui/dialog` — its paragraph colour and its danger contrast held by R116
  since L12, so the surface is already proved and this phase adds no drawing primitive.
- The copy lands in `fr.json`.
- **Nothing else changes**: no verb is added, the restart itself is untouched, and the flag's
  lifecycle is the same on the confirmed path.

## The rule that bites — RED FIRST

Written and run **before** the confirmation exists: it walks the tap, expects a dialog, and
**must fall** saying the restart happened on the tap. That reading is written into this file
before the repair.

Then the repair, and the rule walks the whole path:

1. tap « Redémarrer maintenant »;
2. read the dialog;
3. **cancel** — and read the flag STILL UP and no toast. *(This is the half that separates a
   confirmation from a delay, and the half a cheaper hold would skip.)*
4. tap again, confirm, and read the toast.

The mutation removes the confirmation and the hold falls at step 2. Restored.

## Gates

The oracle — a new dialog on a new path; the divergence is described · `--a11y` on the state that
raises it (a modal's `inert` background and its focus trap are `app/focus.ts`'s and already
held) · `--contracts`.

## Verdict

*(filled when the phase lands)*
