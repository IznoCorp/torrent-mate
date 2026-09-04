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

*(filled when the phase lands)*
