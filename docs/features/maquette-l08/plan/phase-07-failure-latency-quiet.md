# Phase 7 — Failure, latency, and the quiet signal

## Scope

- The scenario surface: which operations fail, with what status, and what latency each response
  is held for (D-L08-8).
- The quiet signal, and the oracle's settle consuming it (D-L08-9).

## Failure and latency

Set synchronously, in-page, before the request is made — the same way `applyState` already drives
`phase: "loading" | "error"` for the six loading states and the five error states that exist
today. A failure carries the status and the body the contract declares for it, so a surface at L09
renders the error it will really meet rather than a generic one.

Latency is a declared number, and it is deterministic: the same state driven twice waits the same
time. It is never a random jitter — a mock that varies is a mock the oracle cannot depend on, and
the Done-when asks precisely that it can.

## The quiet signal

The layer publishes a fact: no request is in flight. `oracle.py`'s settle reads it, guarded, so a
document without the mocks is unaffected.

**Its gate is explicit and it is the phase's risk.** The oracle must read `0 divergence` before
AND after. Nothing fetches today, so the signal resolves immediately and no measurement can move —
if one does, the change is reverted, the seam is left published for L09, and the fact is reported
rather than smoothed over.

**Its mutation is the proof it does something**: make a handler hang, and the settle must wait for
it rather than measuring a page mid-flight.

## Done when

- A declared failure scenario produces the declared status and body.
- A declared latency is observed, and it is the same on two runs.
- The quiet signal is false while a request is in flight and true after.
- The oracle reads 0 divergence, before and after.
- ACC-01, ACC-02, ACC-03 green.
