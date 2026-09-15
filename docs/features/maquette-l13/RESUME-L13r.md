# L13r — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13r.md` (governs) and `RULINGS.md` (L13r appends from 100).

## STATE

- Branch `feat/maquette-l13r`, worktree `/Users/izno/dev/worktrees/wave-l13r`, cut from L13b's PR head
  `fcaff976f` (#601). main `cdde26731` merged in at `9b81c5f49` (docs only, no conflict).
  Steward: the session named in your launch prompt (`Orch : TM frontend`, its reference changes).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l13r`.
- Phases (ruling 101): r·1 → r·2 → r·3 (BEHAVIOUR) → r·4 (BEHAVIOUR) → [midpoint full suite] → r·5 the reference
  dies → r·6 contract names (STOP D with a cut at its opening; never one phase) → r·7 the file dies + full gate + PR.
  r·1 `12f3e242b`, r·2 `d997e7c59`, r·3 `4168932d6`, r·4 `688dab291`, R114 repair `3ddcd70d5`, r·5 `412b75075` — DONE.
- MIDPOINT's one fall (`poster.py`, R114) REPAIRED (ledger): the rule held by accident until r·2.
- NEXT: r·6 (`plan/phase-r06-*.md`) — MEASURE at its opening (families, call sites per family, readers) and send ONE
  STOP D with a cut into sub-phases ≤ 15 each, one family group per commit. Frame-domain after r·5: lib/ 28, app/ 121.
- legacy.js non-blank: 1 600 at the cut, 1 274 r·1, 888 r·2, 663 r·3, 534 r·4, 493 r·5. `scripts/frontend_size_ledger.py`
  re-recorded DOWNWARD in every phase's commit.
- OWED TO r·7: `legacy.js`'s `Object.assign(window, …)` publishes `SETTINGS_STATE`, `icons`, `settingId`, `select`,
  `cadenceFR`, `nextSearchFR`, `stLabel` — readers `settings.py`, `page_host.py` (SETTINGS_STATE/settingId, re-aimed
  at r·5), `audit.py`, `content.py` (the three vocabulary names) → re-aimed from their homes when the file dies;
  `applyState` (literal-key restore in `app/layers.ts`, ruling 102), `select`, `icons` (the engine's import).
- LOGS: `~/Library/Logs/tm-l13r/`. Mutex `sh scripts/heavy.sh --held`; tests lock `/private/tmp/tm-heavy-tests/holder`;
  own lock `/private/tmp/tm-heavy-l13r/holder`.
- GATE FORM: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13r frontend/maquette/harness/run.sh --contracts
  --oracle <full rule paths>` — the only form that reads rule names (rulings 66, 81, 92).
- MUTATIONS: `sh scripts/mutate.sh <full path> "<expr>" <rule paths…>`; commit before; read the NAMED FAIL line;
  « RULE CRASHED » / « RULE NOT FOUND » prove nothing (ruling 77). A mutate run over two rules can pass 600 s:
  launch it in the background and poll its log for `heavy: l13r done`.
- HOLD COUNTS: `harness-hold-counts.py` needs a host on 8899 (start one as `mutate.sh` does, stop it after).
- Push: the pre-push hook is the branch's own; a docs-only push takes the fast path; a code push runs the suite
  (~14 min) under the tests lock. `tests/scripts/test_check_maquette_comments.py` alone before any push.
- Register: no rows during the wave (ruling 85) — ledger lines; the steward numbers rows at the close.
- Traps: zsh does not word-split a multi-word variable (a `$M` command prefix is exit 127); a detached checkout runs
  THAT head's run.sh; the tap registry answers the first registered key in ATTRIBUTE order; `stopPropagation` does not
  stop a listener BESIDE yours; a touch drag suppresses the click itself; `page.route` never sees a request the service
  worker answers; `rename-identifiers.py` refuses a `{ name, type X }` import as a shorthand property (use
  `--properties`) and may already have written other files when it says « Nothing written ».
- Owed at r·7: `--a11y`, hold-counts `--compare` (baseline `taken_at_commit` re-pointed to main's sha in a copy),
  `make lint`, merge main in, version bump above main's, PR READY (conversion: no §§; r·3's/r·4's behaviour said).

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
- 2026-09-15 R114 held by accident until r·2 (the service worker never registered under the withheld avatar):
  `page.route` never sees a request the worker answers; the worker registers on `load`; the engine's synchronous
  avatar, withheld, kept `load` from firing; since r·2 the avatar arrives with the account read. Repair
  `3ddcd70d5`: `service_workers="block"` in `poster.py`, said in its comment. Probe `r114-probe-head.log`, gate
  `r114-fix-gate.log` (19 rules, 1 named, oracle no divergence), mutation `r114-mutation-poster.log` (FAIL by name).
  The species goes to the README's traps at r·7 (steward).
- 2026-09-15 r·5 (ruling 104): `window.__referentiel` died (5 members, product read `icons` only); `icons` door in
  `lib/shell-doors.ts` filled by `app/shell.tsx`; nine hooks renamed to `useEngineDrawing` by the tool; slices →
  `features/<f>/types.ts` (account's deleted); `app/reference.d.ts`, `EngineQueue` and the reference-slice arm died
  (`lib/engine-queue.ts` keeps `QueueCard`, six readers — the opening measurement said the file was dead, corrected).
  493 non-blank. Frame-domain before lib/ 28, app/ 139; after lib/ 28, app/ 121 (ceiling lowered in the commit).
  Gate `r05-gate.log`: 22 rules (5 named), 26 guards, oracle no divergence; `r05-hold-counts.json`: the five
  re-aimed rules at their baseline counts (settings 68, page_host 44, pop 17, followed_sheet_act 12, season_family
  48). Mutations by name: `r05-mutation-pop-season_family.log`, `r05-mutation-followed_sheet_act.log`,
  `r05-mutation-settings-page_host.log`. Boundaries fan-in 4/4, cycles 0.
- 2026-09-15 r·5 tool finding: `scripts/rename-identifiers.py --root=…` refused `useAcquisitionReference` as a
  shorthand property in `import { useX, type Y }` (an import specifier, not an object) and printed « Nothing
  written, in any file » while four other files of that run WERE rewritten; re-run with `--properties`, the diff read
  and typechecked. For the steward (the tool is main's).
