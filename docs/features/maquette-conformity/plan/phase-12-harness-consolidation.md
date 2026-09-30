# Phase 12 — The harness consolidation

Added by the orchestrator, 2026-09-30, after phase 7 (order 52): the lot's harness budget is over its ceiling of
**0.6**. A CONVERSION phase: nothing observable changes.

**The budget's definition** (the orchestrator's ruling, 2026-09-30 — `implementer-office.md` leaves it open):
harness = lines added under `frontend/maquette/harness/**` (rules, drivers, lib); product = lines added under
`frontend/maquette/design/src/**` minus test files (`*.test.*`); recorded baselines (`oracle-reference.json`, the
corpus and record files) and docs count on neither side. Measured ONCE, at this phase's gate, on the final head:

```sh
git diff --numstat origin/main...HEAD | awk '
  $3 ~ /^frontend\/maquette\/harness\// {harness += $1}
  $3 ~ /^frontend\/maquette\/design\/src\// && $3 !~ /\.test\./ {product += $1}
  END {printf "harness +%d, product +%d, budget %.2f\n", harness, product, harness / product}'
```

**The orchestrator's ruling on the target (2026-09-30, after the predecessor's inventory — ≈ 1 560 harness lines
added, the small rules' merge saving ≈ 40–50 %):** (a). The phase folds the 13 small rules into holds of existing
rules and factors the page read, the state loop and the journal into `harness/common.py`, as far as a conversion
goes, every merged hold still falling under its mutation; then it measures ONCE with the definition above and
ACCEPTS the figure reached, said as it is, the residual named as a debt to the consolidation of order 64 (the L16
precedent, 0.602). (b) — counting `responsive.py` outside the lot — is refused: redefining the budget after reading
the figure would be gaming it. No hold is removed.

## What changes

1. **The harness lines this lot added are brought under the budget**, target **≤ 0.60** measured at this phase's
   gate: a check on a surface that already has a rule becomes a HOLD in that rule's file (order 52) — the lot's new
   rules (`one_tab_bar.py`, `segmented_choice.py`, `primary_action.py`, `one_switch.py`, `back_control.py`,
   `on_off.py`, `state_words.py`, `empty_place.py`, and the rest born here) merged where a rule already reads their
   surface, their shared reading factored once in `harness/common.py` rather than copied per file.
2. **No hold is lost**: every merged hold is listed before and after by name (`scripts/harness-hold-counts.py`),
   and each still FALLS under the mutation that proved it when it was born (the ledger names them).

## Acceptance

- The budget, measured once by the command above on the final head and written in the RESUME: ≤ 0.60.
- The oracle ALONE: « no divergence » (a conversion moves no rendering — any divergence is STOP A).
- `run.sh --rules` on every merged rule, green; each born mutation replayed through `scripts/mutate.sh`, each
  falling by its name.
- The static guards; `check-maquette-comments.py --record` for the files that moved.

## Commit

`refactor(maquette-conformity): the harness consolidated — the lot's rules as holds of the rules that read their surfaces`
