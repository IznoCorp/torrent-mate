# L04 — implementation plan

Design: `docs/features/maquette-l04/DESIGN.md`
Lot: `docs/reference/frontend-architecture.md` § Phase 1 → L04 · `IN PROGRESS` · _depends on L01_ · **runs alone**
<sub>« Phase 1 » there groups LOTS. The phases numbered below are this plan's own — same word, two scales.</sub>
Branch: `refactor/maquette-l04` · version 0.98.21 · squash merge, pressed manually

## Why the phases are in this order

**The lot fixes it, and the reason is that a single-shot move of 26 files is unreviewable.** The
five steps of the architecture file map onto six phases here: the guards and the record are
separated, because a guard written while the tree is still moving guards the wrong thing.

**Phase 1 lands alone because it is the only real CODE change.** Breaking two import cycles
changes what a module resolves to; everything after it changes only where a file sits. Separated,
a divergence in phase 1 has one possible cause. That is also why this lot depends on L01: without
the oracle, nothing proves the rendering survived a change that is not a move.

**Phase 2 comes before phase 3, and the measurement says so.** 15 of the 28 shared `Reference`
members are shared with `components/panel.tsx`, and 8 of them only because that one file holds two
domains. Splitting the panel first REMOVES work from the `data.ts` cut rather than adding to it;
doing it the other way round means arbitrating eight members twice.

**Phase 4 is the move proper**, and it is the phase whose whole proof is « the oracle did not
move ». No logic changes in it, by construction.

**Phase 5 installs the guards on a tree that has stopped moving.** A fan-in ceiling measured
mid-move counts importers that are about to change.

**Phase 6 is not a formality.** A lot is not finished because its code exists; it is finished when
every line of its **Done when** is true — including the two records: the grandfathered files with
their converting lot, and the measurements this wave made false.

### Two rules #477 added to the method, and they bind this wave

1. **The landed row is written when the pull request OPENS**, not after the merge — a wave edits
   `IMPLEMENTATION.md` on its own branch, so a row waiting for the merge is a row never written.
   Three consecutive waves announced themselves « in flight » after landing.
2. **Refreshing a decision's measured rationale, in the wave that made it false, is a DUTY, not an
   amendment.** L04 makes several figures in its own lot entry false — two cycles, one hub, six
   duplicate imports, the typing ratchet's « from today's zero ». Phase 6 refreshes them. What was
   DECIDED is untouched; the measurement under it belongs to whoever made it move.

## Phases

| #   | Phase                                                  | File                          | Status |
| --- | ------------------------------------------------------ | ----------------------------- | ------ |
| 1   | The two cycles break                                   | phase-01-the-two-cycles.md    | [ ]    |
| 2   | The panel splits in three                              | phase-02-the-panel-splits.md  | [ ]    |
| 3   | `data.ts` stops existing                               | phase-03-the-hub-dissolves.md | [ ]    |
| 4   | The move to the target tree                            | phase-04-the-move.md          | [ ]    |
| 5   | The seven guards bite                                  | phase-05-the-guards.md        | [ ]    |
| 6   | The ceiling list, and the figures this wave made false | phase-06-the-records.md       | [ ]    |

## ACCEPTANCE criteria

Every criterion is an executable command with a documented expected output — prose criteria are
invalid (`docs/reference/feature-lifecycle.md`). They are re-exercised in full before the squash
merge.

| ID     | Phase | Criterion                                                                                                                                                                                                                                                                                                                    |
| ------ | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | 1     | `python3 scripts/check-frontend-boundaries.py --arm cycles` reports **0 cycles** over the resolved graph of `frontend/maquette/design/src`                                                                                                                                                                                   |
| ACC-02 | 1     | `cd frontend/maquette/design && npm run typecheck` exits 0                                                                                                                                                                                                                                                                   |
| ACC-03 | 1     | `python3 frontend/maquette/oracle.py --check` reports **0 divergence** over 2 739 measurements                                                                                                                                                                                                                               |
| ACC-04 | 1     | `python3 frontend/maquette/harness/navigation.py` exits 0 — R76 still counts exactly one `navigate(` outside the engine, and it now names `go()`'s NEW home; the rule is seen RED with the rule left pointing at `shell.tsx`, then restored                                                                                  |
| ACC-05 | 2     | `python3 scripts/check-frontend-boundaries.py --arm layering` reports **0** imports from `ui/` into `features/` or `routes/`                                                                                                                                                                                                 |
| ACC-06 | 2     | The panel rule (`frontend/maquette/harness/panel.py`) exits 0, and reports every declared block kind registered before the first panel opens; it is seen RED with one registration removed, naming the missing kind, then restored                                                                                           |
| ACC-07 | 2     | `python3 frontend/maquette/oracle.py --check` reports **0 divergence**                                                                                                                                                                                                                                                       |
| ACC-08 | 3     | `test ! -f frontend/maquette/design/src/data.ts` exits 0                                                                                                                                                                                                                                                                     |
| ACC-09 | 3     | `python3 scripts/check-frontend-boundaries.py --arm duplicate-import` reports **0** — the 6 files that imported `data` twice are gone with it                                                                                                                                                                                |
| ACC-10 | 3     | `cd frontend/maquette/design && npm run typecheck` exits 0 — a `Reference` member dropped in the cut fails at its reading site, which is what makes this criterion a proof and not a formality                                                                                                                               |
| ACC-11 | 3     | `python3 frontend/maquette/oracle.py --check` reports **0 divergence**                                                                                                                                                                                                                                                       |
| ACC-12 | 4     | `python3 scripts/check-frontend-boundaries.py --arm tree` reports every file under `design/src` inside a declared bucket, and **0** strays                                                                                                                                                                                   |
| ACC-13 | 4     | `python3 scripts/check-frontend-boundaries.py --arm one-address` reports **0** files under `routes/` declaring more than one `path:`, and **0** address declared twice                                                                                                                                                       |
| ACC-14 | 4     | `python3 frontend/maquette/oracle.py --check` reports **0 divergence** — this is the phase's whole proof: a move changed nothing                                                                                                                                                                                             |
| ACC-15 | 4     | `python3 scripts/check-no-french.py` exits 0                                                                                                                                                                                                                                                                                 |
| ACC-16 | 4     | `python3 scripts/check-markup-contracts.py` exits 0                                                                                                                                                                                                                                                                          |
| ACC-17 | 5     | `python3 scripts/check-frontend-boundaries.py` exits 0 with all seven arms run, and prints the count each arm derived                                                                                                                                                                                                        |
| ACC-18 | 5     | The mutation record shows **each of the seven arms seen RED** on its own deliberate violation, **naming the right defect**, then restored — one recorded mutation per arm, no arm exempted                                                                                                                                   |
| ACC-19 | 5     | `python3 scripts/check-frontend-boundaries.py --arm fan-in` refuses a module outside `ui/`/`lib/` imported by more than **4** features, and reports the actual maximum on the shipped tree                                                                                                                                   |
| ACC-20 | 5     | `grep -c 'check-frontend-boundaries.py' Makefile` returns ≥ 1 and `grep -c 'check-frontend-boundaries.py' .github/workflows/ci.yml` returns ≥ 1                                                                                                                                                                              |
| ACC-21 | 6     | `python3 scripts/check-frontend-boundaries.py --arm size --list-grandfathered` prints every file ≥ 400 non-blank lines under `design/src` **with the lot that converts it**, and the list is the one committed — regenerated, never hand-maintained                                                                          |
| ACC-22 | 6     | `python3 scripts/check-frontend-boundaries.py --arm typing` reports **0** `any` / `as any` / `@ts-ignore` / `@ts-expect-error`, hard zero                                                                                                                                                                                    |
| ACC-23 | 6     | `frontend/maquette/harness/run.sh` — the FULL suite, not `--contracts` — exits 0, and `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` reports **no changed count** on any rule the baseline already held. The criterion is the CONTENT of the report, read, not the exit code |
| ACC-24 | 6     | `make maquette-oracle` reports **0 divergence** over 2 739 measurements                                                                                                                                                                                                                                                      |
| ACC-25 | 6     | `make lint` exits 0 · `make test` reports 0 failed and **0 error** · `make check` exits 0                                                                                                                                                                                                                                    |
| ACC-26 | 6     | `git grep -n 'Two import cycles' docs/reference/frontend-architecture.md` returns nothing — L04's measured-defects table states what is true after the wave, per § 7.1's refresh duty                                                                                                                                        |
| ACC-27 | 6     | `IMPLEMENTATION.md` names L04 with its PR number, and the row was written at PR-open — verifiable in the branch history: `git log --oneline -S'#<PR>' -- IMPLEMENTATION.md` shows a commit predating the merge                                                                                                               |

**ACC-24 and ACC-23 can only be exercised on this machine.** The oracle's measurements are bound
to the machine that took them and `--check` refuses to compare across a platform mismatch, so it
is never wired into CI. The wave is certified here.

## What this plan does NOT do

Named so that « not done » is on the record rather than an oversight (DESIGN § 6):

- **Bundle splitting** — it belongs to L12, it changes loading behaviour, and nothing here may
  change anything observable. The measured `0 lazy()` / `0 dynamic import()` is recorded, not
  fixed.
- **A unit-test runner** — arbitrated by the operator on 2026-08-22. The debt is recorded against
  **L09**, which brings the mock layer a non-vacuous test must rest on.
- **The production frontend** — arbitrated by the operator: the module ceiling covers the maquette
  only. Production is archived at switchover.
- **The harness's 52 flat `.py` files** — named in the lot as a known defect deliberately left
  alone; it waits for a stronger reason than tidiness.
- **B-036** (two French state ids, and the missing arm) and **B-040** (names in files no arm
  reads) — open, each owed its own wave, not taken in passing.
- **An audit of this lot** — that office is the steward's, in a separate session
  (`docs/reference/frontend-steward.md`). An implementer auditing their own lot compares their
  intention with their work.
