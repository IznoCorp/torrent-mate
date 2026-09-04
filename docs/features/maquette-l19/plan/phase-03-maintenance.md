# Phase 03 — Maintenance: the action panel

## Objective

`openActionMaintenance` (`legacy.js:5822–5878`, 57 lines, one caller through `data-maintact`)
moves to `features/maintenance/panel-action.ts`, kind `action`, address `action:<id>`.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- It reads `MAINT_ACTIONS`; the feature already asks for it —
  `features/maintenance/queries.ts`'s `useMaintenanceActions()` caches
  `["/api/maintenance/actions"]`. The producer reads that key from the cache, so the engine's
  copy of the family loses its producer reader.
- **`MAINT_ACTIONS` leaves `app/engine-data.ts`'s `NEEDED`** — the file's own header says why
  that list exists (« what the dying engine reads with no component to ask for it ») and a React
  producer asks for what it draws. What remains in `NEEDED` after this phase is written below.
- `legacy.js:32359` still validates a `action:<id>` address against the family. That is the
  LADDER's, which is L13's, not a producer's: it stays, and this phase says so rather than
  moving a second subject.
- `MAINT_TOPICS` and `RISQUES` do **not** move: the register classes them `interface` — a
  rubric's name and the sentence warning what it deletes are the interface's own words.
- R100 hold (f) gains `maintenance-topic`.

## The rule that bites

`harness/producers.py` gains the `action` kind: the panel is opened through the seam by address
and its title is the action's own. The mutation removes the registration and reads it fall.

Second mutation, on the DATA path rather than the seam: the producer's cache read is pointed at a
key nothing fills, and the hold must fall saying the panel drew nothing — a producer reading the
engine's accessor instead of the cache would survive the first mutation and not the second.

## Verdict

*(filled when the phase lands)*
