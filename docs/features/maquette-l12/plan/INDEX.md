# L12 — Native interaction · PLAN

**Design**: `docs/features/maquette-l12/DESIGN.md`. **Contract**: `frontend-architecture.md` § 4,
`#### L12 — Native interaction` — its « Done when » is the definition of finished.

**Twelve phases.** Each is ONE kind of change (D-L12-6, § 0's rule on L15's and L11's precedent):
a **conversion** phase moves code and proves the rendering did not change — oracle green, zero
divergence; a **behaviour** phase changes what the interface does and names its divergences in its
own commit. **No phase does both.** The kind is written in every row below and at the head of every
phase file.

**Every phase gate**: the oracle, `run.sh --contracts` (13 rules + the repository's cheap guards,
counted and printed by the script), and **every rule of that phase mutation-tested — seen red,
naming the right defect, restored**. `scripts/mutate.sh` refuses a dirty tree and restores from the
index, so the phase's fix is committed before its mutation runs.

**PHASES CHAIN WITHOUT PAUSE — a global constraint, and it outranks the urge to
report.** After a phase's gate is green and its work committed, **start the next phase in the same
turn**. Never end a turn to announce that a phase is complete, and never end one asking whether to
continue. **The only stops this wave has are the ones this plan NAMES**: phase 8's operator-named
choice of virtualiser, the `≤ 613` ceiling on an L14 file, an anomaly that would require deviating
from the plan (deviation only on anomaly plus sign-off), and a red gate that cannot be repaired
within the plan. The operator arbitrates the PERIMETER, never the cadence.

**The self-check, because this rule has been broken repeatedly**: before ending a turn, read the
last paragraph written. If it announces a phase finished, or asks whether to go on, then the next
phase should have started in that same turn. Rigour per phase is unchanged — each still lands as a
green commit with its proof; it is the chaining that changes, not the method.

**Announce on the harness before every run** — `run.sh`, the oracle, `mutate.sh`,
`harness-hold-counts.py`. One machine, one harness; the steward may be auditing here.

| # | Phase | Kind | Owns | New rules |
| ---: | --- | --- | --- | --- |
| 1 | The compositor defaults | behaviour | **P25** (no tap flash), **P26** (a long press selects nothing) | 1 static |
| 2 | The mobile geometry | behaviour | **P11** (`100dvh`), contained overscroll, **P17** = **B-234** (`interactive-widget`) | 2 static |
| 3 | The arbitration moves | **conversion** | `lib/press-arbitration.ts` — the timer, the 12 px tolerance, the point-identified swallow, the `contextmenu` refusal | 1 driven (touch **and** mouse) |
| 4 | The feedback seam | **conversion** | `lib/feedback.ts` — exactly one call site, visual today (D9) | 1 |
| 5 | The pressed states | behaviour | `@media (hover: hover)` for hover, `:active` for pressure, no JavaScript (D9) | 1 driven |
| 6 | Pull-to-refresh joins the vocabulary | **conversion** | `#ptr` leaves the engine for `lib/` (`MODEL.md` Part 8) | 1 driven |
| 7 | The poster declares its box | behaviour | **P29** — the precondition of phase 8 (D-L12-2) | 1 + a CLS probe |
| 8 | The windowing | behaviour | **P24**, the D9 verdict row, the `≤ 613` gate on an L14 file (§ 3) | 1 driven |
| 9 | The declared page transition | behaviour | **P5**, **P20** — `startViewTransition`, `::view-transition-*`, both motion preferences | 1 driven, both preferences |
| 10 | The shared element | behaviour | **P6** — the poster from card to sheet, decoded before it is carried | 1 driven |
| 11 | B-252's two child nodes | **rule only** | the dialog's paragraph `color` under both themes; the danger action's contrast under `light` | 2 |
| 12 | The close | — | the device protocol, the register, the report, the hold counts | — |

**Phase 8 depends on phase 7** and on nothing else in this list (D-L12-2). Phase 10 depends on
phase 9. Phases 3, 4, 5 and 6 run in that order because 5 and 6 consume what 3 and 4 place. The
rest are independent and run in the order written.

---

## What this plan does not do, and why

- **It does not open `app/shell.tsx`** (D-L12-3). It is at 398 of 400 and the transition host is
  `app/navigation.ts` at 197. The subject-split the contract holds in reserve **has no subject**,
  so it is not done. Recorded so that « we looked and it was unnecessary » is not read next wave as
  « nobody looked ».
- **It does not extend L14's four files.** Phase 8 substitutes inside one of them and leaves it at
  **≤ 613** non-blank lines, measured (§ 3 of the design). If it cannot, **the phase stops and
  reports** rather than extending quietly.
- **It does not move a producer, an engine-side gesture caller (L19), or the ladder's handler
  (L13)**, and it touches the engine's two files **only by subtraction** (D5).
- **It does not claim B-268, B-269 or B-270** (D-L12-7). No phase here opens `served_copy.py`, so
  the brief's conditional does not fire. They stay for whoever next touches it.
- **It skips no lot.** § 0's selection rule elects L12 and `IMPLEMENTATION.md` records it as Next.

## One thing the operator must rule on — ANSWERED 2026-08-31, and it went the other way

**⚠ Everything in this section below the rule is VOID.** It asked whether writing a D9 verdict row
in the wave that implements it breaches § 7.1, and reasoned that a **refusal** would dissolve the
question. **The operator answered a different question and reversed the rule the whole section rests
on**: a reliable, maintained, proven, widely used library that solves exactly the problem is
**preferred** to re-coding it, and the candidates are proposed for the operator to choose.

So there is no refusal to dissolve anything: phase 8 **surveys candidates and waits for the
operator's choice** before adopting. DESIGN.md § 2 and `phase-08-the-windowing.md` carry the new
shape. The paragraphs below are kept, struck, because § 7.1 amends by naming what is void rather
than by quietly editing — and so that « it is only arithmetic » is not proposed again as if new.

---

## ~~One thing the operator must rule on~~ (VOID — see above)

**The D9 verdict row is written in phase 8 as a PROPOSAL, not as a settled decision.** The brief
directs this wave to write it (« you write it under § 7.1 before adopting anything »), and § 7.1
says an agent proposes while the operator arbitrates — and that a § 2 decision is **not amended in
the wave that also implements it**.

The reading this plan takes, and the operator may overturn it: **D9 is not being amended.** Its two
rules stand untouched; its table is explicitly « Applied, with the verdicts they produce », so a new
row is an *application* of rules 1 and 2 to a candidate nobody had put to them, not a new decision.
The row lands with its full reasoning in the file rather than in a pull request body — which is what
the brief is protecting against — and it is **flagged in the pull request for arbitration**. If the
operator reads it as an amendment instead, the row comes out and phase 8's adoption waits.

**The steward confirmed this reading on 2026-08-31 and routed the question to the operator — and
added the observation that may dissolve it entirely.** § 7.1's guard is about deciding AND
implementing in one breath. **It only bites if this wave ADOPTS something.** Rule 2 asks whether the
maths has been written; windowing a fixed-height list is a few lines of arithmetic. **So if phase 8's
measurement lands on « write it, no library », the row records a REFUSAL, nothing is adopted, and
nothing waits.** Only the variable-height arm — a scoped adoption — needs the operator's word.
Phase 8 therefore proceeds to its measurement and to the uniform arm without blocking; it blocks
only at the point of adopting a library, and only if the measurement demands one.

## The close (phase 12) owes five things, and the fifth is a measurement

1. The « In flight » row in `IMPLEMENTATION.md` — **written when the pull request opens**, pull
   request number first, then the version (`check-implementation-state.py` refuses a row naming
   neither).
2. The register, written **during** the wave, not at the close.
3. `REPORT.md`, in the repository beside this plan, before the archive move takes the folder —
   **`git add -f`, then `git ls-files` as the check** (B-251).
4. The device-only protocols, **written and dated**, never claimed as passed: the interaction budget
   (`MODEL.md` § 3.1 — a protocol, not a gate), and whether `:active` still needs a touch listener.
5. **The recount of « guards green over what they do not read »** in `BUGS.md`, with the pull
   request or entry that establishes this wave's figure. **Zero is a real answer.**
