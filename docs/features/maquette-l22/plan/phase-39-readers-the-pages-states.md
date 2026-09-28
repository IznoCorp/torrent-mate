# Phase 39 — Readers re-aimed: the page's states

**Numbered 30, then 32, then 34, on 2026-09-27** (was 22; the triage's F51). **Carried at its opening, from the coherence triage (`review-archive/coherence-2026-09-27-triage.md` § B; texts in `coherence-2026-09-27.md`)**: F41 (the state is named
`acq-todo-error`; `acq-todo-loading` is dropped with a dated line unless it is built; B-515's reading is made here); F53
if phase 33 did not take it.

**Amended 2026-09-28 (L22b, at its opening, steward approved):** re-measured ≈ 30 on `24bc410f3` → CUT into **40** (F41: `acq-todo-error` and `acq-todo-loading` — built, the steward's ruling A —, R90 re-aimed, B-515 read), **41** (the twelve other readers and the code sites) and **42** (F53); the rest +2 (43–47).

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n -E 'arr-(idle|loaded|queued|running|error|loading)|arr-\{' -- 'frontend/maquette/harness/*.py'`
  at the opening (the page's own states; `arr-running` is read by `busy.py`'s comment only) → files:
  `add_screen_opens_fresh.py` (`START_STATE`), `audit.py:304`, `fanout.py:241`, `ident.py:82`, `paths_to_sheets.py:50`,
  `resolution_window.py:80,261`, `scen.py:16` (the `("arrivals", "arr-{s}")` template), `state_surfaces.py:15,45,117,128`
  (R90 — `arr-error`, `arr-loading`, and their sentence « ce qui arrive »), `touch.py:115`, `panel_label_once.py:56`
  (`arr-queued`, « the subject — a medium »); and — second touch, first done in phase 3 — `actions.py:40`, `cards.py:50-52`,
  `decision.py:204-208`. `harness/states/acquisition.ts:211` is a CODE site: `applyState({ page: "arr", … })` in a state
  that is not an Arrivées state. **These readers are the reason the rules of phases 6 to 13 exist**: each `arr-*` state
  they drive has an Acquisition successor by then (`acq-now-*`, `acq-todo-*`, `acq-card-*`).
- **Points ≈ 14.** Ten files re-aimed at 1 each (the walk begins somewhere else, so the re-aim is not a rename) 10; three
  second touches 3; the one code site 1.

The page still exists and its states still run; **this phase moves every reader off them BEFORE the page dies**, so the
death phase has zero readers to break (the residual grep is the gate, as after any deletion).

## Red today

**No new rule; each re-aimed rule is red first in the sense that matters**: a rule whose start state is changed is replayed
and must hold what it held — `python3 scripts/harness-hold-counts.py --compare` with **`failed` read FIRST** and every
hold count unchanged, except where a hold's subject genuinely changed and the phase says so, hold by hold.
**R90** (`state_surfaces.py`) takes `acq-todo-loading` and `acq-todo-error` in place of `arr-loading` / `arr-error` — its
per-surface sentences (`"arr-error": "ce qui arrive"`) become the tab's own, read from `fr.json`, never retyped.

## Move

Re-aim the thirteen files and the code site onto the Acquisition states; state, file by file, which successor each takes
and why it reads the same subject. **A rule that reads « Arrivées → Résoudre → no match → manual search » (`ident.py`) now
begins at « À traiter ».**

## Mutation

Each re-aimed rule keeps its own mutation; the phase re-runs one per file, by `scripts/mutate.sh`, and reports which
fell. No new mutation is invented.

## Register

—

## Oracle: states that diverge, declared by name

**None.** Only rule files and one state file change. Any divergence is STOP A.

## Gate

Per INDEX « Gates »; the thirteen files run by name; `scripts/harness-hold-counts.py --compare`.

## Commit

`test(maquette-l22): the rules that started on the Arrivées page start on Acquisition`
