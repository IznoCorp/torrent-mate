# L13b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13b.md` (governs) and `RULINGS.md` (L13b appends from 64).

## STATE

- Branch `feat/maquette-l13b`, worktree `/Users/izno/dev/worktrees/wave-l13b`, stacked on L13a `37e54d0fd`;
  rebase onto `main` only on the steward's word (after #596's squash). Steward: `Orch : TM frontend [7977d1]`.
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13b`.
- Tooling landed: `701ae1aca`, `3023f2305`, `108904b51`, `63f6674a4` (see the ledger and rulings 66–69).
- b·1 DONE (`e3ae69b01`), b·2 DONE (`4f157ca9f`), b·3 DONE (`6c6245fbd`, rulings 70/70-bis),
  b·4 DONE (`bec2b0d5b`, rulings 73–74; `pipe` stays in the engine for the NEW phase b·10-ter).
- legacy.js non-blank: 3248. Surface-openers contract grep: 2 (journey, sheet=plus are b·5's).
- Next: b·5 (acquisition verbs) — its phase file carries ruling 73 b's line: `actionResolve` (act=add:N identify)
  and `actionTake` (sheetprim) die there with their last callers.
- Phase gate form (ruling 66): `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13b
  frontend/maquette/harness/run.sh --contracts --oracle <the phase's rules>` (~270 s).
- Mutations: `mutate.sh <verbs file> "t.replace('registerVerb(\"x\",', 'void (\"x\",')" <rules>`; a rule that
  only CRASHES is not a named fall — replay against another rule that taps the name (b·1 setting, b·4 manual).
- Locks: browser mutex (`sh scripts/heavy.sh --held`); tests lock `/private/tmp/tm-heavy-tests/holder`; own lock
  `/private/tmp/tm-heavy-l13b/holder` (npm ci, tsc -b, vitest run).
- Logs kept (cited): `/private/tmp/tm-l13b/b0[1-4]-*`, `order19-*`, `order24-*`, `order27-*`.
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
