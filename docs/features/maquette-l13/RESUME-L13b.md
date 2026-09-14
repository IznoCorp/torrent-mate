# L13b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13b.md` (governs) and `RULINGS.md` (L13b appends from 64).

## STATE

- Branch `feat/maquette-l13b`, worktree `/Users/izno/dev/worktrees/wave-l13b`, REBASED on main `304346145` (L13a
  squashed, #596). Steward: the session named in your launch prompt (`Orch : TM frontend`, its reference changes).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13b`.
- b·1 `e3ae69b01`… b·4 — see the ledger; b·5 DONE (move + re-aim, ruling 75); b·6 DONE (`c74362af1`, rulings 79,
  79-bis, 82; holds proved both ways: selection.py, pause_verb.py R132, follows.py). Gate: 43 rules (28 named) + 26 guards, 0 failed, oracle no divergence, gate: no violation on `e4a16d970` (log 12:41 > commit 12:35); the two earlier 28-named gates fell on R164 alone (B-498)..
- legacy.js non-blank: 2755. Surface-openers contract grep: 0. `FAN_IN_EXEMPT` keeps `features/acquisition/queries.ts`
  (the engine still reads `follows()` and `suggestions()`).
- NEXT: the MIDPOINT full suite on b·6's head (brief: after b·6, before b·7; its falls repaired in one
  `fix(maquette-l13b)` commit), THEN b·7 (frame verbs, `plan/phase-b07-frame-verbs.md`; the attribute-order trap
  below is b·7's, and the forwarder floor reaches 0 there — ruling 78).
- LOGS: `~/Library/Logs/tm-l13b/` (ruling 76). Mutex and tests lock stay under `/private/tmp`.
- GATE FORM (ruling 66): `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13b frontend/maquette/harness/run.sh
  --contracts --oracle <rules>` — the ONLY form that reads rule names (ruling 81: anything else is refused, exit 64).
- MUTATIONS: `mutate.sh <file> "t.replace('registerVerb(\"x\",', 'void (\"x\",')" frontend/maquette/harness/<rule>.py`
  — full paths (77), it starts the host itself (77-bis); read the NAMED `FAIL` line; « RULE CRASHED » proves nothing.
- A hold that can meet a blocked page prints its FAIL line at once (selection.py's lesson); a print-only rule
  cannot fall by name.
- Registration: module evaluation, named in `app/panel-contributions.ts` (feature-verbs.ts costs app/ domain words).
- Locks: browser mutex (`sh scripts/heavy.sh --held`); tests lock `/private/tmp/tm-heavy-tests/holder`; own lock
  `/private/tmp/tm-heavy-l13b/holder` (npm ci, tsc -b, vitest run).
- Push: the pre-push hook is the branch's own since order 35 (relative hooksPath); read its verdict, not its print.
- Owed: midpoint full suite (above); b·11 full suite with `--a11y`, `--compare`, `make lint`; no local `make check`
  (ruling 68); b·8: the swipe verbs' reaches through `window.openCard`/`window.collapseCard`. Machine restarts
  Monday 05:00: pushed by 04:30, line to the steward at 04:45.

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
- 2026-09-14 pre-push fall (ruling 78): test_check_markup_contracts.py forwarders « assert 4 >= 5 » — b·5 took
  acqtab/pill/fmode/sugmode out of the engine's `store.write({f: …dataset.x})` shape. MEASURED before the floor
  moved: a wrong `data-fmode="gird"` literal now passes the arm (exit 0, « 4 forwarded attribute(s) »).
  b·7 takes the last four; the arm's subject is decided then.
- 2026-09-14 REBASE: `git rebase --onto origin/main 37e54d0fd` (a plain rebase would replay L13a against its own
  squash) replayed 27 commits onto 304346145 with no stop; the comment baseline then read 420 against 422 (main's
  R176/R177 rule files) → `96a9b8f72`; the one `--force-with-lease` pushed 6774bdea2...96a9b8f72.
- 2026-09-14 TRAP: the pre-push hook runs pytest SILENTLY, then re-runs it to print on failure — the printed run
  read « 11414 passed » under a refusal; one retry passed all five checks. Read the verdict, not the print.
- OWED b·8 (ruling 79 b): the swipe verbs `pause`, `remove` and `del` reach `window.collapseCard?.()` — the
  gesture state's move takes that reach away.
- 2026-09-14 b·6 hold red #1 CRASHED (named nothing): with the engine's tile/selMode branch disabled, tile 0's
  tap opened the engine's panel, its scrim blocked the next pg.click, Playwright timed out → « RULE CRASHED »
  (77-bis working). The hold now prints its FAIL line right after the first tap.
- OWED b·8 (ruling 79-bis): `pause`, `remove` and `search-again` settle their swipe row through
  `window.openCard` and `window.collapseCard` (the library's `del` never collapsed).
- 2026-09-14 b·6 HOLDS (proved both ways, gate form): selection.py « a selection tap ticks the medium its tile
  names » (red: « On l'appelait Robin des Bois » not ticked); pause_verb.py R132 « a pending follow's « Chercher »
  says the search and the row comes back to rest » (red: « Chercher — Kyma » never said); follows.py's first named
  check, the search cross (red: filter kept, 0 rows of 14).
- 2026-09-14 TRAP (ruling 81): `run.sh --contracts <rule>` read NO name — « 0 named rule(s) », exit 0 — so two
  « green » steps ran the 18 contracts and not the hold; only `--contracts --oracle <rules>` reads names.
- 2026-09-14 TRAP: a disabled engine branch can leave a layer up that blocks the next pg.click → Playwright
  timeout → RULE CRASHED; a hold that can meet it prints its FAIL line at once. A print-only rule (follows.py
  before b·6) cannot fall by name; a bare-assert rule (actions.py) falls as a crash.
- 2026-09-14 TRAP: follows.py's hold clicked `[data-pill="all"]`; the « everything » pill's id is `tout` — the
  rule timed out green AND red alike. A hold is run green before its red is believed.
- 2026-09-14 b·6 move `c74362af1`: legacy.js 3060 → 2755; B-465 closes by grep (paintSelBar: nothing). The fan-in
  arm measured app/page-switch.ts at 5 > 4 → a `replaceAddress` door in lib/shell-doors.ts; check-state-ownership
  classifies `selectedMedia` (interface); the forwarder floor 4 → 3. Comment baseline `read` 422 → 424.
- 2026-09-14 TRAP: b·6's first gate fell on ONE GUARD, check-i18n-placeholders.py — it reads a shorthand
  `{ label, title }` as title only and says « renders {{label}} literally »; the keys written out → exit 0
  (`f6ac6d688`). A gate's « 0 rules fell » is not its verdict: read `gate:`.
- 2026-09-14 b·6 replays: cat, lmode, del (no hold fell in filters.py, gallery.py, remove_verb.py) and selmode,
  delsel (selection.py crashed) replayed against page_host.py, cards.py, audit2.py, virtual.py and
  selection_survives_the_tab.py — results in the next line.
- 2026-09-14 b·6 gate: 43 rules (28 named) + 26 guards, 0 failed, oracle no divergence, gate: no violation on `e4a16d970` (log 12:41 > commit 12:35); the two earlier 28-named gates fell on R164 alone (B-498).
- 2026-09-14 b·6 mutations: all twelve by name — lens → url_state « changing a dial writes the QUERY »; sort and setsort → library_sort; clear-search → page_host; selected-title → selection.py; clear-filter → follows.py; search-again → pause_verb.py; replays: cat and lmode → page_host, del → audit2 « deleting a medium: no confirmation », selmode → virtual.py and R164, delsel → virtual.py « the dialog names THOSE TWO ».
