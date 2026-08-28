# Phase 8 — The guards

`scripts/check-live-relay.py`. Every arm says what it does **NOT** read before it says what it
does — the form `check-mock-seeds.py` and `check-state-ownership.py` both use, and the form B-085
exists because of.

## The arms

1. **`no-polling`** — refuses `refetchInterval` and `setInterval` under `design/src`, outside the
   dying engine (whose only one is a long-press `setTimeout` at `legacy.js:8324` with its
   `clearTimeout` at 8353 — a delay, not a poll).
   **It starts at zero, which is the dangerous shape**, so it PRINTS THE CORPUS IT READ and
   refuses a corpus below a declared floor. An arm that found no files reports the same word as an
   arm that read them all. This is `check-state-ownership.py`'s `effect-fetch` arm's own reasoning,
   applied to the same danger.
2. **`named-invalidation`** — refuses `invalidateQueries()` with no `queryKey`. One call is
   indistinguishable from a reload and would destroy what L09 built.
3. **`map-completeness`** — every event type the mock stream can emit is mapped or explicitly
   listed as refreshing nothing. Cross-checked against the 40 classes the backend emits, so the
   list cannot quietly stop covering its subject when the backend grows one.

## Where it runs

`make check`, and the `--contracts` tier's cheap-guard list beside the others — it reads what a
maquette phase edits, in seconds.

## Mutations

One per arm, each seen red and restored: add a `refetchInterval` to a surface; add a bare
`invalidateQueries()`; drop one type from the map and from the unhandled list. Each hold must name
its own defect, not a generic failure.

**The corpus floor is mutation-tested too**: point the arm at an empty directory and confirm it
FAILS rather than reporting no violation. That is the one mutation this repository has skipped
most often, and it is the one that produced B-085's count of 40.
