# Phase 10 — Acquisition: a search result to add, and DOIT-8's rule

## Objective

`openAddSheet` (`legacy.js:8495–8531`) moves to `features/acquisition/panel-add.ts`, kind `add`,
no address — **a NEW FILE beside `add-screen.tsx`, never a function in it**:
`features/acquisition/add-screen.tsx` stands at 395 of a 400-line hard ceiling and a single
added line there is a red gate in this phase.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular — DOIT-8's instrument

`product-intent-map.md` reads DOIT-8 `served, unproved`: the confirmation before replacing a film
the library already owns is ONE line (`legacy.js:10788–10789`) and the toast after it (`:10811`),
and **no rule walks « add a film the library owns » and reads it**. This phase writes that rule.

The rule walks the operator's path, not a named state:

1. `/add` with results, a title the library owns;
2. a real tap on it, then on « Ajouter »;
3. read the confirmation SAYING it will replace what is in place;
4. confirm, and read the toast that says the same thing.

**The mutation deletes the confirmation branch** and the hold must fall saying an add replaced a
film with no warning. Then the row turns `served` in the map, naming this rule.

## What this phase does NOT do

It does not draw a confirmation, change its copy, or add a verb. It reads what exists.

## Verdict

*(filled when the phase lands)*
