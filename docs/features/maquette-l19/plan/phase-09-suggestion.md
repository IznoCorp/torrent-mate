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

**Landed** over two commits — the move, and one hold the mutation proved missing.

`features/acquisition/panel-suggestion.ts`, kind `suggestion`, no address (the reasoning is
`ui/panel/contract.ts`'s own and is preserved rather than revisited).

### The finding — §5 was drawn and read by nothing

A mutation forcing every suggestion to be treated as a series fell **no hold** in R120 and none in
`deck.py`. « Une fois acquis, ce film quittera automatiquement votre liste » is §5 in the
interface's own words — a film has an end, a series does not — and a panel offering « Suivre » on
a film is the interface promising a watch that will never end.

R120 reads the verb AND the note, together: either alone passes over a panel that says the right
word and draws the wrong promise. Re-mutated, both fall — « film 'Suivre' · series 'Suivre' » and
« film says it: False ».

### What did NOT move, said rather than inferred

`sugVerb` stays in the engine: `sugTileHTML` reads it, and the tile is drawing the engine still
does. The producer answers the same question through `fr.json` for its own action, and the
engine's copy dies with the tile.

`window.__suggestions` and `installSuggestionsLookup` stay: the deck still indexes into that
seam, and it dies with the deck at phase 14.

### Readings

oracle **2 958, no divergence** · contracts 14 rules + 26 guards, no violation · `producers.py`
22 → **33** holds · `legacy.js` 32 192 → **32 150**
