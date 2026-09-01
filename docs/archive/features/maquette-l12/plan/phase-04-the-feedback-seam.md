# Phase 4 — The feedback seam

**Kind: CONVERSION.**

## What it does

`lib/feedback.ts` exports **one** `feedback(kind)` that every gesture passes through. **Visual
today** — D9 refuses the haptic capability and builds the seam: the target platform exposes no
public API and the workarounds ride an implementation detail that has already been tightened once.
The seam is what makes haptics **a one-file change** if the platform ever allows them.

## The contract, and it is a count

**Exactly one call site** — that is the Done-when's word. Every gesture *calls* it; nothing else
*implements* feedback. A second implementation anywhere is the defect this seam exists to prevent.

## The rule

A static rule counting implementations, not calls: `feedback` is defined in exactly one module, and
no gesture surface reaches for a feedback primitive of its own.

**What it must NOT read**, and this is B-085's shape asked in advance: a rule that greps only
`lib/` would be green over a second implementation in `features/` or in the engine. It reads the
whole tree, and the phase records which paths it walks.

## Mutation

Add a second feedback implementation in a feature → the rule falls naming the file. Restore.

## Done when

One implementation, every gesture routed through it, and the rule bit.
