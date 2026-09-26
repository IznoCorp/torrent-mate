# Phase 3 — The two surviving states take their names

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n 'arr-resolution\|arr-decision' -- 'frontend/maquette/harness/*.py' | wc -l` → **14 lines in
  10 files**: `actions.py`, `attrs.py`, `bugs.py`, `cards.py`, `decision.py`, `hiding.py`, `load_more_scale.py`,
  `message_over_layers.py`, `persistence.py`, `resolution_card.py`. `harness/states/arrivals.ts` declares both (2 of
  its 8). The recorded oracle holds both by id (`python3 -c "import json;print([k for k in json.load(open('frontend/maquette/oracle-reference.json'))['measurements'] if k.startswith('arr-')])"`
  → the 8 `arr-*` ids). The three accessibility files hold the debts by id:
  `git grep -n 'arr-decision\|arr-resolution' -- frontend/maquette/a11y-contrast.json frontend/maquette/a11y-debt.json frontend/maquette/a11y-light-debt.json`
  → 2 entries in each of the three. `actions.py`, `cards.py` and `decision.py` ALSO read `arr-idle` / `arr-loaded`: **they
  are touched again in phase 22** and that is stated rather than hidden.
- **Points ≈ 8.** Two states renamed 2; the recorded debts by id in three files 1; ten rule files whose change is one
  id swapped ½ each = 5.

A rename is one kind of change. **Ids are renamed through `scripts/rename-identifiers.py`** — never by hand and never
by an ad-hoc regex (`CLAUDE.md` § Code Conventions). A state id is a string VALUE, so the run is a `--values` run and its
read-back check is skipped: **the oracle outside the tool is the diff re-read and the harness rule suite re-run.**

## Red today

**No rule in this phase, and that is stated rather than skipped.** A rename is not a behaviour. What holds it is the ten
re-aimed rules replayed unchanged: `python3 scripts/harness-hold-counts.py --compare` with **`failed` read FIRST**
(B-291) and **zero movement in any hold count**; `harness/states.py` asserts both states still render content at
390 px.

## Move

1. `harness/states/tunnel.ts` — the states' home for this lot (DESIGN § 4), composed by `harness/index.ts`. It declares
   `acq-resolution-none` (was `arr-resolution`) and `acq-resolution-tie` (was `arr-decision`); their two entries leave
   `harness/states/arrivals.ts`.
2. Re-aim the ten rule files (mechanical).
3. Re-key the two records in `oracle-reference.json` and the debts in the three accessibility files **by moving the
   entries under the new id — a rename, not a re-measure**. A debt is never re-recorded lower.

## Mutation

None (no rule). A dropped rename is caught by the ten rules' own holds.

## Register

—

## Oracle: states that diverge, declared by name

**None.** The re-keyed records are compared as they are; any divergence on either is a finding (nothing was redrawn).

## Gate

Per INDEX « Gates », plus `--a11y` over the two states (their recorded debts must be found under the new ids).

## Commit

`refactor(maquette-l22): the two resolution states are named for the page that owns them`
