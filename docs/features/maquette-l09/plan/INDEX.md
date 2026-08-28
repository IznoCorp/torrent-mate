# L09 — implementation plan

The design is `../DESIGN.md`. This file owns the ORDER and the ACCEPTANCE criteria; each phase
file owns its own steps. `IMPLEMENTATION.md` owns the status — never this file.

## The order, and why it is this one

Phases 1–4 build the frame. Phases 5–12 walk the eight surfaces **in the order L07 fixed**, so
this pass reuses the understanding that one built. Phase 13 closes.

Nothing about a surface is decided outside the maquette; every phase lands with a rule that
bites, mutation-tested.

| # | Phase | File |
| --: | --- | --- |
| 1 | The shell splits, on five subjects | `phase-01-the-shell-splits.md` |
| 2 | The unit-test runner, and the pure functions | `phase-02-the-runner.md` |
| 3 | The query client, and the settle proved | `phase-03-the-query-client.md` |
| 4 | The state primitives | `phase-04-the-state-primitives.md` |
| 5 | Arrivées, and its resolution screen | `phase-05-arrivals.md` |
| 6 | Médiathèque | `phase-06-library.md` |
| 7 | Acquisition — the deck and the follows | `phase-07-acquisition-deck.md` |
| 8 | Acquisition — the add screen, releases, quality | `phase-08-add-and-releases.md` |
| 9 | Média — the sheet, the matrix, the popover | `phase-09-the-media-sheet.md` |
| 10 | Système, and Maintenance | `phase-10-system-and-maintenance.md` |
| 11 | Configuration, and B-090 | `phase-11-settings-and-b090.md` |
| 12 | Compte, and the install proposal | `phase-12-account-and-install.md` |
| 13 | The close | `phase-13-the-close.md` |

## The gate, per phase

Run **after** the phase, never after a commit inside it — L08-bis missed a three-command split
for exactly that reason.

```
frontend/maquette/harness/run.sh --contracts     # 6 rules + 14 repository guards, ~minutes
frontend/maquette/harness/run.sh --oracle        # the rendering did not move
```

Before the merge: `frontend/maquette/harness/run.sh` entire (55+ rules, the a11y tier and the
oracle), then `make check`.

## ACCEPTANCE

Every criterion is an executable command with a documented expected output. A prose criterion is
invalid (`docs/reference/feature-lifecycle.md`).

| ID | Command | Expected |
| --- | --- | --- |
| ACC-01 | `grep -c . frontend/maquette/design/src/app/shell.tsx` | ≤ 400 (invariant 6) |
| ACC-02 | `python3 frontend/maquette/oracle.py --check` | `no divergence`, at every phase |
| ACC-03 | `cd frontend/maquette/design && npm test -- --run` | all pass, 0 failed |
| ACC-04 | `cd frontend/maquette/design && npm test -- --run` under `xvfb`-less CI | collected without a browser (B-077) |
| ACC-05 | `python3 scripts/check-state-ownership.py --arm server-state` | union ≤ its recorded ceiling (7), and **0 written by a component** |
| ACC-06 | `python3 scripts/check-state-ownership.py --arm effect-fetch` | 0 violations, corpus size ≥ floor, printed |
| ACC-07 | `grep -c 'displayedValue' frontend/maquette/contract/openapi.json` | **2** — declared and `deprecated`, read by no surface |
| ACC-08 | `python3 scripts/compare-contracts.py --check` | exit 0, the precision demand present |
| ACC-09 | `python3 scripts/check-mock-seeds.py` | 7 arms, no violation |
| ACC-10 | `frontend/maquette/harness/run.sh` | every rule, no violation |
| ACC-11 | `make check` | exit 0, 0 failed and 0 error |
| ACC-12 | `python3 scripts/check-mock-seeds.py --arm classification` | **21** families converted, and every one of them gone from the engine |
| ACC-13 | `python3 scripts/check-module-size.py --root frontend` | no file over the hard ceiling |

ACC-05, ACC-06, ACC-07, ACC-08 and ACC-12 are the `Done when` of the lot, said as commands.

**Four of them were AMENDED after an adversarial review ran them, and the amendments are the
finding.** They are recorded here rather than quietly rewritten, because a criterion edited to
match what happened proves nothing at all:

- **ACC-05 and ACC-06 named the wrong script.** Both arms live in `check-state-ownership.py`, a
  separate file by this lot's own D-L09 decision, and `check-frontend-boundaries.py --arm
  server-state` exits with `invalid choice`. A criterion that cannot run is not a gate, and these
  two were written before the split they describe. ACC-05's expected output also said « ending at
  0 »: the union is **7**, all seven written by the DYING ENGINE, and the number that must be zero
  is the COMPONENT share — which is what the arm now prints separately and what the criterion now
  names.
- **ACC-07 expected 0 and the answer is 2, by decision.** `displayedValue` stays declared and
  `deprecated`: no surface reads it, and it is what the formatter's test asserts against. Removing
  it would leave that test with a golden written from its own output. The criterion was written
  before that decision and is corrected to it — the deprecation, not the deletion, is what this
  lot owed.
- **ACC-12 asked the wrong question.** `grep "__referentiel" … | wc -l` counts a hook that reads
  the ENGINE's reference object, which is how every engine-drawn surface still gets its markup —
  it is not « a surface reading a fixture », and it cannot reach 0 while the engine draws
  anything. It is 20 today and would still be 20 with every family converted. What this lot owes
  is that a CONVERTED family is gone from the engine, and that is what the classification arm
  reads, family by family.

**What is NOT amended, and is stated as unmet**: the lot's `Done when` in
`docs/reference/frontend-architecture.md` reads « No surface reads a fixture; the fixture literals
are gone from the engine ». **60 families remain declared in the engine** against 21 converted.
They are the ones whose surfaces the engine still DRAWS — the media sheet, the posters, the cast,
the seasons — and converting their data while the engine draws them would give one surface two
sources. That is L13's subject, and it is written here as an open gap rather than closed by
rewording the sentence that names it.
