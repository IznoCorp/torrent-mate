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

**Landed** over two commits — the move, and the reshaping that made it a subtraction.

### The count, and the repair

| | Holds | Result |
| --- | ---: | --- |
| phase 12, engine as it stood | 8 | **3 fell** — B-309 |
| phase 13, moved reader | **8** | green |
| phase 13, gained the B-249 hold | 9 | green |
| phase 13, the queue guard mutated away | 9 | **fell: « and it leaves the release screen »** |

The mutation is the sharp one: removing the guard makes the arrivals verb swallow the RELEASE
screen's take, and the rule catches it — the exact failure the two-sided reading was written for.

### The two takes are told apart by what they CARRY

An INDEX is the release screen's, a TITLE is a medium's panel — the question the engine's branch
never asked. **It is answered from the QUEUE, never from the value's shape**: « is it a number? »
is a rule about spelling, and a medium whose title is a year would break it (`2012`, `1917`,
`300`).

### The engine had to SHRINK, and the first shape did not

The first commit left `legacy.js` **nine lines longer**, and D5's exception is narrow: the engine
may be added to only to stop a defect that destroys or loses the operator's DATA. B-309 loses an
ACT, which is not that — **the growth had no licence and the shape was wrong.**
`window.__arrivalsVerbs.take(value)` answers whether it ACTED, so the delegation's branch is one
line and the panel's close, the redraw and the sentence live in the feature. 31 920 → **31 909**,
twelve below where the phase found it.

### Two guards caught the new rule's own slips

`check-markup-contracts` refused a class-token anchor (copied from the engine's own code) against
a hard zero, and refused `[data-take]` selected by PRESENCE — which would have made a VALUE
attribute a boolean state in its derived list. The rule anchors on `data-part` and reads the take
from the dataset.

### Readings

oracle **2 958, no divergence** · contracts **17 rules** + 26 guards, no violation · `take.py`
9 holds · `legacy.js` 31 911 → **31 909**
