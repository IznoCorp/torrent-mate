# L13r — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13r.md` (governs) and `RULINGS.md` (L13r appends from 100).

## STATE

- Branch `feat/maquette-l13r`, worktree `/Users/izno/dev/worktrees/wave-l13r`, cut from L13b's PR head
  `fcaff976f` (#601, STACKED: L13b's reader round runs; when L13b squashes onto main, MERGE main in — no rebase).
  Steward: the session named in your launch prompt (`Orch : TM frontend`, its reference changes).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13r`.
- Phases: r·1 constants and helpers → r·2 served fixtures → r·3 engine verbs and drawing (BEHAVIOUR) →
  [midpoint full suite] → r·4 the reference dies → r·5 contract names (STOP D with a cut at its opening; never one
  phase) → r·6 the file dies + the full gate + the PR. None done yet.
- NEXT: r·1 (`plan/phase-r01-constants-and-helpers.md`): the 20 interface constants and 10 helpers find homes, the
  four zero-reader names die; conversion — contracts + oracle ZERO + the named rules unchanged; frame-domain ceiling
  read BEFORE the move (ruling 96: lib/ 28, app/ 139).
- legacy.js non-blank at the cut: 1 600. `scripts/frontend_size_ledger.py` re-recorded DOWNWARD in every phase's commit.
- LOGS: `~/Library/Logs/tm-l13r/`. Mutex `sh scripts/heavy.sh --held`; tests lock `/private/tmp/tm-heavy-tests/holder`;
  own lock `/private/tmp/tm-heavy-l13r/holder`.
- GATE FORM: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13r frontend/maquette/harness/run.sh --contracts
  --oracle <full rule paths>` — the only form that reads rule names (rulings 66, 81, 92).
- MUTATIONS: `sh scripts/mutate.sh <full path> "<expr>" frontend/maquette/harness/<rule>.py`; commit before; read the
  NAMED FAIL line; « RULE CRASHED » / « RULE NOT FOUND » prove nothing (ruling 77).
- Push: the pre-push hook is the branch's own (relative hooksPath); a docs-only push takes the fast path; a code push
  runs the suite (~14 min) under the tests lock. `tests/scripts/test_check_maquette_comments.py` alone before any push.
- Register: no rows during the wave (ruling 85) — ledger lines; the steward numbers rows at the close.
- Traps inherited from L13b (RESUME-L13b.md's ledger, read on this branch): zsh does not word-split a multi-word
  variable; a detached checkout runs THAT head's run.sh (names read only by the branch's tooling); the tap registry
  answers the first registered key in ATTRIBUTE order; `stopPropagation` does not stop a listener BESIDE yours;
  a touch drag suppresses the click itself; a scan that writes history needs a reset before reading; the pre-push
  hook re-runs a failed suite to print it.
- Owed at r·6: `--a11y`, hold-counts `--compare` (baseline `taken_at_commit` re-pointed to main's sha in a copy),
  `make lint`, merge main in, version bump above main's, PR READY (conversion: no §§; r·3's behaviour said).

## LEDGER (append-only)

- 2026-09-15 (steward): branch cut at fcaff976f; BRIEF-L13r.md and this file written; r·1 open for `Agent : l13r 1`.
