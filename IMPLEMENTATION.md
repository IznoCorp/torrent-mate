# Current feature: shell-mobile — the v1 redesign

## THE MISSION CHANGED. Read this before anything else.

**This is no longer a mobile restyling of the shipped app.** It is a REDESIGN — a finished v1,
a version in its own right. The prototype is not a reference the current app is brought towards
piece by piece; it is the product, and the app will be rebuilt onto it.

That reverses the order of work:

1. **Finish the prototype first — every page.** Especially the ones that exist IN PRODUCTION and
   are not yet drawn here. A surface that production has and the prototype does not is a hole in
   the v1, not a later phase. The inventory is below and it is exhaustive. ⚠ **« Every page » is
   the SCOPE, never the running order** — that is `docs/reference/frontend-architecture.md`'s
   lots, and where they stand is § « Where the frontend work stands » just below.
2. **Then the operator judges.** The prototype is bound to the backend only once the operator
   considers the design AND the front-end architecture solid enough. That judgement is theirs, it
   is not a checklist, and no amount of green rules substitutes for it.
3. **Then, and only then, it becomes the new version.** Binding it to the backend is a separate
   mission with its own plan.

Until step 2 is passed, **nothing here derives app code**. The phase table that used to sit in
this file described the opposite order — deriving the app surface by surface — and it is gone.

**Branches:** one per wave (`feat/maquette-sp4b`, `feat/maquette-sp4c`, …) — each wave
squash-merges onto `main` after green CI and a clean final adversarial review (standing
operator instruction). What waits until the end is not `main` but the **binding**:
production keeps running the shipped SPA untouched, the merged waves change only the
prototype track (`frontend/maquette/`, its CI gates and docs), and nothing derives app
code until the operator's judgement (step 2 above). Non-negotiable.

**Spec:** `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md@79ccebe2` (in history)
**The prototype:** `frontend/maquette/design/` — §15 of `docs/reference/product-intent.md`. **Since
L07 the visual reference is the TOKENS and the COMPONENT CATALOGUE**, not one file: `src/styles/theme.css`
(the scale and the palette), `src/styles/base.css` (the base layer), and the `variants.ts` of `src/ui/`
and of each surface, where every drawing decision is written beside the class that applies it.
`src/styles/legacy.css` is the dated residue the dying engine still consumes, and `refonte.html` is now
the CONVERSION LEDGER alone — it carries no style rule, and it dies with the residue at L13. The engine is
`frontend/maquette/design/src/engine/legacy.js@c0a5062ac`, and every migrated surface starts in its own component.
**Bug register:** `BUGS.md` at the repo root — every reported defect, one closed at a time.

---

## Where the frontend work stands — and what comes next

**The target and the ORDER live in `docs/reference/frontend-architecture.md` (BINDING). This
section is the only place that says where the work STANDS.** Duplicating state is what produced a
stale table read as current for three days.

|                            |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Last landed**            | **L16 — §18, the ratio, COMPLETE** (the Trackers page, its two tabs « Torrents » / « Trackers », the tracker policy fields, the per-tracker alert threshold read on the page and on the bar's badge, broken obligations, the card's deferred reason, and the ranking editor — reads, saves, live preview), PR **#634** (squash `f3d8fed01`, version 0.98.106, merged 2026-09-29), 17 phases opened 2026-09-28 on the design re-drawn at PR #623 (rulings 18–20, rounds 7–9). **Correction round C16** (`review-archive/l16/BRIEF-L16-round1.md`): C1–C5, C12 repaired before the pull request's own close gate — the two acceptances' states computed by script, `cards` 79 → 78 named the lot's own (R43's per-foot hold over `acq-now-loaded`, successor R229 `follow_offered.py`), the ranking-conflict contract divergence (backend 412, maquette `200 {conflict: true}`) recorded, not repaired. Register: B-144 and B-298 `fixed #634`; **B-571 filed OPEN** — the deployed host's `pwa.py` `Page.goto` timeout, held by the steward's ruling (order 73) as not blocking READY. Close gate: full suite 182/184 (`entry.py`, `pwa.py` known), `--a11y` 161 states 0/88, contracts tier green, `make lint` 0; CI fell once on `audit2.py` (species B-546, unnamed load fall, 0/5 locally) then green on re-run. **This pull request is the lot's own gesture**: `docs/features/maquette-l16/` deleted WHOLE, every citation of it rewritten `@f3d8fed01`. **The day's other merges landed before it**: **#627** L22's close (the folder cited at its squash, the freeze date, the references) · **#628** the docs wagon (L17's plan at sixty lines a phase, the implementers' office, the register sorted) · **#629** the heavy lock (given back while its holder waits for room) · **#630** L24's design and plan of the orphans · **#632** L24 re-cut on the operator's rulings, and the desktop milestone · **#631** the hairpin repair (the deployed-host rules stop crossing the router's hairpin) · **#633** the intent map (the seven owed halves name L24 as their owner) |
| **Between L22 and L16**    | **L22 — Arrivées dans Acquisition, COMPLETE (a · b, plus the repair train between them)**. **L22a**, PR **#619** (squash `5e5ecd052`, version 0.98.101, merged 2026-09-27), phases 1–14: the contract of arrivals as cards (demands A–C), the ladder, the candidates screen moved from Arrivées to Acquisition (R215/R-L22-n), the two resolution states renamed for the page that owns them. **The repair train of 2026-09-28**, PR **#625** (squash `5644107ee`, version 0.98.102): B-558 fixed — the oracle's `open_frame` now calls `window.__measure(true)` before the first state, so the harness's own welcome hint (900 ms `setTimeout`) no longer races `pwa-ios`'s reading under load, held by R250 `boot_hint.py`; B-559 filed OPEN, split from it — `pwa.py`'s own `Page.goto` timeout under load, two readings no rate, cause not read, frozen by measure 1. **L22b**, PR **#626** (squash `232a908ca`, version 0.98.103, merged 2026-09-28), phases 15–44: « Mis de côté » (a folder set aside stands on the rung it stood on, once B1 was repaired before merge), the bottom bar without Système (three buttons, `/discover` a real address), Arrivées dies as a page and a destination (phases 47b/48), the boot list's engine prefetch dies with it (`app/engine-data.ts`). **Reader B22's one round** (`review-archive/l22/round-1-B22/r1-B22.md`): 1 BLOCKER + 2 MAJOR + 5 MINOR found on the merge candidate; **B1–B6 repaired before this branch's own PR** (`9ae33e6d8`, `15bfe36e2`, `21df4c939`, `98779d026`/`18aaa17c2`/`8a0eab22d`, `2b7b17d06`, `34adc2147`/`d79de9a82`), B7 a record-only correction (no code), **B8 filed OPEN as B-561** (old, present on `main` before L22b) at this docs pull request, which also files **B-562** — B5's count is fixed (`2b7b17d06`) but its own copy sentence, named missing by that very commit, stays open. **This pull request is the lot's own gesture**: `docs/features/maquette-l22/` deleted WHOLE (46 files), every citation of it rewritten `@232a908ca` (11 citations, 5 files — L13's precedent, #607/#608) |
| **Between L13 and L22**    | **L13c — What the engine was blocking**, PR **#607** merged 2026-09-16 (squash `763f15cf9`), version 0.98.98, cut from `feat/maquette-l13c` (stacked on L13r's PR head `22166378e`), with `main`'s squash of L13r (`08400a22a`) and of `e57ac110f` merged in. **L13 IS NOW COMPLETE — its four sub-lots (a · b · r · c) all landed.** **NINE PHASES + c·4-bis** across **ONE IMPLEMENTER SESSION** (`Agent : l13c 1`), rulings 115–119 (opening measures pre-empting the STOP D for two phases — c·1, c·4 — an actual STOP D at c·3's opening only, ruling 118; the other six carried none), landing: the selection surviving every listing writer — lens, category, sort, clear-search, the search commit (B-312, R195 `selection_survives_the_listing.py`, 14 holds); a fresh add screen, no stored query or strip surviving a page change (B-340, R196 `add_screen_opens_fresh.py`, 7 holds); a spent action drawn disabled, its opacity half already L20's (B-339, R197 `disabled_action.py`, 5 holds); the kind chips' and the sheet's cast strip's scrollbar hidden (B-336, R198 `kind_chips_scrollbar.py`, 4 → 6 holds with c·4-bis); the pull indicator closing with the refresh instead of a fixed delay, its centring half unreproduced on this machine (B-331, R199 `pull_follows_the_refresh.py`, 5 holds); the seventh scheduler restored to Réglages' « passages » rubric (B-327, `machine.py`'s kept hold restored); a follow with no provider identity refused (400) rather than silently recorded (B-366, R200 `follow_needs_an_identity.py`, 4 holds); and the library's states at rest guarded green from the start — the seeds already held every state (B-345's library half, R128 gains eight holds). **The MIDPOINT full suite (auditor's order 5) found THREE REAL FALLS under six green phase gates** (c·1–c·5), each replayed alone and confirmed real: `outbox.py` (a module cycle from the phase's own moves, re-routed through `app/shell.tsx`), `surfaces.py` and `virtual.py` (re-aimed and said); pass two clean — 146 rules + 26 guards no violation, a11y 0 dark / 147 light at the ceiling, oracle no divergence. **The gate on the closure head** (c·9, `16abdbcdc` + `a53bba207`): the full suite found TWO MORE falls no phase gate could see — `panel_label_once.py` and `outbox.py`, both because c·7's removal reached a branch serving an unidentified RELEASE — repaired; second pass 147 rules + 26 guards no violation, a11y 0/147, oracle no divergence, `make lint` 0. **ONE READER ROUND** (C13, `review-archive/l13c/round-1/r1-C13.md`): the seven measured points all GREEN (the arms on the final head, every register row set « to confirm » seen, the full suite, the hold-count movements each explained with no drop, the driver's reset and the reference's inheritance measured for B-548, the mock seed's identities, every claimed mutation replayed — 13 replayed, 13 fell); **NINE FINDINGS, ONE MAJOR** (C1 — c·7's new refusal answered by the interface with the opposite of the truth: a refused follow still shows « ajouté »), **EIGHT MINORS** (C2–C9). **Repaired in ONE round**: six commits + one style fixup, one per decided finding — C1+C7 (`62dbcf708`, `863ffbb0c`), C2 (`f4cacfb10`), C3 (`e58731711`), C5 (`fae47234e`), the round's ledger line (`45798a113`) and its style fixup (`13a900427`) — new rule R201 `follow_refusal_is_drawn.py` (five holds), five mutations felled by name, one per decided finding. **C4, C6, C8, C9 left to the steward's docs pull request** — C4 (B-345's library half closes « already satisfied, now guarded »), C6 (B-331's centring half unmeasurable here, the operator's device the only place it lives), C8 (the selection bar's touch floor, a new register row, owner a later lot), C9 (nine states drawing differently by order, an instrument observation, owner none). **Its folder is gone** — `docs/features/maquette-l13/` was the LOT's, and this gesture is what deletes it whole, every citation rewritten `@763f15cf9`. |
| **In flight**               | **The conformity train** (`feat/maquette-conformity`, `Agent : conformity train`, opened 2026-09-29 on `660049325`) — orders 80 and 85: the responsive rule (every named state at seven widths, 320 → 1280 px), then the conversions of the conformity reading § D.1, tabs first — plan `docs/features/maquette-conformity/plan/INDEX.md`, 14 phases. It runs before the case catalogue, L16-bis's code and L17 |
| **Between L21 and L20**    | **maquette-desktop-frame — the B-344 micro-wave**, merged 2026-09-11, squash `33cb259d9`, version 0.98.81, PR **#576**, brief at `docs/features/maquette-desktop-frame/BRIEF.md@33cb259d9`. **NOT A LOT**, TOOLING, and it took nobody's turn: L20 is still next, with `maquette-settings` first. On the design host, on a desktop only, a way out of the harness's phone frame and back. **The stylesheet draws it** — a checkbox outside `#device`, the frame's 520 px block and both re-assertion breakpoints scoped on `:root:not(:has(#desktop-switch:checked))` — and **a harness script remembers it**, by the operator's ruling of 2026-09-08 (« le desktop est une préférence localStorage »): inline in `design/index.html`, it restores the choice before any module runs and only where the control is drawn, because the frame's `overflow: clip` is declared outside any breakpoint. Neither the engine nor `app/shell.tsx` learns the control exists. **R140** (`desktop_frame.py`, 24 holds) holds the switch and **R141** (`desktop_frame_memory.py`, 9 holds) the memory — seen red first, and each of its two mutations felling its own hold, after the first version felled two for one defect. The measured pass read no oracle divergence, `--a11y` 0, 115 rules with `failed` 0 and `make check` at 0 failed; the oracle's reference (87 states x 34 regions, only its `baseCommit` moving) and the hold-count baseline (`failed` read first: **0** — 115 rules, 104 parseable, 2 559 holds) were re-recorded on the squash at this gesture. **Five rounds of independent readers found 25 of B-085's species against the wave's 11** — the row reads 36, the register's total 308 — every one in an instrument the wave had just written. Register entries **B-388 to B-392**, renumbered at the merge of `main` because L21 had filed its own B-370 and B-371 on another branch. Two debts for the register guard's tooling micro-wave: it refuses neither a table cell continued over lines nor rows out of ORDER — both met at this wave's merges of `main`, the second with no conflict and the guard clean. The operator walked it on his Mac and named no repair of the frame. **Its folder left the tree at this gesture.** **And a second one, the day after: maquette-resolution-card — the B-393/B-394/B-395 micro-wave**, merged 2026-09-12, squash `561ac7a39`, version 0.98.84, PR **#585**, brief at `docs/features/maquette-resolution-card/BRIEF.md@561ac7a39`. **NOT A LOT**, and it took nobody's turn: L20 is still next, with `maquette-settings` first. **Three behaviour repairs the operator photographed on 2026-09-11.** The candidate card IS the gesture — the full-width « C'est celui-ci » pill becomes a compact affordance at the button system's icon size and the whole card answers a tap, with the message's « Annuler » as the safety net (B-393). The harness's two floating buttons drop from rank 70 to 53, BELOW the message they were painting over, while the opened panel stays at 60 (B-394) — chrome that ships nowhere must not cover the product's own answer to a verb. The library's selection bar is drawn only on the Médiathèque and the selection SURVIVES a tab change, the operator's own ruling, « Annuler » on return being what clears it (B-395). **Four rules, seen red before they were green**: R161 `resolution_card.py`, R162 `resolution_window.py`, R163 `message_above_harness.py` and R164 `selection_survives_the_tab.py`. **R163 was GREEN over its own defect until it lifted `inert`** — the frame marks the background inert while a layer is open, and `inert` removes an element from hit-testing without changing what is painted, B-381's lesson met on its own subject. A new guard arm came with the ranked list the repair touched: `scripts/csstokens_ranks.py`, which refuses a `z-index` the list does not name, with 13 tests and its plumbing read on all three ends. **Two independent reader rounds, 7 minors then 7 minors, no blocker and no major**, the second round's reader taking every finding on BOTH builds; **A6 was put to the operator and ruled A on 2026-09-12** — « × » means « seen » everywhere in the interface and the way out is « Annuler », so closing the message leaves the held send on its 7 s course. **Register**: B-393, B-394 and B-395 read `fixed #585`, B-396 was filed by the wave (one pickable folder in the seed, so the window's riskiest path has no finger proof), and **round two's seven minors are filed at this gesture as B-460 to B-466**, B-462 carrying the operator's ruling of 2026-09-12 that the card's accessible name announces the confidence and the provider. **B-085 is COUNTED for this wave for the first time — 13, and the row moves the total to 321**: four by the wave, three of them inert mutations, and nine by the two readers, with four findings excluded and their reasons written down. **Both references were re-recorded on the squash at this gesture**, the oracle's `baseCommit` and the hold-count baseline's `taken_at_commit`, the latter with `failed` read FIRST. **Its folder left the tree at this gesture.** **And a third, off any lot's path: tooling-hygiene — the instruments' micro-wave**, merged 2026-09-13, squash `a2721935f`, version 0.98.86, PR **#589**, brief at `docs/features/tooling-hygiene/BRIEF.md@a2721935f`. **NOT A LOT**, TOOLING, and it moved no surface: 104 files, of which 85 are harness rules gaining the invocation guard B-325 asked for (119 modules of 121 guarded, the two others defining no invocation; the hold-count compare read 0 rule changed). Six entries closed — B-384 (`build-identity.mjs` hashes tracked sources, so a command log under `design/src/.claude/` no longer moves the build id), B-385 (the pre-push hook capped by `PYTEST_XDIST_AUTO_NUM_WORKERS`), B-386 (`scripts/heavy.sh` floors and load ceilings by CLASS — browser 4096 MB / 6, test 3072 / 6, rule 2560 / 10; under a named class the environment may only raise the floor and lower the ceiling; a classless call keeps the historical 4 GB / 6 with its overrides), B-387, B-325 and B-346 (the register guard's three-rule head parser) — and two filed on the MEASURED defect rather than the briefed diagnosis, then closed: B-420 (a wrapped index row was refused, misdiagnosed and unnamed) and B-421 (rows below the table are counted; the index was not ascending — four descents frozen by name as a ratchet). B-307 gained its fifth instance with the reading its four predecessors lacked (the same row on both sides of a mode change, the port at 0 px instead of 300). Gated by the wave's own arms and `make check` 11 263 green; a full suite with one fall under load replayed alone, on the steward's ruling that a re-run removes the load a fall needed. **No independent reader round**: merged on the steward's verification, before the operator's ruling of 2026-09-12 (zero rounds for a micro-wave) made that the rule. **Its folder left the tree at this gesture.** **And a fourth, off any lot's path: maquette-mock-layer — the B-379/B-383/B-396/B-380 micro-wave**, merged 2026-09-13, squash `5eafd3cfc`, version 0.98.87, PR **#592**, brief at `docs/features/maquette-mock-layer/BRIEF.md@5eafd3cfc`. **NOT A LOT**, and it took nobody's turn: L20 is still next. The mock layer is the maquette's stand-in for the backend, and four things it said were not true: it answered 200 whatever the contract declared (B-379 — the declared success code is read off `contract/openapi.json`, R170 `declared_codes.py` on the contracts tier); « Re-scraper les métadonnées » on the sheet and the follow panel and « Lancer à blanc » said a sentence and sent nothing (B-383, half of it — each verb now calls its operation, the contract gains `POST /api/media/{provider}/{providerId}/rescrape` 202, the mock moves `metadataRefreshedAt` on the frozen clock, R171 `said_and_done.py` 17 holds; the engine lost six lines; `app/feature-verbs.ts` is one import per feature owning a tap verb and raised the frame-domain ceiling 126 → 130 as the guard's reviewed line); one queued folder offered candidates, so the undo window's riskiest path had no finger (B-396 — S.W.A.T. gains the two candidates its own reason names, R172 `two_picks.py` 16 holds); and the sheet counted the catalogue's total as « aired » (B-380 — aired is DERIVED from episode air dates against the frozen TODAY, the season family and the two families that sum it corrected at the SOURCE through the engine fixture and `build-mock-seeds.py`, a new pill « N à venir » informs without an act, R173 `season_family.py` 48 holds with Dexter as a NAMED exclusion that asserts its disagreement; R160 re-aimed and said: no act where the family has no hole, 24 → 12). Found on the way and filed OPEN: **B-474** (the panel's « Résoudre → » resolves the WRONG folder — `data-resolve` read as the candidate), B-475 (library episode numbers the catalogue does not list), B-476 and B-477 (two more members of the fixture-identity class B-088), B-471 (`readMediaSeasons` declares one shape and answers another), B-472 (the heavy lock is a poll, waiting gives no turn). Gated on the wave's own runs: contracts 19 + 27 no violation, full suite 123 rules, a11y 162/162 light and 0 dark before and after the merge of main, oracle one divergence on `mediasheet-series` among the six states whose drawn numbers the seeds moved, hold counts `failed` 0, `make check` 11 215; the a11y debt files re-recorded on the merged tree (only `takenAtCommit` moved). **No independent reader round, by the operator's ruling of 2026-09-12 (zero rounds for a micro-wave)**; merged on the steward's verification of the files. The hold-count baseline and the oracle reference are re-recorded on this squash by the steward's own hand at this gesture. **Its folder left the tree at this gesture.** **And a fourth: maquette-settings — the B-332/B-361/B-341/B-342/B-343/B-334/B-335 micro-wave**, merged 2026-09-13, squash `a155b54fb`, version 0.98.88, PR **#588**, brief at `docs/features/maquette-settings/BRIEF.md@a155b54fb`, figures at `docs/features/maquette-settings/DESIGN.md@a155b54fb`. **NOT A LOT**, a BEHAVIOUR micro-wave off L13's path, and it took nobody's turn. Seven entries the operator's own walk through « Réglages » found, none of which needed the engine EDITED: a rubric that could not be left on two pages (B-332, B-361 — a rubric is an ARRIVAL by D1b rule 1, it pushes and draws its own back), a field that committed only on blur with its two labels read backwards (B-341), a save that said « Enregistré » over a layer that kept nothing (B-342), a restart banner raised on an object nothing re-rendered (B-343), two secret acts that were sentences rather than acts (B-334, B-335), plus B-345's settings half — the conflict and the restart reachable at rest by a hand. **Three new rules**, each seen RED against the tree as it stood with no mutation needed: R165 `topics.py` (16 holds, both rubric pages), R166 `settings_editing.py` (15), R167 `secret_acts.py` (14); five holds added to R128 (10 → 15); R82 `journey.py` RE-AIMED and said, 74 → 70 — its hold (e) had TAPPED the maintenance topic and asserted the depth unchanged, the exact behaviour B-361 was filed to end. **The engine only shrank**: two delegation branches deleted, `legacy.js` 31 467 → 31 444 non-blank across the wave and its merges, the ledger re-recorded downward in the same commits; one expression in `switchPageFromLayer` COUNTS what the history stack holds instead of assuming a fixed number, by the operator's exception to D5 (« C », 2026-09-12) for this wave and this expression only. **The oracle's 36 divergences are ALL heights on Réglages and Maintenance** — rubrics that draw their own back and a field that draws both its values — accepted cause by cause in DESIGN § « The oracle's divergences », two states outside the announced list (`settings-edited`, `maintenance-delete`) admitted on the same-cause reading; the a11y light ceiling LOWERED 162 → 149 (the `backAction` label now takes `--color-primary-text`, four `.fback` contrast carriers gone and thirteen older ones with them), re-recorded on the merged tree; `make check` 11 400. **B-299 and B-300 are made confirmable by hand and NOT closed** — the confirmation is the operator's. **B-397 filed** (a panel re-produced after an edit pushes a second history entry — the field's long-standing path and L13's ladder), **B-398** and **B-496** (the pre-push hook discards the output of the pass that fell and shows a green re-run under « FAILED »; its one fall on this wave's final push has no reading, by construction). **No independent reader round, by the operator's ruling of 2026-09-12 (zero rounds for a micro-wave)**; merged on the steward's verification of the files (41 files, CI 34724762794 14/14). **B-085's species, counted by the steward: 1** — R82's hold (e), green over the defect B-361 names, re-aimed by the wave; the row moves the total 321 → 322. The hold-count baseline and the oracle reference are re-recorded on `main` by the steward's own hand at the NEXT squash, `519ba2136` (#593), in one run that covers both — the record names the head it measured. **Its folder left the tree at this gesture.** **And a fifth: maquette-scroll-jump — the B-490/B-491 micro-wave**, merged 2026-09-13, squash `519ba2136`, version 0.98.89, PR **#593**, brief at `docs/features/maquette-scroll-jump/BRIEF.md@519ba2136`, figures at `docs/features/maquette-scroll-jump/DESIGN.md@519ba2136`. **NOT A LOT**, the day's repair train, and it took nobody's turn. The operator's own report on his Mac, verbatim: « double scroll systématique sur Acquisition › En cours ; dès que le scroll arrive au niveau de Lucky on remonte automatiquement en haut de la page » — TWO mechanisms, measured apart on a private bench with a setter trap on `scrollTop`. **B-490, the jump**: `restoreScroll()` re-applied the landing offset when the LAST pending `img` loaded, and a lazily loaded poster below the fold loads when the READER reaches it, so their own scroll was undone from the top (Chrome 1440 in the frame 508 → 0, phone 520 → 240); the late re-apply now fires only while `port.scrollTop === landed` — an offset the browser clamped for want of content, never one the reader moved. **B-491, the double scroll**: out of the desktop frame `.device` stops clipping and the closed sheet with its drag band overflowed it by 89 px, giving the DOCUMENT a second scroll beside `#port`; `.stage` now clips its vertical overflow in `harness.css`, a separate commit. **R175 `scroll_keeps_place.py`, 40 holds**, seen red first (40/6 → 40/2 after the guard → 40/0), walked by finger and by wheel at the phone width and on a desktop in the frame; the formal mutation (the guard removed) fells exactly the four return walks and none of the header holds. Gated on 7ae6567a3 under the shared mutex: contracts 18 + 27 no violation, full suite 120 rules, a11y 0 and light 162/162, oracle no divergence, hold counts `failed` 0 with only R175 new; on the merged tree (main a155b54fb): 127 rules no violation, light 149/149, oracle 37 divergences ALL brought by the merge (#588's 36 and #592's 1, both recorded at this gesture), `make check` 11 263. **B-492 filed OPEN** — out of the frame the overflow is the APP's own cascade, no element of the shell clips its absolute layers: the frame model's and L13's. **No independent reader round (measure 2)**; merged on the steward's verification of the files (11 files, CI 34728373954 14/14). **B-085's species: none counted** — the wave's two rules that were re-aimed (R175's own selector, the comment corpus) were its own and seen before its push. **Both references are re-recorded on `main` by the steward's own hand at this gesture** — both `taken_at_commit` and `baseCommit` read `f1e7ac662`, the docs-only squash of #594 that landed on `main` while the run was under way — `git diff --stat 519ba2136 f1e7ac662 -- frontend/` is empty, so the build they measured is this squash's (`failed` read first: 0; 127 rules, no violation, 2 776 holds; the oracle's 37 divergences before the record were #588's 36 and #592's 1, none after). **Its folder left the tree at this gesture.** |
| **Between L19 and L21**    | **maquette-schedulers — the B-308 micro-wave**, merged 2026-09-06, squash `e9820e6a4`, version 0.98.71, PR **#567**. **NOT A LOT**, and it took nobody's turn: L21 is still next. It repaired the one failing rule of the full suite on `main` — `machine.py` read **6 drawn vs 7 real** since `personalscraper-index-full` was scheduled (#557) — so the wave after it does not inherit « one red, it is known ». The row could not be added where the list lived: the size ledger refuses `legacy.js` upward and D5 has the engine dying by subtraction, so the FAMILY left for the seed the Système page already read (`legacy.js` 31 645 → **31 591**, the ledger re-recorded downward in the same commit, the register marking it `converted` — 31 → **32**). `SCHEDULERS_DOWN` went with it, derived now in `features/system/fault.ts`. **Two findings that are not the missing row**: **B-324** filed — the BACKEND's own cron mirror names three of the seven and nothing reads it against anything, which is B-308's finding on the end with no guard at all — and D5's « 254 declarations republished on `window` », already false before this branch (**158** on `main`, **156** here), corrected with its method. **It discharged the obligation L19's gesture left open**: the hold-count baseline was re-recorded on the branch with `failed` read FIRST, and re-recorded again at THIS gesture on the squash (`failed` read FIRST: **0** — 92 rules, 2 180 holds, no movement against the branch's own record; only the pointer moved to the squash). **The review took SIX rounds, five independent readers and the steward's own re-take, each round a fresh reader on the previous round's REPAIRS**: 5 minors → 1 major + 5 → 1 major + 5 → 7 minors → 5 minors → **empty**. Both majors sat inside the previous round's fix, which is the office's oldest reading: Réglages « Les passages programmés » still drew SIX schedulers (pre-existing — the wave made the disagreement between two surfaces VISIBLE; the row cannot be added without converting the 1 461-line `SETTINGS` family, so the label half landed and the row half is **B-327**, L13's), and the hold added for it read `fr.json` from the MAIN checkout through an absolute path — green over the label's absence on any worktree. Seven of the readers' findings are instruments green over what they did not read and are counted in B-085's row. Five entries filed that are nobody's here — **B-324** (the backend's cron mirror), **B-325** (`machine.py` cannot be pointed at a build), **B-326** (the heavy lock's probe), **B-327**, **B-328** — and B-307 at its fourth instance. **Its folder left the tree at this gesture**: `git show e9820e6a4:docs/features/maquette-schedulers/BRIEF.md`. The oracle's reference re-anchored on the squash at this gesture **And a second one the same day: maquette-departure — the B-310 micro-wave**, merged 2026-09-06, squash `f70ca0295`, version 0.98.74, PR **#573**, brief at `docs/features/maquette-departure/BRIEF.md@f70ca0295`. **NOT A LOT**, and it took nobody's turn: L21 ran beside it. Three review rounds by three fresh readers, each on a worktree pinned at the head — **0/1/3 → 0/1/4 → 0/0/3** (blockers / majors / minors), round two's major INSIDE round one's repair (the arrivals' fill holds passing on the user agent's own `both`, held by NAME since), round three's three items prose. The brief's last step — the steward re-reading the transition's last frame on the operator's phone — was VOID before it was due: the operator ruled on 2026-09-06 that device readings are over (« Mac seulement »), and the frame had been read on the Mac as well. Two readings of one seam — a layer outliving the crossing it was supposed to leave on. **B-310**: the `animation:` SHORTHAND resets `animation-fill-mode` to `none`, which the user-agent stylesheet had set to `both`, so `panel-down` ended and the departing snapshot snapped back to the panel AS CAPTURED — open, opaque, at rest — for one frame above the arrived screen. The fill mode is declared as a longhand on all **three** pseudo-elements of that species (`banner-in` and `body-rise` snap back too and show nothing only because a NEW snapshot's un-animated state is its final one); `panel-down` keeps its 450 ms and its curve. **B-338**: `visibility: visible` is hit-testable as well as visible, so the closed scrim answered `elementFromPoint` at the centre of the arrived screen and swallowed the tap — `pointer-events-none` on the CLOSED state only, the fade and the delayed `visibility` untouched, R103's holds unmoved at 18. **One rule, R127** (`harness/departure.py`, 19 holds), seen RED first: `541ms opacity=1 transform=none panel-down=None` against `524ms opacity=0 transform=matrix(1,0,0,1,0,486.172) panel-down finished` — the animation RETAINED where it was dropped. Each mutation falls on its own holds alone (1 and 2 violations). **A measurement nobody predicted**: under `reduce` the crossing ends after THREE frames instead of thirty while the scrim's delay runs unchanged, so the lost-tap window is not shorter there but more than twice as long — **95 → 910 ms over 50 of 92 frames** against 559 → 924 ms over 23 of 64. Gates: hold counts `failed` **0**, 0 changed, one new row; oracle **2 958 measurements, no divergence**, reference NOT re-recorded; `--a11y` **0**, light 166/166; `make check` **11 170 passed, 0 failed, 0 errors**. **Four « guards green over what they do not read », total 250** — `transition.py` asserting the snapshot RUNS and never what it does when it ENDS, `exits.py` reading a leaving layer's `visible` and nothing else, while the property the codebase says that idiom is FOR — « the layer stays hit-testable until it has finished leaving » — is written at three OTHER sites (`ui/variants/layout.ts`, `harness/transition.py`, `styles/base.css`) and measured by none, `check-maquette-comments.py` printing clean over a wave that added a file to its own corpus — it reads the corpus size at `:279-281`, as a floor 10 % BELOW the record, and never asks whether the record has gone stale upward, which is the case that happened, and `check-bug-register.py`'s closure arm refusing an honest `fixed #573` on B-310 while ready to accept a silent closure of B-249, over one paragraph that its `BODY_HEAD` reads as a body head (**B-346**) — the last two caught by gates refusing this wave's own work, not by a reader **And a third, off any lot's path: ci-draft — the CI micro-wave**, merged 2026-09-08, squash `eaedcd916`, version 0.98.77, PR **#578**, brief at `docs/features/ci-draft/BRIEF.md@eaedcd916`. **NOT A LOT**, and it took nobody's turn: L21 and maquette-desktop-frame both ran beside it. The operator's decision — CI stops running while a pull request is a draft, « afin d'économiser du temps de CI » — in two halves, the second of which is what makes the first safe: **`ready_for_review` was in NO trigger of this repository**, so a bare « skip when draft » would have meant a pull request leaving draft dispatches nothing and its checks never run at all. The gate is at JOB level on all fourteen jobs and never at the trigger — a skipped job reports a conclusion, a run that never starts leaves a required check « expected » for ever — the two jobs with a condition of their own compose it with `&&`, and the escape hatch is the `run-ci-on-draft` label, created on the repository and kept by the operator, which needs no new trigger because `labeled` is already among the types. **NINE READINGS ON THE RUNNER**, the four cells of `draft × label` and their controls: `opened` on a draft → fourteen SKIPPED · `labeled` → fourteen SUCCESS · `ready_for_review` with the label STILL ON → SUCCESS, kept and **marked confounded** because the second clause alone accounts for it · `unlabeled` → SKIPPED, the control that shows the skip returns when the hatch is taken away · `ready_for_review` with NO label → SUCCESS, the isolated proof of `draft == false` · **`synchronize` on a draft → SKIPPED, the row the defect's title is about**, dispatched by the wave's own push and unasked, because the defect was never « CI runs when a draft is opened » but that every intermediate PUSH paid the whole pipeline · and the merge candidate green on `ready_for_review` alone. **A workflow change is the one change that cannot be proved against the base**: a `pull_request` run takes its workflow from the merge ref, so this pull request ran the gate it introduced and the gate gated it. Register **B-376**, `fixed #578` — `closed` is the operator's word on a real thing and a merge word on the evidence is not that gesture. **« Zero check-runs » gains a SECOND CAUSE** beside a run that never started (no pull request, a `paths-ignore`, a `CONFLICTING` one), and CLAUDE.md, this file and `docs/reference/feature-lifecycle.md` each say so where they read CI. **The steward's catch is the one the wave missed**: the holds read the condition and the trigger's types and never asked what OTHER events reach the expression — on a `push` trigger `github.event.pull_request` is null, the disjunction is false, and every job would stand down on every push to `main` under a green `skipped`. That arm landed at this gesture, seen red by adding a `push:` trigger and naming it. **The independent adversarial round did not run**: the operator merged on the evidence and skipped it FOR THIS MICRO-WAVE ONLY — his exception, recorded as his and not as a practice. **Its folder left the tree at this gesture.** |
| **Between L10 and L15**    | **L10-ter — the application template**, merged 2026-08-30, squash `d3892d18`, PR **#521**, no release (prose only). **NOT A LOT**: a design phase, and it took nobody's turn. Its products — `docs/features/maquette-l10-ter/{SURVEY,MODEL,QUESTIONS}.md`, `docs/reference/product-intent-map.md` — and what it decided: the engine draws no page and no screen; the frame is modelled in thirteen parts; **L15 · L11 · L12 · L19 · L20 · L16 · L17 · L18 · L13 · L14** is the order; eleven register entries B-228 to B-238. **Three adversarial readers on a phase that wrote no code found four more of B-085's species** — two `served` rows of the clause map resting on proofs that did not read the clause — and the « Guards green » row for the phase reads 5, total 98. **The nine questions were answered on 2026-08-30** (#523): drawer alone, order as written, L14 before L19, every PWA entry point, no pipeline badge, the map ratified, §17's four points dictated, L20 after L19 — and the operator dictated **§20, a tunnel per media**, which re-cut L20 to the global levers; the backend's share went to `docs/reference/backend-demands-architecture.md` |
| **Between L12 and L13**    | **docs-cleanup — the documentation model's first application**, merged 2026-09-01, squash `81ad0492`, version 0.98.60, PR **#539**. **NOT A LOT**, the steward's directives wave, on five decisions the operator dictated on 2026-08-31: the present — the version in production — moved to `docs/production/` (23 files, frozen behind `scripts/production-docs-manifest.json`), 1 215 files of history left the tree and every living citation of them reads `path@79ccebe2` (git is the history), the frame's model and survey became `docs/reference/frame-model.md` and `docs/reference/frame-survey.md`, and `scripts/check-docs-cited-paths.py` holds all of it in three arms, each mutation-tested. The rule is `docs/reference/documentation-model.md`; the move's spec is `docs/features/docs-cleanup/DESIGN.md@81ad0492` — the wave's own folder left the tree at this gesture, as § 4 of the model says every wave's does now. Three findings filed: B-292 (a « parked » L06 spec at a directory no commit ever held), B-293 (38 `Design:` markers naming paths that left the tree, open), B-294 (two dead `.gitignore` lines) |
| **Between L10 and L11**    | **L10-bis — the correction wave**, merged 2026-08-29, squash `e16887eb`, version 0.98.51, PR **#516**, with `#517` re-anchoring the oracle after the squash. **NOT A LOT**, and it took nobody's turn: L10-ter then L11 still follow. It closed the **nineteen** entries the operator arbitrated plus the steward's two audit findings (A-1, A-2), and its FIRST commit was the amendment to `BUGS.md`'s rule 3 — *the absent instrument is the work*. **Group 0 came second and found a defect nobody had filed.** The per-commit split held: over 36 commits, **zero** mix `design/src` with tooling. **What it learned reverses what it had written**: a mutation aimed at one's own instrument does not stand in for a second reader — ten of its first eleven findings were its own mutations, and an adversarial review then returned some fifty defects, nine more of B-085's species coming out of repairing them. **B-085 stands at 93** |
| **Between L07 and L08**    | **L07-bis — the tidy-up**, merged 2026-08-25, squash `ec38ff49`, version 0.98.40. **NOT A LOT**, and it did not take L08's turn: a correction wave arbitrated by the operator immediately after L07, clearing the ground L08 lands on. It executed the seven arbitrations recorded in **#498** and closed thirteen register entries. The three guards that were nearing the hard ceiling are all well under the soft one now — 584, 742, 575 — after three splits taken on a SUBJECT rather than on a line count, and `check-module-size --root scripts` reports clean where it carried four warnings. The no-abbreviation rule is armed: `check-code-abbreviations.py`, its two lists and a per-file baseline. **Three L07 findings stay open on purpose** — B-061 (the oracle is arbitrated NOT widened), B-068 (the prose inventory) and B-071 (the design-notes toggle, which lives in the dying engine and belongs to L13). **What it found is the part that mattered**: B-075 — five guards green over the very defect they were written for, two of them inside the reader of the rule the wave was building; B-076 — the hero animating for a reader who asked for no motion; B-077 — a browser-free test that could not be collected without a browser, caught by CI and by no local gate |
| **Next**                   | **L16-bis — the Trackers page's correction** (the operator's feedback of 2026-09-29: « Torrents » first, a tracker selector, a legend, the torrent card in the media card's style and gestures, an activation switch per tracker, Découvrir's header) — design and plan `docs/features/maquette-l16bis/DESIGN.md` / `docs/features/maquette-l16bis/plan/INDEX.md` (PR #637), re-cut 2026-09-30 into **5** correction phases by surface (orders 98, 99: sized by the agent's context, no points; was 18 phases, 180 points — `plan/CORRESPONDENCE.md`), its nine OPEN questions ALL RULED by the operator 2026-09-29, Découvrir's swipe (Q7) added as DECIDED 10 with one OPEN (10) for the operator's round; its CODE waits for the conformity train, which first builds the single tabs component on the existing validated tab bars (DECIDED 7). Then **L17 — cross-seed** (the six-word model, the per-pair mark, the closed reason set). Design and plan `docs/features/maquette-l17/DESIGN.md` / `plan/INDEX.md` (PR #617), citations of the dead `docs/features/maquette-l16/` and `docs/features/maquette-l22/` folders rewritten `@f3d8fed01` / `@232a908ca` respectively at this gesture. No branch yet — this row names the design, not a session. **C1 — the settings save bar and its three-choice leave
confirmation (operator, 2026-09-29) — runs as a MICRO-WAVE before L17 opens or beside it, never inside L17's own
plan** (`docs/reference/frontend-architecture.md` § 4, after L24's paragraph): not counted in the phase total below,
its own scale unmeasured. **Order after it**: L18 (design PR #618) · L23 (design PR #624) · L24 (design PR #630, re-cut PR #632; its nine OPEN questions ALL RULED — 1–6 at #632's round, 7–9 by the operator 2026-09-29 (`review-archive/l24/rulings-2026-09-29.md`): a settled decision lives on the medium's card (OPEN 1=C), the disk-filling/index-anomaly badge term kept (OPEN 2=A), identification activity read per card only (OPEN 3=A), `/medias` `/systeme` `/controle` answer not-found with no redirect (OPEN 4=A), the journey sheet's « enrichi » unfolds with its eight-rung ladder kept (OPEN 5=B), the desktop milestone at A with the final adaptation phase reserved (OPEN 6=A), ONE « Corriger » act on the decision block for both authors (OPEN 7=A), drawn on the Médiathèque sheet too for a shelved medium (OPEN 8=A), and NO backward compatibility of former addresses — no alias, no redirect — a former address answers not-found (OPEN 9=A + PRINCIPLE), which kills S4's former-addresses redirect table). **PROJECTED FREEZE DATE (auditor's order 54, re-measured at every close)**: remaining planned phases — L16-bis 18, L17 18, L18 36, L23 9, L24 20 — **101 phases**, ÷ the cadence measured on **L16's own squash** (17 phases, phase 1's opening measure `917fd864b` 2026-09-28T17:15Z to the squash merge `f3d8fed01` 2026-09-29T14:14Z ≈ 21 h wall ⇒ ≈ 1.24 h/phase) ⇒ **≈ 125 h of wall time**, + one reader round per remaining lot (5 lots; **L16's own round, C16, is the first measured at this scale** — PR-ready `d6972b4e8` 08:10Z to its close gate `c049eb7a1` 13:24Z ≈ 5 h 14 min, one data point, not yet a cadence for the other four lots' own scale) = **≈ 125 h of drawing wall time, plus five reader rounds of at least ≈ 5 h each, from 2026-09-29**. This is WALL TIME the cadence was measured in, not elapsed calendar time between sessions — it does not predict a calendar date. **The freeze also requires the COMPLETE CATALOGUE of cases** (auditor's order 77(4), operator's principle, 2026-09-29 ~16:4x, verbatim: « De plus même pour l'accrochage, lorsqu'on lancera la suite (accrochage backend) il faudra un exemple de chaque cas de figure, seule une maquette montrant tout les cas possibles est utile » — every surface shows each of its cases (normal, empty, loading, error, data variants) as a named state, reachable from the harness panel's own case catalogue (order 76, not yet built); that catalogue becomes the backend-binding checklist. **UNMEASURED today**: no count of surfaces against cases exists yet, and no phase above carries its points. **What is still undrawn (mission of 2026-08-19: every screen is redrawn)**, measured by comparing `frontend/src/router.tsx`'s eight real production pages (Login, Contrôle `/control`, Pipeline, Config, MediaLibrary, SystemPage, AcquisitionPage, MediaSheetPage — every other route is a legacy redirect, no page of its own) against the maquette's own pages and panels: **DEPTH, not BREADTH, is the gap for six of the eight** — Login (signin/signin-error), Config (cfg/Réglages), MediaLibrary (lib/Médiathèque), SystemPage (sys/Système + maint/Maintenance), AcquisitionPage (acq/Acquisition) and MediaSheetPage (the media sheet panel) each have a maquette page or panel designed, and mostly coded; **L16 now finished coding its own DESIGN** — L17/L18/L23 finish coding what their own DESIGN already draws, not draw a page from nothing. **Two of the eight are BREADTH gaps, named by CLAUDE.md's own mission text and unrepaired at this close**: `/control` (« Contrôle », the pipeline-attention home) and `/pipeline` (the run's own detail) were ruled OUT of the maquette as pages, then that ruling was REVERSED 2026-08-19 — « their redistribution … remains a valid UX proposal, but it does not exempt anything from being drawn » — and two of Contrôle's own panels were read as having no maquette equivalent by a grep of French and English words the maquette's code never spells (2026-09-28): **« Santé »** (the health card, index health, disk usage) is in fact drawn in substance on Système — disks, index, Redis and providers, read by R67 (`docs/features/maquette-l24/DESIGN.md` § 0.1) — save each section saying its own read failed; **« Activité scraping »** (the live scrape-activity feed) is read per medium on the card. Contrôle's other panels (« À traiter », « Dernier run », schedulers) are substance-drawn, redistributed into Acquisition and Système's own pages, per the reversed ruling's own permission — what remains of these two panels, and the standalone `/control`/`/pipeline` addresses themselves, are owned by **L24 — the orphans** (`docs/features/maquette-l24/DESIGN.md` and `plan/INDEX.md`, PR #630/#632, 20 phases, re-cut and now fully ruled above), with the « Décisions » tab (ruled: a settled decision lives on its medium's card), the seven owed halves of the map's `partly` rows and DOIT-9's desktop half (ruled: a proof only); the freeze is reached at L24's close, not L23's. **After it, the desktop adaptation of the screens** (operator, 2026-09-29, OPEN 6) — a milestone after the drawn lots, UNMEASURED: no points, no phases, its contour the operator's once the maquette is ready (`docs/reference/frontend-architecture.md` § 4, « After the drawn lots ») |
| **Daily ledger (order 93)** | Append-only, newest first — date · operator corrections received · phases landed that day · phases remaining. **2026-09-30**: operator corrections received **9** (B-572, B-573, B-576–B-582, `grep -c '\| operator, 2026-09-29\\\|\| operator, 2026-09-30' BUGS.md`) · phases landed **6** (`feat/maquette-conformity` phases 1–6, `git log --since=2026-09-29 --oneline origin/feat/maquette-conformity \| grep -icE 'phase [0-9]+ gate'`) · phases remaining **107** (conformity train 6 of 12 + L16-bis 18 + L17 18 + L18 36 + L23 9 + L24 20, each lot's own `plan/INDEX.md` phase table; the projected-freeze row above's 101 does not yet fold in the conformity train, born after that figure was written) |
| **Before it**              | L22b — PR **#626**, version 0.98.103 · repair train 2026-09-28 — PR **#625**, version 0.98.102 · L22a — PR **#619**, version 0.98.101 · L13r — PR **#605**, version 0.98.96 · L20 — PR **#603**, version 0.98.95 · L13b — PR **#601**, version 0.98.94 · L13a — PR **#596**, version 0.98.92 · L21 — PR **#572**, version 0.98.79 · L19 — PR **#558**, version 0.98.69 · L14 — PR **#547**, version 0.98.65 · L12 — PR **#540**, version 0.98.58 · L11 — PR **#534**, version 0.98.57 · L15 — PR **#528**, version 0.98.55 · L10 — PR **#512** and **#513**, version 0.98.48 · L09 — PR **#509**, version 0.98.45 · L08-bis — PR **#505**, version 0.98.43 · L08 — PR **#503**, version 0.98.42 · L07-bis — PR **#500**, version 0.98.40 · L07 — PR **#494**, version 0.98.37 · L06 — PR **#490**, version 0.98.32 · L05 — PR **#482** · L04 — PR **#478** · L03 — PR **#475**, version 0.98.18 · L02 — PR **#470**, version 0.98.13 · L01 — PR **#467**, version 0.98.10. **Every one of them is in git history** — `git show 79ccebe2:docs/archive/features/<lot>/DESIGN.md` reads a lot's design, the tree holds no archive since 2026-09-01 — a fact stated once, because the sentence it replaces was a LIST that grew a clause per wave (« all three archived; L04 and L05 are archived beside them; L06 and L07 are archived beside them ») and had stopped at L07 while three more lots landed. This row exists beside « Landed, in order » to carry what that row does not: the pull request and the version. It carries nothing else, and it names no wave as « this pull request » — that phrase sat here for weeks pointing at a PR merged long before, which is B-152's shape and the reason this row was re-read at all |
| **Landed, in order**       | L01 · L02 · L03 · L04 · L05 · L06 · L07 · L08 · L09 · L10 · L15 · L11 · L12 · L14 · L19 · L21 · L13a · L13b · L20 · L13r · L13c · L22a · L22b · **L16**, plus the correction waves L07-bis and L08-bis, the design phase L10-ter, and the repair train of 2026-09-28 (PR #625, not a lot). **The engine's lot is COMPLETE** — all four of its sub-lots, L13a · L13b · L13r · L13c, landed at PR #607. **Arrivées dans Acquisition is now COMPLETE** — its two sub-lots, L22a · L22b, landed, closing on this row's own PR #626 (the folder's own death and citation rewrite is THIS pull request's gesture, per the engine lot's own precedent). **L16 — §18, the ratio, landed at PR #634** — its own folder's death and citation rewrite is THIS docs pull request's gesture, per the engine and L22 lots' own precedent. **This row is a HISTORY — the order things LANDED, which is not the plan's order; that is `frontend-architecture.md`'s alone.** And it names no lot that has not landed, not even to say so: `check-frontend-boundaries.py`'s size arm reads this cell for its list of landed lots and refuses a ceiling label naming one of them, so a lot mentioned here in passing is a lot the guard reports as gone. Written after that arm went red over four labels for exactly that reason, in the pull request that added a clarifying sentence to this cell. **This row is the state the plan's § 0 reads** — since 2026-08-28 `frontend-architecture.md` carries the order and the dependencies and no status at all, so a lot's progress exists once and cannot go stale in a second copy |
| **What decides the order** | `docs/reference/frontend-architecture.md`, never this table. This table says only where the work STANDS                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |

**Everything below this line, and above « Where to start », is HISTORY** — the review
cycles, the phase-by-phase walkthroughs and the per-lot decisions from L03 through L10bis,
current only as prose duplicating the table above, and stale independently of it since
2026-09-16 (three days after the last touch this section records). It is git, not this file:
`git show 232a908ca:IMPLEMENTATION.md` reads it whole, exactly as this pull request found it
(the documentation model — history is cited by commit, `docs/reference/documentation-model.md`).

---

## Where to start

**`BUGS.md` at the repo root is the bug register.** Every defect the operator reports is written
there when it is reported, one is closed at a time, and a fix closes only with a mutation-tested
rule that covers the path the operator actually walks. Read it before starting anything. Closed
entries keep their full history in `BUGS-CLOSED.md`, indexed from `BUGS.md`.

Read, in this order:

1. `frontend/maquette/README.md` — the prototype's contract, its named states, the rule set,
   and the traps already paid for. It is short and it saves days.
2. `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md@79ccebe2` — §7 carries the
   method. Its §8 phases describe deriving the app surface by surface, which is the order the
   mission reversed: read them as history, not as instructions.
3. `BUGS.md` — what is reported and not yet confirmed.

**Serve the prototype locally.** There are TWO hosts and the harness measures only one of
them — running the wrong one is a green run over nothing.

|                  | Port     | What                                                                                                                                                | Started by                 |
| ---------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| **Harness host** | **8899** | `harness/server.py --serve`, rooted in `/private/tmp/tm-refonte`, serving a COPY of the build at `/` and folding every router-owned address onto it | `run.sh`, or by hand       |
| **Design host**  | **8712** | `serve.py`, scrypt password-protected (`tm-design.iznogoudatall.xyz`)                                                                               | PM2 (`torrentmate-design`) |

`harness/common.py` pins the first one: `PROTOTYPE = "http://127.0.0.1:8899/"`.
Never 8710/8711/8712/8899 for a server of your own — `harness/server.py`'s `RESERVED_PORTS`
names all four, and the reverse proxy routes the first three to production, staging and the
design host.

**`python3 serve.py 8899` is wrong**, and it is the recipe this file used to carry: `serve.py`
is the DESIGN host, it answers **401** without a session, and the harness would then measure the
sign-in screen — every rule green, nothing measured.

**A plain `python3 -m http.server` is wrong too, and that one is newer.** It was right while a
page lived in the query: the document had one address, `/wrapped.html`, and a static server
serves a file at its own path. Since L05 a page sits on a real path, and a plain server answers
404 to every one of them — which the router renders as its not-found page, so the whole suite
would measure that instead of whatever was under test. `harness/server.py --serve` folds any
address with no file behind it onto the document, and keeps a 404 for the resources that really
are files (`/vite/…`, `/assets/…`, `/sw.js`, `/manifest.webmanifest`). What has not changed is
where it is ROOTED: on the copy of the BUILD, never on `design/`, which would serve unbuilt
TypeScript and measure nothing real.

```bash
# 1. Rebuild, and refresh the copy the harness reads — BEFORE EVERY RUN.
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets

# 2. The harness host — check before starting, it is usually already running.
lsof -nP -iTCP:8899 -sTCP:LISTEN || (python3 frontend/maquette/harness/server.py --serve 8899 /tmp/tm-refonte &)
```

Two traps, each paid for twice. A STALE COPY of the rule scripts can end up in
`/tmp/tm-refonte`, and running those measures the previous version — there is none there today
(`ls /tmp/tm-refonte` → `assets`, `server.log`, `vite/`, `wrapped.html`), so this is a warning
about what to check, not a description of what is there. And a `wrapped.html` that was not
re-copied measures the previous build.

The prototype needs a wrapper supplying a viewport meta; the harness scripts build one. Without
it Chrome falls back to the legacy 980px layout viewport and every measurement is wrong.

**Run the harness.** The project's own `python3` (3.12.4, Playwright 1.62.0) carries Playwright;
the hardcoded 3.11.9 path this file used to require is no longer needed (PM2 keeps it for
`serve.py`).

```bash
cd frontend/maquette/harness
for s in *.py; do
  [ "$s" = common.py ] && continue   # the shared plumbing, not a rule
  python3 "$s" > /dev/null || echo "FAILED: $s"
done
```

Every script fails through its exit code, not through its output. A script that only prints
cannot fail, and a script that cannot fail is a report nobody is obliged to read.

**Two traps, each already paid for twice.** A stale copy of the scripts lives in
`/tmp/tm-refonte`; running from there measures the previous version. And `/tmp/tm-refonte/
wrapped.html` — the harness's copy of the BUILD, the same document the host serves — must be
rebuilt and re-copied before every run, or the same thing happens one level down:

```bash
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets
```

`pwa.py` measures the LIVE host `tm-design.iznogoudatall.xyz`, not the local server. After
editing `serve.py`: `pm2 restart torrentmate-design`.

---

## THE OBJECTIVE — what the maquette is, in one paragraph

**The maquette is the next version of the frontend, and it will REPLACE the current one.** On
switchover day `frontend/src` is ARCHIVED and `frontend/maquette/` takes its place. Nothing is
transposed, translated or merged surface by surface — which is why every page and every
MECHANISM the shipped app has must eventually exist here: afterwards there is nothing left to
take from it. The backend is adapted to what this interface needs, and that work comes after the
interface is frozen.

### What is done, and what remains — measured 2026-08-20

Read this table instead of counting surfaces. **The pages are the part that is finished**; what
remains is most of what makes an application.

|                      | Production                                           | Maquette                                                                                                                                                            |
| -------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API modules          | **11** (`frontend/src/api/*.ts`)                     | **0**                                                                                                                                                               |
| Network calls        | **65** `apiFetch` · 36 `useQuery` · 21 `useMutation` | **1** — and it is a LOGOUT (`legacy.js:11514`). Unchanged by L08, and the row is left in its own unit on purpose: the mock layer declares 53 OPERATIONS and no surface calls one, so counting them here would put a different unit in a measured cell. **Zero data still reaches the maquette from a BACKEND** — a mock layer is not a connection |
| WebSocket            | **24** files                                         | **0**                                                                                                                                                               |
| Service worker / PWA | yes                                                  | no                                                                                                                                                                  |
| Pages drawn          | 9                                                    | 9 + 5 screens — **not the same nine**: `/control` and `/pipeline` have no maquette page (owed, see REMAINS), and `host` + `arrivals` have no production counterpart |

Commands — and the maquette's needs `--include='*.js'` too, because its single call lives in
the legacy engine, a `.js` file the other two globs walk straight past (an adversarial review
ran the command as first written and got 0):

```bash
grep -rhoE '\b(fetch|apiFetch|useQuery|useMutation)\(' \
  --include='*.ts' --include='*.tsx' --include='*.js' frontend/src | sort | uniq -c
grep -rlE 'WebSocket' --include='*.ts' --include='*.tsx' --include='*.js' frontend/src | wc -l
# then the same two over frontend/maquette/design/src
```

**DONE** — 8 pages and 5 screens as final components; TanStack routing with the URL carrying the
state; 82 named states driving 50 rule scripts over 80 recorded rules; the engine moved out of
the fragment (which is now a title and a stylesheet); English names throughout with the shell's
copy in i18n resources; colour and elevation tokenised — **186 of 188** `color:` declarations (`(?<![-\w])color\s*:`; a `\bcolor` regex reads 203/206 because `-` is a non-word character and `background-color` matches it), and the 55 raw values left in BLOCK 2 are all token DECLARATIONS, which is where they belong.

**REMAINS** — the four subjects, and this list is NOT an order.

> ⚠ **The order is `docs/reference/frontend-architecture.md`'s lots, in that file's order, and nothing else.**
> This list used to open « in the order the work actually has to happen », and that sentence
> survived #466 by four days while naming an order that file had replaced. Read as an order it
> sends the next session to draw `/control` or to open the visual language — and the visual
> language is lot **L06**, which `depends on L01` under a Phase 0 that says « Nothing else may
> start ». **Which lot comes next is § « Where the frontend work stands », at the top of this
> file.**

1. **The two pages the mission re-opened** — `/control` (8 panels) and `/pipeline` (10 panels).
   **A lot since 2026-08-29: L20**, declared by L10-ter because four DOIT clauses hang on them.
2. **The visual language (SP5b)** — type, radius and spacing have no scale at all: 21 distinct
   font sizes for 150 declarations, 16 radii, 64 padding values for 112 declarations, and three
   spellings of one pill (`99px` ×25, `9999px` ×11, `50%` ×1).
3. **The size of the gap the SWITCHOVER closes — not work the maquette does now.** The table
   above measures it: 11 API modules against 0, 65 network calls against one logout. But
   **while the maquette is a maquette it is NOT connected to the backend** (operator,
   2026-08-20), and that is deliberate, not a lag: fixtures are what make 82 named states
   drivable and 50 rules deterministic. A prototype wired to live data measures the data, not
   the design. The wiring belongs to the switchover, with the backend adapted to what the
   frozen interface needs. What the table is FOR is honesty about the distance: no document
   stated it before 2026-08-20 — they counted surfaces, and surfaces were never the hard part.
4. **The legacy engine** — 34 626 lines still driving, `__go` shell-side, the 240 ms delay on
   `data-next`, and `/login` + the splash still engine-driven markup rather than components.
   **79 % of those lines are FIXTURES** — `SHEETS_RAW` alone is 20 538 — so the engine's own code
   is about 6 949 lines, and most of the rest stops existing when real data arrives. That is why
   items 3 and 4 are interleaved surface by surface rather than run one after the other.
   <sub>method: bracket-match every `const X = [` / `const X = {` in `legacy.js` and sum the spans over 100 lines</sub>
5. **BLOCK 1 must stop shipping at switchover.** `refonte.html` is split into BLOCK 1 (the
   prototype harness — phone frame, demo bars, design notes) and BLOCK 2 (the application). The
   maquette's own build carries BOTH today, which is right for a prototype and wrong for the
   app. `harness/export.py` used to guard that boundary from the extraction's side and went with
   it; nothing guards it now.

**Items 2 to 5 above are planned in `docs/reference/frontend-architecture.md`** — the settled
architecture decisions and the ordered lots that reach them, each with its dependencies and its
definition of done. (Item 5 is held by its lot L07: BLOCK 1 is deleted rather than converted, and
its disappearance is part of that lot's proof.) That file says what must become true and in what
order; **this section stays the only place that says where the work stands.** Item 1 is
deliberately outside it: those two pages are surfaces to be drawn, and the existing method
covers them.

### THE MISSION — dictated by the operator, 2026-08-19

**The maquette is a NEW VERSION of the app, and EVERY screen is to be redrawn. All of them.**
It is not a reskin of the shipped surfaces and it is not bounded by what production has today.
Its purpose is a new, COHERENT user experience, and the first objective is to **freeze that
interface**.

- **No surface is out of scope.** A production screen with no page here is a page still to be
  drawn, never an arbitration to leave it out.
- **What the maquette already holds is VALIDATED** by the operator. Do not relitigate it.
- **What remains is not only pages**: the UX, the interaction language and the prototype's
  ARCHITECTURE all have to be finished and consolidated before the interface is frozen.
- **The backend follows the interface.** The engine will be adapted to what the new interface
  needs, and that work comes AFTER the freeze. A backend limitation is therefore never a reason
  to draw less — record it, and draw what the experience requires.

**This supersedes the `Gone | Contrôle` ruling below.** Read the section that follows as the UX
argument for WHERE those panels belong — that argument stands — and never as a licence to leave
`/control` or `/pipeline` undrawn. The operator overturned that exemption on 2026-08-19.

---

## What the v1 still owes, page by page

Read from the shipped router (`frontend/src/router.tsx`) and the shipped nav model
(`frontend/src/components/layout/nav.ts`) against the prototype's named states.

Two of production's routes are already redirects and owe nothing: `/scraping` → `/media`,
`/registry` → `/systeme`. A third, `/maintenance`, is **also** a redirect — `MaintenanceRunRedirect`
sends it to `/systeme?tab=journal`, or to `/pipeline?run=…` when it carries a run. The page it
names has not existed for some time; its panels live on `/systeme`.

### The v1's structure, and it is settled

The prototype's four tabs and production's four do not agree: production's bar is
`Acquisition · Médias · Pipeline · Contrôle`, the prototype's is
`Acquisition · Médiathèque · Arrivées · Système`. The disagreement was arbitrated by the
operator rather than split down the middle, and the arbitration replaced the question:

> **The cut is by the NATURE OF THE TROUBLE.** A medium in trouble is Arrivées. A machine in
> trouble is Système. A setting is Configuration. A command run against the library is
> Maintenance.

That axis is the reason the panels can be placed at all. Production's `/controle` has no axis —
it stacks blocked media (`ToHandleList`) on top of disk and provider health (`CompactHealth`)
with nothing saying why they share a page. **So `Contrôle` does not survive AS IT IS**: its
eight panels each have a home under the rule — `ToHandleList`, `ScrapeActivityPanel`,
`LastRunDigest`, `StalledPanel`, `AcquisitionSummaryCard`, `SchedulersPanel`, `CompactHealth`,
`PipelineControls`, read from `frontend/src/pages/Dashboard.tsx`.

> ⚠ **Amended 2026-08-19.** This paragraph used to conclude « none of those homes is a new
> page », and that was read as « `/control` and `/pipeline` are deliberately page-less ». The
> operator has overturned that: every screen is redrawn, these two included. What survives here
> is the PLACEMENT argument — a medium in trouble is Arrivées, a machine in trouble is Système —
> not an exemption from being drawn.

|         |                                                                                         |
| ------- | --------------------------------------------------------------------------------------- |
| Bar     | `Acquisition · Médiathèque · Arrivées · Système` — unchanged                            |
| Off-bar | `Maintenance` · `Configuration`, reached from Système and from the drawer               |
| Redrawn | `Contrôle` — its panels are placed by the rule above, and the page is OWED (2026-08-19) |

Where every shipped panel lands. The first block places itself; the second was arbitrated;
the third is derived from the rule rather than asked again.

| Shipped panel                                         | Home            | Why                                                                                                                                                                               |
| ----------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ToHandleList` — blocked staged media                 | **Arrivées**    | a medium in trouble                                                                                                                                                               |
| `ScrapeActivityPanel`                                 | **Arrivées**    | a medium being identified                                                                                                                                                         |
| `RecentResolutions`                                   | **Arrivées**    | a medium just unblocked                                                                                                                                                           |
| `FlowBoard` — the eight stages                        | **Arrivées**    | the pipeline's health is where its media are                                                                                                                                      |
| `CompactHealth` — disks, index, Redis, providers      | **Système**     | a machine in trouble                                                                                                                                                              |
| `ActionCatalog`, index repairs, `DestructiveLogPanel` | **Maintenance** | commands run against the library                                                                                                                                                  |
| `PipelineControls` + `PipelineActionBanner`           | **Arrivées**    | DOIT-3 — act where one observes. The blocked stage and the button to relaunch it are one glance                                                                                   |
| `RunHistoryTable` · `RunDetail` · `RunLogFeed`        | **Système**     | « succès d'exécution » and « logs ». Arrivées keeps the PRESENT — what is stuck, what arrived in 24 h — and never becomes an archive                                              |
| `AcquisitionSummaryCard`                              | **Acquisition** | the tab already shows it in full; it does not owe a second, shorter copy                                                                                                          |
| `SchedulersPanel`                                     | **Système**     | did it fire, did it succeed. Its HOUR is a setting and lives in Configuration — the schedule and its health are two objects that share a name                                     |
| `LastRunDigest` — « X détectés, Y récupérés »         | **Arrivées**    | a count of media, not of executions. The run's _history_ is Système's; the last run's _result_ is the story of what arrived                                                       |
| `StalledPanel` — per-step reasons                     | **split**       | a torrent deferred for ratio is a medium (Arrivées); a step that raised is code (Système). The operator's rule is explicit: no blocked medium in Système, but its code errors yes |

### The surfaces drawn so far — and the two the operator has since re-opened

**Every row below is drawn and VALIDATED.** What this table is NOT is a statement that the
surface inventory is closed: since 2026-08-19 the mission is that every screen is redrawn, so
`/control` and `/pipeline` — production tabs with no page here — are **owed**, and this table
does not yet list them.

| Surface                                                                       | State                                                                                                                            | Rule                       |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `/login`, `/acquisition`, `/media`, `/config`, `/media/:provider/:providerId` | drawn before this                                                                                                                | R49–R63                    |
| **Arrivées**                                                                  | **drawn** — the pilot's bar, the nine steps of the last real run, its digest, and « arrivé dans les 24 h »                       | R66, `harness/arrivals.py` |
| **Système**                                                                   | **drawn** — the deferral is lifted. PM2 services, schedulers, the pipeline's executions, disks, index, dependencies, code errors | R67, `harness/machine.py`  |
| **Maintenance**                                                               | **drawn** — six rubrics over the engine's 26 real `library-*` commands, plus the destructive journal                             | R67                        |
| **Configuration**                                                             | **extended** — a seventh rubric, « Les passages programmés », over the six real cron schedules                                   | R60 extended               |
| `*` (NotFound)                                                                | **drawn** — and it closed a crash: an unknown id used to stop the whole frame on a TypeError                                     | R68, `harness/address.py`  |
| multi-user account                                                            | **drawn** — the one real account, its session read from `web.json5`, and the place of the others marked EMPTY                    | R68                        |

Every figure on these surfaces is read from the live system — `pipeline_run`, `pm2 jlist`, `df`,
`library.db`, the maintenance registry, `web.json5`, `ecosystem.config.js`. Four of the rules go
back to those sources AT RUN TIME rather than comparing against a number written beside them: R66
against `pipeline_run` by run_uid, R67 against `pm2 jlist` and the maintenance registry in both
directions, R68 against `web.json5`.

---

## The third axis: what the prototype owes as an APPLICATION

The operator's judgement is on the design **and** the front-end architecture. The design is
measured by 50 rule scripts (`ls frontend/maquette/harness/*.py` → 52, minus `common.py`, which
is shared plumbing). `regions.json`'s `$adversarialReview` records **80** numbered rules — but
**16 of them are named in no harness script at all** (R18, R19, R21, R24, R25, R32-R40, R49,
R58), so at most 64 are executable. « 80 rules » is an inventory, never a coverage figure;
the architecture was measured by nothing.

**EVERY FIGURE BELOW CARRIES ITS DATE AND ITS COMMAND, and that is the point of the column.**
The version of this table dated 2026-08-16 was taken before the single file was split, and by
2026-08-19 not one of its eight rows was still true — yet it was captioned « Today » and was
read as current for three days. Worse, two of its numbers (« 83 » and « 265 ») could not be
reproduced by any command anyone could name. Re-measure before citing; if a row's command no
longer produces its number, the row is stale, not the code.

All commands run from `frontend/maquette/design/src`, over `*.js`, `*.ts` and `*.tsx`.

| Measure                              | 2026-08-19                   | Command                                                                                                                                                                                      | 2026-08-16                             |
| ------------------------------------ | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| lines of code                        | **42 176**                   | `find . -name '*.js' -o -name '*.ts' -o -name '*.tsx' \| xargs wc -l`                                                                                                                        | 41 400                                 |
| hardcoded data sets                  | **54** array literals        | `grep -rEho '^\s*(const\|let\|var)\s+\w+\s*(:[^=]*)?=\s*\[' --include='*.js' --include='*.ts' --include='*.tsx' . \| wc -l`                                                                  | « 83 », by no known command            |
| network calls                        | **1**                        | `grep -rEo '\b(fetch\|XMLHttpRequest\|axios)\s*\(' … \| wc -l`                                                                                                                               | 1                                      |
| direct `state.` accesses             | **142**                      | `grep -ro '\bstate\.' … \| wc -l`                                                                                                                                                            | « 265 », by no known command           |
| `currentState()` calls               | **99**                       | `grep -ro 'currentState()' … \| wc -l`                                                                                                                                                       | not measured (the alias still existed) |
| `render()`                           | 1 defined, **67** bare calls | `grep -rEo '(^\|[^.\w])render\(\)' … \| wc -l`                                                                                                                                               | 1 defined, 47 calls                    |
| named `window.__` seams              | **26** distinct              | `grep -rEoh 'window\.__[A-Za-z0-9_]+' … \| sort -u \| wc -l` — the `-h` is load-bearing: without it `grep -r` prefixes each match with its file name and `sort -u` counts 56 file/name PAIRS | 11                                     |
| `history.pushState` / `replaceState` | **1 / 0**                    | `grep -rEo 'history\.(pushState\|replaceState)' …`                                                                                                                                           | 5 / 3                                  |
| reads of browser `location`          | **6**                        | `grep -rEon '(window\.)?location\.[a-zA-Z]+' …`, minus TanStack's own `history.location` / `location.state`                                                                                  | 3                                      |

Two of those moves are explained rather than mysterious: `pushState` fell to 1 because SP3 made
the router the single writer of history, and `state.` fell from 265 to 142 because SP4-fin wave 3
killed the alias — the reads did not disappear, 99 of them became `currentState()`.

None of these numbers is a defect **of the prototype**: a single dependency-free file is
exactly what made it verifiable. They are the **seams** the binding will have to open.

### The three questions, and what they are worth now

**1. Where does a piece of data come in?** 54 array literals by the command in the table above (2026-08-19), against « 83 » claimed on 2026-08-16 by no command anyone can name — the figure depends entirely on what the regex counts, so cite the command with it or do not cite it. What matters is not the count: the number rose across the drawing waves and the
situation improved, which is only apparently contradictory: every new constant is read from a
living source named in its comment — `pipeline_run`, `pm2 jlist`, `df`, `library.db`, the
maintenance registry, `web.json5`, `ecosystem.config.js` — and **four rules go back to those
sources at run time** instead of comparing against a number written beside them. R66 checks the
run by its `run_uid`, R67 counts processes against `pm2 jlist` and commands against the engine's
registry in both directions, R68 reads `web.json5`, R63 reads `acquire.db`.

That is the answer to the question, and it is executable: **a constant whose value is verified
against its source is a named seam; a constant nothing verifies is a coupling.** R63 demonstrated
it on its own by failing when the scheduler ran — a rule that fails with TIME does not signal a
defect, it points at a seam. The triage remains to be done: how many of those constants are
verified against their source, and how many are a coupling.

**It fell again the same day**, a few hours later: the 15:20 run pushed Silo from 9 to 11. Twice
in one session, without a single line of the prototype being touched. That is no longer an
illustration of the question, it is its answer: **those constants cannot be maintained by hand,
and the binding has no choice but to wire them.**

**2. Who owns the state?** Nobody — **142** direct `state.` accesses plus **99**
`currentState()` calls (2026-08-19), against 265 measured on 2026-08-16. **Read that fall as a
RENAME, not as progress**: SP4-fin wave 3 killed the `state` alias, so the reads moved to
`currentState()` rather than going away. Nothing moved on the ownership front and that is
deliberate: splitting the state requires splitting the file, and a single file is exactly what
made the rule suite writable. **This is the question that remains whole**, and the only one of
the three that cannot be settled without first deciding how the prototype gets split.

One thing was still learned crossing it: `state.pipe` **leaked** from one named state to the
next, so the same id did not render the same thing depending on the path taken to reach it. R10
found it. That is the exact cost of ownerless state, and the counter-measure fits in one
sentence: **every named state names ALL of its dials**, as it already named its page and its
phase.

**3. Where does a route live?** It used to live in `state.page`, and the URL did not carry it.
**That is settled.** The measurement that said so was final: `history.pushState` four times,
`location` read **zero** times — the interface told the browser where it was and never asked it.
That was not a debt to hand over, it was a **non-conformity with DOIT-10**, and it showed: a
reload fell back onto the opening page, and no screen could be sent to anyone.

The state travels in the QUERY, not in the path, and that is a decision: this document opens
from a static server, from the prototype host, and from `file://`, and path-based routing
requires a server that rewrites every unknown path to the document — two of those three cannot.
The binding will map `?page=lib` onto production's `/media`; what is judged now is that the URL
and the interface never contradict each other. R69, `harness/url_state.py`.

---

**Next action:** two things are owed and they are of different kinds:

1. **The surfaces the mission re-opened** — `/control` and `/pipeline` have no page here, and
   since 2026-08-19 that is a gap, not an arbitration. Drawing them is maquette-first work:
   drawn, named states, a rule that bites, a mutation that proves it.
2. **The visual language, the application and the legacy engine** — including the three
   questions of this section. **Their scope is written**: `docs/reference/frontend-architecture.md`
   carries the settled decisions and the ordered lots, each with its dependencies and its
   definition of done. Take the first lot in that file's order which the « Landed, in order » row
   above does not name and whose dependencies it does.
   One consequence was already recorded in the SP4-fin plan and still holds: `refonte.html` is
   on its way out — BLOCK 2 becomes a stylesheet of the maquette's own Vite project, and BLOCK 1
   goes with the harness.

> This paragraph read « frame the remaining work with the operator … SP5 has no written scope:
> it is to be agreed before any code » until that scope was agreed and written. Left as it was,
> it sent a session that had just been told where to start back to asking where to start.

Every surface listed in the inventory above IS drawn and validated — `harness/arrivals.py` (R66)
executes green against `library.db` for the most recent one — so nothing there is to be redone.

**This line used to say « draw the missing surfaces — Arrivées first », and that was wrong from
the day it was written.** It and the inventory that contradicts it landed in the SAME commit
(`c49e7ada`): inside that one commit Arrivées was already marked **drawn** while this paragraph
asked for it to be drawn. The contradiction was original, not drift — so « the lower line is
older » is not an argument, and `git blame` refutes it. Whoever reads a conflict here again:
the inventory is the one carrying material proof (a page component, a rule, an executed run).

Note that question 3 was not only architecture: **DOIT-10 requires every detail to have its
URL**, and the prototype's routes used to live in `state.page` alone. That non-conformity is
closed — the URL carries the state in its query, held by R69; what the binding still owes is the
mapping onto production's paths.

---

## What the prototype already settles

These were argued, measured and recorded. Re-opening one costs a day; the reasons are in
`frontend/maquette/regions.json` → `$adversarialReview` (**80** R-entries as of 2026-08-19, « 65 » before) and, nested inside it, `$methodLessons` (**43**, « 37 » before).

- **The prototype is the reference.** A divergence between the app and it is a defect in the app,
  unless the prototype was amended first with the reason written down.
- **The CSS is the maquette's own — RETIRED 2026-08-20.** This entry used to read « CSS is
  extracted, never retyped », then « SP5's target, not today's state ». Both are void: the
  extraction, the `.tm` scoping, the 461-entry allowlist and the rendering-parity probe existed
  so the SHIPPED app could be migrated towards the maquette surface by surface, and the maquette
  REPLACES the app. BLOCK 2 of `refonte.html` IS the application's stylesheet; nothing lifts it
  or copies it. `scripts/check-css-tokens.py` holds what still matters — every `var()` in
  BLOCK 2 resolves inside BLOCK 2.
- **Every gesture answers a pointer** — and a finger is read from the stream the compositor does
  not cancel. A gesture living inside the scrollport reads touch events; one that can claim its
  axis in `touch-action` keeps the pointer path.
- **Episode presence is read, never inferred.** A `number <= owned count` threshold assumes the
  hole is at the end of a season; it is false for 35 series in this library.
- **A trailer always opens YouTube**, never in-app playback, wherever one arrives from.
- **One back control**, in the flow, on every screen that has one.
- **One card, one behaviour.** The poster opens the media sheet, the card body opens the bottom
  panel, a gallery tile answers a long press. The panel carries EVERY action for that medium;
  an inline button is a shortcut, never the only way in. The panel is derived from what is true
  about the medium, so the one reached from a gallery equals the one reached from a card.
- **One builder per shape, not per screen** — and none of them takes markup. `cardHTML` for every
  list, `tileHTML` for every gallery, `panneauHTML` for every bottom panel, a separate builder
  for a release candidate (not a medium: no sheet, no panel). Each takes a descriptor of FACTS;
  a view wanting something outside it adds the fact rather than passing markup.
- **One season rendering**, within a sheet and across sheets.
- **Identify is not follow.** Resolving a stuck folder associates a medium so the pipeline
  finishes; it never creates a follow.

## Method lessons that cost the most

- **A screenshot fingerprint is not an oracle.** Two captures of the same unmodified file diverge
  on 8 to 15 of the states. Use bounding rects plus a computed-style subset.
- **A synthetic event is not a finger.** It is never cancelled, so it cannot tell whether a
  gesture survives the compositor. Two gestures were lost that way and no script noticed.
- **A rule that never bit proves nothing.** Every rule added is mutation-tested: break the
  behaviour on purpose, confirm the rule falls and names the right defect, restore.
- **A derivation must not read back its own output.** The list poster was sized against the
  median card and now sets it, so the computation returns its own answer.
- **A rule can assert the DEFECT.** R53 did, twice, in both directions: it first certified a
  startup screen that flashed for one frame, then demanded a floor that made the bar play twice.
  Writing down the behaviour that exists is not the same as writing down the one that is wanted.
- **« It cannot affect production » is a measurement, not an argument.** The prototype was proved
  harmless by building the bundle on both sides and comparing — and the first comparison said no:
  Tailwind v4 scans from the project root, took six words out of `refonte.html` for utilities, and
  shipped 936 bytes of them to production. The design host's icons, sitting in `frontend/public/`,
  shipped another 56 kB the same way.

---

## Carried, not hidden

1. **Plex deletion.** `api/plex.py` only refreshes. Which route removes an entry on this server is
   a verification step of the binding mission, not a claim of this one.
2. **A real deletion cannot be validated before production.** Staging writes to the real disks and
   the real databases, and fabricating a medium for the proof is forbidden. Protocol: dry-run only
   on staging; the first real deletion happens after the production merge, on a medium the
   operator names, after a genuine `sqlite3 .backup` — a file copy of a WAL database is not a
   backup.
3. **The multi-user account system** is a later mission. The user menu draws its place — profile
   and preferences, disabled, saying why — so the shape is settled before the feature lands.
4. **`?tab=maintenant`.** The label became « En cours »; whether the URL param migrates with a
   legacy redirect or stays is decided when the prototype is bound to the backend. The deep link
   must keep working either way, and the prototype has to DRAW what a legacy link lands on.
5. ~~**The list poster cannot be enlarged by its own derivation.**~~ **Closed**, and the question
   was replaced rather than answered: the poster is no longer a fraction of anything, it reaches
   the card's edges. 84px wide, with the card's height as its floor, so a card at that floor
   gives an exact 2:3 and its artwork is untouched. What remains named in R47 is the limit —
   full height and the 2:3 ratio cannot both hold on a taller card, so cropping is bounded.
6. ~~**The design host and the app share their icons.**~~ **Closed.** The design host carries a
   yellow-ringed set of its own, generated from staging's shape by
   `frontend/scripts/make-design-icons.py`.
7. **The arbitration SCREEN itself is drawn but not built.** `ds/DecisionRow` and the vocabulary
   are derived; the screen's own shape — one folder at a time, the three ways out side by side,
   the progression replacing the desktop deck's keyboard shortcuts — belongs to the Arrivées
   screen the prototype already draws — what is missing is the app, and the app comes after the
   operator's judgement.
8. **The synopsis is not in the read-model.** The library's rows carry it in the prototype, read
   from the `<plot>` of each medium's own NFO — real data, but `library.db` has neither a column
   of `media_item` nor a key of `item_attribute` for it. The app cannot render this surface until
   the read-model grows the field, and the scan that fills it. Nine of 349 titles have no plot at
   all, and those must show nothing rather than a filler.
9. ~~**Editing a setting is drawn only as far as the panel.**~~ **Closed.** Five fields, one
   refusal and one state that crosses them, each derived from the setting's VALUE rather than
   from a list of keys. R60 extended, `harness/settings.py` — 42 checks, eight named states, one
   per field.
10. **Five tokens the app will owe.** The design-system lint found nine hardcoded colours in the
    prototype — a real C19 violation, and one of them (`var(--warning, #d97706)`) was the B-014
    shape again: a fallback onto a token that IS defined, which is a landmine that has not gone
    off. They are tokens now: `--mq-shadow-toast`, `--mq-shadow-pop`, `--mq-shadow-card`,
    `--mq-shadow-badge`, `--mq-scrim-soft`, `--mq-tile-overlay`. Their VALUES live in the
    prototype's own palette. ⚠ **Amended 2026-08-20 (SP5a):** that palette sat in BLOCK 1 and
    was therefore NOT exported, so the generated stylesheet named these tokens and defined
    none of them — thirty-five used, one declared, across 458 `var()` calls. The palette has
    moved into BLOCK 2, where the application's rules can see it, and
    `scripts/check-css-tokens.py` refuses the next `var()` with no declaration. The sentence that stood here — « when the app adopts
    that stylesheet, `tokens/maquette.css` must gain the five it does not yet carry » — is
    obsolete: nothing is owed to `tokens/maquette.css`, and the count was five only because it
    looked at one token family. Measured, because « it
    custom properties in the shipped CSS, and leaving them out keeps `frontend/dist`
    byte-identical.

11. **Answering a decision was a no-op on the acquisition side.** Found while drawing the screen:
    « Résoudre → » on « À traiter » opened the screen, took the choice, and left the item exactly
    where it was, because the answer only ever looked in the Arrivées list. Fixed in the prototype.
    The app's equivalent — whether resolving from one queue clears it from the other — is a
    verification step of the binding mission, on the real API, not a claim of this one.
