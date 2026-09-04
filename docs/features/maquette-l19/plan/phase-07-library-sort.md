# Phase 07 — Library: the sort sheet

## Objective

The sort sheet is built inline in the delegation (`legacy.js:10007`, under `data-sort`) rather
than in a named function — the only one of the ten in that shape. It moves to
`features/library/panel-sort.ts`, kind `sort`, no address.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- **The panel has no address on purpose and keeps none**: its own meta line says the sort « is a
  preference, not a location: it stays on this device and does not enter the URL ». That
  sentence is the interface's, moves to `fr.json`, and the rule below reads it where it is drawn.
- `TRIS` is `interface`-class: the table of six sort names stays the interface's. It moves with
  the producer into the feature rather than to a seed — routing a label through a mock would
  have the interface asking a server for its own words.
- `TRIS` is published on the reference today « because the rule that holds E-001 reads the NAMES
  from the prototype rather than restating them ». **That reader is a RULE, not a component**: it
  keeps reading the names, from wherever they now live, and this phase repoints it rather than
  letting it read a table nobody fills.
- `data-setsort` (the branch that APPLIES a sort) is a verb and does **not** move: this lot
  moves two verbs and this is not one of them.

## The rule that bites

`harness/library_sort.py` already exists. It gains: the sheet opens through the seam, the six
names come from the interface's own table, and the CURRENT sort is the one marked primary. The
mutation inverts the « is this the current sort » test and the hold must fall naming the sort it
marked instead.

## Verdict

*(filled when the phase lands)*
