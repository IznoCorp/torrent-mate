# Phase 7 — Acquisition — the deck and the follows

**Its families**: `FOLLOWS`, `SUGGESTIONS`, `TAKEABLE`, `INFLIGHT`, `DONE_TODAY`. `ST_TONE`,
`URGENCY`, `GROUPS` are `interface`.

**Three more server-state keys leave here**: `sugCount`, `sugGone`, `sugLoading`.

**The mutations are the interesting half**: following, unfollowing, grabbing. Each gets its
optimistic path — a follow appears the instant it is tapped — and its rollback. `grabForFollow` is
where B-091 lived (a hash field answering with a release name); the seed is repaired, and this is
the phase that reads its values rather than its types.

**B-052 and B-054 are open on this surface** (a synthesised follow panel labels a film « Série »;
`data-go="acq"` no longer forces the « now » tab). Neither is this phase's subject. If wiring
makes either reproducible or fixable at no extra cost, it is fixed with its rule and the register
says so; otherwise they stay open and this file records that they were looked at.

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
