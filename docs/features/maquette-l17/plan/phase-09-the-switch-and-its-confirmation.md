# Phase 9 — The switch, and its confirmation

**Ruled.** OPEN 2 = A: the switch's control lives on the tracker's own entry, through the SAME write Réglages uses.
Round 9 Q5 adds the confirmation and its option; F20 splits the flip into two halves on two different clocks; F44
(no confirmation was built) is answered here.

**Opening measure (2026-09-27, on `1d1282567` — L16's tracker entry does not exist on this head):**

- **Commands.** `sed -n 71,112p frontend/maquette/design/src/mocks/handlers/configuration.ts` →
  `updateConfigurationFile` is keyed `<file>:<key>` and moves `raw` AND `displayedValue`. `sed -n 103,130p
  personalscraper/web/routes/config.py` → `"cross_seed": False` (113) and `"tracker": False` (130): the file takes
  effect on the next run, **not at once** — a line reading « stoppé » the instant the file was written would say
  more than the engine knows (NE-DOIT-PAS-1). `sed -n 1,40p frontend/maquette/design/src/ui/disclosure.tsx` — the
  SAME disclosure L16's policy panel opens on the tracker's entry (DOIT-3); this phase adds a FOURTH row to it,
  never a second panel kind (§ 13). `grep -n 'openDeleteDialog' frontend/maquette/design/src/features/library/delete-dialog.ts`
  → the confirmation precedent (a transient state, no URL, D1), the one L16's removal confirmation follows.
- **Points ≈ 13.** The switch row ≈ 25 lines 2½; the confirmation and its option ≈ 35 lines 3½; the sentence 1;
  the handler edit for the first half ≈ 8 lines 1½; for the second half ≈ 10 lines 1½; two states 2; R-L17-e with
  ~~its two mutations 3 → ≈ 15, cut to 13 by folding the confirmation's copy into the SAME component as the switch row.~~

## What it builds

- **The switch row** inside L16's disclosure, and its control; the sentence « pris en compte à la prochaine passe ».
- **The confirmation**: its default copy AND the option « couper aussi les cross-seeds en cours pour ce tracker »,
  **unchecked by default**, naming every running obligation it would end (M4, round 9 Q7's naming discipline).
- **Left unchecked, the switch cuts NEW cross-seeds only — every `active` pair on this tracker is UNTOUCHED** (M6).
  Checked, every `active` pair on this tracker moves to `stopped` / `stoppedAt` / `stopCause: "switch"` in the SAME
  call.
- **Named states**: `tracker-cross-seed-switch-off` (a tracker whose switch is off), `tracker-cross-seed-switch-confirm`
  (the confirmation opened), in `harness/states/trackers.ts` under phase 2's scenario dial.

## Red today

**R-L17-e — the switch, in two halves** (DESIGN § 5). First half: the flip is ANSWERED on the network
(`window.__mocks.answered()`, `updateConfigurationFile`), and the Réglages row, this entry's own switch line and the
summary's `enabled` field move in the SAME render. Second half, ONLY when the option was checked: every `active`
pair on this tracker moves to `stopped` in the SAME call the write answers, never a delayed second one; left
unchecked, no pair moves. Red against `main`: none of it exists.

## Move

1. The switch row and its control; the confirmation, option unchecked by default.
2. The two states.
3. R-L17-e written first, seen red, both halves.

## ~~Mutation~~

Commit first. First half: the control messages without calling → the network hold falls; move the Réglages row and
not the projections → the agreement falls. Second half: check the option and leave a pair `active` → falls; leave
it unchecked and move a pair to `stopped` anyway → the « untouched unless asked » hold falls. **Register**: —.

## ~~Oracle and gate — done when~~

~~Oracle: L16's `tracker-entry-open` (the disclosure gains a fourth row), accepted with « L17 § 3.2: the switch »;~~
~~any other divergence is STOP A. Gate: per INDEX « Gates »; `--a11y` on both states.~~

## Commit

`feat(maquette-l17): a tracker's cross-seed switch is read and changed where the tracker is, cutting new cross-seeds only`
