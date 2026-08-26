# L08 — The data contract and the mocks · plan

The design is `../DESIGN.md`; the lot's « Done when » is
`docs/reference/frontend-architecture.md` § 4 → L08. This file owns the ORDER and the
ACCEPTANCE criteria, and nothing else.

---

## The shape of the wave

**Ten phases, and the order is a dependency order rather than a convenience.**

The contract comes before the seeds because a seed is shaped by the contract it fills. The seeds
come before the handlers because a handler with no seed has to invent one — the single failure
this lot exists to prevent. The guards land WITH what they guard, never in a phase of their own
at the end: a guard written after the fact is a guard written against what exists rather than
against what was wanted, and this repository has paid for that distinction (« a rule can certify
the defect »).

The divergence register is computed LAST, because it is a diff of two documents and it is worth
nothing until both are final.

### The recipe every phase follows

1. Read the phase file. It names its scope and its definition of done.
2. Make the change.
3. **Run the phase gates** (below) — they are cheap and they are not optional.
4. **Mutation-test whatever rule the phase adds**: break the behaviour on purpose, confirm the
   rule falls AND names the right defect, restore. Commit BEFORE the mutation, so the restore is
   a `git checkout` of a known-good tree rather than a re-edit.
5. Commit, scoped `maquette-l08`.

### Three traps this wave meets by construction

- **A guard green because of what it does not read.** Answered in the design's § 3, which is
  written before the guard rather than after it, and by every arm holding a NAMED INVENTORY
  instead of a count. A floor set at today's number is satisfied the day it is written.
- **A local gate that CI cannot run.** `check-mock-seeds.py` needs `node` for the extractor and no
  browser. Its tests must be collectable without a browser (B-077), which means no
  module-level Playwright import in any test file this wave adds.
- **A seed that drifts from its source in silence.** `refresh-maquette-fixture.py` rewrites
  `FOLLOWS` from the live `acquire.db`. The correspondence arm re-extracts on every run, so a
  refresh that does not re-extract goes red — which is wanted, and is written into the guard's
  own docstring so the next reader knows why.

---

## The phases

| #   | Phase                                               | File                                               |
| --- | --------------------------------------------------- | -------------------------------------------------- |
| 1   | The extractor, and the classification of all 81     | `phase-01-the-extractor-and-the-classification.md` |
| 2   | The contract — the artefact and its generated types | `phase-02-the-contract.md`                         |
| 3   | The seeds, extracted and committed                  | `phase-03-the-seeds.md`                            |
| 4   | The seam — one `fetch`, no service worker           | `phase-04-the-seam.md`                             |
| 5   | The handlers, reads                                 | `phase-05-the-handlers-reads.md`                   |
| 6   | The handlers, mutations                             | `phase-06-the-handlers-mutations.md`               |
| 7   | Failure, latency, and the quiet signal              | `phase-07-failure-latency-quiet.md`                |
| 8   | The guards, and R85                                 | `phase-08-the-guards.md`                           |
| 9   | The divergence register, computed                   | `phase-09-the-divergence-register.md`              |
| 10  | The wave closes                                     | `phase-10-the-wave-closes.md`                      |

---

## ACCEPTANCE

Every criterion is an executable command with a documented expected output. A criterion that
cannot be run is not a criterion.

### Gates that run at the close of EVERY phase

The cadence arbitrated by the operator on 2026-08-25: the oracle, the five contract rules, and
the repository's cheap guards — all of which `run.sh --contracts` now carries.

| id     | command                                                      | expected                                                                                              |
| ------ | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| ACC-01 | `frontend/maquette/harness/run.sh --contracts` | exit 0 — 6 rules and 14 repository guards, no violation. **The guard count is read from `REPOSITORY_GUARDS` in `run.sh`, never remembered**: this wave added two |
| ACC-02 | `make maquette-oracle`                                       | `0 divergence` over 2 739 measurements. **This lot displays nothing; any divergence stops the phase** |
| ACC-03 | `cd frontend/maquette/design && npx tsc -b && npm run build` | exit 0 both. `tsc --noEmit` is not the gate                                                           |

### Gates that run at the close of the WAVE

| id     | command                                                                                        | expected                                                                  |
| ------ | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| ACC-04 | `frontend/maquette/harness/run.sh`                                                             | exit 0, 0 failed                                                          |
| ACC-05 | `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` | `unchanged` for every rule. R85's own entry is ADDED to that file by this wave — the suite is 57 rules now, and a baseline naming 56 is a baseline that has stopped describing the suite |
| ACC-06 | `make lint`                                                                                    | 0 errors                                                                  |
| ACC-07 | `make test`                                                                                    | `NNNN passed`, 0 failed **and 0 error**                                   |
| ACC-08 | `make check`                                                                                   | exit 0                                                                    |
| ACC-09 | `python3 frontend/maquette/a11y.py --check`                                                    | 0 violations                                                              |
| ACC-10 | `python3 scripts/check-no-french.py`                                                           | exit 0                                                                    |
| ACC-11 | `python3 scripts/check-code-abbreviations.py` | exit 0. **What it proves and what it does not**: no name uses one of the 56 stems on its blacklist, at an unmoved per-file baseline. It does NOT prove every name is a full word — `lib`, `cat`, `maint` and `hd` are not on that list, and the seed IMPORT bindings mirror the engine's own family names on purpose, so a reader can find the family the seed came from. The seed FILE names, which are this wave's own, are English and written out in full |

### Gates specific to this lot

| id     | command                                                                                                                                                                        | expected                                                                                                                                                                                                |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-12 | `node scripts/extract-maquette-fixtures.mjs --measure`                                                                                                                         | 77 module-level fixture families over 28 789 lines, 4 inside a named function and named, 1 inside an anonymous one counted and not inventoried |
| ACC-12b | `make check-contract-types` | exit 0. It regenerates the types and refuses any difference — the proof BEHIND the exemption the size ceiling and the vocabulary arm grant that file. **Mutation**: append a line by hand, the target exits 1 and prints it |
| ACC-13 | `python3 scripts/check-mock-seeds.py --arm classification` | exit 0; prints `81 fixture(s) in the engine, 81 in the register, 0 out of step`. The names themselves are `--list`, a different flag. **Mutations**: add a fixture family to `legacy.js` (it names it as unclassified); remove one from the register (it names it as missing); change one family's class without moving `$counts` (it prints both tallies); add a literal inside an anonymous function (it names the anonymous count) |
| ACC-14 | `python3 scripts/check-mock-seeds.py --arm correspondence`                                                                                                                     | exit 0; prints the number of families and of leaf values compared. **Mutation**: change one value in a committed seed, the arm exits 1 and names the family, the path and both values                   |
| ACC-15 | `python3 scripts/check-mock-seeds.py --arm lossless`                                                                                                                           | exit 0. **Mutation**: remove a key from a declared mapping, the arm exits 1 and names the key and the family                                                                                            |
| ACC-16 | `python3 scripts/check-mock-seeds.py --arm handlers`                                                                                                                           | exit 0. **Mutation**: put a data literal in a handler, the arm exits 1 and names the file and the line                                                                                                  |
| ACC-17 | `python3 scripts/check-mock-seeds.py --arm provenance`                                                                                                                         | exit 0. **Mutation**: add a seed file with no source family, the arm exits 1 and names it                                                                                                               |
| ACC-18 | `python3 scripts/check-frontend-boundaries.py --arm mocks`                                                                                                                     | exit 0. **Mutation**: import a seed from a feature, the arm exits 1 and names the edge                                                                                                                  |
| ACC-19 | `python3 frontend/maquette/harness/mocks.py` | exit 0, R85's 20 holds all PASS. **Mutations**: make a handler answer a fresh object per call (the determinism hold and the reset hold both fall); delete `NETWORK_QUIET` from `oracle.py` (the settle hold falls, 22 ms against the 700 ms asked) |
| ACC-19b | `python3 scripts/check-mock-seeds.py --arm handlers` | exit 0; prints the module and literal counts. **Mutations**: a display string typed into a handler (it names the string), an unnamed magic number (it names the number), the directory removed (it refuses rather than comparing nothing) |
| ACC-19c | `python3 scripts/check-mock-seeds.py --arm schema` | exit 0. **Mutation**: delete a field from a contract schema the seeds carry, the arm exits 1 and names the seed, the index and the field |
| ACC-25 | flip `__MOCKS_BUILT_IN__` to false in `vite.config.mjs`, `npm run build`, then `grep -c 'no mock route' dist/vite/*.js` and `wc -c dist/vite/*.js` | `0`, and the bundle at 1 571 705 bytes against 2 807 428 with the layer on. **Not a single command** — it edits a file and restores it — and it is kept as a criterion because what it proves has no cheaper form |
| ACC-20 | `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(d['openapi'],len(d['paths']),sum(1 for p in d['paths'].values() for m in p if m in ('get','post','put','patch','delete')),len(d['components']['schemas']))"` | `3.1.0 49 53 43` |
| ACC-21 | `python3 scripts/compare-contracts.py --check`                                                                                                                                 | exit 0 — the committed divergence register equals the computed one. **Mutation**: add an operation to the maquette contract without re-running, the check exits 1 and names it                          |
| ACC-22 | `git diff --stat origin/main -- personalscraper/` | ONE line, `__init__.py`, and nothing else. It cannot be empty: § 10-3 requires every pull request to bump the version, and the version lives in that directory. « Empty » was the criterion until the command was run |
| ACC-23 | `git diff --stat origin/main -- frontend/src/`                                                                                                                                 | EMPTY. Production is archived, not harvested (D7)                                                                                                                                                       |
| ACC-24 | `grep -rn "from \"\.\./engine\|from \"\./engine" frontend/maquette/design/src/mocks/` | no match — `mocks/` IMPORTS nothing from `engine/` (D-L08-10). It was a grep for the WORD `legacy`, which the comment explaining the rule and one seeded synopsis both contain: the check read prose where it meant to read an edge. The edge itself is held by `check-frontend-boundaries.py --arm mocks` |

### The two references

**Not expected to move, and that is the proof.** L08 displays nothing. If either reference does
move, the wave stops and reports rather than re-recording — and it could not re-record from
anywhere but the operator's machine in any case (`"platform": "Darwin/arm64"`).
