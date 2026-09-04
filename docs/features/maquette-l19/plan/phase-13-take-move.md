# Phase 13 — `data-take`: the move, and R103's floor

## Objective

The reader moves into `features/arrivals/`, joining the emitter's world. Phase 12's rule reads it
green with **the same assertion count**.

## What changes

- The branch at `legacy.js:10255` calls the arrivals feature's verb; the 260 ms wait goes with
  it, and the panel leaves inside the navigation's own commit.
- **R103 gains a refused floor on the take path** — zero frames of bare page — beside the one
  phase 08 added on the journey path. It keeps PRINTING the five sites this lot does not own.

## The proof

Phase 12's hold, unchanged, green, same assertion count. The mutation re-run against the new
reader falls naming the same defect. R103's new floor mutated by putting the wait back.

## What is written down rather than claimed

The contract says R103 « then REFUSES the gap instead of printing it ». **Two of the seven sites
leave with this lot and five do not** (`DESIGN.md` § 3.3 names each with its owner). The
reversal is made for what this lot owns; the remainder is carried into `REPORT.md` with its
owners, rather than announced as done.

## Verdict

*(filled when the phase lands)*
