# Phase 6 — Médiathèque

**L07 split this over two phases** (the card, then tiles/selection/filters). Here it is one:
the card is a component, not a data source, and the whole surface reads one set of queries.
Said explicitly so the order is seen to be kept rather than quietly changed.

**Its families**: `CATS`, `RECENT`, `INCOMPLETE`, `LIBRARY`, `LIB_TOTAL`, `SYNOPSIS`. `LIB_PAGE`
and `TRIS` are `interface` — a page size and a set of sort names — and stay.

**What this surface really tests**: paging. `LibraryList` currently owns a hand-written infinite
scroll with a simulated failure, a stale-load guard keyed on the store's version, and a page
counter (`libCount`) living in the UI store. **Four of the eleven server-state keys are here** —
`libCount`, `libErr`, `libLoading`, `libFailedOnce` — and all four leave in this phase. That is
invariant 4's largest single fall, and the arm must show it.

**The simulated failure is not deleted, it is MOVED**: it becomes a scenario the layer serves, so
the named error state keeps rendering what it rendered.

**What must not move**: `libRowHTML` and `tileHTML` are transplanted verbatim — they carry the
`data-*` the document-level delegation reads. And `paintSelBar()` stays the fragment's, repainted
after render exactly where `fillLib` repainted it.

## What every surface phase carries

Four things, and none is optional:

1. **Its reads go through the cache**, never through `window.__referentiel`.
2. **Its mutations carry an optimistic path and a rollback**, or a written reason why one cannot
   exist. An action answers the finger before the network does — this is the largest single lever
   on how native the interface feels, and no animation later repairs a tap that waits for a round
   trip (DOIT-4).
3. **Its share of the fixture dies in the same commit** (D5). The engine is touched only by
   subtraction; its part is removed, never rewritten.
4. **A rule that bites**, mutation-tested: break the behaviour on purpose, see the rule fall and
   name the right defect, restore.

## The gate

`frontend/maquette/harness/run.sh --contracts`, then `--oracle`. Run **after** the phase, not
after a commit inside it.

## Done when

- `grep -rn "__referentiel" <this surface's files>` → 0.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`, or every divergence named,
  understood and accepted with its reason (D-L09-7). Never « the data changed ».
- The invariant-4 arm's count has fallen by this surface's share, and the arm says so.
