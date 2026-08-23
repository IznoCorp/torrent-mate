# Phase 5 — The seven guards bite

**A guard installed on a tree that is still moving guards the wrong thing**, which is why this
phase comes after the move and not with it. Phase 1 wrote the cycle arm as a standalone check
because it had to prove its own fix; this phase folds it in with the other six.

## Shape

**One script, `scripts/check-frontend-boundaries.py`, one arm per guard.** That is the house shape
— `check-no-french.py` has fourteen arms, `check-markup-contracts.py` four — and the reason is the
same: the gate keeps ONE command, and each arm's header names the corpus it reads and the defect
class it refuses. `--arm <name>` runs one; no flag runs all seven and prints the count each derived.

**Wired into `make check`** beside `check-markup-contracts.py`, and into the CI `checks` job at the
same place. It reads only `frontend/maquette/design/src` — the operator's arbitration
(D-L04-1): production is not touched.

## The seven arms

| #   | Arm                | Refuses                                                                                            | Floor                              |
| --- | ------------------ | -------------------------------------------------------------------------------------------------- | ---------------------------------- |
| 1   | `cycles`           | any cycle in the resolved import graph                                                             | hard zero                          |
| 2   | `fan-in`           | a module outside `ui/` and `lib/` imported by more than **4 features**                             | hard                               |
| 3   | `layering`         | `ui/` or `lib/` importing `features/` or `routes/`; one feature importing another                  | hard zero                          |
| 4   | `size`             | ≥ **400** non-blank lines (REPORT), ≥ **250** (WARN); `engine/` grandfathered whole with L13 named | grandfathered list, never extended |
| 5   | `typing`           | `any`, `as any`, `@ts-ignore`, `@ts-expect-error`                                                  | hard zero, from today's zero       |
| 6   | `duplicate-import` | the same module imported twice by one file                                                         | hard zero                          |
| 7   | `one-address`      | a `routes/` file declaring more than one `path:`; an address declared twice                        | hard zero                          |

Plus `tree`: every file under `design/src` inside a declared bucket, and `data.ts` absent.

**Why 4 for the fan-in ceiling.** The architecture file states its own intent — « the one that
would have stopped `data.ts` at four importers instead of seventeen ». It counts FEATURES, not
modules, and `ui/`/`lib/` are exempt by its wording. That exemption is why the store hooks and the
navigation door went to `lib/` in phases 1 and 3: they are domain-free and non-rendering, so **no
exemption has to be invented for them** and the guard's sentence stands unamended.

## Each arm is mutation-tested, and none is exempted

**A guard that never bit proves nothing.** For each of the seven: break the behaviour on purpose,
confirm the arm falls and **names the right defect**, restore, confirm it goes green again.

| Arm                | Its mutation                                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `cycles`           | restore `data.ts`'s type-only import of `PanelDescriptor` in a scratch file — a cycle is reported, naming both ends |
| `fan-in`           | add a fifth feature importer to a `features/` module — refused, naming the module and its importers                 |
| `layering`         | import a feature from `ui/panel/index.tsx` — refused, naming both sides                                             |
| `size`             | append blank-stripped lines to a file at 399 until it crosses 400 — REPORT, naming the file and its count           |
| `typing`           | write `const x: any = 1` in one component — refused, naming file and line                                           |
| `duplicate-import` | split one import statement in two over the same module — refused, naming file and module                            |
| `one-address`      | declare a second `path:` in one `routes/` file — refused, naming the file and both addresses                        |

**The floor has no baseline file, no budget and no `--allow-additions`** for arms 1, 3, 5, 6, 7 —
they are at zero today and stay there. Arm 4 carries a grandfathered LIST, which is phase 6's
subject, and arm 2 carries a NUMBER, not a list.

## The mutation record is a deliverable

Each mutation is run, its red output captured, and the restore verified. The record goes in the
phase's report and is cited by ACC-18. **A recorded mutation nobody ran is a sentence in a file** —
the exact defect this repository has paid for, and the reason `--record` refuses a baseline taken
on a red suite.

## Proof

- `python3 scripts/check-frontend-boundaries.py` exits 0 with all seven arms run, printing each
  derived count.
- Every arm seen RED on its own mutation, naming the right defect, then restored.
- `grep -c 'check-frontend-boundaries.py' Makefile` ≥ 1 and the same in `.github/workflows/ci.yml`.
- `make check` exits 0.
- **The oracle reports 0 divergence** — a guard changes no rendering, and a divergence here would
  mean a mutation was left in.

## Trap met here

**A gate proves what it READS.** Before an arm is trusted, the question is asked out loud: what
corpus does it walk, and what shape does it recognise? A selector the harness BUILDS spells itself
in neither shape a naive reader expects; the same is true of an import written across several
lines, or a re-export. Each arm's corpus is stated in its header, and each arm prints what it
derived — a number nobody compares is a number nobody reads.
