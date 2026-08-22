# Phase 1 — The instrument, and the debt recorded

## Gate

Produced before this phase starts:

- `docs/features/maquette-l03/DESIGN.md` on `feat/maquette-l03`, version 0.98.18.
- `main` merged in at `f5568068` or later, so the oracle reference (`baseCommit 8adc5643`) is an
  ancestor of `HEAD` and `oracle.py --check` compares without warning about its provenance.

**Nothing in Phases 2–6 may start before this phase closes.** Every later phase promises « the
rendering did not move » and « the violation count went down »; neither statement exists until
the instruments do.

## Why this phase exists

Three things are broken or absent, and all three are load-bearing for the wave's own proofs.

1. **There is no accessibility instrument at all.** The lot's Done when requires one in the gate.
2. **The hold-count baseline's commit pointer is dangling.**
   `frontend/maquette/hold-counts-baseline.json` names `taken_at_commit c7714c38` — a commit of
   the L02 branch that the squash merge replaced. It is **not an ancestor of `HEAD`** and does
   not exist on a fresh clone. This is the same defect `oracle.py` had (#473), on the instrument
   that carries proof 2 of this wave.
3. **`--compare` does not check that pointer.** It reads `taken_at_commit` and prints it, and
   that is all. `oracle.py --check` at least *warns* — it appends « NOT an ancestor of HEAD: a
   squash merge replaced that commit, so re-record it ». It does **not** refuse; the only thing
   it refuses on is a platform mismatch. This tool does neither, so the baseline rots in silence
   for as long as nobody thinks to look, which is exactly what happened.

## Sub-phases

### 1.1 — `axe-core` and the measuring script

`npm install --save-dev axe-core` in `frontend/maquette/design`. Write
`frontend/maquette/a11y.py`, modelled on `oracle.py`: it drives the prototype through the 83
named states of `design/src/states.js`, injects `axe.min.js` from `node_modules` on each, runs
the audit, and collects violations per state and per rule.

Three modes, and they mirror the oracle's vocabulary rather than inventing a second one:
`--record` writes the debt file, `--check` fails on any violation, `--rules R1,R2` narrows to a
named subset so a phase can enforce the part it owns before the rest is clean.

`color-contrast` is run and recorded in `a11y-contrast.json`, and is **never** part of what
`--check` fails on (DESIGN § D-L03-4).

Commit: `feat(maquette-l03): axe-core drives the 83 states and records what it finds`

### 1.2 — The `--a11y` tier and its CI step

Add `--a11y` to `frontend/maquette/harness/run.sh` as a fourth tier beside `--contracts`,
`--oracle` and the full suite. It reuses the script's existing build-and-copy preamble — a stale
`wrapped.html` measures the previous build, which has cost this project two debugging sessions.
Include it in the full suite. Add a `make maquette-a11y` target.

Add one step to the CI job `harness-contracts`, which already runs
`npm ci --prefix frontend/maquette/design` and installs Chromium, gated on the same
`needs.changes.outputs.maquette == 'true'` as its neighbours.

**In this phase the tier records; it does not yet fail on a non-zero count.** The floor is made
hard in Phase 6, when the count is zero. A gate that is red from the day it lands teaches nobody anything and
gets muted.

Commit: `feat(maquette-l03): the a11y tier runs in the suite and on every maquette PR`

### 1.3 — Record the debt, before anything is touched

Run `--record` on the branch with no accessibility change in it. Commit `a11y-debt.json` and
`a11y-contrast.json`. These two files are the wave's starting line and the only figures the
burn-down is measured against.

If the count is large enough to change the shape of the lot, that is an arbitration to bring to
the operator (DESIGN § 7), **not** a target to quietly trim.

Commit: `docs(maquette-l03): record the accessibility debt as it stands before the wave`

### 1.4 — Repair the hold-count baseline, and make it refuse to rot

Re-record `hold-counts-baseline.json` on the branch (`--record`, the full 20-25 min suite) so its
`taken_at_commit` is an ancestor of `HEAD`. Then give `--compare` a guard, and make it **stronger
than the oracle's, on purpose**: the oracle only warns, and a warning is what let this baseline
sit dangling for four days under a green gate. `--compare` **refuses** when the baseline commit is
unreachable or is not an ancestor of `HEAD`, says which of the two it is, and names the command
that fixes it.

**Why refusing is affordable here and is not for the oracle.** Both files must be re-recorded
after a squash merge; the difference is what a wrong comparison costs. A hold count is the whole
of proof n° 2 — « the suite is green at unchanged hold counts » — and a comparison against a
baseline whose provenance cannot be established turns that proof back into a sentence. The
re-record is already a required step of every wave's close (Phase 6.4), so the guard enforces a
step that exists rather than inventing one.

Fix the stale echo in the `maquette-oracle` Makefile target: it announces « 82 states x 33
regions » where the reference holds 83.

Commit: `fix(maquette-l03): a hold-count baseline whose commit is gone cannot be compared against`

### 1.5 — The fixture that made the suite unrecordable

`scripts/refresh-maquette-fixture.py --check` exits 1 on `main` — verified by checking `main`
out and running it there, not inferred. One value has drifted: « Kyma, l'onde mystérieuse ·
searches: fixture 11 vs database 12 ». The CI step that runs it on every maquette pull request
is red before this branch exists, and the harness rule `content.py` fails for the same value.

It is repaired here rather than reported, because `--record` **refuses to write a baseline taken
on a red suite** — so with this standing, proof n° 2 cannot be obtained at all.

Commit: `fix(maquette-l03): refresh the follow fixture, which had drifted from acquire.db`

## ⚠ The trap this phase paid for, and the next wave will meet it too

**A hold-count recording needs a QUIESCENT tree, and « the served copy is frozen » is not
enough.** `run.sh` and `harness-hold-counts.py` build and copy the prototype ONCE at the start,
so editing `design/src` mid-run does not disturb the rules that read `/tmp/tm-refonte`. That
reasoning is correct, and it is incomplete — three rules do not read that copy:

| Rule | What it really reads |
| --- | --- |
| `entry.py`, `startup.py` | the **design host** on 8712, and `serve.py` re-reads `index.html` **from disk on every request** — markup is hot, only its Python is cold |
| `content.py` | the operator's live `acquire.db` |

Edited during the first recording, `index.html` was therefore served NEW to the host and OLD in
the prototype copy: `entry.py` reported six « renders the same on both sides » failures with
`host=0` everywhere, and `startup.py` timed out filling a form. Neither was a defect in anything.
**The recording was discarded and retaken on a stopped tree.**

## Verification

| ID | Command | Expected |
| --- | --- | --- |
| ACC-01 | `frontend/maquette/harness/run.sh --a11y` | exit 0, one line per state |
| ACC-02 | `python3 frontend/maquette/a11y.py --record` | writes `a11y-debt.json` with a count per state and per axe rule |
| ACC-03 | `git merge-base --is-ancestor "$(python3 -c 'import json;print(json.load(open("frontend/maquette/hold-counts-baseline.json"))["taken_at_commit"])')" HEAD` | exit 0 |
| ACC-04 | `python3 scripts/harness-hold-counts.py --compare <a baseline pinned to a fabricated commit> --only logout` | exit non-zero, naming the dangling pointer |
| ACC-05 | `grep -c '83 states' Makefile` / `grep -c '82 states' Makefile` | `1` / `0` |

**Mutation check for ACC-04**, run after the phase is committed: point a copy of the baseline at a
commit that does not exist, confirm `--compare` refuses and names it, restore. Committing first is
not a detail — mutating before the commit is how a mutation gets shipped.

## Out of scope for this phase

No `role`, no `aria-*`, no `tabindex`, no tag substitution. This phase measures; it changes
nothing the oracle can see, and `oracle.py --check` must report 0 divergence at its close for
exactly that reason.
