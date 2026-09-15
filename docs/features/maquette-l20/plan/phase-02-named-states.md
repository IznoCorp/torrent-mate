# Phase 2 — The named states' home has already left the engine

> **Re-targeted by the steward on 2026-09-13**: L13 runs before L20 (the operator's seventh measure), and L13a phase 1 moves the whole state table into `design/src/harness/states/` (L13's design § 4.1) — so this phase no longer moves the HOME; it adds Système's ids to `harness/states/system.ts` under the ceiling, and B-352 closes in L13a, not here.

> **Re-targeted again by the steward on 2026-09-14, after L13a merged (`304346145`)**: `engine/states.js`
> does not exist any more — L13a's phase a·1 deleted it whole, composing all eleven surfaces' tables
> under `design/src/harness/states/` via `harness/index.ts`, `system.ts` (Système's four) among them.
> There is no ceiling left to read and nothing left to shrink: this phase is a plain DECLARATION, not
> a move. Its subject — spanning this phase and phases 3–8, exactly as it always did — is **the 26
> named states of DESIGN § 5, declared in `design/src/harness/states/system.ts` beside the four that
> already live there**; this phase's own share of it is the documenting comment below, not the
> runnable entries, because `states.py` still fails a declared id with no surface to render it (§ «
> The rule »), and that constraint never depended on where the table lived. No engine import, no
> spread into an engine table, no `scripts/frontend_size_ledger.py` re-record, no
> `scripts/check-frontend-boundaries.py` reading of a file that is gone. Every figure below that named
> `engine/states.js` is now a citation of `frontend/maquette/design/src/engine/states.js@60530dbd8` —
> what stood THEN, before L13a — and the live command beside each reads `system.ts` as it stands today.

**A mechanical prerequisite once, a verification now — and it is still a phase because it still has
its own gate and its own register entries to confirm closed.** DESIGN § 5's 26 states still land
progressively, one surface at a time, exactly as before: **this phase itself declares none of
them.** What it once existed to do — leave the engine before anything could be declared anywhere —
L13a already did, whole, for all eleven surfaces, not only Système's slice.

## What was measured then, and what is measured now

`frontend/maquette/design/src/engine/states.js@60530dbd8` read **786** non-blank lines
(`grep -cve '^[[:space:]]*$'`) and `scripts/frontend_size_ledger.py`'s `GRANDFATHERED` record held it
at **786**, to « L13 — the scenario table goes with the engine it drives ». That ceiling is why this
phase was cut in the first place: Système's four took twenty lines for four in that shape
(`sed -n '580,599p'` of the same blob), so twenty-six states was on the order of a hundred and thirty
— **even two would have been refused**. **All of that is history now**: `system.ts` carries no
ceiling, `scripts/check-frontend-boundaries.py` reads no such file, and `frontend_size_ledger.py`
holds no record for a path that left the tree. B-306 (the ceiling arm itself) closed at `fixed #558`,
before this branch existed; B-352 (no surface born after L19 could enter the oracle's corpus for want
of a home) closed at `fixed #596`, L13a's own pull request. **Both register rows this phase once
carried are shut already, by other lots.**

What is live today:

    python3 -c "import re;print(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"', open('frontend/maquette/design/src/harness/states/system.ts').read(), re.M)))"

reads **4** — Système's four, moved whole by L13a, with no ceiling above them. Phases 3–8 add this
lot's 26 beside them, each its own subset, as the rule below still requires; phase 9 reads the count
after.

## The move that is no longer this phase's to make

- `design/src/harness/states/system.ts` was **created by L13a's phase a·1**, already holding
  Système's four states in the `[id, label, run]` shape. It is a top-level directory beside `mocks/`,
  `contract/`, `i18n/` and `engine/`: **the state table is the HARNESS's own fixture**, and belongs to
  no feature — L13a's own framing, not this lot's.
- Composition is `harness/index.ts`'s `namedStates()`, which already spreads `...systemStates()` into
  the one table `installHarness()` drives. Phases 3–8 add to `systemStates()`'s returned array as they
  draw each surface; that composition needs no new caller from this phase.
- Nothing is added to `legacy.js`, which reads no state table at all any more (L13a's phase a·1) — so
  there is nothing left for this phase to subtract from it either.
- **What this phase DOES add**: one dated comment line atop `systemStates()` in `system.ts`, naming
  DESIGN § 5 and the 26 ids it lists, and that phases 3–8 add them here one surface at a time. A
  declared intention, not a declared state — the array itself gains nothing until the phase that
  draws the surface behind an id.

**The alternative once examined and refused — dead with the file it was refused for, since
2026-09-14.** It read: `window.__recordStates(table)` did `STATES = table` (`legacy.js:8683`), so a
second caller WIPED the first; making it accumulate would have been a one-line change inside the
engine that altered the seam's semantics for every existing caller, to save a two-line import. Neither
`window.__recordStates` nor the seam it names exists on this branch — `legacy.js` reads no state table
— so the alternative has no subject left to be re-proposed against. Kept here as the record of a
decision this lot does not have to make twice.

## The rule

**No new rule, and the reason is that the existing one is the right instrument.**
`frontend/maquette/harness/states.py` drives every id `window.__states()` answers and asserts each
renders content, has no horizontal overflow at 390 px and raises no JS error. Its hold COUNT is
therefore the proof this phase is looking for:

- before this phase: it drives **87** ids;
- after this phase: still **87**, because this phase adds none — Système's four already live in
  `system.ts` and answer as before, and this lot's 26 are declared but not yet drawable, so each is
  added to the module in the phase that draws it (3–8).

**That is the discipline, and it is deliberate, and it has nothing to do with where the table
lives**: a state id declared before its surface exists would make `states.py` fail on « renders
nothing », which is the pass it is supposed to enforce, whether the table sits in a grandfathered
engine file or in a file with no ceiling at all. So this phase adds no id of its own; each later
phase adds its ids to `harness/states/system.ts` with the surface that answers them, and phase 9
reads the final count.

⚠ **The count is read, not assumed.** `python3 scripts/harness-hold-counts.py --compare` with
`failed` read FIRST (B-291), and a count that moved in this phase is a finding: nothing here draws
anything.

## Gate

`run.sh --contracts` under the shared lock, announced; `states.py` driving 87 ids, unchanged. No
boundary-check reading — `scripts/check-frontend-boundaries.py` has no grandfathered file left to
read. The oracle: **zero divergence everywhere** — no surface changed and no state's behaviour did.

## Commit

`docs(maquette-l20): the 26 named states land in system.ts, phase by phase — nothing left to move`
