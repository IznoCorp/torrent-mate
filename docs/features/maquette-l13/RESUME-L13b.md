# L13b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13b.md` (governs) and `RULINGS.md` (L13b appends from 64).

## STATE

- Branch `feat/maquette-l13b`, worktree `/Users/izno/dev/worktrees/wave-l13b`, stacked on L13a `37e54d0fd`;
  rebase onto `main` only on the steward's word (after #596's squash). Steward: the session named in your launch prompt (`Orch : TM frontend`, its reference changes at every resume).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13b`.
- Tooling landed: `701ae1aca`, `3023f2305`, `108904b51`, `63f6674a4`, `{tooling}` (rulings 66–69, 77/77-bis).
- b·1 DONE (`e3ae69b01`), b·2 DONE (`4f157ca9f`), b·3 DONE (`6c6245fbd`, rulings 70/70-bis),
  b·4 DONE (`bec2b0d5b`, rulings 73–74; `pipe` stays in the engine for the NEW phase b·10-ter),
  b·5 DONE (`d8d1a3e8b` move + `ebc53e4ea` re-aim, ruling 75; gate and mutations in the ledger).
- legacy.js non-blank: 3060. Surface-openers contract grep: 0. `FAN_IN_EXEMPT` keeps `features/acquisition/queries.ts`
  (the engine still reads `follows()` and `suggestions()`).
- NEXT: b·6 (library verbs), `plan/phase-b06-library-verbs.md` — its first hold is `selectedTitle`; the dialog-door
  amendment is already landed (`lib/shell-doors.ts` `dialog`, b·5).
- LOGS: `~/Library/Logs/tm-l13b/` (ruling 76). The mutex and the tests lock stay under `/private/tmp`.
- Phase gate form (ruling 66): `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13b
  frontend/maquette/harness/run.sh --contracts --oracle <the phase's rules>` (~270 s once the mutex is free).
- Mutations: `mutate.sh <verbs file> "t.replace('registerVerb(\"x\",', 'void (\"x\",')" frontend/maquette/harness/<rule>.py`
  — FULL rule paths; since `{tooling}` it refuses a missing path and starts the 8899 host itself (77/77-bis). Read the
  NAMED check line (`FAIL …`), never the « FELL » line; « RULE CRASHED » is an instrument fall.
- Features register at module evaluation, named in `app/panel-contributions.ts`: a new `install…Verbs` import in
  `app/feature-verbs.ts` costs app/ domain words that `check-frame-domain.py` refuses over 138.
- Locks: browser mutex (`sh scripts/heavy.sh --held`); tests lock `/private/tmp/tm-heavy-tests/holder`; own lock
  `/private/tmp/tm-heavy-l13b/holder` (npm ci, tsc -b, vitest run).
- Owed: full suite at the midpoint (after b·6, before b·7) and at b·11 with `--a11y`, `--compare`, `make lint`;
  no local `make check` (ruling 68). Machine restarts Monday 05:00: pushed by 04:30, line to the steward at 04:45.

## LEDGER (append-only)

- 2026-09-13 tooling: `tests/scripts/test_run_sh_builds_once.py` RED at line 143 (`oracle.py --check` 0 == 1) before
  the run.sh change; 95 passed after.
- 2026-09-13 b·1: DESIGN § 6's « to, deletefield, addfield tap 0 rule files » was a NAME grep; `settings.py` (R60)
  already tapped the switch and the list removal by `data-part`, holding a boolean filed and a count. The holds
  added read the drawn value (`aria-checked` flip), the removal at index 1 (re-aim: was the first button), and the
  addition. Hold counts: settings.py 65 → 68, failed 0.
- 2026-09-13 b·1 red: engine branches deleted by mutate.sh → settings.py 5 violations (log `b01-red.log`).
- 2026-09-13 trap: two new maquette source files move `comment-references-baseline.json` `read` (415 → 417);
  `tests/scripts/test_check_maquette_comments.py` falls until `check-maquette-comments.py --record`, while the
  guard itself exits 0.
- 2026-09-13 trap: `mutate.sh` refuses any dirty tree, untracked files included — red-against-the-engine runs on a
  detached checkout of the holds commit, the move committed first on the branch.
- 2026-09-13 b·1: `page_host.py`'s staged edits re-aimed to `window.__changeSetting` (harness/publish.ts), zero net lines.
- 2026-09-13 b·1: ESLint is not configured for `frontend/maquette/design` (all files ignored); its frontend gate is
  `tsc -b` + `vitest run` + the guards.
- 2026-09-13 ruling 65 (steward): b·2 Q1 `data-account` valueless (the registry dispatches on KEY presence —
  `Object.keys(node.dataset)`, `act(node.dataset[key] ?? "")`), four sites by scripted exact replacement; Q2
  entry.py → `window.__entry.signOut()`, fan-in `app/entry.ts` 3 → 4 = ceiling. A log that a RESUME, an amendment or
  a commit body CITES is kept until the merge; only uncited working logs are pruned at stand-down.
- 2026-09-13 steward address changed to `Orch : TM frontend [7977d1]`.
- 2026-09-13 auditor orders 24–26 (to RULINGS.md in-branch): 24 run.sh single phase-gate invocation (build once →
  contracts → oracle → re-aimed rules replayed → one verdict), after order 19's commit; 25 next contracts run at
  TM_HARNESS_JOBS=3 with vm_stat + vm.swapusage before/after (swap moved → back to 2); 26 no local `make check`
  before L13b's PR — CI's test job is the authority; pre-PR gate = make lint + full suite + --a11y + --compare +
  the pre-push pytest.
- 2026-09-13 series 2 of b·1 killed while still waiting on the mutex (nothing had run) and relaunched with the
  gate at TM_HARNESS_JOBS=3 and the memory readings (order 25).
- 2026-09-13 numbering (steward [7977d1]): 64 = RESUME-L13b.md is a NEW file (predecessor's handshake answer,
  RESUME.md is L13a's and dies at its gesture); 65 = b·2 `data-account` + cited-log retention; 66–68 = orders 24–26.
  Sequence confirmed: b·1 gate (JOBS=3 + memory log) → order 19 → order 24 → b·2.
- 2026-09-13 trap: reader-a's `mutate.sh` hung 46 min at 0 % CPU on `panel.py`; `heavy.sh`'s age-only stale-break
  freed the mutex while the served-copy lock stayed held, so a whole series was refused at the door in 1 s each —
  order 27 (ruling 69) is the repair. A killed mutate leaves its MUTATED build in /tmp/tm-refonte: the first step
  after it must rebuild, and `build-stamp.json`'s `commit`/`dirty` is read before trusting a count.
- 2026-09-13 b·1 mutations (verbs.ts, `registerVerb("x",` → `void ("x",`): secret → secret_acts 8 violations;
  to → settings 2; deletefield → settings 2; addfield → settings 1; cancelsetting → settings 3; save →
  settings_editing 4; reloadsettings → seeds_at_rest 1; restart → settings_editing 1; confirmrestart → settings 2;
  qsettings → page_host 3. `setting` → settings_editing only CRASHED (Playwright timeout on the panel input), so it
  was replayed against page_host.py + journey.py (`b01-mutation-setting-named.log`).
- 2026-09-13 b·1 gate: 23 rules (6 named) + 26 guards no violation, oracle no divergence, 268 s wall at JOBS=3;
  swap 124,19M and Swapouts 45904 unchanged before/at/after.
- 2026-09-13 trap: `run.sh`'s failure listing (`hits="$(… | grep … | head)"`) exited run.sh silently under
  pipefail when a fallen rule printed no known pattern — fixed in `108904b51`.
- 2026-09-13 b·1 `setting` replay: page_host.py FELL, named — « and a real tap on a setting opens THAT setting —
  paths:paths.torrent_complete_dir → {'open': False, …} »; journey.py does not catch it (no hold fell).
- 2026-09-13 ruling 70: « B-290's index reading is owed to phase b·9's R-L13-a/b/c when they bind to numbers » —
  no rule reads `history.state.__TSR_index`; b·3 takes it by a throwaway probe (`b03-tsr-index-probe.py`, never
  committed) before and after its move.
- 2026-09-13 TRAP FOR b·6/b·7: the tap registry answers the FIRST registered key in ATTRIBUTE order
  (`Object.keys(node.dataset)`), the engine the first matching BRANCH. A tile emits `data-tile`, `data-panel`,
  `data-mediasheet` in that order; the engine checks tile (selMode only, 2623) < mediasheet (2651) < panel
  (2763), so a tile opens the SHEET. Registering `panel` (b·7) before `mediasheet` in attribute order would make a
  tile open the PANEL instead — b·7 must reorder the emitters' attributes or dispatch by branch order, and say so.
- 2026-09-13 STANDING (operator): the machine restarts Monday 05:00. No gate, mutex run or push that would run past
  04:55; every commit pushed and `git ls-remote` = HEAD by 04:30; RESUME-L13b.md at a phase boundary with its state
  block current (`Agent : l13b 2` reads it first); tree clean, no process left; one line to the steward at 04:45.
- 2026-09-14 b·4: now-tab and arrivals card feet emit `data-take` / `data-resolution`; `.cfoot` died. `pipe`
  refused by check-state-ownership.py when moved to a feature (ruling 74) → phase b·10-ter. `manual` mutation
  crashed ident.py (null.click) → replayed: bugs.py « 8. manual search pre-filled → « None » ».
- 2026-09-14 trap: zsh does not word-split `$F`; a multi-file variable passed to ruff failed with exit 2 and
  pytest never ran while an old log showed « passed » — run such lists through `bash -c` or spell them out.
- 2026-09-14 b·5 holds: the follows list carries no incomplete series in acq-now-loaded — the completion is read
  from `followsheet-gaps` (Tintin). Red: panel.py 4 violations with the engine's sheetprim/standby/tmdb/complete branches deleted (b05-red.log); before: 14 rules no violation, panel.py 51 → 59.
- 2026-09-14 order 34 (ruling 76): the 05:00 reboot wiped `/private/tmp` — every earlier L13b log cited above
  (`b01-*` … `b05-red.log`, `order*-*`) is gone; gate logs now under `~/Library/Logs/tm-l13b/`.
- 2026-09-14 b·5 move: `installAcquisitionVerbs` in `app/feature-verbs.ts` measured app/ 140 > 138 on
  check-frame-domain → module-evaluation registration named in `app/panel-contributions.ts` (0 words);
  `askReplacement` refused by the vocabulary arm (« Replacement ») → `askBeforeReplace`. Comment baseline `read`
  418 → 420, legacy.js dated references 12 → 10.
- 2026-09-14 b·5 RE-AIMS: page_host.py `__referentiel.actionTake(first.t)` → a tap on that card's `[data-take]`;
  panel.py `panel.produce('more')` → a tap on `[data-more]` (`ebc53e4ea`) — no rule tapped the renamed opener.
- 2026-09-14 b·5 gate: 31 rules (16 named) + 26 guards no violation, oracle 87 × 34 no divergence (log
  `b05-gate.log` 10:15:59 > commit 09:53:19; ~22 min waiting on l13a-14); swap 0 / Swapouts 0 before and after.
- 2026-09-14 TRAP (ruling 77): bare rule names (`panel.py`) → `python3` « can't open file », exit 2 → eight
  « FELL — the rule exited 2 » over nothing (series #1, `void/`).
- 2026-09-14 TRAP (ruling 77-bis): heavy.sh stops the 8899 host its wrapped run started, and mutate.sh never
  started one → eight ERR_CONNECTION_REFUSED tracebacks, exit 1, « FELL » (series #2, `void2/`).
- 2026-09-14 b·5 mutations (series #3, host listening, 0 tracebacks): acqtab → page_host « a real tap on a tab
  opens THAT tab »; pill/fmode/sugmode → page_host's pill, display-mode and suggestion-mode taps; sheetprim/
  complete/tmdb → panel.py R56's three; standby → « and its tap closes the panel and says the run »; more →
  « the watch's panel offers its run »; journey → journey.py « the journey opens from the follow sheet, at an
  address of its own »; add → add_footer « adding a medium announces it ». confirmadd → replacement.py: no hold
  fell; replayed → add_footer.py « adding a medium announces it — … reached by the « replace » route », bugs.py « 10. a real add brings the screen's footer into being » (b05-mutation-confirmadd-replay.log).
