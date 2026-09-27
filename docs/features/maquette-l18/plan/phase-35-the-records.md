# Phase 35 — The records of the lot

**Amended 2026-09-27** (renumbered from the first drawing's phase 28): the fixture register's `x-unseeded` rows
now include `seeds/roles.json` (phase 27) alongside `seeds/accounts.json` (phase 2). Re-estimated at **10**
(unchanged).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `grep -c '"account/body"' frontend/maquette/oracle-reference.json` → 114 records carry the region; `python3 -c` over the states directory → **114** states on this head (L22 and L16, L17 add theirs before this lot opens).
- `frontend/maquette/a11y-debt.json` (`profile` at line 1841), `a11y-light-debt.json` (line 358), `a11y-contrast.json` (line 76): the accessibility records the new states extend; **a debt is never re-recorded lower**.
- `python3 scripts/check-mock-seeds.py` → the fixture register's `provenance` arm holds the six accounts; `frontend/maquette/hold-counts-baseline.json` (`taken_on` 2026-09-16, 148 rules) is re-recorded with `python3 scripts/harness-hold-counts.py --compare` reading **`failed` FIRST** (B-291).
- **Points ≈ 10.** the oracle records the new states, and the reference is re-recorded once (2) + the accessibility records for the new states (three files) (3) + the fixture register reconciled with the six accounts and the invented requests (1) + `hold-counts-baseline.json` re-recorded, movements written down (1) + the sweep for dead keys and comments naming the removed place or the dead flag (2) + `comment-references-baseline.json`, if the ratchet moved (1).

**The memory the tooling keeps of a surface is not the surface** (L22 phase 26's argument). A ratchet that does not move after a removal is a guard reading nothing: `screens.accountPage.others*` and `SETTINGS_STATE.readOnly` are gone, and the records must say so.

## Red today

—

## Move

The records, re-recorded once, each movement written down.

## Mutation

—

## Register

—

## Oracle: states that diverge, declared by name

**The oracle re-records; it does not diverge on a state that existed unless a phase named it** (§ 4.1). Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`chore(maquette-l18): the records of the lot — regions, oracle, accessibility, baselines`
