# Phase 6 — The floor bites

## Gate

Produced by Phases 1–5:

- `a11y.py` records and checks; the `--a11y` tier runs in the suite and on every maquette PR.
- Landmarks, names, focus management, keyboard paths and live regions are in.
- The oracle has been at 0 divergence at the close of every phase.

The floor is made hard only now, and deliberately: a gate that lands red gets muted, and a muted
gate is worse than none because it reads as green.

## What this phase does

Turns a recording instrument into a refusing one, proves that both new holds actually bite, and
hands L06 what this wave measured but did not fix.

## Sub-phases

### 6.1 — Hard zero

`a11y.py --check` and the `--a11y` tier exit non-zero on **any** violation, `color-contrast`
excepted. No threshold, no tolerated list, no baseline file to compare against — the floor is a
literal zero, in the same form L02 gave the class-anchor floor.

`a11y-debt.json` stops being a live comparison point and becomes what it always was: the record
of where the wave started. Say so in the file, or the next reader will take it for a tolerance.

Commit: `feat(maquette-l03): the accessibility floor is a hard zero`

### 6.2 — The mutation checks

**Commit first, then mutate, then restore.** Mutating before the commit is how a mutation gets
shipped.

Two mutations, because the wave added two holds and they fail differently:

1. Remove one `aria-label` from a control. `--a11y` must fall **and name that control** — not
   merely go red. A rule that fails without saying what fell is a rule someone will disable.
2. Break the focus restoration — do not return focus to the trigger on close. The focus rule must
   fall and name the layer.

Record both in the phase's commit body: what was broken, what the gate said, that it was
restored.

Commit: `test(maquette-l03): both new holds seen red on a deliberate break, and restored`

### 6.3 — The handover to L06

Two things this wave measured and deliberately did not fix (DESIGN § 6):

- **Colour contrast** — `a11y-contrast.json`, with its count and its locations.
- **Touch-target size** (WCAG 2.5.8) — measured here and recorded in the same file.

Cite both from `docs/reference/frontend-architecture.md` § L06 so the next lot inherits a number
rather than a memory. **A measurement that lives only in a merged PR body is a measurement nobody
finds.**

Commit: `docs(maquette-l03): L06 inherits the contrast and touch-target figures`

### 6.4 — The wave's own record

Update `IMPLEMENTATION.md` § « Where the frontend work stands »: L03 moves from *In flight* to
*Last landed*, with its PR number, its version and its measured end state. Mark the lot `LANDED`
in `docs/reference/frontend-architecture.md`.

**And the step that a wave has now forgotten twice**: after the squash merge, re-record the
oracle reference (`make maquette-oracle`, then `python3 frontend/maquette/oracle.py --record`,
commit) *and* re-record the hold-count baseline. The squash replaces the commit both files name,
and Phase 1 taught this wave what a dangling pointer costs when nothing checks it.

Commit: `docs(maquette-l03): the wave's record, and what the next session needs`

## Verification — the full ACCEPTANCE re-exercise

| ID | Command | Expected |
| --- | --- | --- |
| ACC-13 | `frontend/maquette/harness/run.sh --a11y` | 0 violations over 83 states, `color-contrast` excepted |
| ACC-14 | `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` | no changed count |
| ACC-15 | `python3 frontend/maquette/oracle.py --check` | 0 divergence |
| ACC-16 | the mutation record in 6.2's commit body | both holds seen RED, each naming the right defect, both restored |
| ACC-17 | `make check` | exit 0 |
| ACC-18 | `test -f frontend/maquette/a11y-contrast.json && grep -c 'a11y-contrast' docs/reference/frontend-architecture.md` | file present, `≥ 1` |

Plus every earlier criterion, ACC-01 through ACC-12, re-run on the final tree. A criterion that
passed at its own phase and was never re-run proves only that it passed then.

## Out of scope

Everything DESIGN § 6 names: touch-target remediation and contrast remediation are L06's;
B-036 waits for a wave of its own.
