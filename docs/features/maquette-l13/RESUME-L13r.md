# L13r — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l13/BRIEF-L13r.md` (governs) and `RULINGS.md` (L13r appends from 100).

## STATE

- Branch `feat/maquette-l13r`, worktree `/Users/izno/dev/worktrees/wave-l13r`, cut from L13b's PR head
  `fcaff976f` (#601). main `cdde26731` merged in at `9b81c5f49` (docs only, no conflict).
  Steward: the session named in your launch prompt. Head: `git log -1`; pushed: `git ls-remote`.
- Phases (ruling 101): r·1 → r·2 → r·3 (BEHAVIOUR) → r·4 (BEHAVIOUR) → [midpoint full suite] → r·5 the reference
  dies → r·6–r·13 contract names by family group (rulings 105–108) → r·14 the projection dies (ruling 109) → r·15 the file dies + full gate + PR.
  r·1 `12f3e242b`, r·2 `d997e7c59`, r·3 `4168932d6`, r·4 `688dab291`, R114 repair `3ddcd70d5`, r·5 `412b75075`,
  r·6 `86468f8b8` (+ `b9ee587a9`), r·7 `4fc8c0fe2`, r·8 `b187e68f7`, r·9 `4fb1b2418` (+ `f6393dcf6`), r·10 `e827267b6`,
  r·11 `e572a0708`, main 60c6d9b1d (L20 #603) merged `9e978aeaa` (+ `2864fb7c3`), r·12 `7238cd33b`, r·13 `9506bf881`
  (+ `3dcde3533`) — DONE.
- NEXT: r·14 `plan/phase-r14-the-projection-dies.md` — OPEN IT BY A MEASURE and one STOP D. `engine-shape.ts` has no
  product caller since r·13. The question the measure answers: `scripts/build-mock-seeds.py` reads the families for
  `seeded_families`/`projection_for`/`seed_of` (engine fixtures — do any seeded, unconverted families remain?),
  `file_for` (each converted family's seed FILE name) and `rejoined` (the `join` of converted seeds); `check-mock-seeds.py`
  imports it (`module.build()`, `rejoined()`, `file_for`, `converted_families`, the lossless arm l.283–308); CI path
  `ci.yml:103`. Then r·15 the file dies + PR. Sweep method (steward): reads, literals handed to the product, generic
  families, JS blocks, AND quoted one-letter keys kept in harness lists (`KEPT_PARTIAL` species). Frame-domain lib/ 28, app/ 121.
- OWED TO r·15: `legacy.js`'s `Object.assign(window, …)` publishes `SETTINGS_STATE`, `icons`, `settingId`, `select`,
  `cadenceFR`, `nextSearchFR`, `stLabel` — readers `settings.py`, `page_host.py` (SETTINGS_STATE/settingId, re-aimed
  at r·5), `audit.py`, `content.py` (the three vocabulary names) → re-aimed from their homes when the file dies;
  `applyState` (literal-key restore in `app/layers.ts`, ruling 102), `select`, `icons` (the engine's import).
  OWED TO THE PR BODY / docs PR (steward): the `decision.kind` enum demand (r·7); the instrument minors the steward
  filed (crash instead of FAIL under a shape mutation; vacuous holds: url_state, deck_verbs, audit, page_host, address).
- LOGS `~/Library/Logs/tm-l13r/`; mutex `sh scripts/heavy.sh --held`; tests lock `/private/tmp/tm-heavy-tests/holder`.
- GATE FORM: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13r frontend/maquette/harness/run.sh --contracts
  --oracle <full rule paths>` — the only form that reads rule names (rulings 66, 81, 92).
- MUTATIONS: `sh scripts/mutate.sh <full path> "<expr>" <rule paths…>`; commit before; read the NAMED FAIL line;
  « RULE CRASHED » / « RULE NOT FOUND » prove nothing (ruling 77). A mutate run over two rules can pass 600 s:
  launch it in the background and poll its log for `heavy: l13r done`.
- HOLD COUNTS need a host on 8899 (start it as `mutate.sh` does). Push: code push = suite ~14 min under the tests lock,
  never while the mutex is held; `test_check_maquette_comments.py` first. No register rows (ruling 85).
- Traps: zsh does not word-split a multi-word variable (a `$M` command prefix is exit 127); a detached checkout runs
  THAT head's run.sh; the tap registry answers the first registered key in ATTRIBUTE order; `stopPropagation` does not
  stop a listener BESIDE yours; `page.route` never sees a request the service worker answers; `rename-identifiers.py`
  refuses `{ name, type X }` imports (use `--properties`) and may have written files when it says « Nothing written ».
- Owed at r·15: `--a11y`, hold-counts `--compare` (baseline `taken_at_commit` re-pointed to main's sha in a copy),
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
- 2026-09-15 ruling 105: r·6 measured (25 families, 37 call sites, 28 cache-reading rules) and cut into r·6–r·11, one
  family group each; « the file dies » is r·12 (file moved). Earlier ledger lines' « r·7 » now read r·12.
- 2026-09-15 r·6 (ruling 105): the eight `$card` families left the projection; `QueueCard` = the contract's schema;
  13 typed sites from tsc's diagnostics replaced at line:column; `MediumCard` and the arrivals card take title,
  secondaryLine, reason, chip { tone, text }, withoutPoster (follows, suggestions and search build that shape);
  `window.__queue` typed. First gate `r06-gate.log` fell on `page_host.py` (crash: a multi-line JS block read
  `first.t` that the line grep missed) — re-aimed, amended; gate `r06-gate-2.log` on `86468f8b8`: 28 rules (12 named),
  26 guards, oracle no divergence. `r06-hold-counts.json`: the ten re-aimed rules at their baseline counts. Grouped
  mutation `r06-mutation-queue.log` (queueNow's lists back to `t`): eight fell by name; `url_state.py` did not — its
  journey subject falls back to the first follow BY DESIGN, so no queue mutation can fell it (the re-aim is proved by
  the typecheck only); `page_host.py` crashed (no verdict) → `b9ee587a9` optional-chains its click (zero net line),
  gate `r06-gate-3.log` green, mutation `r06-mutation-page_host.log` FAIL by name.
- 2026-09-15 r·7 (ruling 105): PENDING_DECISIONS, DECISIONS_REGLEES, PIPELINE left the projection; the arrivals' types
  are the contract's schemas; 47 typed sites replaced at line:column by the RECEIVING type's name (a type-aware
  version of the line:column script); `lastRunRows` takes the contract's steps. Harness sweep: zero readers. Gate
  `r07-gate.log`: 24 rules (6 named), 26 guards, oracle no divergence; `r07-hold-counts.json`: the six named at
  baseline. No re-aim, no mutation.
- 2026-09-15 r·7 backend demand (steward): `features/arrivals/resolution-cards.tsx`'s candidate card casts
  `decision.kind` to "movie" | "show" — the contract types `PendingDecision.kind` as a string; the backend owes an
  enum. A demand for the docs PR, not a product change.
- 2026-09-15 r·8 (ruling 105): FOLLOWS and INCOMPLETE left the projection; `Follow`/`IncompleteShow` are the contract's
  schemas through `lib/contract-schemas.ts` (fan-in: five features importing `contract/types.d.ts` directly — r·1's
  door precedent); 121 typed sites at line:column; `FollowSubject` for a panel's composed subject; 44 harness lines in
  18 rules re-aimed; `markup_anchors.py`'s two audit.py exemption lines follow the docstring. First gate `r08-gate.log`
  FELL (25 rules, oracle 70 divergences, the follows tab empty): `app/engine-data.ts` prefetched the follows under the
  same key through `toEngineShape<unknown>("FOLLOWS")`, invisible to tsc (probe `r08-probe-errors.log`); removed,
  amended. Gate `r08-gate-2.log` on `b187e68f7`: 37 rules (20 named), 26 guards, oracle no divergence;
  `r08-hold-counts.json`: 20 named at baseline. Mutations: `r08-mutation-follows.log` (`all()` back to t/k/st/own) —
  13 fell by name; `actions.py` fell by its bare `assert` on the paused count (line 70, the re-aimed read; an
  assert-style rule prints no FAIL line); `busy.py` and `follow_has_sheet.py` crashed ON the re-aimed reads
  (no verdict, ruling 77); `audit.py` did not fall — its vocabulary check only reports a movie wearing series words,
  so a follow with no kind reports nothing (vacuous under this mutation by design); `r08-mutation-incomplete.log`:
  `library_sort.py` fell by name.
- 2026-09-15 r·8 finding: `features/system/queries.ts` projects DISKS, INDEX, DEPENDENCIES, ERRORS, EXECUTIONS (and
  SCHEDULERS) through a generic `family` parameter — the ruling-105 measurement counted literal family strings only,
  so five families sit in no phase. For the steward.
- 2026-09-15 r·8 (steward's reading): the THREE mutate « RULE CRASHED » lines are actions.py (its bare `assert` on the
  re-aimed paused count — a fall), busy.py and follow_has_sheet.py (crashed ON the re-aimed reads, the read proved
  live); accepted with audit.py's vacuity as url_state's, filed as an instrument minor by the steward.
- 2026-09-15 ruling 106 (amended by order 38): the system families are a new r·11; the sheet is r·12, « the file
  dies » r·13 (files moved, INDEX, BRIEF, state block re-pointed). Ledger lines above keep the numbers they had.
- 2026-09-15 r·9 (ruling 105): SUGGESTIONS (both reads and the paging `after`), SEARCH, RELEASES left the projection;
  the contract's schemas through `lib/contract-schemas.ts`; `window.__suggestions` typed; 62 typed sites at
  line:column; the follow verb's slice takes `title`/`kind`; `emphasis` in the card markup, the panel converts to its
  own `e`. 8 harness lines in 5 rules re-aimed. Gate `r09-gate.log`: 24 rules (8 named), 26 guards, oracle no
  divergence; `r09-hold-counts.json`: the eight at baseline (add_footer 13 = r·3's +2). Mutations:
  `r09-mutation-suggestions.log` — follow_verb and producers FAIL by name, deck FELL by its exit verdict,
  deck_verbs did not fall (its reserve read is used for positions only, the re-aimed fields feed no hold);
  `r09-mutation-releases.log` — release_take_sentence did not fall: its premise compared the resolution with ""
  and passed on None, then left with no verdict → `f6393dcf6` (truthiness, same lines), gate `r09-gate-2.log` green,
  `r09-mutation-releases-2.log` FAIL by name.
- 2026-09-15 ruling 107: r·10 measured ≈ 18 and cut — r·10 settings + secrets, r·11 library + maintenance actions +
  account, r·12 every `Fact` family (system, JOURNAL, SCHEDULERS) with `Fact`'s keys in full words, r·13 the sheet, r·14
  the file dies (files moved, INDEX, BRIEF, state block re-pointed; dated and ledger lines keep their numbers).
- 2026-09-15 r·10 (ruling 107): SETTINGS and SECRETS left the projection; `SettingsTopic`/`Setting`/`Secret` are the
  contract's schemas (`Setting.topic` optional, flattened only); 50 typed sites at line:column; 35 harness lines in 7
  rules re-aimed. First gate `r10-gate.log` FELL on settings.py alone (a crash): the rule hands the product a literal
  `{f, c, n}` (line 478) that the read sweep could not see (`r10-settings-alone.log`); fixed, amended. Gate
  `r10-gate-2.log` on `e827267b6`: 23 rules (7 named), 26 guards, oracle no divergence; `r10-hold-counts.json`: the
  seven at baseline. Grouped mutation `r10-mutation-settings.log` (both reads back to the engine's keys): settings,
  settings_editing, page_host, redraw_entry FAIL by name; producers, secret_acts and seeds_at_rest crashed (the
  mutation empties the settings page the product draws from contract names; seeds_at_rest's crash is ON its re-aimed
  read `topic.settings`) — no verdict, ruling 77.
- 2026-09-15 r·11 (ruling 107): LIBRARY, CATS, MAINT_ACTIONS, ACCOUNT left the projection; `LibraryRow` (LibraryItem),
  `LibraryCategory`, `MaintenanceAction`, `Account` are the contract's schemas; 43 typed sites + the account's two
  `mail`; the library card markup's input in contract names. 9 harness lines in 6 rules re-aimed, audit2.py's `x.t`
  a follow read r·8 missed. Gate `r11-gate.log` on `e572a0708`: 23 rules (7 named), 26 guards, oracle no divergence;
  `r11-hold-counts.json`: the eight at baseline. Mutations: `r11-mutation-library.log` — content FAIL by name,
  filters RULE CRASHED (assert-style prose rule); `r11-mutation-actions.log` — producers FAIL by name, page_host did
  not fall (its action title is printed, compared by no hold); `r11-mutation-account.log` — address did not fall
  (with no address drawn, « every address drawn is the account's » holds over an empty set); `r11-mutation-follows-
  audit2.log` — audit2 FELL by its exit verdict.
- 2026-09-15 stand-down of `Agent : l13r 2` after r·11 (gauge 59 + r·12 ≈ 15 left no margin for r·12's opening STOP; the
  steward's call). SERVICES found projected through `useSystemRead` at the stand-down, in no ruling's list — r·12's
  measure says it.
- 2026-09-15 ruling 108 (+ amended): r·12 measured ≈ 13 at its opening (32 tsc diagnostics in 7 files on the trial rename;
  seven `useSystemRead` families + JOURNAL); the merge of main before its code; the projection entries stay to r·13.
- 2026-09-15 merge of main 60c6d9b1d (L20, #603) at `9e978aeaa`: 5 conflicts; r·7 re-applied to L20's `usePipelineState`,
  r·10 to `useBoundSetting`, r·5 to `run-screen.tsx`; fr.json and imports by union; `comment-references-baseline.json`
  re-recorded (no file above either side). Gate `merge-gate.log` FELL by name on `queued_by_hand.py` (R185, L20's, read
  `follow.t`, r·8's rename) → `2864fb7c3` re-aimed; gate `merge-gate-2.log`: 36 rules (21 named), 26 guards, oracle no
  divergence. Pushed 46ea8980c.
- 2026-09-15 r·12 (ruling 108): SERVICES, SCHEDULERS, DISKS, INDEX, DEPENDENCIES, ERRORS, JOURNAL left the projection;
  `Fact` died in `lib/engine-drawing.ts` (readers: the contract's schema); `FactRow` in full words; 14 literals at
  line:column (account, arrivals, maintenance, system page, L20's `locks.tsx`); `DeletionJournal` the contract's;
  `PipelineRun` died (EXECUTIONS reader-less since the merge). `machine.py` one cache read re-aimed (`tone`). Gate
  `r12-gate.log` on `7238cd33b`: 31 rules (12 named), 26 guards, oracle no divergence. `r12-hold-counts.json`: 11 at
  their counts, machine.py 92 → 90 = L20's removal of the runs tuple from `DERIVED` (two holds per tuple: the list found,
  the tone's word), not r·12. Mutation `r12-mutation-machine.log` (the re-aim reverted): five FAIL by name.
- 2026-09-15 ruling 109: r·13 measured ≈ 18–19 (tsc 22 on the trial typing + ~20 untyped sheet readers + the projection's
  apparatus) and cut — r·13 the sheet, r·14 the projection dies (new), r·15 the file dies (file moved, INDEX, BRIEF, state
  block re-pointed; dated and ledger lines keep their numbers).
- 2026-09-15 r·13 (ruling 109): SHEETS_RAW left the projection; `MediaSheet` the contract's schema typed first (the
  `Record` had hidden its readers), `MediaSheetFields` optional in contract names, `CatalogSeason` = `SeasonSummary`,
  the local episode shapes in number/title/airDate; 57 sites at tsc's line:column in three passes, two casts and
  mock-seeds' seasons by exact replacement. First gate `r13-gate.log` FELL by name on `priming.py` (f): its
  `KEPT_PARTIAL` kept the engine key `y` as a STRING (invisible to a read sweep) → `3dcde3533` (`year`, and the dead
  `key === 'y'` branch of `OPEN_CARRYING` removed). Gates `r13-gate-2.log` (36 rules, 15 named) and `r13-gate-3.log` on
  `3dcde3533` (priming): oracle no divergence. `r13-hold-counts.json`: 14 at baseline, screen_addresses 51 → 58 =
  L20's seven checks added by the merge (R187's run screen), not r·13. Mutation `r13-mutation-priming.log` (`y` back):
  (f) FAIL by name.
