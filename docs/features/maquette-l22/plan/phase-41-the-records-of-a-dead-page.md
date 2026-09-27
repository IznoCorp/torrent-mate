# Phase 41 — The records of a dead page

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -c arrivals -- frontend/maquette/regions.json frontend/maquette/fixture-register.json frontend/maquette/hold-counts-baseline.json scripts/frame-domain-baseline.json scripts/code-abbreviations-baseline.json scripts/code-vocabulary.txt scripts/check-component-once.py`
  → `regions.json` (2 regions, `arrivals/pilot-bar`, `arrivals/body`, 5 lines), `fixture-register.json` (13 lines: « arrivals —
  what is blocked … »), `hold-counts-baseline.json` (`arrivals.py`), `frame-domain-baseline.json` (the `arrivals`
  directory name and the `arr` alias are DERIVED from the tree — the ceiling falls with them),
  `code-abbreviations-baseline.json` (`arrivals.py`: 3), `code-vocabulary.txt:85` (the word `arrivals`),
  `check-component-once.py:23` (a docstring). `oracle-reference.json`: the six `arr-*` records left after phase 3
  (`idle`, `running`, `queued`, `loaded`, `loading`, `error`). The three accessibility files carry the same six ids:
  `a11y-contrast.json:30-37`, `a11y-debt.json:699-970`, `a11y-light-debt.json:124-172`.
- **Points ≈ 10.** `regions.json` and the oracle reference 2; the three accessibility files 1; the ratchets that fall
  (`frame-domain`, `code-abbreviations`, `hold-counts`) 3 — **each falls and is re-recorded LOWER, never higher, with its
  guard's own command**; the vocabulary word and the docstring 1; the fixture register's thirteen lines re-worded to name
  their new readers 3.

Nothing here is behaviour: it is the memory the tooling keeps of a page that no longer exists, and **a ratchet that does not
fall after a deletion is a guard reading nothing**. Each figure is re-taken by the guard's own reader, not by hand.

## Red today

**No rule** — each ratchet's own guard is the check: `python3 scripts/check-frame-domain.py`,
`python3 scripts/check-code-abbreviations.py` and `python3 scripts/harness-hold-counts.py --compare` read the LOWER figures.
**The oracle reference and the three accessibility files are edited by REMOVING the six ids** — a deletion, never a
re-record: a full `oracle.py --record` or `a11y.py --record` would re-baseline every state and hide a drift — and
`oracle.py --check` reads the result.

## Move

Remove the two regions and the six records; remove the six ids from the three accessibility files; re-record the three
baselines downward; drop the vocabulary word if no name uses it any more; re-word the fixture register's « arrivals — … »
lines to the surface that reads each seed now.

## Mutation

None (no rule). A baseline left too high would be caught by its own guard's « may fall, may not rise » ratchet only
downward; the phase reports each before/after pair.

## Register

—

## Oracle: states that diverge, declared by name

The six `arr-*` records leave the reference; **nothing else may move.** Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y`; `scripts/harness-hold-counts.py --compare` with `failed` read FIRST; every ratchet's guard.

## Commit

`chore(maquette-l22): the oracle, the accessibility records and the ratchets forget the Arrivées page`
