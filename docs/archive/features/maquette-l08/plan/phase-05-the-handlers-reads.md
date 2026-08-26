# Phase 5 — The handlers, reads

## Scope

One handler per read operation the contract declares. Each returns a payload assembled from seeds
and from nothing else.

## The rule that makes the guard possible

**A handler contains no data literal.** Its payload traces to a seed import; its own code is
matching, filtering, paging and shaping. A number in a handler is a page size or a status code,
declared as a named constant, never a value the interface will display.

That is what ACC-16's arm reads, and it is what makes « seeded from the fixture » checkable at all:
without it a handler could return a hand-typed object and every other arm would stay green.

## The derived responses

The engine's `derived*()` arrows answer per scenario — `real` returns one set, `loaded` another.
They are not literals, so they are not seeds; the handler declares the two sets by naming the seed
families each scenario composes, and R85 holds that both are reachable and deterministic.

## Done when

- Every read operation in the contract has a handler.
- No handler holds a data literal.
- The same request twice returns byte-identical bodies.
- ACC-01, ACC-02, ACC-03 green.
