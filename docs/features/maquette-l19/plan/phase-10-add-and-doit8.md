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

**Landed.** `features/acquisition/panel-add.ts`, kind `add`, a NEW FILE beside `add-screen.tsx`
(395 of 400 — a single line added there is a red gate).

### R121 — DOIT-8's instrument

Four holds, each failing differently: the PANEL announces the replacement before the act is
tapped; the act raises a DIALOG, not a message after the fact; CANCELLING leaves the medium
unadded; and a medium the library does NOT own is added with no dialog at all.

**The last one is not thoroughness.** A rule reading only the owned case passes a build that asks
« are you sure? » about everything — the shape that teaches an operator to tap through without
reading.

**Which result is owned is read from the LAYER's answer, never named in the rule.** A title
written into a rule goes stale the day the fixture changes, and the walk would then pass for the
wrong reason.

**The mutation** (`if (result.owned)` → `if (false)`) fells **four** holds and prints the medium
added silently: « cancelling leaves the medium UNADDED — [0] → [0] ».

R121 joins the contracts tier.

### Two guards caught this phase's own slips

- `check-markup-contracts` refused `[data-part='row']` — a leftover constant the rule never used,
  and the three-ends contract caught **from the markup end**: « a value selected and emitted
  nowhere is a rule selecting nothing ».
- `check-no-french` refused `identifying`.

### Readings

oracle **2 958, no divergence** · contracts **15 rules** + 26 guards, no violation ·
`replacement.py` 8 holds · `legacy.js` 32 150 → **32 113**

### What the map still needs

DOIT-8's row turns `served` naming R121 — **written in phase 16**, where all four rows the map
hands this lot are amended in one edit, with the proposal stated in the pull request body
(`product-intent-map.md` is the operator's to amend).
