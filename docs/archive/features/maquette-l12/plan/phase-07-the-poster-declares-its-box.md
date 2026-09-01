# Phase 7 — The poster declares its box

**Kind: BEHAVIOUR.** **Owns P29** — « no layout shift when a poster loads ».

**It runs BEFORE phase 8, and that order is a decision** (D-L12-2): a declared item box is the
precondition of the uniform arm of the D9 verdict row, not a neighbour of it. Phase 8 rests on what
this phase makes true.

## What it does

Every poster box declares its size — `aspect-ratio`, or width and height. Measured today: the
`2/3` ratio is declared **five times in `legacy.css`** (`:454, :457, :823, :1612, :1760`) — that is
the **dying** stylesheet, unlayered residue with a date of death at L13 (D10), which may not grow
and takes its declarations with it. The gallery **variants** are where the box belongs now.

## The instrument, and it is two

P29's row names both, and one alone is not enough:

1. a **static read** of the gallery variants — every poster box declares its size;
2. a **CLS probe** on a named state — the layout does not shift when the image arrives.

The static read alone would be green over a declared box the layout ignores. The probe alone would
be green on a fast fixture that never made the browser wait.

## The trap

**The probe must make the image arrive LATE.** A fixture that resolves instantly produces no shift
whether or not the box is declared — a probe that measures nothing reads exactly like a probe that
measures success. The image is delayed deliberately, and the phase records how.

## Mutation

Strip the ratio from one gallery variant → the static rule falls naming the variant, **and the CLS
probe falls too**. Both must be seen red: if only the static one falls, the probe is not measuring.
Restore.

## Done when

P29 reads true by both instruments; `legacy.css` has not grown; both mutations bit.
