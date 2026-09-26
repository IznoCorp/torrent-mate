# L17 — §19, cross-seed is seen and decided · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L17 — §19, cross-seed` (its « Where it lives »
and « Done when » lines). It is not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every figure carries the
command that produces it, every decision carries its reason, every screen carries its named states. **Nothing under
`frontend/maquette/design/` was touched to write it** — it is prose and numbers, written on `origin/main` at
`46806a88d` (2026-09-27), and the lot opens after L16 (the plan's order is L13 · L22 · L16 · L17 · L18). It is drawn
IN ADVANCE, by the auditor's order 47: a drawing ruled before the code costs zero rework.

**Two consequences of that date, said before anything else.**

1. **L16's files do not exist on this head.** `ls frontend/maquette/design/src/features/` names `account`,
   `acquisition`, `arrivals`, `library`, `maintenance`, `media`, `releases`, `settings`, `system` — no `trackers`.
   L17 EXTENDS L16's drawing (`docs/features/maquette-l16/DESIGN.md`, merged #614, read and not amended): the roster,
   the tracker's detail, its obligations, `trackersBadge`, `features/trackers/live.ts`. Every figure below about a
   file L16 creates is taken from L16's plan, and the phase that reads it says so and re-takes it at its opening.
2. **The mock is INVENTED, and the lot says so on every seed row.** No fixture exists for cross-seed: neither contract
   carries a route for it, the engine's two events reach no surface, and the live configuration has the mechanism
   switched OFF everywhere (§ 0.2). L08's « seeded from the fixture it replaces » does not apply; D7's first real case
   does (`docs/reference/frontend-architecture.md` § 2, D7). Every seed row this lot adds is marked `x-unseeded` — the
   contract's own word for « nothing was invented here » and « nobody looked » being different things — and none is
   ever presented as lived data (§13, `product-intent.md` § 13).

**Its spine is not mine.** `product-intent.md` § 19 « Ce que l'opérateur a tranché » (dictated 2026-08-30) dictates the
lot: AUTOMATIC, a PER-TRACKER off switch, a per-torrent per-tracker state in four words, the state on the Trackers
page and a per-tracker block in the media sheet for the administrator only. The operator's organisation rulings of
2026-09-26 place it. This document transcribes; where a ruling left a hole it says OPEN and draws no choice (§ 7.2).

---

## 0. What L17 owes, said once

`docs/reference/product-intent.md` § 19, § 17 (points 1, 2, 4 and « Ce que cela tranche »), § 18, § 12, § 13,
NE-DOIT-PAS-5, -6 and -8 and DOIT-14 give the lot the fourteen clauses below. The table says, for each, the surface
that serves it (§ 3) and the phases that build it (`plan/INDEX.md`).

| # | The clause | Its source | The surface that serves it | Phases |
| --- | --- | --- | --- | --- |
| 1 | The engine cross-seeds **alone, active by default** — no act is asked of the operator | § 19, « Ce que l'opérateur a tranché » | no control: the STATES read (S1–S3); the default itself is a backend demand (H, § 6.2) | 1, 5 |
| 2 | A **per-tracker off switch** — NE-DOIT-PAS-6 becomes that setting, tracker by tracker | § 19, same | S2's head reads it; the control's home is OPEN 2 | 9 |
| 3 | **For each torrent, the state tracker by tracker**: « actif », « stoppé », « tracker sans cross-seed », « erreur de cross-seed » | § 19, same | S3 (the tracker's section) and S5 (the media block), one derivation | 4, 6 |
| 4 | **The per-tracker state lives in the Trackers page** | § 19, same; organisation ruling 11 | S1 (the roster's line) and S2 (the detail's head and section) | 5, 6 |
| 5 | **A per-tracker block in the media sheet, for the administrator profile only** | § 19, same; § 17 | S5 — the gate is OPEN 1 | 10, 11 |
| 6 | **An injection is seen** | § 19 point 1 | « actif » with its date and its origin on S3; the obligation's origin on S4; the stream moves both (S6) | 6, 8, 13 |
| 7 | **A refusal is explained** — a layout mismatch is not a policy refusal, and each « nothing » has its reason | § 19 point 1, § 8, DOIT-2, NE-DOIT-PAS-5 applied to a success | S3's « erreur » rows with the reason in clear words, grouped by the kind of trouble | 4, 7 |
| 8 | **The cross-seed attaches to the MEDIUM**, so an obligation shows its origin | § 19 point 2, § 18 point 2 | S5 (a title says where it seeds); S4 (an obligation says whose copy it is); every row leads to the sheet by provider ID (NE-DOIT-PAS-9) | 8, 10 |
| 9 | **To decide is also to refuse** — prevent as much as provoke; no « occupé » | § 19 point 3, DOIT-4, DOIT-14 | prevent: the switch (clause 2); provoke: OPEN 3 | 9, 15 |
| 10 | **NE-DOIT-PAS-8 is the hard limit**: no automation more aggressive | § 19 point 4 | one read per screen visit, no poll (R-L17-k); the engine's own daily quota and delay are shown, never bypassed | 6, 15 |
| 11 | **Ruling 12: the cross-seed speaks on the Trackers tab, and its refusals join the badge** — no notifications box | organisation ruling 12; L16 OPEN 3 = B, the second term | S6 | 12, 13 |
| 12 | **Ruling 11: the Trackers page holds ratio, cross-seed, the tracker itself**, shown by rights | organisation ruling 11; § 17 point 4 | the page L16 lands and L17 extends; the rights are L18's | all |
| 13 | **The interface shows the truth** — every state drawn is the tracker's/engine's, none computed locally | NE-DOIT-PAS-1, § 13 | R-L17-b: one derivation for the roster, the section and the block | 5, 6, 10 |
| 14 | **DOIT-14 reads `served` with a rule** | `product-intent-map.md`, DOIT-14 row (`to draw`, owner L17) | the close reports against it (§ 6.3) | 19 |

### 0.1 The rulings this design is read against, and what each moved

The rulings are the operator's and are not reopened here. « Organisation ruling N » is his entry of 2026-09-26 (10–15)
or 2026-09-15 (1–9) in `docs/reference/operator-method.md`, numbered as `docs/features/maquette-l22/DESIGN.md` § 0
numbers them; the rulings of 2026-09-26 that decide L16 are in that lot's design (§ 5, « Ruled »).

| Ruling | What it dictates | What it moved in this design |
| --- | --- | --- |
| organisation ruling 11 (2026-09-26) | the place Arrivées frees goes to « Trackers » — ratio, cross-seed, the tracker itself; the bar is composed by rights | § 3: there is no page of L17's own; the cross-seed is drawn INTO the page L16 lands. The rights are L18's (§ 7.1) |
| organisation ruling 12 (2026-09-26) | every thing speaks where it lives, a badge on the bar tab that carries it — the ratio and the cross-seed on Trackers; no notifications box; Système's history the only trace of the past | § 3.6 (the tab's second badge term; no box); § 7.2 OPEN 4 names the tension a FEED would have with « the only trace of the past » |
| organisation ruling 15 (2026-09-26) and L22's OPEN 2 | Système leaves the bar; the bar draws only its present buttons, in equal shares of 1/n | nothing: L16 read it at three buttons; L17 adds no button |
| L16 OPEN 1 = A (2026-09-26) | Trackers enters the bar at L16 with the ratio alone; **L17 adds the cross-seed and a SECOND TERM to the badge** | § 3.6 |
| L16 OPEN 2 = A (2026-09-26) | no right declared before L18; Trackers shows for the mock's single account | § 7.2 OPEN 1 — the media block is the one surface of L17 that is *admin only*, so the same question comes back a second time, for a block |
| L16 OPEN 3 = B (2026-09-26) | the badge counts the trackers under threshold AND the obligations in breach; **the refused cross-seeds join it at L17** | § 3.6 and OPEN 8 (which refusals) |

### 0.2 What the engine and the tree measure — found while drawing

Every line below is a fact the drawing rests on, with the command that reads it on `46806a88d`.

| # | Fact | Command → reading |
| --- | --- | --- |
| 1 | **The engine is 797 non-blank lines and emits two events** | `grep -cve '^[[:space:]]*$' personalscraper/acquire/cross_seed.py` → 797; `grep -n 'class CrossSeed' personalscraper/acquire/events.py` → `CrossSeedInjected` (353), `CrossSeedRejected` (373) |
| 2 | **`CrossSeedInjected.source_tracker` is the TARGET tracker** — the tracker the `.torrent` was fetched from and now seeds on; the interface needs it named `tracker` | `sed -n 353,371p personalscraper/acquire/events.py` (« The tracker the ``.torrent`` was fetched from (target) ») |
| 3 | **A refusal carries a CLOSED-SET reason of twelve codes, eleven reachable** (`recheck_failed` is « reserved »); **none is a tracker POLICY** — § 19 point 1's « rejet pour politique de tracker » has no code today | `sed -n 386,411p personalscraper/acquire/events.py` → `fetch_failed`, `magnet_not_supported`, `parse_failed`, `inject_failed`, `self_candidate`, `piece_length_mismatch`, `file_list_mismatch`, `root_name_mismatch`, `v2_hybrid`, `obligation_write_failed`, `verify_timeout`, `recheck_failed` |
| 4 | **A SKIPPED check emits NEITHER event** — eight reasons are only logged (`disabled`, `not_found`, `seed_pure`, `no_piece_size`, `v2_hybrid`, `no_save_path`, `all_excluded_recent`, `not_queryable_for_media_type`) | `grep -n 'skip_reason = ' personalscraper/acquire/cross_seed.py` → seven assignments (one of them takes two values, line 221). So the states « stoppé » and « tracker sans cross-seed » **cannot be derived from the two events**: the backend must keep a state (demand B, § 6.2) |
| 5 | **Every default is OFF — the constitution's « actif par défaut » is not what the engine does** | `grep -n 'cross_seed: bool\|enabled: bool' personalscraper/conf/models/api_config.py personalscraper/conf/models/watch_seed.py` → `cross_seed: bool = False` (`api_config.py:288`), `CrossSeedConfig.enabled: bool = False`; `grep -n 'cross_seed' config.example/tracker.json5` → `false` on both providers; `config.example/watch_seed.json5:4-5` → `enabled: false` |
| 6 | **The live configuration, as the maquette seeds it, has the switch OFF on all three trackers and the engine OFF** | `grep -n -A4 'cross_seed' frontend/maquette/design/src/mocks/seeds/settings.json` → `tracker.providers.lacale.cross_seed`, `.c411.cross_seed`, `.tr4ker.cross_seed` and `cross_seed.enabled`, each `raw: false`, `displayedValue: "non"` (lines 603, 620, 671, 807). This is the operator's own setting and is read as such (§ 2.3). **The seeded roster has THREE trackers**; L16's design says the example config names two (`c411`, `tr4ker`) — L17 draws the roster L16's seed carries and re-measures it at its opening |
| 7 | **The switch already has a write, and a home in Réglages** | `git grep -n 'updateConfigurationFile' -- frontend/maquette/design/src/mocks/handlers/configuration.ts` → `PUT /api/config/files/{name}`, whose body is keyed `<file>:<key>` and whose handler moves the setting's `raw` AND `displayedValue` (lines 71–112); `personalscraper/web/routes/config.py:103-130` (`RESTART_IMPACT`) → `"cross_seed": False` (113), `"tracker": False` (130) — « effective next run », not immediate |
| 8 | **No route in either contract carries the cross-seed** | `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if any(x in p.lower() for x in ('cross','tracker','seed'))])"` → `[]`; the same command on `frontend/openapi.json` → `[]` |
| 9 | **The two events are exempted from every live rule, by name** | `sed -n 130,148p frontend/maquette/design/src/features/acquisition/live.ts` → `acquisitionLiveExemptions.types` lists `CrossSeedInjected`, `CrossSeedRejected` beside the ratio events and `TrackerAuthFailed`; the file is 148 non-blank lines |
| 10 | **Two registers disagree on whether the events reach the stream** | `docs/reference/frontend-backend-demands-stream.md:76-77` says they « are emitted, reach the stream »; `BUGS.md` B-145 (2026-08-26) says nothing under `personalscraper/web/` relays them; `git grep -n CrossSeed -- personalscraper/web` → no match. **The design does not settle it**: demand I files it for the backend brief |
| 11 | **No account carries a role, in either contract** — `readAccount` answers `name`, `email`, `avatar`; the backend's `GET /api/auth/me` answers one string map (`username`). The only role the backend serves is the DEPLOYMENT role on `GET /api/config/status` (`role`: prod or staging; `read_only`) — a ceiling on the instance, not an account's right | `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(json.dumps(d['components']['schemas']['Account']))"`; `grep -n 'role' personalscraper/web/models/config.py` (lines 147, 160). **The architecture's « behind the served role the backend already exposes » therefore has no account role to read** (OPEN 1) |
| 12 | **The media sheet is a SCREEN composed in a route, not a panel descriptor**: `routes/media-sheet.tsx` is 42 non-blank lines and hands the screen the follows (`MediaScreenProperties = { readFollows }`) because two features never import each other (invariant 7). The « `panel-seasons` precedent » the architecture cites registers a block into the BOTTOM PANEL (`registerBlock("saisons", …)`) | `sed -n 1,30p frontend/maquette/design/src/routes/media-sheet.tsx`; `git grep -n 'registerBlock' -- frontend/maquette/design/src` |
| 13 | **The state's colour vocabulary already exists**: `ui/variants/surfaces.ts` (375 non-blank lines, 25 under the 400 ceiling) holds `chip` with the tones `warning`, `success`, `danger`, `info`, `waiting`, `neutral` — the four states need no new CVA variant | `sed -n 60,80p frontend/maquette/design/src/ui/variants/surfaces.ts` |
| 14 | **The stream mock is at the ceiling**: `mocks/stream.ts` is 399 non-blank lines of 400 — an event is emitted by a NAMED STATE or a rule through `window.__mocks.emit`, never by a line added to that file | `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/stream.ts` → 399 |
| 15 | **The contract's counters** before this lot: 63 operations required, 16 required-and-missing | `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"` → 63; `sed -n 20,29p docs/reference/frontend-backend-demands.md` → 16 (L22 and L16 will move both before L17 opens) |

---

## 1. What L17 builds on, and does not redraw

L16's design is the base (`docs/features/maquette-l16/DESIGN.md`, plan `plan/INDEX.md`). This lot **adds to it and
never redraws it**. The extension points, each named by the L16 phase that creates it:

| L16 gives (file, per L16's plan) | L17 adds |
| --- | --- |
| the roster row — `features/trackers/` (L16 phase 3): ratio, trend, volumes, alert badge | one line: the cross-seed state of THAT tracker (S1) |
| the tracker's detail `/trackers/$name` (L16 phases 4–5): head, obligations, active torrents | a SECTION of the cross-seed's torrents with their four-word states and refusals (S3); a line in the head that reads the switch (S2) |
| the obligation's row (L16 phase 5) | a mark and a path when the obligation is a cross-seed's (S4) |
| the tracker summary read (L16 phase 1, § 2.3 item 1) | a `crossSeed` sub-object on the same read — the badge and the roster keep ONE read (§13) |
| `trackersBadge` (L16 phase 10) | the second term (S6) |
| `features/trackers/live.ts` (L16 phase 10) | the two cross-seed events (S6) |
| `mocks/handlers/trackers.ts` (L16 phase 1) | the cross-seed handlers — in that file if it stays under 400 non-blank lines, or a `mocks/handlers/cross-seed.ts` by SUBJECT (the `staging.ts` / `pipeline.ts` precedent); the opening measure decides |
| the `acquisitionLiveExemptions` residue (L16 phase 10) | the last two names leave it |

**What L17 does NOT need from L16 and must not assume:** the obligation's release verb, the policy panel, the ranking
editor. A phase that reads one of them says so.

---

## 2. The contract (D7) — and it comes FIRST

D7: the maquette declares the contract its interface REQUIRES, and every divergence from the backend's is a demand. **A
demand is filed by EDITING THE CONTRACT** (`frontend/maquette/contract/openapi.json`) and regenerating
`docs/reference/frontend-backend-demands.md` (`python3 scripts/compare-contracts.py --write`, then `--check`); the
register is « COMPUTED, NEVER WRITTEN ». This section says what the surfaces of § 3 read. **It invents no shape the
demands § 5 does not name**: `docs/reference/backend-demands-architecture.md` § 5 names the feed of injections and
refusals with their reasons, the per-tracker state, the verbs to prevent and provoke, the events reaching the stream,
the per-tracker off switch as a config write, and the per-torrent per-tracker state route with four states, role-aware.
Every shape below is one of those, **drawn as owed** — PROPOSED here as a register row (§ 6.2) and filed by the lot's
phase 1 once the operator has read the design. The operationIds are proposals and adjust.

### 2.1 What is drawn — and which OPEN question makes it conditional

| Surface | Reads / acts through | Declared today | Conditional on |
| --- | --- | --- | --- |
| S1 — the roster's line; S2's head | the tracker summary read (L16), **extended**: per tracker `crossSeed{enabled, engineEnabled, seeding, refused, lastInjectedAt}` | L16's, not yet declared — **the sub-object is new** | OPEN 7 (`engineEnabled` — say the engine's own switch or fold it) |
| S3 — the tracker's section | `GET /api/trackers/{name}/cross-seed` — `readTrackerCrossSeed` (new): rows `{title, media{provider, providerId}\|null, state, reason\|null, at, origin}` | no | OPEN 5 (a fifth row kind), OPEN 6 (what `state` means) |
| S4 — an obligation's origin | the obligations read (L16), **extended** with `crossSeedOf{infoHash, title, media\|null}` | L16's, not yet declared — the field is new | — |
| S5 — the media block | `GET /api/media/{provider}/{providerId}/cross-seed` — `readMediaCrossSeed` (new, **role-aware**) | no | OPEN 1 (drawn at L17, or held for L18) |
| the off switch | the EXISTING `PUT /api/config/files/{name}` (`updateConfigurationFile`), body `tracker:tracker.providers.<name>.cross_seed` — **no new operation under either reading**; a dedicated write is a demand only if the operator asks for a control that answers with the tracker's state, not with `restartRequired` | yes (fact 7) | OPEN 2 (where the control lives) |
| « provoke » | `POST /api/trackers/{name}/cross-seed/search` — `searchCrossSeed` (new): one torrent, one call, an answer that is a visible « en file », never « occupé » | no | OPEN 3 (an act, or none) |
| the feed | `GET /api/cross-seed/events` — `readCrossSeedEvents` (new): newest first, each `{type, at, tracker, title, media\|null, reason\|null}` | no | OPEN 4 (a feed, or none) |
| S6 — the badge | the tracker summary read (`crossSeed.refused`) | extended, as S1 | OPEN 8 (which refusals count) |
| S6 — the stream | `CrossSeedInjected`, `CrossSeedRejected` through `/ws/events` | emitted; whether relayed is disputed (fact 10) | — |

### 2.2 The shapes' closed sets — drawn from the engine, not invented

- **The four states**, as the operator wrote them: « actif », « stoppé », « tracker sans cross-seed », « erreur de
  cross-seed ». Their English identifiers (`active`, `stopped`, `trackerWithout`, `error`) are a proposal; the words
  live in `fr.json`. **OPEN 5 asks whether a FIFTH situation — the engine looked and found nothing — is a word or a
  sentence; OPEN 6 asks what « stoppé » and « tracker sans cross-seed » each mean.** The contract's `state` enum is
  those four, and the seed and the handler read the operator's answers to both.
- **The reason**, on a refusal: the engine's twelve codes (fact 3), grouped by the KIND of trouble, because § 19 point
  1 asks that a layout mismatch is not read as a policy refusal. The grouping is the design's, and it is prose, not a
  contract field:
  - **the files are not the same** — `piece_length_mismatch`, `file_list_mismatch`, `root_name_mismatch`, `v2_hybrid`,
    `self_candidate` (the candidate is the source itself);
  - **the attempt failed** — `fetch_failed`, `verify_timeout`, `recheck_failed`, `magnet_not_supported`, `parse_failed`;
  - **the engine could not finish** — `inject_failed`, `obligation_write_failed`.

  Each code has ONE sentence in clear French in `fr.json` (NE-DOIT-PAS-4: no bare code, no machine English);
  R-L17-a holds that every code the contract declares has one. **The tracker POLICY case has no code** (fact 3): the
  design draws it as the STATE (« stoppé » when the operator's switch is off, « tracker sans cross-seed » when the
  tracker takes none), never as a reason; a policy REASON is demand B's question to the backend, and the operator's
  (§ 7.1).

### 2.3 The mocks — INVENTED, and each must MOVE (D7: « a mock that answers without moving certifies nothing »)

There is nothing to seed from, so the seed is written by the lot from the CASES below, chosen so that every state, every
family of reason and every gate of § 3 is reachable, and **no more**. The phase that writes it (phase 2) picks the
titles from the mock's own library seeds (`frontend/maquette/design/src/mocks/seeds/media-sheets.json` holds 326 keys,
`python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/media-sheets.json'))))"`);
the trackers are the roster's. **The states are invented, and the file, the fixture register and the contract say so**:
`x-unseeded` on each operation (`grep -c 'x-unseeded' frontend/maquette/contract/openapi.json` → 33 today), one row per
seed file in `frontend/maquette/fixture-register.json`, and `python3 scripts/check-mock-seeds.py` in the same commit
(its `schema` arm holds every seed against the contract schema, its `provenance` arm the four-way correspondence).

| Case (invented) | What it must make reachable |
| --- | --- |
| a title cross-seeding on two trackers, injected on two dates | « actif », twice, with their dates and the obligation's origin (S4) |
| a title whose tracker's switch is off | « stoppé » on every row of that tracker; the roster line says the switch is off |
| a tracker that takes no cross-seed for a kind of media | « tracker sans cross-seed » (OPEN 6 decides the cause the seed carries) |
| three refusals, one per family of § 2.2, plus one candidate that failed on transport | « erreur de cross-seed » with a sentence per family; R-L17-c's contrast |
| a title with no candidate found anywhere | the row OPEN 5 decides (a fifth word, or a sentence at the block) |
| an identified title AND an unidentified torrent | NE-DOIT-PAS-9: a sheet link by provider ID, and the resolution path for the torrent with none |
| one obligation that IS a cross-seed's, one that is not | S4's mark, and its absence |

**The switches are the operator's own setting, and the design reads them as such.** The three per-tracker switches and the
engine's own are `false` in the settings seed, which IS derived from the live configuration (fact 6). That is HIS
setting — the per-tracker switch already turned off — and **nothing in this lot changes those rows**. Two consequences.
(1) The mock's DEFAULT state reads what the live configuration says: every tracker's switch is off, every row of every
section reads « stoppé », and the roster's line says so. (2) The states that must draw « actif », « erreur de cross-seed »
or a refusal need a switch ON, and the switch has ONE source — the Réglages row, read by both surfaces, because two seeds
saying different things about one setting on two pages of one application is the defect §13 names. They therefore run
under a SCENARIO: a dial on the mock's own state (`frontend/maquette/design/src/mocks/state.ts`, where `conflict` at
line 235 and `movedFiles` are already such dials, default at line 311) that a named state sets through `applyState`, and
that turns the switches on in the mock's state, never in the seed file. **`mocks/state.ts` is 398 non-blank lines of 400**
(`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/state.ts`), so the dial is DECLARED in a module of its own
that the state reads, unless the opening measure finds the file has moved. **The STOP D at phase 2 is only this**: whether
the dial is the carrier — the design's reading — or the steward names another; the register marks every row the scenario
brings as invented, and the seed file's derived rows stay derived.

**What each mock must MOVE.**

- the switch write (the existing `updateConfigurationFile`) moves the settings row AND what the summary read and the
  section read project — one seed, several projections (fact 7: the handler already moves `raw` and `displayedValue`);
- the extended obligations read answers `crossSeedOf` from the SAME rows as the section (an obligation that is a
  cross-seed's is a row of S3 too);
- the media route answers the SAME rows filtered to the title, and answers nothing for an identity that is not the
  administrator's (OPEN 1, reading A);
- an emitted `CrossSeedRejected` (through `window.__mocks.emit`, fact 14) moves the tracker's `refused` count and adds
  its row — the mock's answer after the event equals what a refetch would return.

### 2.4 The stream

`docs/reference/frontend-backend-demands-stream.md` § 3 already lists the two events as « claimed by no rule ». L17
claims them in `features/trackers/live.ts` (the file L16 creates), each rule refreshing the summary read and the
tracker's section and nothing else; the two names leave `acquisitionLiveExemptions`, which keeps `TrackerAuthFailed`
(the system feature's) with a rewritten `because`. R91's fan-out (`frontend/maquette/harness/fanout.py`, 486
non-blank lines) reads the rule.

---

## 3. The surfaces, drawn

Copy is given in « guillemets » as `fr.json` will carry it, with the English key where one is proposed; a key that
exists is REUSED, never retyped. **The operator's four state words are verbatim.** The section's title is the
operator's own word, « Cross-seed » (his § 19 title and his four states use it); Réglages calls the same setting
« Partage croisé » (`grep -n '"cross_seed"' frontend/maquette/design/src/i18n/fr.json` → lines 105 and 189) — one thing,
two names, which this lot does not settle (§ 7.1). `data-part` names are English (D4).

### 3.0 The addresses (D1)

**L17 adds no page and no path.** The cross-seed is drawn INTO surfaces that already have an address: `/trackers` (the
roster's line), `/trackers/$name` (the section and the head), `/media/$provider/$id` (the block). D1's rule holds — a
section of a page is state, not identity, and nothing of L17's is in the query. A FEED (OPEN 4, reading B) would be a
second view of `/trackers`; its address is that phase's to measure (D1: a view of the same page is a search
parameter, adjusting replaces), not improvised here.

### 3.1 S1 — The roster's line

**Its place.** L16's roster row (`features/trackers/`). One line beneath the ratio, on its own row of the row's grid so
that it never shares a line with the ratio (DOIT-9).

**What is on the screen.** The tracker's cross-seed at rest, in one sentence assembled from the summary read:
« Cross-seed : actif — 4 torrents, 1 refusé » / « Cross-seed : stoppé — interrupteur coupé » / « Cross-seed : tracker sans
cross-seed » (`screens.trackers.crossSeed*`). The count of torrents equals the number of rows S3 lists (R-L17-b). The
line is a PATH to the section of the detail, not a second control. **OPEN 7** adds a variant: when the engine's own
switch is off, the line says so instead of reading the tracker's own switch.

`data-part`: `trackers/cross-seed`. **Named states:** `trackers-cross-seed` (the roster, each line reading its tracker's
state), and — only under OPEN 7 reading A — `trackers-cross-seed-engine-off`.

### 3.2 S2 — The tracker's detail: the head reads the switch

**Its place.** The head of `/trackers/$name` (L16 phase 4), one row beside the ratio, the volumes and the trend.

**What is on the screen.** The switch's state in words (« Cross-seed actif sur ce tracker » / « Cross-seed coupé sur ce
tracker »), and — after a change — « pris en compte à la prochaine passe » (fact 7: the config file takes effect on the
next run, and a head that read « stoppé » the instant the file was written would say more than the engine knows,
NE-DOIT-PAS-1). **Where the CONTROL is, is OPEN 2.**

`data-part`: `tracker/cross-seed-switch`. **Named state:** `tracker-cross-seed-switch-off` (the head of a tracker whose
switch is off, its section reading « stoppé » on every row).

### 3.3 S3 — The tracker's cross-seed section

**Its place.** `features/trackers/tracker-cross-seed.tsx` (new), a section of `/trackers/$name`, after the obligations and
the active torrents (L16 phase 5). Its own read (`readTrackerCrossSeed`), so its own loading and error states.

**What is on the screen.** One row per torrent cross-seeded, refused or held on THIS tracker: the title (a path to its
sheet by provider ID, NE-DOIT-PAS-9; a torrent with no identity leads to the resolution, never to a dead link), the
state in the operator's word on the `chip` (`actif` → `success`, `stoppé` → `waiting`, `tracker sans cross-seed` →
`neutral`, `erreur de cross-seed` → `danger` — the word carries the meaning, the tone only helps, fact 13), the date the
state took (« injecté le … » on an « actif » row) and its origin (« partage croisé de <torrent d'origine> »). **An
« erreur de cross-seed » row carries its reason in full** (§ 2.2): the sentence for its code, the kind of trouble it
belongs to, the candidate's tracker and the source torrent — never the bare code. **Nothing is offered on a row that
the engine does not allow** (§ 17 point 1), and the section makes **one read per visit** (NE-DOIT-PAS-8, R-L17-k).

`data-part`: `tracker/cross-seed`, `tracker/cross-seed-row`, `tracker/cross-seed-state`, `tracker/cross-seed-reason`,
`tracker/cross-seed-origin`. `data-region="tracker/cross-seed"`.

**Named states.**

| id | What is on the screen |
| --- | --- |
| `tracker-cross-seed` | the section with a row in each of the four states |
| `tracker-cross-seed-refused` | a refusal opened: its sentence, its kind of trouble, the candidate's tracker, the source |
| `tracker-cross-seed-empty` | nothing cross-seeds on this tracker — « Rien n'est partagé sur ce tracker. » (`screens.tracker.crossSeedEmpty`) with its reason (the switch is off, or nothing matched), a real answer (§ 8) |
| `tracker-cross-seed-loading` · `tracker-cross-seed-error` | the two the contract requires of every surface; the error is `SurfaceError` |

### 3.4 S4 — An obligation says where it came from

**Its place.** The obligation's row in the tracker's detail (L16 phase 5).

**What changes.** An obligation that a cross-seed CREATED (the engine persists the obligation on injection — fact 1's
event docstring, « emit-after-persist ») gains a mark, « partage croisé de <torrent d'origine> », and a path to the
origin's sheet by provider ID. § 19 point 2: without it the obligation of § 18 appears without its origin. An
obligation that is not a cross-seed's reads as it did — no mark, no empty slot.

`data-part`: `tracker/obligation-origin`. **Named state:** `tracker-obligation-cross-seed`.

### 3.5 S5 — The media sheet's block (per tracker, administrator only)

**Its place.** `features/trackers/media-cross-seed.tsx` (new) — the block is DRAWN by the trackers feature and COMPOSED
into the media screen by `routes/media-sheet.tsx`, the way the follows already are (fact 12; invariant 7: `features/media`
must not import `features/trackers`). `MediaScreenProperties` gains one prop — a render function for the block — and the
screen places it after the library facts (`media-library-facts.tsx`, 245 non-blank lines) and before the identifiers, in the
sheet's fixed order (« hero → trailer → synopsis → cast → library state → identifiers → actions »,
`media-screen.tsx`'s own header). The architecture's « media sheet's descriptor » is read as this composition, not as a
panel block kind (fact 12); **the reading is recorded as a correction the contract needs** (`plan/INDEX.md`, « What this
plan believes the CONTRACT gets wrong »).

**What is on the screen.** For the title, ONE BLOCK PER TRACKER (§ 19: « un bloc par tracker »): the tracker's name, the
state of THIS title's torrent on it in the operator's word, its date or its reason, and a path to the tracker's page
(`crossReference()`, `ui/variants` — the helper Système's locks block already uses). A title that is not owned has no torrent
and draws no block, and says why in one line (§ 8: « Pas possédé — rien à partager »). **Who sees it is OPEN 1.**

`data-part`: `media/cross-seed`, `media/cross-seed-tracker`. **Named states** (reading A of OPEN 1 only):
`media-cross-seed` (the administrator's sheet, an owned title, one block per tracker) and `media-cross-seed-hidden` (the
same sheet for an identity that is not the administrator's — the block ABSENT, not disabled, not empty).

### 3.6 S6 — The badge's second term, and the stream

**The badge.** L16's `trackersBadge` counts the trackers under their alert threshold AND the obligations in breach (L16
OPEN 3 = B). **L17 adds the refused cross-seeds** (the operator's ruling of 2026-09-26). The function stays ONE function
the feature exports and the frame names once (L22's DESIGN § 3.6); it reads the summary read's `crossSeed.refused`. **What
a « refused cross-seed » IS, and when it leaves the count, is OPEN 8.** No box collects it and no line on Système repeats
it (organisation ruling 12).

**The stream.** `CrossSeedInjected` and `CrossSeedRejected` are claimed by `features/trackers/live.ts`; a refusal that
arrives moves the roster's line, the section and the badge without a refetch, like L16's ratio events.

**Named states:** `bar-trackers-refused` (the bar at its present buttons, the Trackers tab carrying a badge that only the
refusals justify — beside L16's `bar-trackers-alert`, on the frame's own region).

### 3.7 The verbs, and the feed — drawn only under the reading the operator takes

- **The off switch (OPEN 2).** Reading A draws a control in S2's head; reading B draws none and links to the Réglages
  row. § 4 counts both.
- **« Provoke » (OPEN 3).** Reading A draws one act on a torrent's row — « Chercher un partage croisé » — bounded by the
  engine's own quota and delay (`CrossSeedConfig.max_searches_per_day` 250, `min_delay_between_searches_s` 30, fact 5's
  file): a tap asks ONCE, the answer is a visible « en file » if the engine is throttling, and a second tap on the same
  torrent is the one refusal DOIT-4 allows (a duplicate of the same act, NE-DOIT-PAS-3). Reading B draws nothing.
- **The feed (OPEN 4).** Reading B draws a chronological list of injections and refusals on the Trackers page; reading A
  draws none, because S3's rows already carry the date of an injection and the reason of a refusal.

**Named states, conditional:** `tracker-cross-seed-search` and `tracker-cross-seed-search-queued` (OPEN 3, A);
`cross-seed-feed`, `cross-seed-feed-empty`, `cross-seed-feed-loading`, `cross-seed-feed-error` (OPEN 4, B).

---

## 4. The named states

**Measured before naming them**: 114 states exist, summed across the eleven files `harness/states/` holds (the counting
command of L22's DESIGN § 4):

    python3 -c "import re,glob;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open(f).read(), re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"   →  114

L22 (−8 + 23 and two more) and L16 (a `harness/states/trackers.ts` of about seventeen) land before this lot opens, so the count
it starts from is theirs, re-taken by phase 1. **L17 adds nine states unconditionally and up to nine more by its OPEN
readings — nine to eighteen.** Every one is reachable by `window.__go("<id>")`, has an English id, and its French label is what
the panel says. They live in `harness/states/trackers.ts` (L16's file) while it stays under invariant 6's 400 lines, and in a
new `harness/states/cross-seed.ts` composed by `harness/index.ts` (68 non-blank lines) when it would not — the phase that
crosses 400 measures and decides.

| # | id | Label (French, as the panel lists it) | Lands in phase |
| --- | --- | --- | ---: |
| 1 | `trackers-cross-seed` | « Trackers — la ligne cross-seed de chaque tracker » | 5 |
| 2 | `tracker-cross-seed` | « Tracker — la section cross-seed, une ligne par état » | 6 |
| 3 | `tracker-cross-seed-empty` | « Tracker — rien n'est partagé, et pourquoi » | 6 |
| 4 | `tracker-cross-seed-loading` | « Tracker — cross-seed, chargement » | 6 |
| 5 | `tracker-cross-seed-error` | « Tracker — cross-seed, erreur » | 6 |
| 6 | `tracker-cross-seed-refused` | « Tracker — un refus, sa raison en entier » | 7 |
| 7 | `tracker-obligation-cross-seed` | « Tracker — une obligation née d'un cross-seed, son origine » | 8 |
| 8 | `tracker-cross-seed-switch-off` | « Tracker — l'interrupteur est coupé, chaque ligne « stoppé » » | 9 |
| 9 | `bar-trackers-refused` | « Barre — Trackers porte un refus de cross-seed » | 12 |
| 10 | `trackers-cross-seed-engine-off` | « Trackers — le moteur entier est coupé » (OPEN 7, A) | 5 |
| 11 | `media-cross-seed` | « Fiche — le bloc par tracker, vu de l'administrateur » (OPEN 1, A) | 10 |
| 12 | `media-cross-seed-hidden` | « Fiche — le même titre, sans le bloc, pour un autre compte » (OPEN 1, A) | 11 |
| 13 | `tracker-cross-seed-search` | « Tracker — « Chercher un partage croisé » sur une ligne » (OPEN 3, A) | 15 |
| 14 | `tracker-cross-seed-search-queued` | « Tracker — la recherche est en file, dite » (OPEN 3, A) | 15 |
| 15 | `cross-seed-feed` | « Cross-seed — le fil des injections et des refus » (OPEN 4, B) | 17 |
| 16 | `cross-seed-feed-empty` | « Cross-seed — le fil est vide, et pourquoi » (OPEN 4, B) | 17 |
| 17 | `cross-seed-feed-loading` | « Cross-seed — le fil, chargement » (OPEN 4, B) | 17 |
| 18 | `cross-seed-feed-error` | « Cross-seed — le fil, erreur » (OPEN 4, B) | 17 |

`tracker-cross-seed-loading` and `-error` ARE named although the `phase` dial can drive them, for the reason L22 wrote
(`harness/state_surfaces.py`, R90, walks a per-surface list of loading and error states with the sentence each says).
**What has no named state and why.** The switch's flip, the tap on « Chercher un partage croisé » and the arrival of an
event are ACTS, not surfaces: R-L17-e, R-L17-i and R-L17-h walk them by finger or through `window.__mocks.emit` and read
the network and the render.

### 4.1 What the oracle will do (D8)

The new surfaces are NEW, so the reference RECORDS them and proves nothing about them. What the oracle is for here is the
other direction — **no existing state may diverge unless a phase names it**:

| Phase | Existing states that WILL diverge | Reason (accepted by name, D8) |
| --- | --- | --- |
| 1–4 | none — a contract, a seed, a handler, a vocabulary | — |
| 5 | L16's `trackers-list` (each row gains a line) and `tracker-alert-active` where it draws the roster | « L17 § 3.1: the row's cross-seed line » |
| 6, 7 | L16's `tracker-detail` and its variants (a section after the lists) | « L17 § 3.3: the cross-seed section » |
| 8 | L16's `tracker-detail` again, where an obligation is a cross-seed's | « L17 § 3.4: the obligation's origin » |
| 9 | L16's `tracker-detail` head | « L17 § 3.2: the head reads the switch » |
| 10 | `mediasheet-series`, `mediasheet-movie` on `screen-media/body` (a block on an owned title) — reading A only | « L17 § 3.5: the per-tracker block » |
| 11–13 | none by the oracle — the gate removes an element, the badge's number is text, the tab's rectangle does not move | — |

**The oracle's silence over the badge and over the block's ABSENCE proves nothing, and this design says so before the phase
does**: the oracle reads a rectangle and a computed style, never a count or a missing element (`docs/features/maquette-l22/DESIGN.md`
§ 4.1 wrote the same warning about the bar). **This lot is held by § 5's rules or by nobody.**

The accessibility tier (`--a11y`) is re-read at phases 6, 10 and 18 over the states this lot adds.

---

## 5. The rules that bite

Numbers: the harness's highest rule number was `R223` at this writing
(`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1`, on `46806a88d`). L22 and L16 run ahead of
this lot, so **phase 4 — the first phase that writes a rule — re-takes that command against `origin/main` at the moment it
runs and binds every label below to a consecutive free number then, the mapping written into the report.** A number taken
from this document without re-measuring is a collision. Each rule is written RED FIRST; none of the surfaces exists on
`main`, so each is red for that reason and needs no mutation to be seen red; the mutation comes after the move.

| Rule | Phase | What it READS | The mutation that fells it |
| --- | ---: | --- | --- |
| **R-L17-a** — the words, and no bare code (NE-DOIT-PAS-4) | 4 | every state chip the surface draws reads one of the operator's four words (a fifth only if OPEN 5 reading A is ruled); **every reason code the contract's `state`/`reason` enums declare has a sentence in `fr.json`**, and no rendered text is a bare code | draw the code instead of its sentence → falls; remove one sentence → falls; add a fifth chip word → falls |
| **R-L17-b** — one derivation (§13, NE-DOIT-PAS-1) | 5, re-aimed 6, 10, 12 | the state and the count drawn on the roster's line, on the section's rows and in the media block equal the mock's own field; the roster's count of torrents equals the section's rows; the badge's refusal term equals the summary's `refused` | compute a state or a count client-side → falls; disagree the roster's count from the section → falls |
| **R-L17-c** — a refusal is readable with its reason (§ 19 point 1, DOIT-2) | 7 | on `tracker-cross-seed-refused`: the row draws the sentence of ITS code, its kind of trouble, the candidate's tracker and the source; **a layout mismatch and a transport failure read differently** | draw one constant sentence → the contrast hold falls; drop the reason → falls; draw the code → R-L17-a falls too |
| **R-L17-d** — an obligation says where it came from (§ 19 point 2) | 8 | a seeded obligation created by a cross-seed carries the mark and a path to the origin's sheet by provider ID; one that is not carries neither | drop the mark → falls; mark every obligation → the absence hold falls |
| **R-L17-e** — the off switch (§ 19, NE-DOIT-PAS-6 as a setting) | 9 | the flip is ANSWERED on the network (`window.__mocks.answered()`, `updateConfigurationFile`), the Réglages row and every projection of the tracker's state move in the SAME render, and the head says « pris en compte à la prochaine passe ». **Reading B of OPEN 2**: the Trackers page draws NO control and its state follows the Réglages row when that row changes | make the control message without calling → the network hold falls; move the row and not the projections → the agreement falls |
| **R-L17-f** — the block, for the administrator only (§ 19, § 17 point 1) | 11 (OPEN 1, A) | on `media-cross-seed`: one block per tracker, each reading the SAME field as the roster (R-L17-b); on `media-cross-seed-hidden`: the block is **absent from the DOM** for the other identity, not disabled and not empty; a title not owned draws no block and says so | show it to every identity → the absence hold falls; draw one block for all trackers → the per-tracker hold falls |
| **R-L17-g** — the badge's second term (ruling 12, L16 OPEN 3) | 12 | the Trackers tab's number equals the trackers under threshold plus the obligations in breach plus the refusals OPEN 8 counts, on `bar-trackers-refused`, and moves when a seeded refusal moves | drop the term → falls; count every skipped check → falls |
| **R-L17-h** — the events are claimed (R91's fan-out; B-145) | 13 | `CrossSeedRejected` emitted through `window.__mocks.emit` moves the roster's line, the section's rows and the badge WITHOUT a refetch; `CrossSeedInjected` the same; neither name is in `acquisitionLiveExemptions` any more | leave a rule out of `features/trackers/live.ts` → the state stops moving and falls; put a name back in the exemption → falls |
| **R-L17-i** — « provoke » is bounded, answered and visible (DOIT-4, NE-DOIT-PAS-3, -8) | 15 (OPEN 3, A) | a tap asks ONCE (`answered()` counts one call); an engine throttling answers a visible « en file », never « occupé »; a second tap on the same torrent is the one refusal (a duplicate); the quota is drawn | let a double tap send two → falls; answer « occupé » → falls |
| **R-L17-j** — the feed (OPEN 4, B) | 17 | newest first; each entry carries its date, its tracker, its title and, for a refusal, its sentence; an empty feed says why | unsort it → falls; drop the reason → falls |
| **R-L17-k** — one read per visit (NE-DOIT-PAS-8) | 6 | opening the roster, a tracker's detail and a title's block makes each operation ONE call, and a wait on the page makes none | add a refetch interval → falls |

**Seeds into existing rules, not new rules of their own** (L20's precedent): `harness/states.py` is seeded with every new
state (it asserts each renders content, has no horizontal overflow at 390 px and raises no JS error);
`screen_addresses.py` needs nothing (no address is added); `state_surfaces.py` (R90) takes the loading and error states.
**Every state is proved at the phone's real width** (`docs/reference/product-intent.md` § 12, DOIT-9): a state row that
shares a line with an essential figure fails `states.py` at 390 px.

### 5.1 Rules L16 wrote that this lot re-aims

R-L16-e (« one derivation for the alert, four readers ») reads the tab's count; the badge's second term makes that count a
sum of three, so the rule is **re-aimed in phase 12**, out loud, and its mutation re-run. R91 (`fanout.py`) is re-aimed in
phase 13 for the two names that leave the exemption. Neither is left green over a changed reading.

---

## 6. The register rows and the demands touched

### 6.1 The register rows

Read, not edited by this pull request (a documentation-only PR that touches nothing outside `docs/features/maquette-l17/`
and the one dated line of the architecture file):

| Row | State | What happens |
| --- | --- | --- |
| **B-145** — « 797 lines of engine that inject torrents at third parties, and no way to know it happened » | `open` | its READING half closes when the surfaces land; its backend half (a route, the events on the stream) stays owed. The close annotates the row and never closes it alone |
| **B-144** — the ratio's three operations | `open`, L16's | not this lot's; L17 extends the read L16 declares |
| **B-539** — « no cross-seed join check exists » (the joined-fields guard's loss, L13r) | `open` | a homonym: it is a seed-correspondence guard, not the § 19 feature. The name collision is noted so nobody reads it as owed here |

### 6.2 The demands PROPOSED (D7) — in the register's own form, not asserted

Ten rows, none invented outside `backend-demands-architecture.md` § 5 — each is a shape that section names, made typed by
the drawing. The lot files A–C in phase 1 and D, E and F in the phase that draws each (a demand is filed where its surface is drawn, L22's precedent), by editing `frontend/maquette/contract/openapi.json` and
regenerating the register; the operationIds adjust.

| # | operation | operationId | what it is for | Filed in phase |
| --- | --- | --- | --- | ---: |
| A | the tracker summary read (L16's) | extended | per tracker: `crossSeed{enabled, engineEnabled, seeding, refused, lastInjectedAt}` — the roster's line, the head and the badge read ONE answer (§13) | 1 |
| B | `GET /api/trackers/{name}/cross-seed` | `readTrackerCrossSeed` (new) | the section's rows: the four states, the reason on a refusal, the date, the origin. **The backend must KEEP a state**: eight skip reasons emit no event (fact 4), so « stoppé » and « tracker sans cross-seed » cannot be derived from `CrossSeedInjected`/`CrossSeedRejected`. Includes the case OPEN 5 decides | 1 |
| C | `GET /api/media/{provider}/{providerId}/cross-seed` | `readMediaCrossSeed` (new, role-aware) | a title's per-tracker block; the answer for an identity that is not the administrator's is the absence of the route's data, not a 403 after a gesture (§ 17 point 1). **The role itself is L22's demand D and L18's model**; L17 files a first consumer | 1 (OPEN 1, A) |
| D | the obligations read (L16's) | extended | `crossSeedOf{infoHash, title, media\|null}` — an obligation says which torrent's copy it is (§ 19 point 2) | 8 |
| E | `POST /api/trackers/{name}/cross-seed/search` | `searchCrossSeed` (new) | one torrent, one search, an answer that is a visible « en file » under throttle; bounded by the engine's daily quota and delay | 14 (OPEN 3, A) |
| F | `GET /api/cross-seed/events` | `readCrossSeedEvents` (new) | the feed, newest first | 16 (OPEN 4, B) |
| G | the config write | none new | the per-tracker switch is `tracker.providers.<name>.cross_seed` through the EXISTING `updateConfigurationFile` (fact 7). A row is proposed only if the operator wants a control that answers with the tracker's own state | — |
| H | engine defaults | not an operation | `TrackerProviderConfig.cross_seed` and `CrossSeedConfig.enabled` default to `False` today (fact 5); § 19 dictated « actif par défaut », and the backend follows the interface (§ 15). **The engine's default becomes ON**, both flags — a demand, not a question: the operator's live configuration turning the switches off is his own setting and stays (§ 2.3) |
| I | the stream | not an operation | the two events reach `/ws/events`, with `tracker` (not `source_tracker`, fact 2) and the reason; the registers disagree on whether they do (fact 10) |
| J | `readAccount` (L22's demand D) | re-shaped | an administrator fact on the account — **L18's shape**; L17 is a first consumer only under OPEN 1, reading A (fact 11: no account role in either contract, only the deployment role) | 11 (OPEN 1, A) |

### 6.3 The clause-map rows PROPOSED (the operator amends the map; this lot does not)

`docs/reference/product-intent-map.md`, **DOIT-14** — « rendre le cross-seed visible et décidable (§19) » — reads
`to draw`, owner **L17**, surface « none — no route in either contract, no event relayed to a surface ». Proposed: surface
`features/trackers` (the roster's line, the section, the obligation's origin) and `features/media` composed at the route (the
block), proof R-L17-a … k; the row reads `served` at the close when every rule of the readings taken is green, and `partly`
if OPEN 1 is ruled B (the block held for L18). The operator amends the map; the close reports against the row.

---

## 7. What this design does NOT draw, and what is OPEN

### 7.1 Not drawn — and whose it is

- **The Trackers page itself, its bar tab and its ratio** — L16's. L17 draws into it.
- **The rights model, the bar's composition by rights, the role on the account** — **L18's** (organisation ruling 11, § 17).
  L17 adds no role to the navigation table; the only gate it draws is OPEN 1's, and only if that reading is ruled.
- **A cross-seed decision per TITLE** (« un titre qu'il compte supprimer », § 19 point 3). § 19's own ruling of 2026-08-30
  made the refusal « ce réglage, tracker par tracker »; no per-title stop is dictated and none is drawn. It is not
  « out of scope » by this design's choice: it is not in the operator's words, and OPEN 6 (what « stoppé » means) is where
  he can say otherwise.
- **A tracker-policy REASON on a refusal** — the engine has no such code (fact 3). The design draws the policy case as a
  state (§ 2.2). If the operator wants a code, that is demand B's, and the words follow.
- **Push notification of a refusal** — a platform demand (`backend-demands-architecture.md` § 4, the FCM channel), filed by
  L16 for the ratio; nothing here reads it.
- **A rename of Réglages' « Partage croisé »** — one setting, two names (§ 3, opening). The operator's word.
- **The engine's own tuning** (`max_searches_per_day`, `min_delay_between_searches_s`, `exclude_recent_search_days`) —
  configuration, Réglages'; the surface may SHOW the quota (OPEN 3, A) and never sets it.
- **Anything the engine does** — the backend follows the interface (§ 15), after the freeze.

### 7.2 OPEN design questions — eight, each with TWO readings and NO choice

Nothing below is decided by this document. Each keeps its readings and what each costs the plan; the operator's answer,
when it comes, is written under it in one line and carried into the body where it bites.

**OPEN 1 — the media sheet's block, before L18's model exists.** § 19 dictates the block « réservé au profil
administrateur » (§ 17: the Operator role). No account carries a role in either contract (fact 11), so « the served role
the backend already exposes » (`frontend-architecture.md`, L17's « Dictated ») is the DEPLOYMENT role of the instance, not
an account's right. *Reading A — drawn at L17, behind a value the mock serves.* The block lands at phase 10 and its gate at phase 11: the
block is gated on an administrator fact the mock serves for the account (an `admin` fact on `readAccount`, proposed as a
first consumer of L22's demand D and subsumed by L18's model), and a SECOND mock identity makes R-L17-f prove « shown to the administrator,
absent for the others » now; L18 redraws the gate on the full model. The cost: a field and a second identity in the mock
before L18's model — the small rights model L22's OPEN 11 and L16's OPEN 2 (ruled A) refused for the same reason.
*Reading B — held until L18.* The block is drawn by L18 on the model; L17 keeps S1–S4 and S6 and phases 10 and 11 leave the plan
(−22 points, and −6 more for the media route in phases 1 and 3). The cost: clause 5 of § 0 is not served at L17's close, DOIT-14 reads `partly`, and « Done when »
(`frontend-architecture.md`, « The map's DOIT-14 row reads `served` ») is met only after L18.

**OPEN 2 — where the off switch's CONTROL lives.** The switch is the setting `tracker.providers.<name>.cross_seed`, already
in Réglages (fact 6, 7). *Reading A — on the Trackers page*, in the tracker's head (DOIT-3, « agir là où l'on observe »):
one control that calls the existing config write and moves the Réglages row and every projection in the same render
(R-L17-e); the cost is a second door onto one setting (§13: it holds while the write is one), a control, its confirmation
copy and its state. *Reading B — in Réglages only*, the Trackers page reading the state and linking to the row
(`crossReference()`, and the addressed panel `setting:tracker.providers.<name>.cross_seed`): no control, no second door,
and the operator who sees a tracker « stoppé » must leave the page to change it — which DOIT-3 names as the thing to
avoid. Cost in points: A = 10 at phase 9, B = 6 (fact 7: the write exists under both readings, so neither declares an operation).

**OPEN 3 — what « provoke » means on the surface.** DOIT-14 asks « de quoi l'empêcher ou le provoquer »; § 19's ruling of
2026-08-30 made the engine AUTOMATIC. *Reading A — an act per torrent*, « Chercher un partage croisé » on a section row:
one bounded search (the engine's own daily quota of 250 and delay of 30 s stand, NE-DOIT-PAS-8), a visible « en file »
under throttle, one new operation (demand E) and R-L17-i; the cost is an act on a mechanism the operator ruled automatic,
and the surface's first place to send a burst if it is ever wrong. *Reading B — none*: prevention is the switch, provoking
is the engine's business, and DOIT-14's « provoquer » is read as « the engine provokes it alone »; phases 14 and 15 leave the
plan (−17 points) and demand E is not filed.

**OPEN 4 — a feed of injections and refusals, or none.** `frontend-architecture.md`'s L17 says « a feed if the operator
chooses one ». *Reading A — none.* S3's rows already carry the date of an injection and the reason of a refusal, and
organisation ruling 12 says Système's history is « la seule trace du passé »: a feed on Trackers would be a second one.
The cost: the past of a torrent that changed state is not listed — a row shows its LAST state. *Reading B — a feed* on the
Trackers page, newest first, one operation (demand F), four states and R-L17-j (phases 16–17, +24 points); the cost is
the tension with ruling 12, which the operator alone lifts, and a second history beside Système's.

**OPEN 5 — what a (torrent, tracker) pair reads when the engine looked and found NOTHING.** § 19's four words describe a
tracker that has a cross-seed, none, a stop or an error; **the commonest case — a search that returned no candidate — is
none of them**, and DOIT-2 says every « nothing » has its reason. *Reading A — a fifth word* (« sans correspondance »,
proposed), added to the operator's four: the section and the block list the pair, R-L17-a reads five words, and the
words are his to dictate. *Reading B — no row*: a pair with nothing found is not listed; the section's empty state and
the block's one line say « aucune correspondance trouvée » (a sentence, not a state), and the four words stay four. The
cost: A adds a word to a dictated vocabulary and a row per pair (the section grows with the library); B keeps the
vocabulary and loses the row that says « the engine looked here ».

**OPEN 6 — what « stoppé » and « tracker sans cross-seed » each mean.** The operator's two words are not defined by § 19.
*Reading A — by CAUSE*: « stoppé » is the operator's switch off on that tracker (a decision, read on every torrent of it);
« tracker sans cross-seed » is a tracker that takes none by its nature (not queryable for this media type, no capability —
the engine's own `not_queryable_for_media_type`) (a fact). The states derive from configuration and eligibility; the
backend keeps no past. *Reading B — by HISTORY*: « stoppé » is a cross-seed that was running and was stopped (the switch
turned off after an injection, the torrent removed); « tracker sans cross-seed » is a tracker where none ever ran and
none can. The cost: B needs the backend to keep a stopped record with a date (demand B grows), the seed needs a stopped
row, and a torrent read « stoppé » by history must be told apart from one read by the switch; A keeps demand B smaller and
loses the word « was ».

**OPEN 7 — the engine's OWN switch.** `CrossSeedConfig.enabled` is a global kill-switch above the per-tracker ones (fact 5,
seeded as `cross_seed.enabled` in Réglages). § 19 dictates per-tracker only. *Reading A — said*: when the engine is off,
the roster's line and the section say « le moteur est coupé » and every tracker reads the engine's cause, not its own switch
(`engineEnabled` in demand A; state `trackers-cross-seed-engine-off`); the cost is a second cause to draw and the line's
variant. *Reading B — folded*: the per-tracker answer reads « stoppé » under an engine that is off and the surface never
names the engine, so a tracker whose OWN switch is on reads « stoppé » with no reason on the page — a « nothing » with no
sentence (DOIT-2), unless demand B carries the cause. Cost: A = +2 points at phase 5 and one state; B = the state costs
nothing and demand B carries the cause.

**OPEN 8 — which refusals the badge counts, and when they leave it.** The operator ruled that « the refused cross-seeds »
join the Trackers badge (L16 OPEN 3 = B); the closed set holds refusals that are the search's ORDINARY outcome
(`file_list_mismatch`, `piece_length_mismatch`, `self_candidate` — most candidates a search finds are not the same files)
beside real failures (`fetch_failed`, `inject_failed`). *Reading A — failures only*: the badge counts the pairs whose state
is « erreur de cross-seed » by a FAILURE kind (§ 2.2, « the attempt failed » and « the engine could not finish »); a
layout mismatch is read on its row and never counts. *Reading B — every refusal*: the badge counts every pair in
« erreur de cross-seed », the reason separating them on the page. In both, a refusal leaves the count when its pair's
state changes (a later attempt succeeds, the switch is cut) — the count is DERIVED from the state, and no « seen » gesture
is drawn. The cost: B risks a badge that never reads zero on a library the engine searches daily (a badge that always
speaks says nothing, ruling 12); A costs one more sentence in the count's own definition and the kind on each refusal.

---

## 8. What this design believes the contract gets wrong

Recorded as `docs/reference/frontend-architecture.md` § 7.1 asks; **no file outside `docs/features/maquette-l17/` is edited
for it, except the one dated line under the L17 heading** — the steward amends the plan and the operator amends the
constitution and the map.

1. **« In the media sheet's descriptor … the media feature's `panel-seasons` precedent »** — the sheet is a screen composed in
   a route (fact 12); `panel-seasons` registers a bottom-panel block. The block is drawn by `features/trackers` and composed
   at `routes/media-sheet.tsx`.
2. **« Behind the served role the backend already exposes »** — the backend serves no account role (fact 11); only the
   instance's deployment role. OPEN 1 is the question that follows.
3. **« Active by default »** is not what the engine does, nor what the live configuration says (facts 5, 6): demand H.
4. **« The two events reach the stream »** and « nothing relays them » are both written in the registers (fact 10): demand I.
5. **§ 19 point 1 names a « rejet pour politique de tracker »** the engine cannot say (fact 3): the design draws the policy
   case as a state and the operator decides whether a code is owed.
</content>
