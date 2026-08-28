# Phase 3 — The query client, and the settle PROVED

**This phase is the lot's hinge.** Everything after it rests on the oracle measuring a wired
surface at rest. That has never been exercised.

## What lands

- `@tanstack/react-query` (D-L09-1).
- `lib/query-client.ts` — the client and its cache policy. **In `lib/`, not under a feature**
  (invariant 10, D-L09-4): it is the application's shape, and the surface that motivated it is
  not its subject.
- The provider in `app/`, composed in the router tree — never in a page.
- The typed read and mutate helpers, generated against `mocks/contract-types.d.ts`, so an
  operationId that does not exist is a compile error.

## The cache policy, decided here and not per surface

Written down in one file so twelve surfaces cannot each invent one:

- **Fresh until a mutation says otherwise** — invalidation by mutation, not by a clock. The live
  relay (L10) is what will drive invalidation for real, and a staleness duration picked now would
  be a number nobody could defend later.
- **No retry.** A retry hides a failure the interface is required to show (NE-DOIT-PAS-5), and it
  would make the scenario surface's injected failure arrive three times late.
- **No refresh on window focus.** The oracle drives 83 states in one context; a focus-triggered
  refresh would put a request in flight during a measurement.

## THE PROOF, and it is the phase's real content

`window.__mocks.quiet()` is read by `oracle.py`'s settle today. **It resolves immediately, because
nothing asks the layer for anything.**

**THIS PLAN SAID « wire one read from the cheapest surface » AND THAT WAS WRONG, corrected here
rather than quietly done differently.** Wiring a surface out of order to prove an instrument
breaks the one rule this lot's proof rests on — surfaces are walked in the order L07 fixed — and
it would have made the first surface's own oracle reading meaningless, because that surface would
already have been half-converted by the phase that measured it.

**What is proved here instead is the SIGNAL, exercised against real requests** — `harness/settle.py`
(R89), six holds:

1. `inFlight()` counts a request really held back.
2. `quiet()` loses a race against a timer shorter than the injected latency — judged by which
   settles FIRST, never by a stopwatch, because a duration has one answer on an idle machine and
   another on a loaded one.
3. It resolves once the request lands, and the count is back to zero.
4. **The waterfall**: read → render → read again. `quiet()` must wait for a request the first one
   had not issued yet.
5. The budget is named: `oracle.py` races the signal against **2 000 ms** and goes on without it,
   so a request slower than that is measured in flight, by design.

**What is deferred, and it is written here rather than assumed**: whether the ORACLE calls the
signal end to end. That is phase 5's, at the first real surface, using the lever `oracle.py`
already publishes for it — `TM_ORACLE_NO_SETTLE=1`. Measure the wired surface with the settle and
without it; without it the oracle must read the skeleton and **diverge**. **If it does not, the
settle is doing nothing and this lot stops there** (§ 7.1).

### What hold 4 cost, because it is this repository's own failure mode

The waterfall hold was written first as « read `inFlight()` after quiet, expect 0 ». **Both
behaviours produce 0**: released a task later, the second request is already counted so quiet
waits for it; released inside the settlement, quiet answers before the second request exists. The
mutation that removes the macrotask left the hold GREEN. What distinguishes them is ORDER — did
the second request FINISH before quiet answered — and the hold reads that now. Counted in
`BUGS.md` § Guards green over what they do not read.

## The two arms, written here and driven down later

- **Invariant 4** — a count of store keys that name server state. It starts at **11** and is
  refused **upward**. It cannot be pre-satisfied; it has eleven real things to remove. It must
  REFUSE a computed key rather than skip one, and print how many engine writes it skipped.
- **Invariant 5** — no data request inside a `useEffect`. It is at zero the day it is written,
  which is B-075's shape, so it **prints its corpus size and refuses a corpus below a declared
  floor** (3 today).

## What the client cost, measured

**+24 784 bytes**, unminified: **2 813 256** at the phase-2 commit against **2 838 040** with the
client and its provider wired.

<sub>`cd frontend/maquette/design && npm run build && wc -c dist/vite/*.js`, run on each side of the change</sub>

## The two arms — and the shape of each is the point

`scripts/check-state-ownership.py`, its own file rather than a ninth arm of
`check-frontend-boundaries.py`: that guard answers « which module may import which » and these
answer « where does a value live », and it is 793 lines against a soft ceiling of 800.

- **`server-state`** starts at **11** and is refused upward, so it cannot be pre-satisfied. It
  prints the two shares apart — 4 written by a component, 10 by the engine over 38 write sites —
  and holds a **second ceiling on the component share**, because the union alone cannot see a
  component newly copying a key the engine already writes.
- **`effect-fetch`** is at zero the day it is written, which IS B-075's shape, so it prints its
  corpus (**3** `useEffect` call sites) and refuses a corpus below that floor.

**Four mutations, each seen red and restored.** The macrotask removed from `releaseWaiters`
(hold 4, above). A component writing `pipe` — a key the engine already writes — falls the
component-share ceiling where the union stayed at 11. A key on neither list is refused by name. And
the corpus narrowed to five buckets falls the floor, printing « 0 read against a floor of 3 ».

⚠ **One restoration silently did not happen**: `git checkout --` on a file git does not track yet
is a no-op, and `|| true` swallowed the error. Caught by re-reading the file rather than by
trusting the command — « a failed command is not a no-op », from the other end.

## Done when

- The bundle figure is MEASURED and written above — done.
- Both arms run in `run.sh`'s repository-guard tier and in `make check` — done.
- R89 runs in the contracts tier, and its mutation was seen red and restored — done.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`, before and after.
