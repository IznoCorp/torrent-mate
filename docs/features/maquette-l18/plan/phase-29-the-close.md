# Phase 29 — The close

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `grep -n '^| B-143' BUGS.md` → row 205, `open`, `by audit` (closed here by the operator's rule of the register).
- `grep -n "A medium in trouble" frontend/maquette/README.md` → the cut table (L22's close rewrites it); `sed -n 225,246p docs/reference/frame-model.md` → Part 9 (« the entry ») says the gate is the frame's and that rights are a feature's to read — **which this lot preserves**; the frame model's rows that name the bar are re-read at the opening (`grep -n -i "bar" docs/reference/frame-model.md`).
- `python3 scripts/check-intent-map.py` and `python3 scripts/check-docs-cited-paths.py` read by OUTPUT, not by exit code (B-346).
- **Points ≈ 9.** the register: B-143 closed, and the rows the lot found (1) + `frontend/maquette/README.md`: the gate's sentence and the cut table if it names accounts (2) + `docs/reference/frame-model.md`: Part 9 and the bar's composition rows (2) + the map's three proposed rows reported to the operator (DOIT-12, NE-DOIT-PAS-7, NE-DOIT-PAS-3) (1) + `IMPLEMENTATION.md`: the state row (1) + the demands' final `compare-contracts.py --check` (1) + the report, and the debts named: deleting or disabling an account, an approval flow, the media sheet's trace (1).

**The close re-reads the map and the register rather than trusting what the phases claimed.** It runs the full gate once (INDEX « Gates »), writes the report, and names the debts DESIGN § 7.1 lists — never silently dropped.

## Red today

—

## Move

The documents.

## Mutation

—

## Register

B-143 closed by the close.

## Oracle: states that diverge, declared by name

—

## Gate

Per INDEX « Gates ».

## Commit

`docs(maquette-l18): the close — B-143, the README, the frame model, the debts`
