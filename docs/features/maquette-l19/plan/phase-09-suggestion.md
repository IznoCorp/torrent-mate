# Phase 09 — Acquisition: a suggestion

## Objective

`openSugSheet` (`legacy.js:8419–8463`, two callers) moves to
`features/acquisition/panel-suggestion.ts`, kind `suggestion`, no address.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- The suggestion panel is keyed on an INDEX into the deck's order, which is why it carries no
  address: `ui/panel/contract.ts`'s own comment says a panel keyed on a position in a list the
  engine regenerates would, after that list moved, reopen about something the operator never
  asked for. **That reasoning is preserved, not revisited.**
- It reads the suggestions through `window.__suggestions`, the seam
  `installSuggestionsLookup` publishes. The producer reads
  `["/api/acquisition/suggestions"]` from the cache directly instead. **The seam is not removed
  here** — the deck still indexes into it, and it dies in phase 14 with the deck.
- The undo toast (« … écarté », `legacy.js:8421`) is the engine's interface machinery and stays:
  it is a verb's consequence, not a producer's output.

## The rule that bites

`harness/producers.py` gains the `suggestion` kind, driven from `acq-discover-deck` by a real tap
on the card's body. The mutation removes the registration; the hold falls naming the kind.

## Verdict

*(filled when the phase lands)*
