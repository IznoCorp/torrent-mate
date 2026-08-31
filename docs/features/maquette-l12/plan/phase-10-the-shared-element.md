# Phase 10 — The shared element

**Kind: BEHAVIOUR.** **Owns P6** — a shared element survives navigation: the poster carries a
`view-transition-name` on the card **and** on the sheet.

**Depends on phase 9.**

## What it does

The poster that a tap carries from a card into its sheet is one element across the transition. The
name is declared on both ends — a `view-transition-name` present on only one end produces no shared
transition and no error, which is the landmine shape this repository already knows from `var()`.

## The performance floor, and it is this phase's real subject

**Images a transition carries are decoded BEFORE they are needed.** The contract states the reason
and it is measured, not theoretical: *the same asynchronous decode that makes the oracle flicker
makes a shared-element transition tear.* A poster still decoding when the transition starts is the
defect; `decode()` before the switch is the remedy.

## The rule

One driven rule: the name is present on **both** ends (a static read that names which end is
missing — not a count, which would be green on two names at one end), **and** the carried image is
decoded before the transition starts.

## Mutation

Strip the name from the sheet's end → the rule falls **naming the sheet**, not merely reporting a
count. Remove the decode → the decode half falls. Restore.

## Done when

P6 reads true; the carried image is decoded before it is carried; both mutations bit; the phase's
oracle divergences are named in its commit.
