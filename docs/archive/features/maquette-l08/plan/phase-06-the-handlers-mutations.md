# Phase 6 — The handlers, mutations

## Scope

One handler per mutation the contract declares (D-L08-3).

## What a mutation handler owes

**A mutation changes what the next read returns**, or it proves nothing: L09's optimistic paths
and rollbacks are written against a layer where following a mutation with a read shows the change.
So the layer holds an in-memory state, initialised from the seeds at install and reset by a
published call.

**And the reset is what keeps the oracle possible.** A named state that mutates and is then
measured must measure the same thing every time it is driven. The reset is part of the driving
surface `__go` already goes through, so a state is reached from a known store rather than from
whatever the previous state left.

## What is NOT here

No optimistic path, no rollback, no cache invalidation. Those live in the surface and they are
L09's. This phase delivers a layer that ANSWERS a mutation truthfully — nothing more.

## Done when

- Every mutation operation in the contract has a handler.
- A mutation followed by the matching read shows the change.
- A reset returns the layer to its seeded state, byte-identically.
- ACC-01, ACC-02, ACC-03 green.
