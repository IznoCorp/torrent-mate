# L13c — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13c.md` (governs) and `RULINGS.md` (L13c appends from
115).

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
- DONE: c·1 (`a78287834`…`8cf2fa574`, B-312 `to confirm`, B-548 filed), c·2 (`069fb3a8e` + `f67401890`,
  B-340 `to confirm`), merge of L13r's squash `08400a22a` (`0a32a745a`, pushed), c·3 (`9848c02b4`,
  B-339 `to confirm`), c·4 (`30658ccf7`, B-336 `to confirm`), c·4-bis (`795649a4c`), the merge of
  `e57ac110f` (`93a24bdc1`, pushed), c·5 (`e122c8478` + `d69bafaa1`, B-331 `to confirm`, its centring
  half unreproduced here), the MIDPOINT full suite (green at the second pass, `514635320`), c·6
  (`5bcbfb354`, B-327 `to confirm`), c·7 (`818ea85eb`, B-366 `to confirm`), c·8 (`d725ebda2`,
  B-345's library half `to confirm`). NEXT: c·9, the close.
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
  on the model of `docs/features/maquette-l13/BRIEF-L13r.md@08400a22a` / `docs/features/maquette-l13/RESUME-L13r.md@08400a22a`, before L13r's own pull request opens. c·1 open for
  `Agent : l13c 1` once the steward spawns it, stacked on L13r's head per measure 9.
- 2026-09-15 c·1 (`Agent : l13c 1`): rulings 115–117. Five writers stopped dropping the selection
  (lens, cat, setsort, clear-search, the search commit). R195 `selection_survives_the_listing.py`,
  14 holds: red `c01-red.log` (11 FAIL on the tree before the move), green `c01-gate-2.log` on
  `6150f81d0` (24 rules, 26 guards, 0 failed; oracle 18 divergences, all `lib-selection-filtered`
  absent from the reference, accepted B-312); mutation `c01-mutation-lens.log` fells the two « the
  lens » holds by name. Trap paid: the driver's `reset()` did not write `libCat` or the sort, so a
  state or a rule moving them leaked into every later `__go` (9 `shell/library-count` divergences
  first read as inherited — they were this state's); `libLens`/`libMode` leak too but the reference
  records it (probe `c01-probe-dials.log`, B-548). Dialog fold at four kept (ruling 116): a
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
- 2026-09-16 c·4 (`Agent : l13c 1`): ruling 119. R198 `kind_chips_scrollbar.py`, 4 holds; red
  `c04-red.log` (computed `thin` at 390 and 369 px although the strip wears `pillScroll`), green
  `c04-gate-2.log` on `30658ccf7` (25 rules, 2 named, oracle no divergence), mutation
  `c04-mutation.log` (both widths fall). Traps paid: an unlayered `*` rule in `base.css` beats every
  layered utility — read the COMPUTED value, never the class; headless Chrome paints overlay bars, so
  a drawn-bar-height hold cannot fall (dropped, said); `ui/variants/controls.ts` sits at the 400-line
  ceiling — run check-frontend-boundaries before committing a comment there. Owed, not this phase's:
  the media cast strip (`features/media/variants.ts`) carries the same defeated idiom.
- 2026-09-16 c·4-bis (`Agent : l13c 1`, steward's order): the sheet's cast strip; R198 6 holds; red
  `c04bis-red.log` (thin), green `c04bis-gate.log` on `795649a4c`, mutation `c04bis-mutation.log`.
- 2026-09-16 c·5 (`Agent : l13c 1`): R199 `pull_follows_the_refresh.py`, 5 holds; sampling
  `c05-red.log` (spinner centred at every moment here, offset 0 — the centring half unreproduced on
  this machine), red on both closing holds and both message holds at two answer times; green
  `c05-gate-2.log` on `d69bafaa1` (26 rules, 3 named, oracle no divergence); mutations
  `c05-mutations.log` (fixed delay → both closings; `place-items-center` removed → the centring hold,
  drawing the operator's screenshot at x = 0). Trap paid, twice over: `__go` RESETS the mock scenario,
  so a latency set before a driven state is no latency at all; and a rule that reads « the indicator
  is up » cannot read anything once the refresh it stands for answers instantly — R55 and `press.py`
  re-aimed with an answer time, said in both files.
- 2026-09-16 MIDPOINT (`Agent : l13c 1`): pass 1 `midpoint-full-suite.log` — three falls, each
  replayed alone and all real (the inverse probe on the pre-c·1 sources passed): `outbox.py` fell to a
  MODULE CYCLE (`app/pull-indicator.ts` importing `lib/query-client`, which imports `app/outbox`,
  moved the queue's boot) — the refresh is handed in by `app/shell.tsx` instead; `surfaces.py` and
  `virtual.py` re-aimed and said (an empty add screen; a search that keeps the selection). Pass 2
  `midpoint-full-suite-2.log`: 146 rules + 26 guards no violation, a11y 0 dark / 147 light at the
  ceiling, oracle no divergence.
- 2026-09-16 c·6 (`Agent : l13c 1`): the seed's seventh scheduler; B-327's kept hold restored in
  `machine.py`; red `c06-red-2.log` (six drawn against seven), green `c06-gate-2.log` on `5bcbfb354`,
  mutation `c06-mutation.log`, oracle accepted `settings-field-schedule` by name (`c06-accept.log`,
  diff verified by script). Trap paid: a pinned COUNT in a unit test moves with a seed row
  (`format.test.ts`, 159 → 160 and 6 → 7) — `check-maquette-unit-tests` is the guard that says so.
- 2026-09-16 c·7 (`Agent : l13c 1`): R200 `follow_needs_an_identity.py`, 4 holds; red `c07-red-2.log`
  (the layer answered 200 and recorded a follow nothing identifies), green `c07-gate.log` and
  `c07-gate-2.log` on `818ea85eb` (28 rules, 5 named, twice over — the follow panel's other readers
  too), mutation `c07-mutation.log`. The phase's own « tsc must fail » proof does not hold on this
  tree and the measure had said so: the refusal is the layer's, on the JOIN path. Trap paid: a mock
  refusal's words are tool text and stay English; the French belongs to the interface.
- 2026-09-16 c·8 (`Agent : l13c 1`): R128 gains eight library holds, GREEN from the start — the seeds
  already hold every state the library draws (345 rows, a title twice, a followed title, five with a
  hole, 20 without a poster). Green `c08-gate.log` on `d725ebda2` (27 rules, 4 named, oracle no
  divergence); mutations `c08-mutations.log` (a category emptied; the duplicate made single) fall by
  name. Trap paid, and it was MINE: the first reading was red on five holds because it judged a PAGED
  listing by one page and read `total` (the library's own 1 861) where `loaded` (345) is what the
  layer holds. Owed to the steward: the other surfaces' share of B-345 is not measured here.
