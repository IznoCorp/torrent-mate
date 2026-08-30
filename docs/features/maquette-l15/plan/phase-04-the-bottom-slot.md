# Phase 4 — The bottom slot

**Kind** conversion. **Part** 6.

## What it is

The place above the tab bar where a feature may put a bar of its own, and where the install
proposal and the toast also sit — all clearing the bar through `--tm-bottom-bar-h`. Today there is
no slot: the engine appends `.selbar` to `#device` directly.

## What lands

`app/bottom-slot.tsx` — the slot's node, and a **registry** a feature registers a component into.
The registry is the frame's, the component is the feature's; the frame names no domain word for it
(the registration carries the name).

`app/frame.tsx` lands here too, and it is D-L15-1: the frame composed as one element and one
installer, so `app/shell.tsx` (380 of 400) does not grow past invariant 6's ceiling.
`installDrawerDismissGesture()` moves into it.

## The rule

A hold on the **z-order as one ranked list**, which is what Part 6 says this part owns: the slot's
occupant paints above the tab bar and below the drawer, read from `getComputedStyle` and from
`elementFromPoint`, never from a table written beside the code. **Its mutation**: lower the slot's
`z-index` under the bar's and confirm the hold falls naming the pair.

## Trap

An empty slot must occupy nothing. A registry whose default renders a zero-height box still
publishes a bar height, and the oracle would read every surface shifted by it.
