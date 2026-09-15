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
- DONE: c·1 (`a78287834`…`8cf2fa574`, B-312 `to confirm`, B-539 filed), c·2 (`069fb3a8e` + `f67401890`,
  B-340 `to confirm`), merge of L13r's squash `08400a22a` (`0a32a745a`, pushed), c·3 (`9848c02b4`,
  B-339 `to confirm`). NEXT: c·4 (same shape likely: `pillScroll` already carries the idiom).
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
- 2026-09-15 c·1 (`Agent : l13c 1`): rulings 115–117. Five writers stopped dropping the selection
  (lens, cat, setsort, clear-search, the search commit). R195 `selection_survives_the_listing.py`,
  14 holds: red `c01-red.log` (11 FAIL on the tree before the move), green `c01-gate-2.log` on
  `6150f81d0` (24 rules, 26 guards, 0 failed; oracle 18 divergences, all `lib-selection-filtered`
  absent from the reference, accepted B-312); mutation `c01-mutation-lens.log` fells the two « the
  lens » holds by name. Trap paid: the driver's `reset()` did not write `libCat` or the sort, so a
  state or a rule moving them leaked into every later `__go` (9 `shell/library-count` divergences
  first read as inherited — they were this state's); `libLens`/`libMode` leak too but the reference
  records it (probe `c01-probe-dials.log`, B-539). Dialog fold at four kept (ruling 116): a
  selection of ≥ 5 names hidden titles only inside « et N autres » — for the operator.
- 2026-09-15 c·1 close: the oracle accepted `lib-selection-filtered` by name (`2092bbb27`, diff = the one
  state + count + baseCommit); re-gate `c01-gate-3.log` « gate: no violation ». Ruling 116 carries the
  operator's A.
- 2026-09-15 c·2 (`Agent : l13c 1`): R196 `add_screen_opens_fresh.py`, 7 holds, red `c02-red-2.log`
  (4 FAIL), green `c02-gate-3.log` on `f67401890` (27 rules, 5 named, 26 guards, 0 failed, oracle no
  divergence); mutations `c02-mutations.log` (stored query → f1+f2; visit not begun → f4+f5). Re-aimed:
  R121 `replacement.py` and `bugs.py` read `window.__addedPositions()`. Traps paid: « + » lives on
  Acquisition only (a walk must take the tab); `add_footer.py` fell on its second add because the
  search seed gives the film « Star Wars : The Clone Wars » the series' identifiers (tmdb 4194) — the
  key now carries the kind; the seed itself is the fixture-identity class, left as it is. A new name
  word must be in `scripts/code-vocabulary.txt` — run check-no-french before every commit.
- 2026-09-15 c·3 (`Agent : l13c 1`): STOP D → ruling 118. R197 `disabled_action.py`, 5 holds; reading
  `c03-reading-detail.log` (opacity alone differs, L20's half), red `c03-red.log` (the « + » hold),
  green `c03-gate.log` on `9848c02b4` (25 rules, 3 named, oracle no divergence), mutations
  `c03-mutations.log` (base half removed → 3 drawing holds; plus handed back → the icon hold). The
  merge of `08400a22a` (`0a32a745a`): 15 conflicts resolved by re-applying c·1/c·2 onto main's files,
  checked by script (merge delta = main delta on 18 code files). A green reading before the move is
  not a pass: replay the rule directly to read WHAT differs before claiming a defect gone.
