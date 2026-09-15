# L13 — The engine's residue · PLAN

Design: `docs/features/maquette-l13/DESIGN.md`. Contract:
`docs/reference/frontend-architecture.md` § 4, entry `#### L13 — The engine's residue`.
**Every figure this plan relies on is in the design, with its command; the plan repeats none.**

---

## THE CUT, AND HOW THIS FILE ABSORBS THE RULING

The design's § 1 recommends **three sub-lots — L13a (conversion), L13b and L13c (behaviour)** — each a
wave of its own, with its own branch, squash, reader round and Mac walk, in that fixed order. The
operator RULED B on 2026-09-13 (decision round; ruling 27 of `RULINGS.md`).

- **Ruled B (three sub-lots)**: each table below is one wave; its pull request is its
  STOP C. **L13b opens STACKED on L13a's final head (auditor's order 7, 2026-09-13) and is rebased onto `main`
  after L13a's squash; L13c opens the same way on L13b's.** A full suite runs at each sub-lot's MIDPOINT
  (after b·6, after c·5) beside the last phase's (auditor's order 5, 2026-09-13).
- **If the ruling is A (one wave)**: the three tables are one, the phases keep their numbers
  (`a·1` … `c·9`), there is one STOP C at the end. **No phase file changes.**

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into the
next one. Stopping to announce « phase N done » is the failure mode L12, L14, L19, L20 and L21 each
wrote this paragraph to prevent, and it is written HERE because the chat gets compacted and this file
does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of
continuing? » If the answer is yes, the next phase exists, and none of the STOPs below is the reason,
**continue**. The only permitted halts:

- **STOP B** — the oracle diverging on a state the phase did not touch.
- **STOP C** — the pull request (one per sub-lot under B).
- **STOP D** — a measurement that contradicts a home the design decided (§ 3). The phase re-takes its
  own figures before it moves anything; a figure that no longer supports the home is reported to the
  steward with the command, and the phase does not improvise a new home.
- **STOP E (L13b only)** — L13b phase 9 does not open before the operator has read the design's
  D-L13-1 (§ 8). Phases 1–8 do not wait for it. **Ruled 2026-09-13 (A): the operator ratified
  D-L13-1 as written** — a layer left for an arrival keeps its entry and Back reopens it; a redraw
  replaces. STOP E is lifted for b·9. Nothing changes in L13a: its conversions keep both shapes
  exactly as they are, byte for byte.

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## Why thirty-nine phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says « commit
before the mutation »), and its gate is the contracts tier plus the oracle — minutes, not the full suite.
The full gate runs three times in the whole lot: before each sub-lot's pull request (a·19, b·13, c·9).

The count follows from two rules, not from appetite. One kind of change per phase means a verb move and
a timer removal cannot share a commit; and one surface per conversion phase (D-L07-7) means an oracle
divergence names its surface. Merged further, a divergence would have two candidate causes, which is the
unattributable result « surface by surface » exists to avoid.

**Phases that are a single mechanical commit with no new rule**: a·4, a·5, a·6, a·12, a·15, a·17, a·18,
a·19, b·3, b·7, b·13. **Phases that write a rule first**: b·1, b·2, b·4, b·5, b·6, b·8, b·9, b·10 and all
of L13c. The rest of L13a are conversions whose proof is the oracle and the unchanged hold counts.

---

## The rule that governs every phase

**One kind of change per phase, and the phase says which.**

- **A CONVERSION phase** (all of L13a): **the oracle and the hold counts unchanged.** Read
  `python3 scripts/harness-hold-counts.py --compare` with **`failed` FIRST** (B-291 — the baseline is
  never re-recorded while a rule fails), then the per-rule movement: none is the expected reading. A
  rule RE-AIMED in the phase keeps its count and says so in its docstring; a re-aim is said out loud in
  the commit body, never slipped in. The oracle: zero divergence on every state.
- **A BEHAVIOUR phase** (L13b, L13c): **the rule FIRST, seen RED against the engine** while the
  engine's branch still exists — the strongest form, no mutation needed — then the move, then the
  same rule green with its holds counted, then a mutation that fells it, named. Where the engine's
  branch no longer exists, the rule is mutation-tested at the moment it is written. The oracle may
  diverge ONLY on the states the phase names, each accepted with its reason (D8).

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` — by
hand leaves the served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD (B-273): a
guard's exit code is read by hand.

**The engine only SHRINKS.** Every phase that touches `legacy.js` subtracts and re-records
`scripts/frontend_size_ledger.py` DOWNWARD in the same commit. The one addition allowed is a verb the
design names (`drivenWithoutHistory`, a·1), inside a phase that subtracts far more.

**Guards and baselines die in the phase that kills what they read** — never in a closing sweep.

**Every heavy run is wrapped.** The shared lock for anything touching the one served copy or the 8899
host: `HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh l13 <command>`, announced to the
steward one line before and one after. The wave's own lock for everything else heavy:
`HEAVY_LOCK=/private/tmp/tm-heavy-l13/holder HEAVY_FREE_FLOOR_MB=2560 PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh l13 <command>`.
Output to a FILE, exit code read in the same call, **never `| tail -N` on a long gate**. Kill what is
started, prove it with `ps`.

**Amended 2026-09-13 by the office's three precisions** (`docs/features/maquette-l13/BRIEF-L13a.md`, « Method »),
and they make the two commands above VOID where they differ. **Locks by class, never by a floor set in
the environment**: anything touching the served copy or the 8899 host runs
`TM_HARNESS_JOBS=2 sh scripts/heavy.sh --class browser <wave> <command>`, announced one line before and one
after; every pytest, `make check` and `git push` runs under the ONE tests lock every wave shares,
`HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder PYTEST_XDIST_AUTO_NUM_WORKERS=2 sh scripts/heavy.sh --class test <wave> <command>`;
`npm ci` and a build into the worktree's own `dist/` keep the wave's own lock. **A phase's gate is the
contracts tier plus the oracle**; the full suite, `--a11y`, `harness-hold-counts.py --compare` and
`make check` run once per sub-lot, before its push. **The « In flight » row** is written when the pull
request opens and returns to « None » in the sub-lot's last commit before the merge.

**Never `cd` into `frontend/maquette/design/src`** (B-384) — absolute paths from the worktree root.
**Documents are added BY FILE**, never a folder (B-304).

**Rule labels (R-L13-a…) are LABELS.** The phase that writes a rule re-takes
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against `origin/main`
and binds the label to the next free number then.

---

## L13a — What moves unchanged (CONVERSION)

| # | Phase | What it lands | Deletes | Re-aims | Register |
| --- | --- | --- | --- | --- | --- |
| a·1 | [The harness module](phase-a01-harness-module.md) | `design/src/harness/`: `drive.ts`, `states/<surface>.ts`, `panel.tsx`, `index.ts` | `engine/states.js`; `__go`/`__states`/`__reset`/harness panel from the engine; the ledger's `states.js` entry | `states.py`, rules reading `applyState(`/`state.` | B-352 |
| a·2 | [The seams become imports](phase-a02-seams-become-imports.md) | `harness/publish.ts`; 19 names imported; `__servedIdentity` as a JSON element; `__mocks` import | 153 product `window.__` reads | `identity.py`, `outbox.py` wording | — |
| a·3 | [The ladder's handler](phase-a03-ladder-handler.md) | `app/layers.ts`, `app/page-switch.ts`, `app/addressed-panels.ts`; the sheet a rung | the handler, page switch and `REOPEN` from the engine; `app/layer-registry.ts` | `drawer.py`, `exits.py` (`__layers`) | — |
| a·4 | [The boot](phase-a04-boot.md) | `app/arrival.ts` | `__startEngine`, `world`, `adoptWorld`, `__releasePage` | `boot_order.py` BOOT_STEPS, `bridge.py` (f′) | — |
| a·5 | [What nobody reaches](phase-a05-dead-code.md) | — | `#screen` and its readers, the mount placement, 4 dead branches, `sheetSeasonsHTML`/`epState`/`seasonsOf`, `quota` | 8 harness readers of `#screen` | B-232 |
| a·6 | [The identity demand](phase-a06-identity-contract.md) | `ids`/`poster` on 7 list schemas, `MediaSheet.title`; types, seeds, demands regenerated | — | — | — |
| a·7 | [Layout primitives](phase-a07-layout-primitives.md) | `.screen.open`, `.sheet.dragging`, section, empty, endmark, skeleton, surface error as variants/components | their `legacy.css` rules | — | — |
| a·8 | [Actions, chips, facts, poster](phase-a08-actions-chips-facts.md) | `sact`/`btnprimary`/`cfoot`/`mediaadd`/`primary`/`solid`, chip tones, facts rows, poster box | each rule with its LAST emitter (DESIGN § 2.6); `chipHTML`, `factRowsHTML`; the features' `posterBox` calls | R80 floor lowered, pairs named | — |
| a·9 | [Arrivées](phase-a09-arrivals.md) | `ui/card.tsx` on Arrivées and the resolution screen; `flux` | `cardHTML` callers there; the card rules `cardHTML` no longer emits elsewhere | — | — |
| a·10 | [Médiathèque](phase-a10-library.md) | tile, library row, swipe row, gallery; the kind chips' strip | `tileHTML`, `libRowHTML`, `swipeHTML`; `LIBRARY` | — | — |
| a·11 | [Acquisition](phase-a11-acquisition.md) | now, follows, Découvrir deck and suggestion card, add screen | `cardHTML`, `POSTERS` from the engine; the format helpers move to the feature | `poster.py` | — |
| a·12 | [Releases and quality](phase-a12-releases.md) | the two screens' residue classes | their rules | — | — |
| a·13 | [Média — artwork and cast](phase-a13-media-artwork.md) | `sheet.hero`, `sheet.castPortraits`, `trailerVideo` read | `HERO_IMAGES`, `CAST`, `trailerIds` | `audit2.py`, `screen_addresses.py`, `transition.py` | — |
| a·14 | [Média — seasons and identity](phase-a14-media-identity.md) | season tree variants; `ids` read by every crossing | `SHEETS_RAW`, `OWNED`, `sheetFor`, `titleForProviderId`, `addressIdsFor`, `ownedFor` | `audit2.py`, `screen_addresses.py`, `priming.py`, `panel.py`, `url_state.py` | — |
| a·15 | [Système, Maintenance, Compte](phase-a15-system-maintenance-account.md) | `flux`, fact rows | `MAINT_ACTIONS` | `page_host.py:248`, `url_state.py` | — |
| a·16 | [Configuration, and the engine's support](phase-a16-settings-and-support.md) | `allSettings` over the cache; `field`/`readonly`/`rulenote` | `SETTINGS`. **Amended 2026-09-13 (ruling 57)**: `engine-shape.ts`, `engine-data.ts`, `engine-redraw.ts`, `lib/engine-drawing.ts`, `__referentiel` are VOID here and go to b·13 | `settings.py`, `page_host.py`, `url_state.py` | — |
| a·17 | [The entry's styles](phase-a17-entry-styles.md) | the 13 shell classes' rules in an `entry` block of `styles/base.css` that `serve.py` extracts | their `legacy.css` rules | `logout.py`, `startup.py`; `serve.py:416`, `serve.py:452` | — |
| a·17-bis | The ≡ harness panel dies — the operator's ruling on Q2, 2026-09-13 ([phase-a01](phase-a01-harness-module.md) § Amendment); **ruling 31** (2026-09-13) scopes it and orders it BEFORE a·18, renumbered from a·18-bis: `legacy.css` cannot die while a component still needs its `.hpanel` rules | — | the panel half of `harness/panel.ts` and its five `h*` verbs (`hclose`, `hgo`, `hscen`, `hphase`, `htmdb`); the « ≡ » opener `#scenBtn` in `design/index.html` (« Harnais — états et données »); the `.hpanel` rules, which live in `styles/legacy.css`; the i18n keys only the panel read; `closeHarnessPanel` in `harness/drive.ts` and `__etatsDetailles`, which only the panel reads; `.hpanel` in `app/layers.ts:93`; the comments naming « the ≡ panel » (`ui/variants/frame.ts:37`, `app/shell.tsx:47`, `harness/index.ts`, every `harness/states/*.ts:4`). **STAYS** (ruling 31): `[data-part="harness/bar"]`, `#notesBtn` and its toggle code | `message_above_harness.py` drops its `harness/panel` and `#scenBtn` reads and keeps `harness/bar`; `audit.py:82,99,118` and `dest.py:46` drop `harness/panel` from their exclusions and keep `harness/bar`; `hiding.py` (`#notesBtn`) and `chrome.py` (R51, `harness/bar`) do NOT move. Outside the harness, re-taken by grep on 2026-09-13: `scripts/markup_verbs.py`'s answers to the five `registerVerb h*`; `scripts/check-markup-contracts.py:25,211` (the `data-hscen`/`data-hphase` contract) and its two assertions in `tests/scripts/test_check_markup_contracts.py:76,765`; `scripts/nofrench_values.py:30,66`; `scripts/code-vocabulary.txt:482` (`hscen`; the other four `h*` words at `:455,467,481,483` go if no name uses them any more). `harness/panel_verbs.mjs` reads `ui/panel` action targets and is NOT a reader of the ≡ | — |
| a·18 | [`legacy.css` dies](phase-a18-legacy-css-dies.md) | — | `legacy.css`, its import, residue guard + ceiling, R80 + `test_residue.py`, baseline row, `markup_dressing` lines | `check-poster-box.py`, `csstokens_login.py`; `resolution_card.py` → `harness/factories.py` (ruling 59) | — |
| a·19 | [`refonte.html` and R72](phase-a19-refonte-and-r72.md) | R72 with (b) and (c) mutation-tested | `refonte.html`, hold (a) | the 16 path readers | — |

## L13b — The engine's verbs and the ladder's shape (BEHAVIOUR)

| # | Phase | What it lands | Deletes | Rules | Register |
| --- | --- | --- | --- | --- | --- |
| b·1 | [Settings verbs](phase-b01-settings-verbs.md) | 13 names registered in `features/settings/` | their branches | written first for `to`, `deletefield`, `addfield` | — |
| b·2 | [Account, maintenance, releases](phase-b02-account-maintenance-releases.md) | `signout`, `sheet=utilisateur`, `maintact`, `releases`, `profile` | their branches | first for `signout`, `releases` | — |
| b·3 | [Media verbs](phase-b03-media-verbs.md) | `mediasheet`, `ep` | their branches | — | — |
| b·4 | [Arrivals verbs](phase-b04-arrivals-verbs.md) | `pipe`, `manual`, `resolve`, `leave`, `next`, `act=resolve`, `.cfoot` | their branches | first for `next` | — |
| b·5 | [Acquisition verbs](phase-b05-acquisition-verbs.md) | 11 names + `confirmadd` | their branches | first for `sheetprim`, `standby`, `complete`, `tmdb` | — |
| b·6 | [Library verbs](phase-b06-library-verbs.md) | 12 names + `.act`; `mediaNamedBy`/`openDeleteDialog` to the feature | their branches | first for `selectedTitle` | B-465 |
| b·7 | [Frame verbs](phase-b07-frame-verbs.md) | `page`, `go`, `navgo`, `drawer`, `toast`, `phase`, `panel` in `app/` | the delegation listener itself | — | — |
| b·8 | [The gestures](phase-b08-gestures.md) | swipe rows, suggestion card, deck, drag guard, pull indicator | `E` gesture block | the one-tap hold | B-337 |
| b·9 | [One ladder shape](phase-b09-one-ladder-shape.md) | D-L13-1; the redraw replaces | the 240/260 ms timers | R-L13-a, R-L13-b; `exits.py` refuses the gap | B-290, B-397 |
| b·10 | [The panel's return](phase-b10-panel-return.md) | Back reopens the panel; `panel-down`'s reverse | — | R-L13-c | B-275 |
| b·11 | [The library's membership read](phase-b11-membership-read.md) (added 2026-09-13 by a·10, ruling 41; rulings 53, 61) | an exact membership read by title (and year) in the contract; `mediaNamedBy`, `knownMedium`, `follow-facts.ts`'s `inLibrary` and `openDeleteDialog` read it; **and, by ruling 53 (2026-09-13), the follow panel's season block reads `readMediaSeasons` by the follow's identity (Silo's fourth season named), with the seasons half of the `window.__mocks` seed accessor**; the harness re-aims at the `window.__mocks` seeds, the nine `window.SEASONS` readers among them (`busy.py`, `followed_sheet_act.py`, `message_over_layers.py`, `queued_ask_mark.py`, `season_family.py`, `season_grab_unfollowed.py`, `season_grab.py`, `seeds_at_rest.py`, `priming.py` — re-taken by grep) | `LIBRARY`, `INCOMPLETE`, `SEASONS`, `knownMedium`, their window exports | first for the membership read, and first for the season block | — |
| b·12 | [The pipeline's status is the layer's](phase-b12-pipeline-status.md) (added 2026-09-13 by ruling 74) | the `pipe` store key → `usePipeline()` / `/api/pipeline/status`; the `data-pipe` verb asks runPipeline / killPipeline; page.tsx:102/122 and app/arrival.ts:29 re-aimed; arr-idle / arr-running / arr-queued re-aimed | legacy.js's `data-pipe` branch, the `pipe` store key | arrivals.py, page_host.py green before and after; red with the layer call removed | — |
| b·13 | [`legacy.js` dies](phase-b13-legacy-js-dies.md) | — | `legacy.js`, `seams.ts`, and (ruling 57, from a·16) `engine-shape.ts` and its test, `engine-data.ts`, `engine-redraw.ts`, `lib/engine-drawing.ts`, `__referentiel` with `reference.d.ts` and the slices, the two exemptions and the reference-slice arm — the interface constants they publish need homes first (phase-a16 § Amendment), the parser arms, the debt section, the ledger entry, `resync.py` — and the ~547 lines of `LIBRARY`, `INCOMPLETE` and `knownMedium`, gone at b·11 first | the four harness reads of the file | — |

## L13c — What the engine was blocking (BEHAVIOUR)

| # | Phase | What it lands | Register |
| --- | --- | --- | --- |
| c·1 | [The selection survives the lens](phase-c01-selection-survives-lens.md) | the ruling of 2026-09-05, with its two guard-rails | B-312 |
| c·2 | [A fresh add screen](phase-c02-fresh-add-screen.md) | « + » opens empty; identify still seeds | B-340 |
| c·3 | [A disabled action looks disabled](phase-c03-disabled-action.md) | the action variant's `disabled:` half | B-339 |
| c·4 | [The kind chips hide their bar](phase-c04-kind-chips-scrollbar.md) | `pillscroll`'s two declarations | B-336 |
| c·5 | [The pull indicator](phase-c05-pull-indicator.md) | centred, and gone when the refresh is | B-331 |
| c·6 | [The seventh scheduler](phase-c06-seventh-scheduler.md) | one seed row, the held-back hold restored | B-327 |
| c·7 | [No follow without a sheet](phase-c07-follow-without-sheet.md) | unrepresentable; the tile's guard goes | B-366 |
| c·8 | [The library's states at rest](phase-c08-library-seeds-at-rest.md) | the seeds a hand needs | B-345 |
| c·9 | [The close](phase-c09-close.md) | register, README, frame-model, frame-survey, plan § 5 | all |

---

## The ordering, and its reason

**L13a phase 1 is first because every later phase is proved through `__go`.** Moving the driver
after anything else would move the instrument under a change it is measuring.

**The seams before the ladder, the ladder before the boot.** Phase 3's modules import instead of
reading `window`, which phase 2 makes the norm; phase 4's arrival calls phase 3's handler.

**What nobody reaches comes after the boot** because the mount-node placement it removes sits beside
the handshake phase 4 replaces — one file, opened once.

**The contract before the drawing.** Phase 6 declares the fields; each surface phase switches its own
readers, so no phase changes a contract and a drawing together.

**The primitives before the pages, the pages in D-L07-7's order** (Arrivées, Médiathèque, Acquisition,
releases, Média, Système/Maintenance/Compte, Configuration) — the order L07 and L09 walked, so the
understanding they built is reused. Média is split because its two halves kill different families.
Configuration is last because `SETTINGS` is still read by the engine's field verbs through
`allSettings`, which phase 16 re-points and L13b phase 1 then moves.

**`legacy.css` dies after the last surface, `refonte.html` after that**: neither can go while a class
it styles or a hold it feeds still exists.

**L13b: settings first, frame last.** Five of settings' thirteen are forwarders — the cheapest proof
the mechanism holds. The frame's `page`/`go`/`navgo` call `switchPage`, and taking them last deletes
the listener itself. **The gestures before the ladder's shape**: the swipe's click guard and the
ladder both decide what a tap after a movement means. **The shape before the return**: B-275's rule
reads the entry D-L13-1 writes. **The file dies last.**

**L13c: the selection and the add screen first** (reported twice by the operator), the close last.

---

## Gates

**Per phase**: `run.sh --contracts` under the shared lock (it prints its rule count and the
repository's cheap guards), `python3 scripts/check-frontend-boundaries.py` exit 0 with the ledger
re-recorded, `python3 scripts/check-no-french.py` exit 0, and the oracle per the governing rule.

**Before each sub-lot's pull request**: the full suite (`frontend/maquette/harness/run.sh`, not
`--contracts`), expected no failure; the `--a11y` tier at 0; `harness-hold-counts.py --compare`
with `failed` read first and every movement written; `make check` at zero failures **and zero
errors**; `python3 scripts/check-bug-register.py` and `python3 scripts/check-intent-map.py` read by
OUTPUT (B-346).

**The steward is told BEFORE a full-suite run.** A rule that falls while another session held the
harness is re-run alone before it is read, and the re-run's loss of load is said in the same breath
(B-277, B-307).

**The « In flight » row is the steward's per-lot docs PR's (auditor's order 15, 2026-09-13)**: the wave does not touch
`IMPLEMENTATION.md` beyond a citation the paths guard forces; the pull request body carries the figures.

---

## Departures from the brief, recorded as § 7.1 asks

1. **Three homes where the brief names one `app/layers.ts`** — design § 9.2, measured: the handler
   keeps the name; the page switch and the addressed-panel table are its two siblings.
2. **`legacy.css` is a conversion, not a deletion** — design § 2.6 and § 9.5: 92 classes style React
   components without a variant. It is eleven phases of L13a, not one.
3. **The phase count** — the brief's example cut named four sub-lots; the design recommends three (§ 1).

## Residue (pending Q5)

Measured on `1cb0a2dc1` after b·13 was measured and not opened (ruling 98). Names are neutral until the operator's Q5.

| Phase | File | Kind | Moves | Dies |
| --- | --- | --- | --- | --- |
| residue 1 | [constants and helpers](phase-residue-1-constants-and-helpers.md) | conversion | 20 interface constants, 10 helpers | 4 dead names |
| residue 2 | [served fixtures](phase-residue-2-served-fixtures.md) | conversion | 11 served families + POSTERS_HD + TODAY to their seeds | 13 literals |
| residue 3 | [engine verbs and drawing](phase-residue-3-engine-verbs-and-drawing.md) | behaviour | settings machine, render/currentState/applyState, search mount, toast/openSheet/closeSheet/showSignIn | — |
| residue 4 | [the reference dies](phase-residue-4-reference-dies.md) | conversion | — | `__referentiel`, 9 slices, reference.d.ts |
| residue 5 | [contract names](phase-residue-5-contract-names.md) | conversion, may be lot-sized | 24 families, 41 call sites | engine-shape.ts |
| residue 6 | [the file dies](phase-residue-6-the-file-dies.md) | deletion + full gate | — | legacy.js, seams.ts, engine-data, engine-redraw, engine-drawing, their instruments |

