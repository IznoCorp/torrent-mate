# Phase 4 — The runs list becomes `FactRows` (D.1 #13)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "runRow|runHead|runLine" -g '*.ts' -g '*.tsx' frontend/maquette/design/src` → **3** variants
  (`features/system/variants.ts:11–19`) used at `features/system/run-list.tsx:167–177`; `rg -l "runs/row|runs/outcome"
  -g '*.py' frontend/maquette/harness` → `run_history.py`, `no_sentence_to_arrivals.py`, `back.py` (readers of the
  parts — the parts stay).
- **Points ≈ 9.** `run-list.tsx` ≈ 20 lines edited (4); the three variants removed (1); `FactRows`' `target` carries
  `{ run }` (1); the outcome as a chip at the row's end (`success` / `danger` / `info` / `neutral`) (2); the rule's
  `runs-list` hold re-aimed green (1).

## Red today

R-conformity-a on `runs-list` (phase 1's first red).

## Move

Each run is a `FactRows` row — label « when · trigger », value the outcome CHIP, sub-line « what it did »,
`target: { run: runUid }`, `part: "runs/row"` — inside the page's `factList`. The UA button border goes with the
`<button>` it was on. `runs/outcome` stays a part (the chip carries it).

## The one visible change

The list's right edge is painted, and the outcome reads as a chip rather than as plain text in the head — the
report's item: « the responsive rule goes green on `runs-list` ».

## Mutation

Restore `runRow` on the row → R-conformity-a falls on `runs-list` by name.

## Oracle: states that diverge, declared by name

Every Système state that draws the runs list (built by script: page `sys`), and `run-detail`'s parent if drawn.

## Commit

`refactor(maquette-conformity): the runs list is fact rows with the outcome chip — its right edge painted`
