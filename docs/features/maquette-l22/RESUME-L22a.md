# L22a — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l22/BRIEF-L22a.md` (governs) and `RULINGS.md` (the lot's own, from 1).

## STATE

- Branch `feat/maquette-l22a`, worktree `/Users/izno/dev/worktrees/wave-l22a`, cut from `origin/main` `1c0dbea64`
  (the squash of #612: DESIGN and plan). Steward: the session named in your launch prompt (`Orch : TM frontend`, its
  reference changes with its process).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l22a`.
- Phases: `plan/INDEX.md` 1–14 (L22a); 15–27 are L22b's.
- DONE: 1 (572108fb8) · 2 (e2ebfd06a, R215) · 3 (1bb06de4f, RULINGS 1) · 4 (bd5e1904b) · 5 (41ec588c6+930458687,
  R207, RULINGS 2) · 6 (87ba2da4d+ec8b6f561, R208) · 7 (1076e2679+0498f72cb, R212) · midpoint suite (load only) ·
  8 (ccb83058c, 8-bis 340cbb917, 9a578c7a8, 038aeaa64; R206; RULINGS 3, 4) · 9 (2eda1b035+fb2621788, R209, RULINGS 5) ·
  10 (92f3c3370+02a38bd02, R221, RULINGS 6) · 11 (92386365f+4cf87444e, R222, RULINGS 7) · 12 (822a4c1f4, R203 = R16
  re-aimed; no oracle divergence).
  NEXT: HELD by the steward (2026-09-26 21:1x) — phases 13 and 14 wait for the operator's word on ruling 10 and on
  « À récupérer » / « Rangé aujourd'hui » / « Cherché, rien trouvé » (nothing new is built on those three sections).
  Then the close: merge origin/main, bump, full suite + --a11y + --compare, pre-push pytest, PR READY.
- Numbering: B-553 and R223 are the repair train's; this lot's next register row is B-555, its next extra rule R224.
- `--a11y` runs on every phase gate that draws (RULINGS 4); the light ledger stands at 98.
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
