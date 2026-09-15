# L13c — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13c.md` (governs) and `RULINGS.md` (L13c appends from
110).

## STATE

- Branch `feat/maquette-l13c`, worktree `/Users/izno/dev/worktrees/wave-l13c`, cut from L13r's PR
  head `22166378e`. L13r's squash onto `main` and merge are the steward's, named when they land.
  Steward: the session named in your launch prompt (`Orch : TM frontend`, its reference changes).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13c`.
- Phases (`plan/INDEX.md` § « L13c »): c·1 the selection survives the lens (B-312) → c·2 a fresh add
  screen (B-340) → c·3 a disabled action looks disabled (B-339) → c·4 the kind chips hide their
  scrollbar (B-336) → c·5 the pull indicator (B-331) → [MIDPOINT full suite, auditor's order 5] →
  c·6 the seventh scheduler (B-327) → c·7 no follow without a sheet (B-366) → c·8 the library's
  states at rest (B-345's library half) → c·9 the close (register re-read, `REPORT.md`, the lot's
  gesture, the pull request).
- None DONE yet. NEXT (`Agent : l13c 1`): c·1, after the handshake.
- LOGS: `~/Library/Logs/tm-l13c/`. Mutex `sh scripts/heavy.sh --held`; tests lock
  `/private/tmp/tm-heavy-tests/holder`; own lock `/private/tmp/tm-heavy-l13c/holder`.
- GATE FORM: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13c
  frontend/maquette/harness/run.sh --contracts --oracle <full rule paths>` — the only form that
  reads rule names (rulings 66, 81, 92; measure 17).
- MUTATIONS: `sh scripts/mutate.sh <full path> "<expr>" frontend/maquette/harness/<rule>.py`; commit
  before; read the NAMED FAIL line; « RULE CRASHED » / « RULE NOT FOUND » prove nothing (ruling 77).
- Push: the pre-push hook is the branch's own (relative hooksPath); a docs-only push takes the fast
  path; a code push runs the suite (~14 min) under the tests lock.
  `tests/scripts/test_check_maquette_comments.py` alone before any push.
- Register: each c-phase closes its OWN row in the same commit that lands it (B-312, B-340, B-339,
  B-336, B-331, B-327, B-366, B-345) — unlike L13b/L13r, L13c is not filing rows at the close, it is
  CLOSING the ones the lot already owes; c·9 re-reads B-071, B-220, B-236 (stale, DESIGN § 9.10) for
  the steward to close, and re-reads every other row DESIGN § 10 assigns.
- Traps inherited from L13b and L13r (their RESUME ledgers, read on this branch): zsh does not
  word-split a multi-word variable; a detached checkout runs THAT head's `run.sh` (rule names read
  only by the branch's own tooling); the tap registry answers the first registered key in ATTRIBUTE
  order; `stopPropagation` does not stop a listener BESIDE yours; a touch drag suppresses the click
  itself; a scan that writes history needs a reset before reading; the pre-push hook re-runs a
  failed suite to print it; never `cd` into `design/src` (B-384); a reference reading rolling
  `design/src` back then `git checkout HEAD --` DISCARDS uncommitted work — commit first.
- Owed at c·9: `--a11y`, hold-counts `--compare` (baseline `taken_at_commit` re-pointed to main's
  sha in a copy), `check-bug-register.py`, `check-intent-map.py`, merge main in, version bump above
  main's, `REPORT.md`, the lot's gesture (`docs/features/maquette-l13/` deleted whole, every
  citation of it rewritten `path@<merge sha>`), PR READY (behaviour: §§ cited per phase).

## LEDGER (append-only)

- 2026-09-15 (steward): branch not yet cut. BRIEF-L13c.md and this file written AHEAD (order 39),
  on the model of BRIEF-L13r.md / RESUME-L13r.md, before L13r's own pull request opens. c·1 open for
  `Agent : l13c 1` once the steward spawns it, stacked on L13r's head per measure 9.
