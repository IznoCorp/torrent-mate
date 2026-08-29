# Phase 2 — `quiet()` learns about the stream

**This is the first lot where `quiet()` has to mean something.** It resolved immediately for its
whole life because nothing fetched, and has counted `fetch` since L08. A delivery goes nowhere
near `fetch`.

## Steps

1. `mocks/index.ts` — count a delivery from the moment it is dispatched until the fan-out it
   caused has been ISSUED. The gap this closes is the one `releaseWaiters()` already documents for
   a read-render-read waterfall: `inFlight` is 0 between the delivery and the refetch it provokes,
   and `quiet()` would resolve over a world about to change.
2. `emit()` returns a promise that settles once that fan-out has been issued, so a rule can await
   an event's consequences without a sleep.
3. Keep the macrotask release. Do not replace it with a microtask: waiters released inside a
   settlement run before the application's own continuation, which is the defect the comment in
   `releaseWaiters()` records.

## The rule

**R89 (`harness/settle.py`) — extended, not replaced.** New holds:

- `quiet()` does not resolve while a delivery is dispatched and its fan-out not yet issued.
- `quiet()` resolves once it has, and the counter is back to zero.
- A burst of N events leaves the counter at zero, not at N − 1 or −1.

R89 is already on the `--contracts` tier and stays there: a phase that breaks the settle must be
the phase that hears about it.

**Mutation**: count the delivery but not its fan-out. The hold must fall on the window, naming it
— a signal that reports quiet while a refetch is about to be issued.

## The trap this phase is walking into

An instrument that starts meaning something is an instrument that can start being wrong, and R89
went green over the exact defect it names once already (B-105). So the mutation here is run
BEFORE the extension is trusted by phase 3, and the result is written in the phase's commit body.
