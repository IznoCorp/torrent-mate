# Phase 15 — The episode popover's sentence

## Objective

`openPopEp` (`legacy.js:31542–31565`), driven from the delegation at `:9911`, moves to
`features/media/`. **The frame's half is not touched**: `app/popover-host.ts` already places the
layer behind `{ anchor, content }`, and `frame-model.md` Part 12 is explicit — the frame
places, the feature says the sentence.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- The sentence is per EPISODE and per state: what `S02E07 — en médiathèque` means is the media
  domain's knowledge, which is why it lands in `features/media/` beside `panel-seasons.tsx` that
  draws the cell the reader tapped.
- Its copy moves to `fr.json`; `EP_LABEL` is the vocabulary it reads and is already the
  reference's.

## The rule that bites

`harness/pop.py` already drives the popover's PLACEMENT. This phase adds a hold on the
**sentence's TEXT for the episode the reader tapped** — not on the layer's presence, and not on
the layer's box: the placement is the frame's and is already held, and a hold that reads the
layer would go green over a sentence about the wrong episode.

The mutation makes the producer answer the neighbouring episode's sentence; the hold falls naming
the episode tapped and the one described.

## Verdict

**Landed** over two commits. `features/media/popover-episode.ts` says the sentence;
`app/popover-host.ts` keeps the layer, its anchoring, its dismissal and its stacking, untouched.

### `pop.py` had two holes, and both are this phase's

**(1) Its verdict never reached the exit code.** `main()` computed `ok` and discarded it: that half
could print « needs review » and pass the suite. Only the second half raised.

**(2) It read the popover's TEXT and never asked whose it was.** A popover that opened correctly
and described its NEIGHBOUR satisfied every check.

### The mutation, twice — and the first reading was the useful one

| Attempt | Mutation | Result |
| --- | --- | --- |
| 1 | the producer answers the season's FIRST episode | **fell nothing** |
| 2 | the same, after the hold was sharpened | fell, naming the episode described instead |

**Why the first passed is the whole lesson**: `SssEnn` is composed from the CELL the reader
tapped, so it stays right whichever episode was looked up. What a wrong lookup actually shows is
the other episode's TITLE and its air DATE — read now from the référentiel, never from the
popover, and compared with what the popover says:

```
FAIL missing episode: S03E02 says 'S03E02 · Coke en stock (1) | Diffusé le 6 juil. 1992 …'
     — missing title 'Coke en stock (2)', air date '13 juil. 1992'
```

The third tap was written as a BLOCK statement, so reading the cell's `data-ep` from it answered
nothing — and the new half said so rather than passing on an empty comparison.

### Readings

oracle **2 958, no divergence** · contracts 17 rules + 26 guards, no violation · `legacy.js`
31 654 → **31 637**
