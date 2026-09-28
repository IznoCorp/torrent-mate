# Phase 2 — The candidates screen changes hands

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n 'features/arrivals' -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine'`
  outside the feature → **6 import lines in 5 files**: `app/live-updates.ts:29`, `app/navigation.ts:37,38`,
  `app/panel-contributions.ts:32`, `app/shell.tsx:73`, `routes/resolution.tsx:14` (plus two comment mentions:
  `features/acquisition/verbs.ts:15`, `lib/live-rule.ts:8`). The four files that move, by
  `grep -cve '^[[:space:]]*$'`: `resolution-screen.tsx` 210, `resolution-cards.tsx` 242, `decision-vocabulary.ts` 81,
  `decision-vocabulary.test.ts` 51 = **584 lines**. Splits: `verbs.ts` (141) — `take`, `resolution`, `resolve`, `leave`,
  `manual` and `next` move (`pipe` stays with the page), `queries.ts` (123) — `useDecisions`,
  `installDecisionLookup`, `pendingDecisions` move, `types.ts` (31) — the four decision types move, `live.ts` (108) —
  the decisions and staging rules move (the pipeline-status rule stays until phase 36). `lib/addresses.ts:74`
  `"/resolution/$folder": "arr"` and `lib/addresses.test.ts:52` (`toBe("arr")`). Harness files that read the parent:
  `common.py`, `screen_addresses.py`, `url_state.py` (`git grep -l SCREEN_PARENTS -- 'frontend/maquette/harness/*.py'`) —
  read from the source, so re-read and not re-aimed. `features/acquisition/queries.ts` stands at 326 lines and
  `add-screen.tsx` at 382 against invariant 6's 400: **the moved code lands in NEW files** (`resolution-*.ts`,
  `decision-queries.ts`), never as a growth of those.
- **Points ≈ 13.** Four files moved 4; four splits (verbs, queries, types, live) 4; six import lines and the
  registrations they feed ≈ 1; the address parent and its test ≈ 1; the new rule with one mutation 3.
- **Found (2026-09-26).** `next` moves too although it dies in phase 14: it reads `pendingDecisions`, which moves, and
  a feature cannot import a feature (invariant 7), so leaving it behind would have made Arrivées import Acquisition.
  Its own arrivals-side hold (`arrivals.py`) does not read it.

Ownership moves; **nothing is redrawn**. The screen keeps its address, its markup, its keys (`screens.resolution`, 29)
and its verbs' names; what moves is which feature owns them, and what a cold link renders beneath it.

## Red today

**R-L22-n — the addresses** (DESIGN § 5), written FIRST, seeded into `screen_addresses.py` and `back.py` beside their
existing holds:

- `/resolution/$folder` is declared in `SCREEN_PARENTS` with `acq` as its parent;
- opening the screen from a card PUSHES — asserted on `history.length`, never on the address alone;
- a cold `/resolution/<folder>` renders **Acquisition** beneath it (the parent is rendered, not merely recorded — D1b
  rule 3).

**Red against `main`**: the parent is `arr`, so a cold link renders the Arrivées page beneath the screen.

## Move

1. Move `resolution-screen.tsx`, `resolution-cards.tsx`, `decision-vocabulary.ts` (+ its test) into
   `features/acquisition/`; split the verbs, queries, types and live rules as measured above; re-point the six import
   lines. The verbs keep their `data-*` names and their i18n keys (`verbs.arrivals.taken/resolved/left` are read from
   their new home — their keys are renamed only in phase 37, with the group).
2. `lib/addresses.ts`: `"/resolution/$folder": "acq"`; `addresses.test.ts` follows.
3. `routes/resolution.tsx` composes the screen from its new home.

## Mutation

With the commit made first, `scripts/mutate.sh` puts the parent back to `arr`. R-L22-n must fall, naming the parent.

## Register

— (B-515 and B-531 die with the page in phase 37; this phase touches none).

## Oracle: states that diverge, declared by name

**None expected.** Nothing was redrawn. `arr-resolution` and `arr-decision` are measured as they stand (they are
renamed in phase 3); **if either diverges, that is a finding and not an acceptance** — a move that alters a pixel means
the screen depended on where it lived.

## Gate

`sh scripts/heavy.sh --class browser l22 frontend/maquette/harness/run.sh --contracts`; the oracle;
`python3 scripts/check-frontend-boundaries.py`, `python3 scripts/check-live-relay.py`,
`python3 scripts/check-component-once.py` (the last one's docstring names `features/arrivals/`); the design's
`tsc -b`, `eslint`, `vitest`.

## Commit

`refactor(maquette-l22): the candidates screen and what it is built from move to Acquisition`

**Amended 2026-09-26 (L22a, at the phase):** the design tree has no eslint configuration (`npx eslint` there finds none, and neither `Makefile` nor CI runs one), so the gate is `tsc -b` + `vitest`; the move also carried `candidateCard`/`candidatePick` out of `arrivals/variants.ts`, read the number words through `t()` (a direct `fr.json` import put the dictionary at five importing features, over the fan-in ceiling of four), and struck a « 13 » out of a `check-live-relay.py` comment that the new `decision-queries.ts` made its stale-figure arm collide with.
