# L13b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13b.md` (governs) and `RULINGS.md` (L13b appends from 64).

## STATE

- Branch `feat/maquette-l13b`, worktree `/Users/izno/dev/worktrees/wave-l13b`, on main `a0253f34f` (L13a
  squashed #596; #599 rebased in, #600 merged in). Steward: the session named in your launch prompt (`Orch : TM frontend`, its reference changes).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13b` (push at every boundary under the tests lock).
- b·1–b·12 DONE, every gate green, every mutation named (commits and readings in the ledger). legacy.js 1 600
  non-blank; the engine's click listener dead; B-290 / B-397 / B-275 closed by b·9–b·10's rules.
- b·13 measured, NOT opened — STOP D (ruling 98, its six figures there).
- Pre-PR gate on the rebased code `6a3302eed`: --contracts 18 + 26 guards, FULL SUITE 135 rules + 26 guards « no
  violation », --a11y 0, hold-counts --compare no failure (movements in the ledger), make lint 0.
- Q5 = B (RULING 99): L13b CLOSES at b·12. b·13 VOID for L13b; the residue is L13r — The engine's residue, phases
  r·1–r·6 (`plan/phase-r01…r06-*.md`, INDEX « L13r — The engine's residue »), nothing of it executed on this branch.
- CLOSURE DONE (l13b 5, steward [31ca3c]): bump 0.98.94 + renames `69b39608d`; main `a0253f34f` MERGED in
  `a7640e97b` (plain push — a force-push is refused by the permission classifier); PR #601 READY; B-290/B-397/B-275
  `fixed #601`. NEXT, not an implementer's: the reader round on #601's head, the merge, the gesture, the docs PR.
- ZSH TRAP, three times this session: a multi-word variable is ONE argument in zsh, and macOS bash has no
  `mapfile` — build rule lists and file lists in Python or spell them out.
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
- Register rows: L13b owns B-512–B-529 (a reserved block, counted up from B-512; B-512 is R164);
  L20 writes from B-530.
- Owed: nothing of the phases. Machine restarts Monday 05:00: pushed by 04:30, line to the steward at 04:45.

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
  refused by check-state-ownership.py when moved to a feature (ruling 74) → phase b·12. `manual` mutation
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
- 2026-09-14 b·6 gate: 43 rules (28 named) + 26 guards, 0 failed, oracle no divergence, gate: no violation on `e4a16d970` (log 12:41 > commit 12:35); the two earlier 28-named gates fell on R164 alone (B-512).
- 2026-09-14 b·6 mutations: all twelve by name — lens → url_state « changing a dial writes the QUERY »; sort and setsort → library_sort; clear-search → page_host; selected-title → selection.py; clear-filter → follows.py; search-again → pause_verb.py; replays: cat and lmode → page_host, del → audit2 « deleting a medium: no confirmation », selmode → virtual.py and R164, delsel → virtual.py « the dialog names THOSE TWO ».
- 2026-09-14 R164's register row is B-512, not B-498: main's docs PR #597 (squash `4f242ecb3`) added B-498–B-511
  after this branch's base; L13b's rows are the reserved block B-512–B-529 (next B-513), L20 writes from B-530.
  `abd0ad88f` carries the first number in its message.
- 2026-09-14 MIDPOINT full suite: 128 rules (3 at a time, 17 min, swap 0 before and after), 1 failed; falls: touch.py (R55) « the long press opens the panel on the 5 surfaces — follows gallery » (25 holds, 1 violation), log midpoint-full-suite.log (owed). Stood down after it (gauge in the report).
- OWED l13b 3 (midpoint, ruling 84: not repaired here, the gauge read 60 %): R55's long press on the FOLLOWS GALLERY
  no longer opens the panel on b·6's head; the other four surfaces hold. UNMEASURED attribution — suspects: b·5 moved
  `fmode` (the gallery's switch) and b·6 moved the swipe/tile verbs; a follows tile's attributes vs the registry's
  first-registered-key rule (the attribute-order trap above) may now swallow the press. First step: R55 alone in
  the gate form on the pre-L13b base (37e54d0fd's tree on main 304346145) and on b·4/b·5/b·6 heads, then the fix
  proved both ways, in ONE `fix(maquette-l13b)` commit before b·7 opens.
- 2026-09-14 l13b 3 TRAP, and it voided a reading: a DETACHED CHECKOUT of an older head runs THAT
  tree's `run.sh`, which does not read rule names — the base reading came back « 18 rules », 0
  named, no oracle, exit 0 (ruling 81's trap, in a new disguise: the tooling that reads names is
  L13b's own first commit). The method that answers it: `touch.py` is byte-identical on every head
  of this branch (md5 1f1a9404), so the INSTRUMENT stays at the branch's head and only
  `frontend/maquette/design/src` is rolled back (`git checkout <sha> -- …`, tree dirty and said).
  Other rules then fall on the mixed tree — expected, and only the named rule's line is read.
- 2026-09-14 l13b 3 ATTRIBUTION of the midpoint fall: b·3 sources GREEN, b·4 GREEN, b·5
  `ca3682762` RED, head RED (logs `l13b3-r55-sources-b0{3,4,5}.log`, `l13b3-r55-head.log`). R55
  reproduces ALONE on the head — a real defect, not R164's intermittence.
- 2026-09-14 l13b 3 MECHANISM (throwaway probe, never committed): the press's click-swallower
  (`lib/press-arbitration.ts`) called `stopPropagation`, which stops a listener on another NODE and
  leaves every other listener on `document` running. That sufficed while a panel's action was
  answered by the engine's delegation in the BUBBLE phase (`legacy.js:2224`, no capture flag); the
  tap registry answers in CAPTURE (`lib/verbs.ts:92`), BESIDE the swallower, so from b·5 the lift
  fired acquisition's `sheetprim` (« Chercher maintenant », exactly under the thumb on a 204px
  tile) and the panel closed again — PRODUCED, its text in place, never open. Probe before:
  follows gallery `open: False` with « Kyma… Chercher maintenant » already rendered, library
  `open: True`; after: both True. The panel's absence of `data-open` with its content present is
  the signature to recognise next time.
- 2026-09-14 l13b 3 FIX `4210f72d5`: `stopImmediatePropagation` in that swallower. It also MEASURES
  the install order — it can only work if the swallower is registered before the registry, so the
  green reading is the proof of an order nobody had written down. Proved both ways: red on
  `8003a5a1c` twice (full suite, then alone), green after (`l13b3-fix-gate.log` 18:18 > commit
  18:13), mutation `stopImmediatePropagation()` → `stopPropagation()` fell by name
  (`l13b3-fix-mutation.log`, « FAIL the long press opens the panel on the 5 surfaces — follows
  gallery », the rule exited 1), file restored, tree clean.
- 2026-09-14 l13b 3 frontend gate before that commit (own lock): `npx tsc -b` clean, `npx vitest
  run` 114/114 in 8 files.
- 2026-09-14 ruling 85 (steward): no register row for a defect born and repaired inside the same
  unshipped branch — the ledger and the pull request's body carry it; the MECHANISM gets a dated
  amendment in `plan/phase-b05-acquisition-verbs.md` and a trap in `frontend/maquette/README.md`,
  because every later phase moves verbs into that same capture-phase registry.
- 2026-09-14 b·7 MEASURED against its own plan, three corrections (rulings 86, 86-bis): the engine's listener
  answered EIGHT keys, not seven; `phase` is server state by `check-state-ownership.py`'s table and `app/` is a
  COMPONENT bucket of that arm at a share ceiling of 0 (`COMPONENT_BUCKETS`, line 55) — so `phase` stays beside
  `pipe`, both until their conversions. `applyState` was moved to `app/layers.ts`, measured RED by the same arm (a
  write whose argument it cannot read is refused, not skipped) and moved back — ruling 16's move belongs to the
  phase that deletes the engine. `render()` has SEVEN product callers outside the delegation plus a not-found
  settle, so it stays to b·13 and the frame's verbs redraw through it.
- 2026-09-14 b·7 shapes that worked: the frame's six verbs in `app/frame-verbs.ts`, registered at module
  evaluation and named in `shell.tsx` (283 lines, far from its ceiling); the acquisition landing dial written BY
  ACQUISITION through a `resetLandingDial` door (a page's dial is not the frame's to name, and a forwarded patch is
  what the ownership arm refuses); the press opening through an `openAddressedPanel` door until b·8; `openDrawer`
  exported as a function because a named state opens the drawer without a tap.
- 2026-09-14 b·7 TRAP, and it is the day's most expensive: `stopPropagation` does not stop a listener BESIDE yours
  on the same node, and the tap registry (capture, `document`) now sits beside two such listeners. It cost two
  defects the gate caught and a third found earlier: (1) the press's click-swallower — R55, repaired in
  `4210f72d5`; (2) `lib/stacked-surface.ts`, which gives its entry back and REPLAYS the tap: its `stopPropagation`
  no longer reached the page verbs, so the switch ran twice, the second walk landed on the exit guard and the
  guard's push destroyed every forward entry (`history.length` 5 → 3, `url_state.py`'s topic gone) —
  `stopImmediatePropagation` in `cee7319df`; (3) the registry never called `preventDefault` on a LINK, which the
  engine's delegation did, so the drawer's `<a>` entries reloaded the document and the opening page replaced the
  destination (`drawer.py`, five falls). ASK OF EVERY VERB MOVED FROM NOW ON: who else answers this click, and in
  which phase?
- 2026-09-14 b·7 method note: the attribute-order trap must be re-asked for EVERY newly registered name, on every
  element that carries it — `panel` made four emitters' order load-bearing and the design named three; the fourth
  (`discover-cards.ts`) was found by walking every element carrying both keys.
- 2026-09-14 TRAP (my own, and it cost two repairs): reading a reference by rolling `design/src` back and then
  `git checkout HEAD -- frontend/maquette/design/src` DISCARDS uncommitted work in that tree — two fixes made
  between the gate and the reference reading were wiped silently and had to be re-applied. `mutate.sh` refuses a
  dirty tree for exactly this reason; a reference reading deserves the same rule: commit first.
- 2026-09-14 b·7 mutations, all named: `page` → url_state.py « changing page writes the PATH »; `panel` →
  cards.py R43/R44 « the body opened no panel » (panel.py did not fall, surfaces.py and actions.py CRASHED);
  `drawer` → selection_survives_the_tab.py « every page the drawer offers is walked to by a finger » (drawer.py
  and journey.py CRASHED); `stopImmediatePropagation` → `stopPropagation` → url_state.py's topic hold; the link's
  `preventDefault` removed → drawer.py's five entries. Logs `l13b3-b07-mutations{,2}.log`.
- 2026-09-14 b·7 figures: legacy.js 2755 → 2644 non-blank (ledger down), app/ frame-domain 138 unchanged, fan-in
  4/4, cycles 0, comment baseline `read` 424 → 425, vocabulary + « landing », forwarded-value arm and its tests
  deleted (B-513). Frontend gate: tsc -b clean, vitest 114/114; tests/scripts pair 127 passed.
- 2026-09-14 b·8 landed in three commits (the move, then the hold, then the hold RE-DRIVEN): the swipe's shape in
  `lib/swipe-arbitration.ts` with its thresholds named and identities read (`data-part`), Découvrir's two swipes in
  `features/acquisition/card-gestures.ts` beside the feed functions they call, the pull's indicator in
  `app/pull-indicator.ts` with the reset the harness drives. Ruling 59 repaired: the reset removes the two state
  classes instead of writing `className = "ptr"`, which erased every utility the markup paints — index.html's
  comment amended in the same commit.
- 2026-09-14 b·8 MEASURED, and it is ruling 88's first catch: the engine's drag guard said `stopPropagation` and
  was registered before the tap registry, so since the registry began the click ending a drag fired the verb under
  the finger. `stopImmediatePropagation` + installed first is the repair.
- 2026-09-14 b·8 TRAP, the day's second expensive one: AFTER A TOUCH DRAG THE BROWSER SUPPRESSES THE CLICK ITSELF
  (the engine's own comment said so, and I wrote the hold with touch anyway). The hold passed, then stayed green
  under BOTH mutations of the mechanism it was written for — a hold that measures the browser's suppression rather
  than the guard. Re-driven with a MOUSE, it falls by name on both. Ask of every gesture hold: does the browser
  deliver the event this hold reads, or does it swallow it for its own reasons?
- 2026-09-14 b·8 the phase file's own proof was wrong twice: the travel threshold LOWERED to 0 is unobservable
  (the axis dead zone is 6px, so a committed drag has always travelled more than 4), and the mutation that bites
  is the threshold raised out of reach; and B-337's hold already existed (`pause_verb.py` hold 4), so the phase
  keeps it green rather than writing it. Both said in the phase's amendment.
- 2026-09-14 b·8 figures: five of the seven `window` gesture getters were read by NO rule (measured file by file)
  and died with the `defineProperties` block, which does not go empty — `store` and `state` stay. `openCard` and
  `swallowClick` are published from their new owners, so NO rule was re-aimed. Vocabulary + five words (degree,
  guard, indicator, opacity, travel — the last two measured after the constants were named for what they are).
  Guards: state-ownership clean, frame-domain app/ 138 unchanged, boundaries clean, markup-contracts clean,
  no-french 0, comment baseline 425 → 426. tsc -b + vitest 114/114.
- 2026-09-14 b·8 mutations: `stopImmediatePropagation` → `stopPropagation` and `DRAG_TRAVEL_PIXELS` → 100000 both
  fell by name on press.py's new hold (« the click that ends a drag opens no panel »); the deck binding removed
  (`deck/card` → `no-such-part`) fell deck.py by exit code (ruling 49), unnamed. Logs
  `l13b3-b08-mutations{,2,3}.log`; the two first attempts (threshold → 0, and the touch-driven hold) are the
  findings above.
- 2026-09-14 b·9 RED READINGS (logs `l13b3-b09-r188-red3.log`, `l13b3-b09-r189-red3.log`): R188 — `take`,
  `journey`, `releases` and `profile` pop the panel's entry before the arrival pushes (length/index unchanged),
  `mediasheet` pushes correctly but no opener reopens the panel on the way back; 9 violations over 16 holds.
  R189 — three edits through the panel's own commit button pushed FIVE entries (6/4 → 11/9); « one Back closes
  it » PASSES, and that half alone proves nothing because the first Back's own redraw closes the panel.
- 2026-09-14 b·9 TWO INSTRUMENT TRAPS, both paid for and both written into the rules: a subject SCAN that opens
  and closes a panel per candidate writes history, and without a reset before the reading four of R188's five
  openers PASSED on a ladder the scan had left one entry deep — a green accident. And R189 first drove
  `window.__changeSetting`, which files a pending edit WITHOUT re-producing the panel: it passed on the only
  path that cannot stack an entry. A hold must drive what the defect travels through, and be run green before
  its red is believed — twice in one phase, from two directions.
- 2026-09-14 l13b 3 stood down here: gauge read before the push, everything on disk and pushed, tree clean,
  nothing running, working logs pruned and the cited ones kept (ruling 65).
- 2026-09-14 l13b 4 b·9: exits.py (R103) reversal = `close_then_wait_sites()`, a source read of design/src naming
  file:line for any `setTimeout` after `.close(`/`bridge.back(`/`.rewind(` in the same verb or any bare 240/260 ms
  wait; red on exactly the nine of ruling 90 a (`l13b4-b09-r103-red.log`).
- 2026-09-14 l13b 4 b·9 MOVE `57cef9fb1`: sheet entry `{ layer, kind, subject, openedOn }` (`layerEntry`,
  `panelRecord`, `layerRecordOf` in lib/navigation-entry.ts); BACK onto a recorded sheet entry reopens when the
  store's page == openedOn, else steps over; closing an open sheet onto a recorded entry reopens the one under it
  (journey over follow); `isOnItsOwnEntry` in panel-host makes a same-kind-and-subject produce write no entry;
  the screens door closes the panel with `close(true)` in go()'s commit (`leavePanel`); `screens.profile`/`add`
  take `replace` (profile from the release screen, manual). Ladder before/after: the two route-to-route leaves
  stay [list, destination] — the pop+push became one REPLACE.
- 2026-09-14 l13b 4 b·9 gate on `57cef9fb1`: 35 named, 1 fall journey.py « one Back closes it — open=True » —
  the journey now opens OVER the follow sheet; re-aimed out loud in `0bceb9578` (Back reopens panel=follow);
  re-gate 22 rules (4 named) + 26 guards 0 failed, no divergence (`l13b4-b09-gate2.log`), swap 0.
- 2026-09-14 l13b 4 b·9 mutations (`l13b4-b09-mutations.log`), all named: close(true) → close() → R188 pushes/Back
  on mediasheet, releases, profile; the entry read removed → R189 « 6/4 -> 11/9 »; a 260 ms wait restored on
  releases → R103 « features/releases/verbs.ts:93 »; take's close → close(true) → R188 « take acts and its panel's
  entry unwinds — 5/3 -> 5/3 »; the same-page reopen removed → R188 Back ×1 on the three screens. The no-reopen
  mutation does not fell journey (that path reopens through the ladder's rank branch, which R188's journey reads).
- 2026-09-14 TRAP (ruling 92): the first b·9 gate passed 35 paths as ONE zsh word; run.sh's `basename` check read the
  last path (`said_and_done.py`, which exists), ran 1 named rule and printed « gate: no violation ». Repaired in
  `b64ae8f76`, red first.
- 2026-09-14 order 38 (ruling 93): 73 references renamed in 21 files (`b·11` → `b·13` first, then the two
  inserted phases), three phase files git-moved, R-b10bis-N labels → R-b11-N; `grep -rc 'b·10-bis\|b·10-ter'
  docs/features/maquette-l13/` → 0.
- 2026-09-14 l13b 4 b·10: R190 red on `d027a8d0b` (`l13b4-b10-r190-red.log`) — « return is DRAWN — pseudo-elements
  seen: [] »; B-275's half and the two reduce halves were already green (b·9 made the reopening). Move `b1c3c602d`;
  gate `l13b4-b10-gate.log` 34 rules (16 named) + 26 guards, 0 failed, no divergence. Mutations
  (`l13b4-b10-mutations.log`): the reverse animation → `none` fell « return is DRAWN » (only root and tab-bar
  pseudo-elements seen); the transition removed from the ladder fell « seen: [] »; reduce halves green under both.
  The rank-branch reopening (a panel closed over a panel) is deliberately NOT drawn.
- 2026-09-15 l13b 4 b·11 red on `397758dc4` (`l13b4-b11-red.log`): R191 only the delete walk (the five titles pass on the
  engine, seed == copy); R193 only « the panel follows the answer »; R192 exactly six titles. Silo is the OTHER way:
  served four seasons (S4 « à venir »), engine three.
- 2026-09-15 l13b 4 b·11 MOVE `09bd737de`: contract `readLibraryMembership` { inLibrary, rows, incomplete, ids }
  (`rows` keeps the removal dialog's « Doctor Who » count), `lib/membership.ts`, `lib/season-rows.ts` (query +
  `seasonsHeld` out of features/media); knownMedium → `heldMedium` (followed or served membership, « not yet » while it
  lands); the panel's season summary takes the sheet's conventions AND the sheet's `possede` (membership would make
  American Dad! diverge: not in the library seed, its sheet holds its episodes); `window.__mocks.seasons()` (served
  rows by identity) and `seasonFamily()` (the seed); legacy.js 2284 → 1643.
- 2026-09-15 l13b 4 b·11 first gate: 16 falls (`l13b4-b11-gate.log`). Causes, all mine and repaired: followFacts
  produced before membership/incomplete landed (sync produce path skips `needs`); a delete only INVALIDATED the
  membership (a producer reads getQueryData synchronously) → removeQueries; seasonsHeld counted duplicate episode
  numbers (Dark Matter 18/13) → a Set; the cold wait never asked for the seasons; the accessor looked one title up
  (Silo's episodes live under « Silo (2023) »); the live-relay arm wanted a refresh rule for the new address;
  compare-contracts regenerated `docs/reference/frontend-backend-demands.md` (generated, not hand-edited).
- 2026-09-15 TRAP, OLDER THAN b·11 and found by its gate: the removal dialog's buttons carried `data-toast`; since the
  toast verb moved into the tap registry (capture, document, stopPropagation) the click never reached React's
  `onClick`, so « Supprimer » confirmed nothing — `virtual.py` « confirming removes THOSE TWO » was the first rule to
  run it since. Repaired in `937cee0f0` (the confirmation shows its message from `run`); no register row (ruling 85).
  ASK OF EVERY DESCRIPTOR: does a control carry BOTH a registered verb key and an onClick?
- 2026-09-15 l13b 4 b·11 second gate (`l13b4-b11-gate2.log`) lost 7 contract rules to ERR_CONNECTION_REFUSED (the repair
  train killed the 8899 host mid-run); they passed on the next run. Holds re-aimed: busy/queued_ask_mark/season_grab
  a hole is owned > 0 && owned < aired (House of the Dragon, held by nobody, draws no shortfall);
  season_grab_unfollowed's count reads `seasonFamily()`.
- 2026-09-15 l13b 4 b·11 mutations (`l13b4-b11-mutations.log`), all named: inLibrary → true → R191 « Kyma … says NOT in
  the library » + the delete walk; seasons → a constant → R192 on nine series, Silo named; incomplete → [] → R193 both
  halves; the dialog's data-toast put back → virtual.py « confirming removes THOSE TWO ». TRAP: an uncommitted doc line
  made mutate.sh refuse all four at the door (exit 1, no FAIL line) — `git status` before a series.
- 2026-09-15 l13b 4 b·12 red on `86ccb19fa` (`l13b4-b12-red.log`): arrivals.py « the status read answers None » ×3 —
  the status read carried no `state` at all. Move `0fd43802b`: L20's `state` verbatim, `pipe` verb in arrivals,
  `data-retry` frame verb, the engine's click listener deleted whole (1643 → 1600), `window.__pipeline`.
- 2026-09-15 l13b 4 b·12 gate (`l13b4-b12-gate.log`): 3 falls, attributed — busy.py and season_grab.py read the status
  query's CACHE on pages where no surface observes it (None), queued_ask_mark.py still read the dead store key;
  re-aimed to the layer's answer (`7d12186c2`); re-gate 21 (4 named) green, no divergence.
- 2026-09-15 l13b 4 b·12 mutations: the verb's layer call removed → arrivals.py six holds by name; the retry verb
  emptied → « NO RULE FELL » (`l13b4-b12-mutations.log`) — a verb born without a hold — so R90 gained « arr-error's
  « Réessayer » asks every active read again » (`50c42e7e0`), green (`l13b4-b12-gate3.log`), then red by name under the
  same mutation (« active answers 1 -> 1 », `l13b4-b12-mutations2.log`).
- 2026-09-15 TRAP: the PreToolUse hook that guards network commands matches the word « fetch » anywhere in a Bash
  command, heredoc text included, and blocks the whole command — write such an edit to a scratchpad .py file.
- 2026-09-15 TRAP (order 36, steward [31ca3c]): a turn was ended on a background gate; a long run is waited for INSIDE
  the tool call (a bounded loop polling the log for « heavy: l13b done »), never a turn ended on it.
- 2026-09-15 l13b 4 full suite on 033f7b301: two deterministic falls, attributed and repaired — mouse.py (b·8: the guard's
  `stopImmediatePropagation` in document capture blinded the rule's own document listener; re-aimed to window capture,
  defaultPrevented read after the dispatch, `5bea5ffe1`) and R157 acted_surface_redraws.py (b·11: served season rows
  make a follow nobody holds offer the season act; the subject scans now take a follow whose season family seed holds
  a hole, `7db042da1` + `6a3302eed`); pwa.py fell under the compare's load only and passed alone. The baseline's two
  drops (shell 4→3, message_above_harness 3→2) were L13a's (a·17-bis removed one check each) and vanished once main's
  re-recorded baseline came in with the rebase.
- 2026-09-15 l13b 4 REBASE onto 72712bb51: conflicts only in BUGS.md (row blocks — main's B-498–B-511/B-530 kept, L13b's
  B-512/B-513 inserted in order), frontend/maquette/README.md (main's directive trap block kept, L13b's three traps added
  as one-line rules) and docs/features/maquette-l13/BRIEF-L13a-bis.md (deleted on main, kept deleted). Code diff against
  the pre-rebase tip = main's own files only. The pre-push pytest then refused the comment floor (read 437 → 438 from
  main's release_candidates.py) — `2096e5047`.
- 2026-09-15 hold-counts on the rebased code (`l13b4-rebased-hold-counts.log`): arrivals 24→27, decision 24→26, exits
  18→19, gestures 14→18 (main's), logout 8→10, panel 51→59, pause_verb 9→11, press 15→17, settings 65→68,
  state_surfaces 31→32, take 9→11; NEW follow_seasons 12, incomplete_served 5, ladder_entries 15, library_membership 8,
  panel_return 6, redraw_entry 4, release_candidates 4 (main's). No fall.
- 2026-09-15 TRAP: `--compare` is not a run.sh flag; it is `scripts/harness-hold-counts.py --compare
  frontend/maquette/hold-counts-baseline.json`, and it needs the 8899 host up (start and stop it inside the wrapper).
- 2026-09-15 l13b 4, the auditor's reading: the two re-aims of the full suite are INSTRUMENT minors — the rules read
  wrongly, no product defect. b·8 (mouse.py): its own document-capture listener sat beside the guard that stops the
  click immediately, so it read an empty list; b·11 (R157): its subject scans took a follow nobody holds, whose season
  ask rightly absorbs nothing. Mutations on `1cb0a2dc1` (`l13b4-reaim-mutations.log`): the guard's preventDefault +
  stopImmediatePropagation removed → mouse.py « a library row, drag right : click swallowed False », « drag left : click
  swallowed False » (the rule exits 1); the season ask absorbing nothing → R157 « the panel the grab was pressed ON has
  moved … — 0 → 0 mark(s) » and « the panel was redrawn by the act … — texts AGREE ».

