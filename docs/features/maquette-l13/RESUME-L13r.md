# L13r — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13r.md` (governs) and `RULINGS.md` (L13r appends from 100).

## STATE

- Branch `feat/maquette-l13r`, worktree `/Users/izno/dev/worktrees/wave-l13r`, cut from L13b's PR head
  `fcaff976f` (#601). L13b squashed onto main as `5df76af33`, merged in at `e76d619aa` (tree unchanged).
  Steward: the session named in your launch prompt (`Orch : TM frontend`, its reference changes).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13r`.
- Phases (ruling 101): r·1 constants and helpers → r·2 served fixtures → r·3 the engine's product verbs (BEHAVIOUR)
  → r·4 the engine's frame verbs (BEHAVIOUR) → [midpoint full suite] → r·5 the reference dies → r·6 contract names
  (STOP D with a cut at its opening; never one phase) → r·7 the file dies + the full gate + the PR.
  r·1 DONE (`12f3e242b`), r·2 DONE (`d997e7c59`), r·3 DONE (`4168932d6`), r·4 DONE (`688dab291`); all pushed.
- MIDPOINT full suite (`midpoint-full-suite.log`): ONE fall, `poster.py` (R114) « the posters ACTUALLY landed once
  released — 9 decoded while withheld and 9 after ». Reproduced alone twice. BISECTED: green on r·1's head
  `0d313dd2a`, red on r·2's `c29a5c5c7` — r·2 introduced it; not the avatar install (mutation removing it: still
  red). Green on main's L13b head at 05:58 (`tm-steward/gesture-l13b-0529.log`, 5 holds). Suspect to read first: a
  request the page route no longer sees (a service worker, or an image loaded before the route) since r·2.
- NEXT (`Agent : l13r 2`): REPAIR R114's fall before r·5 (the midpoint's falls are the wave's), then r·5
  (`plan/phase-r05-reference-dies.md`). Frame-domain after r·4: lib/ 28, app/ 139.
- legacy.js non-blank: 1 600 at the cut, 1 274 after r·1, 888 after r·2, 663 after r·3, 534 after r·4 (55 of code). `scripts/frontend_size_ledger.py`
  re-recorded DOWNWARD in every phase's commit.
- OWED (r·1's republications): `legacy.js` publishes `stLabel`, `cadenceFR`, `nextSearchFR` on `window` (readers
  `audit.py`, `content.py` → re-aimed at r·7) and `__referentiel.baseTitle`/`dateFR` (readers `followed_sheet_act.py`,
  `pop.py`, `season_family.py` → re-aimed at r·5) from their new homes; r·3 adds `SETTINGS_STATE`/`settingId` (owed r·5);
  r·4 leaves `applyState` (literal-key restore in `app/layers.ts`), `select`, `icons` to r·7 (ruling 102).
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
- 2026-09-15 r·1: the 20 interface constants and 10 helpers left `legacy.js` (1 600 → 1 274) — homes
  `features/acquisition/follow-vocabulary.ts`, `features/arrivals/decision-vocabulary.ts`, `features/media/format.ts`,
  `lib/markup-text.ts`, the maintenance and quality pages, `features/system/fault.ts` (`SERVICES_PANNE` derived there,
  named state `system-outage`); 63 `fr.json` keys; `initialsOf`, `EP_SWATCH`, `MOIS`, `LIB_PAGE` died (grep over
  `design/src` and `harness/` 0 and 0). Frame-domain before and after lib/ 28, app/ 139. Gate `r01-gate.log`: 39 rules
  (24 named), 26 guards, oracle no divergence; `r01-hold-counts.json`: the 24 named rules' counts unchanged against
  `tm-l13b/l13b4-rebased-hold-counts.log` (19 counted, 5 prose verdicts read by exit). First gate fell on ONE guard, fan-in (three new tests importing
  `fr.json` made six readers): the tests now load the words through `lib/unit-words.ts`, the frame's own door.
- 2026-09-15 r·1 OWED to r·4 and r·6: the five republications named in the state block — the phase that kills the
  publication re-aims their readers (steward's condition, handshake answer to r·1).
- 2026-09-15 r·2 (ruling 100): the thirteen fixture families left `legacy.js` (1 274 → 888); `check-mock-seeds.py`
  classification 13 → 0 in the engine, 65 → 78 converted. `lib/clock.ts` (frozen by the boot with the layer's
  instant), `Suggestion.posterHighDefinition` (contract, seed join, types), `features/account/avatar.ts` through
  `lib/topbar-avatar.ts`; the status read exempted in `features/acquisition/live.ts`. Frame-domain before and after
  lib/ 28, app/ 139. Gate `r02-gate.log`: 38 rules (24 named), 26 guards, oracle no divergence; the first gate fell
  on `content.py` alone (the cache is reset by the next named state: the cron is now read while the follows tab is
  drawn). `r02-hold-counts.json`: 0 movement on the 24. Six re-aims, each seen to fall by name
  (`r02-mutation-<rule>.log`): machine, address, content, season_family, season_grab_unfollowed, mocks (R85).
- 2026-09-15 ruling 101: r·3 measured ~25 points and was cut, numbered — r·3 product verbs, r·4 frame verbs; the
  former r·4/r·5/r·6 are r·5/r·6/r·7 (files moved). The r·1 ledger's « owed to r·4 and r·6 » now reads r·5 and r·7.
- 2026-09-15 r·3 (ruling 101): the settings working state → `features/settings/state.ts` (reset →
  `harness/settings-reset.ts`), `addVerb` → `features/acquisition/add-label.ts`, the removal → `delete-dialog.ts`, the
  press → `lib/press-arbitration.ts` `installPanelPress()` (first at boot); `mountSearch`, `openSheet` and seven
  reader-less names died (888 → 663). Rule first: R96 (`add_footer.py`) +2 holds on the done verb, green on the engine,
  red with its branch mutated, red again on `add-label.ts` (`r03-mutation-add_footer.log`). Gate `r03-gate.log`: 35
  rules (19 named), 26 guards, oracle no divergence; holds: add_footer 11 → 13 (the two written), 18 others unchanged.
  The reference-slice arm refuses an empty corpus: `SettingsReference` declares the two names still published.
- 2026-09-15 r·4 (rulings 102, 103): `render` → `app/redraw.ts` behind the `redraw` door (18 product readers,
  `app/engine-redraw.ts`, two harness state tables); `state`, `store`, `view`, `render`, `toast`, `closeSheet`,
  `showSignIn` published by `harness/publish.ts`; `__navEchec` → `app/page-switch.ts`; `toastUndo` died; `applyState`
  stays. `check-state-ownership.py`: `notFound`, `sugCount`, `sugLoading` reclassified interface, `discover-feed.ts`'s
  dead exemption deleted, ceiling 7 → 0; `test_check_maquette_comments.py`'s debt floor 200 → 190 (199 measured).
  Gate `r04-gate.log`: 33 rules (20 named), 26 guards, oracle no divergence; `r04-hold-counts.json`: 0 movement.
- 2026-09-15 MIDPOINT: `poster.py` falls (state block); bisect logs `midpoint-poster-bisect-r01.log` (green),
  `midpoint-poster-bisect-r02.log` (red), `midpoint-poster-diag-avatar.log` (the avatar is not the cause). Stood down
  at 68 % measured; the repair is `Agent : l13r 2`'s first act.
