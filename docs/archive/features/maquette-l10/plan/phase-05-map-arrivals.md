# Phase 5 — The map: Arrivées and the pipeline

The first phase where a cache entry moves. Everything before it dispatched into an empty table, so
any movement here is attributable to here.

## Steps

1. `features/arrivals/live.ts` — the feature's own table, `{types, keys}`, with the reason each
   event refreshes what it refreshes written beside it.
2. Registered through `app/live-updates.ts`. The feature is named there; its events and its keys
   are not (invariant 10).
3. Keys are PREFIXES and are chosen against `features/arrivals/queries.ts` as it stands:
   `["/api/pipeline/status"]`, `["/api/staging/media", scenario]`, `["/api/decisions/"]`.
   A prefix one element too short covers siblings nobody listed — it compiles, and its types
   agree. That is the shape L09 paid for three times.
4. Events that reach the browser and refresh nothing in this feature are **written down as
   refreshing nothing**. A decision, never an omission.

## The rule

**R91 (`harness/fanout.py`)** — the contract's first clause made measurable. For each rule: drive
a named state, snapshot every cache entry with its `dataUpdatedAt` and its invalidation state,
emit ONE event, assert the set that changed is exactly the declared set.

A too-wide invalidation and a missing one both fall out of the same comparison, which is why the
rule does not read the source: a map that reads correctly can still fan out wider than it says.

**Mutation, twice** — this rule is only honest if it catches both directions:
- widen a key by one element → the hold must fall naming the extra entries;
- delete a rule → the hold must fall naming the entry that did not refresh.
