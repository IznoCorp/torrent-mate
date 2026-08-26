# Phase 8 — Acquisition — the add screen, releases, quality

**Its families**: `SEARCH`, `RELEASES`, `NOTFOUND`, `NOTFOUND_REAL`. `RESOLUTIONS` and `AUDIOS`
are the releases surface's own vocabulary.

**Two more server-state keys leave**: `added`, `notFound`.

**DOIT-7 is what this surface owes**: never a dead end. Unidentified goes to candidates; zero
candidates goes to a pre-filled manual search. The loading and error primitives from phase 4 are
what make that true rather than asserted, and the empty state here is the one that must offer a
door rather than a blank.

**B-022 is closed** (« Voir mes suivis » was inert) — the wiring must not reopen it, and the
existing hold is what says so.

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
