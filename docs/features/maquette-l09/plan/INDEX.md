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
| ACC-05 | `python3 scripts/check-frontend-boundaries.py --arm server-state` | count ≤ its recorded ceiling, ending at 0 |
| ACC-06 | `python3 scripts/check-frontend-boundaries.py --arm effect-fetch` | 0 violations, corpus size ≥ floor, printed |
| ACC-07 | `grep -c 'displayedValue' frontend/maquette/contract/openapi.json` | 0 |
| ACC-08 | `python3 scripts/compare-contracts.py --check` | exit 0, the precision demand present |
| ACC-09 | `python3 scripts/check-mock-seeds.py` | 7 arms, no violation |
| ACC-10 | `frontend/maquette/harness/run.sh` | every rule, no violation |
| ACC-11 | `make check` | exit 0, 0 failed and 0 error |
| ACC-12 | `grep -rn "__referentiel" frontend/maquette/design/src/features \| wc -l` | 0 — no surface reads a fixture |
| ACC-13 | `python3 scripts/check-module-size.py --root frontend` | no file over the hard ceiling |

ACC-05, ACC-06, ACC-07, ACC-08 and ACC-12 are the `Done when` of the lot, said as commands.
