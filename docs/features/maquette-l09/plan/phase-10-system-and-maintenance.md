# Phase 10 — Système, and Maintenance

**Its families**: `SERVICES`, `SCHEDULERS`, `EXECUTIONS`, `DISKS`, `INDEX`, `DEPENDENCIES`,
`ERRORS`, `MAINT_ACTIONS`, `JOURNAL`, `BLOCKED`. `SERVICES_PANNE`, `SCHEDULERS_DOWN`,
`MAINT_TOPICS`, `RISQUES` are `interface`.

**One more server-state key leaves**: `pipe`.

**This is where D-L08-5's cost is most visible.** `DISKS` holds
`« 1,8 To libres · 15 To · rempli à 88 % »` as one pre-formatted string, and `SERVICES` holds
`« depuis ce matin 09 h 36 »`. They are carried VERBATIM and the underlying facts are recorded as
demands — decomposing them here would forfeit the zero-divergence proof, which is exactly the
trade D7 already arbitrated. This phase adds no new demand of its own beyond what
`compare-contracts.py` already computes.

**A maintenance action is destructive**, and NE-DOIT-PAS-6 governs it: explicit confirmation.
An optimistic path on a destructive action is the one place a rollback is not enough, and the
written reason for having none goes here rather than in a commit message.

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
