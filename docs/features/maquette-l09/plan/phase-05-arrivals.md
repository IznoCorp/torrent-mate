# Phase 5 — Arrivées, and its resolution screen

**First surface, and it is chosen by L07's order rather than by convenience.**

**Its families** (`features/arrivals/reference.ts`): `PIPELINE`, `PENDING_DECISIONS`,
`DECISIONS_REGLEES`. The label and tone maps beside them — `REASON_LABEL`, `REASON_TONE`,
`REASON_DETAIL`, `DECISION_STATE`, `DECISION_STATE_DETAIL`, `VIA_LABEL` — are classified
`interface` in the register: they are French the reader sees, they **move to `i18n/fr.json`** and
never onto the network. L08's D-L08-6 says so in as many words.

**Its mutations** are the lot's first, and they are the ones the constitution cares most about: a
decision settled, a pipeline verb. DOIT-4 — a legitimate action is never refused, it is queued
and visibly so — is what the optimistic path must render.

**The trap here, and it is measured**: `arrivals.py` holds R66 against the operator's live
`library.db`, so it runs in the full suite and never in `--contracts` (B-049). A red `arrivals.py`
between phases says nothing about the change under test.

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
