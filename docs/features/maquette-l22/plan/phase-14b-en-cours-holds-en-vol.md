# Phase 14-bis — « En cours » holds « En vol » alone

Added 2026-09-26 by the steward on the operator's round 7 (DESIGN § 7.3, rulings 2 and 3 there), accepted as L22a's
own by the auditor's method decision of 23:2x: **« En cours » keeps « En vol » ALONE, its queue included, and says
« rien en cours » when nothing moves; « À récupérer », « Rangé aujourd'hui » and « Cherché, rien trouvé » leave it.**
A phase that REMOVES: it undoes what phases 5, 6, 7, 10 and 12 drew on those three sections, and nothing else.

**Opening measure — written by the steward on `53a4d4c78` against L22a's branch at `b0532e514`; the implementer
RE-TAKES every figure at the phase's opening, before moving anything (STOP D if a home no longer holds):**

- **Commands.** `git grep -n -E "takeable|doneToday|notFound" -- frontend/maquette/design/src/features/acquisition`
  → `now-tab.tsx` (the three sections), `arrival-slots.ts` (arrivals filed into done-today), `acquisition-tabs.tsx`
  (the « En cours » count), `follow-facts.ts`, `resolution-verbs.ts`; the i18n keys
  `screens.acquisition.takeable/takeableFoot/notfound/notfoundNoteLead/doneToday` (`git grep -n` them in `fr.json` and
  in the tree — a key read nowhere after the move is deleted).
- **Points ≈ 14.** The three sections' markup and their slotting deleted (≈ 60 lines, 12); « rien en cours » as the
  empty state of « En cours » (one key, its line, 1); R-L22-v, the new rule with its mutations (see below) — its
  label is the next free number, R224 or later (R223 is the repair train's), bound at the opening (3). **If the
  re-measure exceeds 15, the phase is cut at its opening** and the steward told.

## Red today

**R-L22-v — « En cours » holds « En vol » alone**: on `acq-now-loaded` and `acq-now-idle`, the tab draws exactly one
section, « En vol » (its queue inside it), and none titled « À récupérer », « Rangé aujourd'hui » or « Cherché, rien
trouvé »; on a scenario where nothing moves, the tab reads « rien en cours » and draws no section. **Red against the
branch**: the three sections are drawn.

## Move

Delete the three sections from `now-tab.tsx` and the slotting that fills them (`arrival-slots.ts`: an arrival no
longer lands in done-today; a card that reached its last rung leaves « En cours »); the « En cours » count counts
« En vol » alone; the empty state says « rien en cours ». **`acq-card-rungs` is re-anchored** (RULINGS.md § 2 re-read,
said in the commit): it was six rungs reached through the takeable, not-found and done-today rows on « En cours »; it
becomes the rungs the real rows reach across « En vol » and « À traiter », the eight held whole on `sheet-journey` as
ruling 2 already says. Every harness rule that read those sections is re-aimed OUT LOUD in its docstring and the
commit body — never left green over a reversed behaviour.

## Mutation

With the commit made first: restore one section (« Rangé aujourd'hui ») → R-L22-v falls by name; drop the empty
sentence → the « rien en cours » hold falls.

## Register

— (the contract's `notFound` and `doneToday` families lose their consumer: a ledger line, not a register row; nothing
on the engine side — DESIGN § 7.3 item 3.)

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded`, `acq-card-rungs`, `acq-card-requester`, and the states that draw the same « En
cours » body beneath them (the mechanism phases 5–7 named: `now-tab.tsx` under pwa-*, relay-*, signin*, startup),
each on `acquisition/body` — accepted by name with « L22 § 7.3: « En cours » holds « En vol » alone ». Any other
divergence is STOP A.

## Gate

The shared-lock `run.sh --contracts --oracle` with R-L22-v and every re-aimed rule NAMED, `--a11y` (the light ledger
may only fall), then the phase's commit.
