# Phase 8 — The close

**Owns**: the six things `INDEX.md` lists. No code moves here; a defect found here is repaired in
the phase that owns it, and the close is re-run.

## In this order

1. **The full suite**: `frontend/maquette/harness/run.sh` (no flag), announced to the steward. A
   rule that falls is re-run alone before it is read (B-277); a rule that falls alone is a defect
   of this wave, repaired in its phase.
2. **`--a11y`**: `frontend/maquette/harness/run.sh --a11y` — 0 findings, the light ceiling unmoved.
3. **`scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json`** —
   every movement written into the report: R100 rises by the (f) holds, R119 is new (the recorder
   is re-run only at the post-merge gesture, which is the step that names the squash). Read
   `failed` in the totals first.
4. **`make check`** — zero failures AND zero errors; the tree's own figure named with its condition
   (the operator's checkout carries 16 tests a clone does not).
5. **`BUGS.md`**: the « Guards green over what they do not read » row for L14 — the count of
   instruments found green over what they do not read during this wave, itemised, or **0**
   written down. The total moves by that figure.
6. **`REPORT.md`** in `docs/features/maquette-l14/`: what the wave produced (the counts before and
   after, from the commands), the two behaviour changes and their rules, the decisions the
   operator rules on (D-L14-3), the debts NOT taken and why, what the review rounds returned and
   where. Force-added; `git ls-files docs/features/maquette-l14/REPORT.md` prints it.
7. **`IMPLEMENTATION.md`**: the « In flight » row — `PR **#NNN**` first, then `version 0.98.61`;
   `python3 scripts/check-implementation-state.py` green on the branch.
8. **The pull request**: title and body in English, the constitution's §§ cited (§12, §13, §15,
   §16, DOIT-10, DOIT-11), the before/after table, D-L14-3 flagged for arbitration, the session
   link. CI green on the head sha — read the check-runs on the LOCAL sha, never `pr-checks` right
   after a push.
9. **The steward**: one message with the pull request number and the head sha. The reviewers'
   findings arrive by message; each round's blockers and majors are repaired with their mutation
   seen red, the round after reads the repairs, and the report's review section grows one
   paragraph per round. **The wave is not done until a round returns nothing.**

## Definition of done

Every line of the contract's « Done when » true, read through the commands: `--arm size` at 2,
`check-component-once.py` at 0, the oracle at zero divergence, the full suite green, the report in git, the
row written, the steward's last round empty.
