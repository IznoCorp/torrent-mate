# Phase b·11 — `legacy.js` dies

A deletion: with its last listener gone, the engine file and every instrument that reads it are deleted or re-aimed in ONE
commit (DESIGN § 3, last row). This is the LAST phase of L13b.

## The proof FIRST

- **Nothing left reads the engine.** Before deleting,
  `grep -rn "engine/legacy\|legacy\.js" frontend/maquette/design/src --include=*.ts --include=*.tsx --include=*.js` lists
  only the file itself and comments. The oracle reads zero divergence, and every rule is green.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - The four harness reads of the file are RE-AIMED, each keeping its count, said in its docstring:
    - `mocks.py`, which reads `TODAY`: it reads the mock layer's own date;
    - `said_and_done.py`, which reads `dataset.rescrape` in the engine: it reads the feature source;
    - `page_host.py:951` and `navigation.py:149`.
- **The contract's two command checks**, recorded in the report:
  1. `python3 scripts/check-frontend-boundaries.py --arm size` lists **no GRANDFATHERED** file.
  2. `grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)"` over the engine reads 0 BY CONSTRUCTION,
     because the file is gone. It is read on `frontend/maquette/design/src` with `--include=*.js`, and it prints no line.
- **`make check`** exits 0, with zero failures and zero errors.

## The move — all in ONE commit

- **The engine itself.** Delete `frontend/maquette/design/src/engine/legacy.js` and
  `frontend/maquette/design/src/engine/seams.ts`. The `engine/` directory is then empty.
- **Parsers that read the file**:
  - the extractor's `ENGINE` path in `scripts/extract-maquette-fixtures.mjs`;
  - the parser arms `classification`, `lossless` and `correspondence` of `scripts/check-mock-seeds.py`, and the engine parse
    in `scripts/build-mock-seeds.py`. Each is deleted, or takes « the engine is gone → no subject », the branch
    `scripts/check-frontend-boundaries.py`'s reference-slice arm already has (DESIGN § 5.1). The arms `schema`,
    `provenance`, `generated` and `handlers` survive.
- **State ownership.** `ENGINE_SOURCES` goes from `scripts/check-state-ownership.py`.
- **The French checks.**
  - `scripts/check-no-french.py` loses its allowed set, and its `check_unread_javascript` allow-list loses
    `engine/legacy.js`.
  - `DEBT_FILE` goes from `scripts/nofrench_lexicon.py`.
  - **The FRENCH DEBT section of `scripts/code-vocabulary.txt`** (its banner and its words, DESIGN § 3) is removed BY HAND.
    **No arm forces it**: with the file gone and the banner left, the debt arm keeps refusing those words everywhere and
    stays green, so nothing would ever say the section outlived its subject.
- **The size ledger.** The `engine/legacy.js` entry leaves `scripts/frontend_size_ledger.py`.
- **The resync tool.** `frontend/maquette/resync.py`, which reads and writes a block converted long ago, is deleted.
- **Beside the design's row, re-taken before deleting.** In `scripts/check-frontend-boundaries.py`, the `engine` bucket, the
  typing arm's engine exemption, and `engine` in `MOCKS_MAY_NOT_IMPORT`. Each loses its subject, and the phase reads each
  arm's behaviour on an absent bucket.
- **Harness publications.** Every name in `harness/publish.ts` (new file, a·2) that only the engine read goes.
- **The comment citations** of the file in `scripts/` and in the harness are rewritten to cite it by commit.

## Gate

Per INDEX « Gates ».

**Before L13b's pull request (STOP C)**: the full suite (`run.sh`, no flag) with no failure; the `--a11y` tier at 0;
`harness-hold-counts.py --compare` with `failed` read first and every movement of L13b written; `make check` at zero
failures and zero errors; `python3 scripts/check-bug-register.py` and `python3 scripts/check-intent-map.py` read by
OUTPUT. The steward is told before the full-suite run. **STOP C: the pull request.**

## Commit

`chore(maquette-l13): the engine file and every instrument that read it are deleted`

## Amended 2026-09-13 — a fan-in exemption to remove

a·2 added `features/acquisition/queries.ts` to `FAN_IN_EXEMPT` in `scripts/check-frontend-boundaries.py`,
because `engine/seams.ts` imports it. If an earlier L13b phase has not removed the entry with the engine's
last read of `followActions`/`suggestions`, this phase removes it with `engine/seams.ts`.

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** (1) the reference-slice arm of `check-frontend-boundaries.py` returns 1 on an absent engine — the arm and the `features/*/reference.ts` slices leave `ARMS` in this commit; (2) `check_unread_javascript` and `check_french_debt` hit the no-french vacuity hold with the engine gone — both arms are deleted with their `ARMS` entries, docstring headings and counter keys (`nofrench_lexicon.py`), and « no arm forces it » is corrected: an arm REFUSES it; `DEBT_FILE` leaves with `check-no-french.py`'s import; `check_arm_count` holds `CLAUDE.md`'s « fifteen arms » and the docstring count — same commit; (3) `FAN_IN_EXEMPT`'s `engine/engine-shape.ts` and `OUTSIDE_IMPORTS_ALLOWED`'s three engine entries die here; (4) the React-side support dies here (ruling 57): `engine-shape.ts` + test, `lib/engine-drawing.ts`, `__referentiel` + `reference.d.ts` + slices, `engine-data.ts`, `engine-redraw.ts` — and the twelve interface constants need HOMES first (`icons`, `EP_LABEL`, `TODAY`, `REASON_LABEL/DETAIL/TONE`, `ST_TONE`, `stLabel`, `MAINT_TOPICS`, `SERVICES_PANNE`, `AUDIOS`, `RESOLUTIONS` → a `lib/interface-constants.ts` or the one feature that reads each): this phase is CUT IN TWO commits, b·11a « the constants find homes » then b·11b « the file dies ».
