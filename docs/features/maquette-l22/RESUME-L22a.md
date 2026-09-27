# L22a — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l22/BRIEF-L22a.md` (governs) and `RULINGS.md` (the lot's own, from 1).

## STATE

- Branch `feat/maquette-l22a`, worktree `/Users/izno/dev/worktrees/wave-l22a`, cut from `origin/main` `1c0dbea64`
  (the squash of #612: DESIGN and plan). Steward: the session named in your launch prompt (`Orch : TM frontend`, its
  reference changes with its process).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l22a`.
- Phases: `plan/INDEX.md` 1–14 (L22a); 15–27 are L22b's.
- DONE: 1 (572108fb8) · 2 (e2ebfd06a, R215) · 3 (1bb06de4f) · 4 (bd5e1904b) · 5 (41ec588c6+930458687, R207) ·
  6 (87ba2da4d+ec8b6f561, R208) · 7 (1076e2679+0498f72cb, R212) · midpoint (load) · 8 (ccb83058c, 8-bis 340cbb917,
  9a578c7a8, 038aeaa64, R206) · 9 (2eda1b035+fb2621788, R209) · 10 (92f3c3370+02a38bd02, R221) · 11 (92386365f+
  4cf87444e, R222) · 12 (822a4c1f4, R203 = R16 re-aimed) · 13 PART (the phase commit: the operator's rule « Suivis par
  défaut, puis le dernier onglet ouvert (mémoire locale) » — R202 red 4 FAIL, green, three mutations fell by name,
  `13-mutation-exprs.txt`; journey.py re-aimed green) · 13 CLOSED by « l22a 2 »: origin/main merged (9bfc83f2c),
  R175 onto « Suivis » (3a5164f39), gate 39 rules + 26 guards 0 failed, oracle exit 0 (none accepted), --a11y light 98.
  14 (736ee5ca6+b75a13bbb+0f2e32f72, R205) · RULINGS 9 (cd834db40): order 14-ter → 14-bis-a → 14-bis-b ·
  14-ter (594debc68+2 busy.py commits, R225; take path re-aimed: busy, actions, page_host; a11y light 98).
  NEXT: 14-bis-a (one_ladder/acq-card-rungs, requester_line, release_candidates, R47 Star Trek understood), then
  14-bis-b: re-apply `~/Library/Logs/tm-l22a/14b-move.patch` + `14b-now_holds_in_flight.py` (R224, red 5 FAIL
  seen), section readers; measure at opening, >15 = STOP. Then the close (full suite ONCE, after 14-bis-b).
- B-553/R223 are the repair train's (next row B-555, next rule R224); `--a11y` on every drawing gate, light at 98.
- Oracle: `oracle.py --accept` takes NO state names and rewrites the whole reference; each acceptance is its own
  commit naming the states and the mechanism. The « En cours » body (now-tab.tsx) is drawn beneath pwa-*, relay-*,
  signin*, startup and the acq-card-* states, so every change to it moves them together.
- Rule labels → numbers (bound at phase 1 on `origin/main` 1c0dbea64, highest R201): a R202 · b R203 · c R204 ·
  d R205 · e R206 · f R207 · g R208 · h R209 · i R210 · j R211 · k R212 · l R213 · m R214 · n R215 · o R216 ·
  p R217 · q R218 · r R219 · s R220 · t R221 · u R222.
- LOGS: `~/Library/Logs/tm-l22a/`. Mutex `sh scripts/heavy.sh --held`; own npm lock
  `/private/tmp/tm-heavy-l22a/holder`.
- GATE FORM: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l22a frontend/maquette/harness/run.sh
  --contracts --oracle <full rule paths>` — the only form that reads rule names.
- MUTATIONS: `sh scripts/mutate.sh <full path> "<expr>" frontend/maquette/harness/<rule>.py`; commit before; read the
  NAMED FAIL line and keep the EXPRESSION; « RULE CRASHED » / « RULE NOT FOUND » prove nothing.
- PUSH: `sh scripts/heavy.sh --class test l22a git push -u origin feat/maquette-l22a`, its own command from the
  worktree root, no `cd … &&`, no `HEAVY_LOCK=`; a refusal = STOP with its exact text.
  `tests/scripts/test_check_maquette_comments.py` alone before any push.
- Traps: `git grep plex` needs `-w` (« Duplex »); `git grep data-pipe` also finds `data-pipeline-*`; `journey.py`
  reads `/arrivals` through `ARRIVALS`; a scripted `str.replace` that matches nothing is a silent no-op — assert it.

## LEDGER (append-only)
- 2026-09-26 phase 1 — gate's first run: R75 `screen_addresses.py` « walking to the profile WRITES the address » fell
  (null `.click()` after a 300 ms wait) and passed on the re-run: a flake under load, not the phase's.
- 2026-09-26 phase 2 — the design tree has no eslint configuration: the gate is `tsc -b` + `vitest`.
- 2026-09-26 phase 3 — STOP on the rename tool; RULINGS 1 (auditor): exact quoted substitution in five rules.
- 2026-09-26 phase 6 — `app/engine-data.ts` prefetched the queue key with its own five-family projection; repaired in
  the phase commit (read whole), and the queue's answer named `AcquisitionQueue` in the contract.
- 2026-09-26 phase 6 — a gate lost `boot_order.py` to « BrowserType.launch: Timeout 180000ms » under load 4.3; re-run clean.
- 2026-09-26 midpoint suite (0498f72cb, `~/Library/Logs/tm-l22a/midpoint-suite.log`): 151 rules + 26 guards, one fall —
  entry.py, « Page.goto: Timeout 30000ms exceeded », no hold read, load 7.6 (5/15 min) while the steward's pre-push
  pytest ran outside the mutex. Re-read ALONE at 19:31 (mutex free, no pytest/chrome in ps, load 2.83):
  green (`midpoint-entry-alone.log`). Verdict: LOAD, not the code.
- 2026-09-26 phase 8 — CADENCE FAULT: phases 5–7 drew cards without running `--a11y`; the light ratchet stood at 234
  against 147 at phase 8's gate. RULINGS 4: repaired at the variants (8-bis, 340cbb917), ledger re-taken at 98. From
  now to the PR, `--a11y` on every phase gate that draws.
- 2026-09-26 phase 9 — back.py's R215 docstring paragraph, written in phase 2 by a `str.replace` whose anchor did not
  match, never landed (silent no-op); added in phase 9. Every scripted edit is asserted from here on.
- 2026-09-26 phase 9 — re-aimed out loud: R128 reads the blocked arrival in « À traiter »; R215 opens the screen from
  « À traiter »; acq-card-blocked and acq-card-no-identity stand on the « À traiter » tab.
- 2026-09-26 phase 13 — R175 (scroll_keeps_place.py) was left reading Lucky on « En cours » by phase 9, which moved
  every blocked card to « À traiter »; phase 9's gate did not run it. Re-aimed onto `?tab=todo`, its « fresh arrival »
  holds pass and its « return from the resolution » holds fall: « À traiter » is too short to leave posters loading.
- 2026-09-27 phase 13 — successor « l22a 2 »: the warm exits from « À traiter » already popped to `?tab=todo`; only the
  cold link fell (the floor opened the remembered tab), repaired in phase 14 by `landingTab()`.
- 2026-09-27 phase 14-bis exploration — paths_to_sheets.py « acq-add-results really draws rows — 0 » fell inside a
  35-rule run and passed ALONE on the clean tree (`14b-paths-alone.log`): load, not the phase.
- 2026-09-27 phase 14-bis-a — R47 (cards.py) fell on the clean tree: phase 10's Plex-match card, two stacked feet,
  poster cropped 51 % (bound 40 %); unshipped defect, repaired by RULINGS 10 (feet side by side). From now on
  `cards.py` runs in every gate that touches a card.
- 2026-09-27 phase 14-bis-b1 — RULINGS 12: Arrivées' « Ça coince » still offers « Résoudre → » on Top Chef, a step no
  pick unblocks (ruling 5's guard), while its panel now offers « Relancer » / « Abandonner ». R43 reads Acquisition's
  folder cards only; Arrivées is not redrawn — it dies in L22b (phase 25).
