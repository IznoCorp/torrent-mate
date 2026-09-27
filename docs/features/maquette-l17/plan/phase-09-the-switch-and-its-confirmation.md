# Phase 9 — The switch, and its confirmation

**OPEN 2 = A, unconditional**: the switch's control lives on the tracker's own entry, through the SAME write
Réglages uses. **Round 9 Q5 adds the confirmation and its option**, and **F20 splits the flip into two halves** on
two different clocks; **F44's own finding (no confirmation was built) is answered here, not merely noted.**

**Opening measure (2026-09-27, on `1d1282567` — L16's tracker entry does not exist on this head):**

- **Commands.** `sed -n 71,112p frontend/maquette/design/src/mocks/handlers/configuration.ts` →
  `updateConfigurationFile` is keyed `<file>:<key>` and moves `raw` AND `displayedValue`. `sed -n 103,130p
  personalscraper/web/routes/config.py` → `"cross_seed": False` (113) and `"tracker": False` (130): the file takes
  effect on the next run, **not at once**, so a line that read « stoppé » the instant the file was written would
  say more than the engine knows (NE-DOIT-PAS-1). `sed -n 1,40p frontend/maquette/design/src/ui/disclosure.tsx` —
  the SAME disclosure L16's policy panel already opens on the tracker's entry (DOIT-3); this phase adds a FOURTH row
  to it, never a second panel kind (§ 13). `grep -n 'openDeleteDialog' frontend/maquette/design/src/features/library/delete-dialog.ts`
  → the codebase's own confirmation precedent (a transient state, no URL, D1), the pattern L16's own removal
  confirmation already follows.
- **Points ≈ 13.** The switch row inside L16's disclosure ≈ 25 lines new 2½; the confirmation, its default copy AND
  the unchecked-by-default option (« couper aussi les cross-seeds en cours pour ce tracker », round 9 Q5) naming
  every pair this would stop, ≈ 35 lines new 3½; the sentence « pris en compte à la prochaine passe » 1; the
  handler edit so the tracker's own switch line reads the settings row the write moved (the FIRST half of R-L17-e,
  same render) ≈ 8 lines 1½; the handler edit so a CHECKED option moves every `active` pair on this tracker to
  `stopped`/`stoppedAt`/`stopCause: "switch"` in the SAME call (the SECOND half) ≈ 10 lines 1½; two states —
  `tracker-cross-seed-switch-off`, `tracker-cross-seed-switch-confirm` — 2; R-L17-e, with its two mutations, 3 →
  ≈ 15, cut to 13 by folding the confirmation's copy into the SAME component as the switch row rather than a second
  file.
- **Found.** The six words already read the switch (phases 5–7); this phase adds the way to change it. **Left
  unchecked, the option means the switch cuts NEW cross-seeds only — every `active` pair on this tracker is
  UNTOUCHED** (M6: the global and the per-tracker facts both never cut what runs unless asked to).

## Red today

**R-L17-e — the switch, in two halves** (DESIGN § 5). First half: the flip is ANSWERED on the network
(`window.__mocks.answered()`, `updateConfigurationFile`), and the Réglages row, this entry's own switch line and the
summary's `enabled` field move in the SAME render. Second half, ONLY when the confirmation's option was checked:
every `active` pair on this tracker moves to `stopped` in the SAME call the write answers, never a delayed second
one; left unchecked, no pair moves. Red against `main`: none of it exists.

## Move

1. The switch row and its control; the confirmation, with the option unchecked by default, naming every running
   obligation the option would end (M4, round 9 Q7's own naming discipline carried here).
2. The two states in `harness/states/trackers.ts`, under the scenario dial of phase 2 (a tracker whose switch is
   off, and the confirmation opened).
3. R-L17-e written first, seen red, both halves.

## Mutation

Commit first. First half: make the control message without calling → the network hold falls; move the Réglages row
and not the projections → the agreement falls. Second half: check the option and leave a pair `active` → falls;
leave the option unchecked and move a pair to `stopped` anyway → the « untouched unless asked » hold falls.

## Register

—

## Oracle: states that diverge, declared by name

L16's `tracker-entry-open` (the disclosure gains a fourth row) — accepted with « L17 § 3.2: the switch ». Any other
divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on both states.

## Commit

`feat(maquette-l17): a tracker's cross-seed switch is read and changed where the tracker is, cutting new cross-seeds only`
