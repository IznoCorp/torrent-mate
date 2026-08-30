# Phase 11 — The popover layer

**Kind** conversion. **Part** 7.

## What converts, and what deliberately does not

`openPopEp` builds two things at once. The **layer** — the node, its placement clamped to
`#device`, its dismissal on the next `pointerdown` — is the frame's and moves. The **sentence** it
shows (« Sortie prévue le … », the episode's state label) is a PRODUCER, and a producer is Part
12's, which is **L19's** (D-L15-4).

## What lands

`ui/popover.tsx` at `.eppop` with its `data-part="episode/popover"`, and `app/popover-host.ts`
publishing `window.__popover` with `{ anchor, content }` where `content` is a descriptor of facts —
the same shape `window.__panel` receives. The engine keeps the five lines that COMPUTE the facts
and hands them over.

## What the engine loses

The node creation, the `innerHTML`, the `appendChild` to `#device`, the geometry and the
`pointerdown` dismissal. Two of `SURVEY.md`'s nineteen sites (`32060`, `32061`).

## The rule

A hold that opens a popover on the first and on the last cell of a season matrix and asserts it
stays inside `#device`'s rectangle on both — the clamp is the whole of what this layer does that a
tooltip does not. **Mutation**: remove the clamp and confirm the hold falls naming the overflowing
edge.

## Trap

The dismissal is a `pointerdown` listener registered with `{ once: true }` inside a `setTimeout(0)`
— because the very tap that opened it would otherwise close it in the same task. That ordering is
load-bearing and is preserved, not re-derived.
