# Phase 12 — The harness consolidation

Added by the orchestrator, 2026-09-30, after phase 7 (order 52): the lot's harness budget read **1.09** by the
orchestrator (1.27–1.38 by the branch's own reading at the midpoint, harness lines added against design lines
added, `git diff --numstat origin/main...HEAD`) against a ceiling of **0.6**. A CONVERSION phase: nothing observable
changes.

## What changes

1. **The harness lines this lot added are brought under the budget**, target **≤ 0.60** measured at this phase's
   gate: a check on a surface that already has a rule becomes a HOLD in that rule's file (order 52) — the lot's new
   rules (`one_tab_bar.py`, `segmented_choice.py`, `primary_action.py`, `one_switch.py`, `back_control.py`,
   `on_off.py`, `state_words.py`, `empty_place.py`, and the rest born here) merged where a rule already reads their
   surface, their shared reading factored once in `harness/common.py` rather than copied per file.
2. **No hold is lost**: every merged hold is listed before and after by name (`scripts/harness-hold-counts.py`),
   and each still FALLS under the mutation that proved it when it was born (the ledger names them).

## Acceptance

- The budget, measured by the command above and written in the RESUME: ≤ 0.60.
- The oracle ALONE: « no divergence » (a conversion moves no rendering — any divergence is STOP A).
- `run.sh --rules` on every merged rule, green; each born mutation replayed through `scripts/mutate.sh`, each
  falling by its name.
- The static guards; `check-maquette-comments.py --record` for the files that moved.

## Commit

`refactor(maquette-conformity): the harness consolidated — the lot's rules as holds of the rules that read their surfaces`
