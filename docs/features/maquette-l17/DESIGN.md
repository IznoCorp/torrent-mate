# L17 — §19, cross-seed is seen and decided · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L17 — §19, cross-seed` (its « Where it lives »
and « Done when » lines). It is not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every figure carries the
command that produces it, every decision carries its reason, every screen carries its named states. **Nothing under
`frontend/maquette/design/` was touched to write it** — the lot opens after L16 (the plan's order is L13 · L22 · L16
· L17 · L18), and this is the design read before it does.

**Written 2026-09-27 on `46806a88d`; AMENDED 2026-09-27 on `1d1282567`** against the operator's rulings of
2026-09-27 (round 8, 17 questions of which OPEN 1–8 and Q18 are this lot's; round 9, 19 questions of which Q5, Q7
(in part), Q8, Q9, Q10 and Q11 are this lot's; round 10, 7 questions of which Q3 and Q5 are this lot's;
`docs/reference/operator-method.md`), the auditor's coherence audit of 2026-09-27
(`review-archive/coherence-2026-09-27.md`, its triage `review-archive/coherence-2026-09-27-triage.md` § C) and the
auditor's rulings-coherence round the same day (`docs/reference/rulings-coherence-2026-09-27.md`, M1–M9, of which
M4, M5 and M6 are this lot's). **This is an AMENDMENT, not a redraw from a blank page**: the surface model of
§ 3 below changes in one place only — the cross-seed no longer has a section of its own, because ORGANISATION
RULING 19 (round 9) killed the `/trackers/$name` detail screen it would have lived on and replaced it with L16's two
tabs, « Torrents » and « Trackers ». Every other clause of § 0 stands as first drawn; § 0.1 says what each ruling
moved, and a clause this amendment leaves untouched says so.

**All eight OPEN questions of § 7.2 are ruled.** None is reopened here. § 7.2 below is kept as the RECORD of what was
open and what each answer costs — the form the operator's own words take when a plan is re-cut from them — never as
a live choice.

**Its spine is not mine.** `product-intent.md` § 19 « Ce que l'opérateur a tranché » (dictated 2026-08-30, amended
2026-09-27 with point 5) dictates the lot: AUTOMATIC, a PER-TRACKER off switch, a per-torrent per-tracker state — now
in SIX words, not four — the state on the Trackers page and, **held for L18** (OPEN 1 = B), a per-tracker block in
the media sheet for the administrator only. This document transcribes; where a ruling still leaves a mechanical
consequence to state without a choice, it is stated as such and never presented as this design's own invention.

---

## 0. What L17 owes, said once

`docs/reference/product-intent.md` § 19, § 17 (points 1, 2, 4 and « Ce que cela tranche »), § 18, § 12, § 13,
NE-DOIT-PAS-5, -6 and -8 and DOIT-14 give the lot the clauses below. The table says, for each, the surface that
serves it (§ 3) and the phases that build it (`plan/INDEX.md`).

| # | The clause | Its source | The surface that serves it | Phases |
| --- | --- | --- | --- | --- |
| 1 | The engine cross-seeds **alone, active by default at the switchover** — no act is asked of the operator; his own switches, off today, are HIS setting and are not touched | § 19, round 9 Q9 | no control: the states read (S1–S3); the default itself is a backend demand (H, § 6.2) | 1, 5 |
| 2 | A **per-tracker off switch**, on the Trackers page AND in Réglages, through the SAME write — cutting NEW cross-seeds only, with an option to cut the running ones too | § 19; OPEN 2 = A; round 9 Q5 | S2 (the tracker's own entry) | 9 |
| 3 | **For each torrent, the state tracker by tracker, in SIX words**: « actif », « stoppé », « tracker sans cross-seed », « erreur de cross-seed », « sans correspondance », « pas encore cherché » | § 19; OPEN 5 = A; round 10 Q5 | S3 — the torrent's cross-seed mark, in the Torrents tab | 4, 6, 7 |
| 4 | **The per-tracker state lives in the Trackers page** — now the Torrents tab's row (the mark) and the Trackers tab's entry (the summary and the switch) | § 19; organisation rulings 11, 19 | S1 (the roster's line, Trackers tab), S2 (the tracker's entry), S3 (the mark, Torrents tab) | 5, 6, 7, 9 |
| 5 | **A per-tracker block in the media sheet, for the administrator profile only** | § 19; § 17 | **held for L18** — OPEN 1 = B | — |
| 6 | **An injection is seen** | § 19 point 1 | « actif » with its date and its origin on S3; the obligation's origin on S4; the stream moves both (S6) | 6, 8, 13 |
| 7 | **A refusal is explained** — a layout mismatch is not a policy refusal, and each « nothing » has its reason; **an ordinary mismatch never counts as a failure** | § 19 point 1, § 8, DOIT-2, NE-DOIT-PAS-5 applied to a success; F22 | S3's « erreur » rows with the reason in clear words, grouped by the kind of trouble | 4, 7 |
| 8 | **The cross-seed attaches to the MEDIUM**, so an obligation shows its origin | § 19 point 2, § 18 point 2 | S4 (an obligation says whose copy it is); every row leads to the sheet by provider ID (NE-DOIT-PAS-9) | 8 |
| 9 | **To decide is also to refuse** — prevent as much as provoke; no « occupé »; **a refusal is REMEMBERED**, and a title can be cut entirely | § 19 point 3, DOIT-4, DOIT-14; round 9 Q11 | prevent: the switch (clause 2) and the per-torrent cut (clause 9-bis); provoke: OPEN 3 = A (S3's act); memory: the exclusion (S3-bis) | 9, 10, 11, 14, 15 |
| 9-bis | **Cutting a torrent's cross-seed on ONE tracker removes its qBittorrent entry, without its files, and closes any running obligation there « libérée »** | round 9 Q8; M4 | S3's per-pair gesture, « couper le cross-seed sur ce tracker » | 10 |
| 10 | **NE-DOIT-PAS-8 is the hard limit**: no automation more aggressive | § 19 point 4 | one read per screen visit, no poll (R-L17-k); the engine's own daily quota and delay are shown, never bypassed; the 3-day exclusion window governs the AUTOMATIC sweep only, never a hand-provoked search | 6, 14, 15 |
| 11 | **Ruling 12: the cross-seed speaks where it lives, and its failures join the Trackers badge** — no notifications box; failures only, with a reserved slot for the future upload lot | organisation ruling 12; L16 OPEN 3 = B; OPEN 8 = A; round 8 Q18 = B | S6 | 12, 13 |
| 12 | **Ruling 19: the Trackers page is two tabs — Torrents (every torrent, filterable by tracker) and Trackers (one entry per tracker)** | organisation ruling 19 | the page L16 lands and L17 extends into BOTH tabs; the rights are L18's | all |
| 13 | **The interface shows the truth** — every state drawn is the tracker's/engine's, none computed locally; **the global switch cuts nothing running** | NE-DOIT-PAS-1, § 13; M6 | R-L17-b: one derivation for the roster, the mark and the badge | 5, 6, 7 |
| 14 | **DOIT-14 reads `served` with a rule** — `partly` at L17's close, `served` only once L18 draws the media block | `product-intent-map.md`, DOIT-14 row; OPEN 1 = B | the close reports against it (§ 6.3) | 18 |

### 0.1 The rulings this amendment is read against, and what each moved

The rulings are the operator's and are not reopened here. « Organisation ruling N » is his entry in
`docs/reference/operator-method.md`, numbered as `docs/features/maquette-l22/DESIGN.md@232a908ca` § 0 numbers them; L16's own
re-read continues the count from 16.

| Ruling | What it dictates | What it moved in this amendment |
| --- | --- | --- |
| organisation ruling 11, 12, 15 (2026-09-26) | unchanged since the first drawing — no page of L17's own, one badge term, no notifications box | nothing new; § 3.6 stands |
| organisation ruling 18 (2026-09-27) | a tracker's ACTIVE torrents (cross-seeds included), one row each, with marks; « Retirer de qBittorrent » | L16's, drawn by L16; L17's cut (clause 9-bis) is the SAME kind of gesture, on the SAME row, for one tracker only |
| organisation ruling 19 (2026-09-27) | the Trackers page is TWO TABS, « Torrents » and « Trackers »; no per-tracker detail screen | **kills the standalone cross-seed section this document first drew**; § 3 below replaces it with S3 — a MARK on the Torrents tab's row, never a second page |
| round 8 (2026-09-27), L17 OPEN 1–8 and Q18 | the eight OPEN questions of § 7.2 below, ruled; the upload-to-tracker lot is separate, after L18 | § 7.2 (kept as record); § 0, every row above |
| round 9 Q5 (2026-09-27) | the tracker switch cuts NEW cross-seeds only; its confirmation offers, unchecked by default, cutting the running ones too; a torrent carries its own « couper le cross-seed sur ce tracker » | § 3.2 (S2, the switch); § 3.3 (S3's per-pair cut) |
| round 9 Q7 (2026-09-27) | a shared-files removal (L16's) names the consequence and takes every entry; L17's own cut confirmation names every tracker with a running obligation (hit-and-run) | § 3.3 (M4's confirmation rule) |
| round 9 Q8 (2026-09-27) | cutting a torrent's cross-seed on ONE tracker removes the entry WITHOUT files, marks « stoppé » with its date, closes the obligation there; resuming is « Chercher un cross-seed » | § 3.3 (S3's cut), § 3.3's OPEN 6 record (now B, by history) |
| round 9 Q9 (2026-09-27) | the operator's own switches, off today, are UNTOUCHED EXAMPLE VALUES, not his choice; the engine goes active by default AT THE SWITCHOVER; **the mock shows the LIVE states by default** | § 2.3 (the seed's default scenario, reversed from the first drawing) — **supersedes this document's own first reading, recorded below** |
| round 9 Q10 (2026-09-27) | « Cross-seed » everywhere — the section, the mark, the switch (Réglages included), the button, now « Chercher un cross-seed » | § 3 (opening); § 7.1 (Réglages' rename, no longer left alone) |
| round 9 Q11 (2026-09-27) | every cut is REMEMBERED: cutting a torrent's cross-seed on a tracker excludes that pair from the engine's future passes; « Ne plus partager ce titre » cuts every tracker and excludes the whole title; an exclusion undoes | § 3.3 (S3-bis, new) |
| round 10 Q3 = B (2026-09-27, rulings-coherence) | « Libérer » is not a gesture of its own; L17's own cut closes an obligation « libérée » the same way L16's removal does | § 3.3 (M4's confirmation, restated) |
| round 10 Q5 = A (2026-09-27, rulings-coherence) | a SIXTH word, « pas encore cherché », with its reason when the backend has one | § 2.2, § 3.3, § 4 (the sixth word) |
| M4 (2026-09-27, rulings-coherence) | a removal or a cross-seed cut, confirmed in the app, always closes « libérée »; the confirmation is owed whenever a RUNNING obligation would end | § 3.3 (S3's cut confirmation) |
| M5 (2026-09-27, rulings-coherence) | a failure is a STATE: it leaves the count the moment its row stops reading as failed, with no fresh gesture; a refused tracker (L16's) counts 1 | § 3.6 (R-L17-g's own rule, unchanged in substance from the first drawing — this is the confirmation the first drawing already read correctly) |
| M6 (2026-09-27, rulings-coherence) | the global switch cuts NOTHING running; moteur coupé and identifiant refusé are two distinct facts, both said; « en file » is an act's state, not a row word | § 3.1, § 3.2 (OPEN 7's reading, restated) |

### 0.2 What the engine and the tree measure — found while drawing, and what changed at the amendment

Every line below is a fact the drawing rests on. Facts 1–15 are as first measured on `46806a88d` (2026-09-27); one
new fact is added at the amendment.

| # | Fact | Command → reading |
| --- | --- | --- |
| 1–15 | Unchanged from the first drawing — the engine's 797 lines, its two events, the closed twelve-code reason set, the eight skip reasons with no event, every default `False`, the live seed's three switches off, the existing write, no route in either contract, the two events exempted from live rules, the registers' disagreement on the stream, no account role in either contract, the media sheet's composition (now L18's), the colour vocabulary, the stream mock's 399 lines, the contract's counters | see the first drawing's own commands, re-taken at each phase's opening — none of these facts changed at the amendment |
| 16 | **The engine stops at the FIRST verified injection, though its search walks every tracker** — F26 | `sed -n 220,260p personalscraper/acquire/cross_seed.py` → the loop returns on the first accepted candidate; nothing in the engine tries a SECOND eligible, switched-on tracker once one has succeeded. **The interface's own per-tracker state (clause 3) needs a state on EVERY eligible tracker, not only the one the engine happened to try first** — demand B (§ 6.2) asks the backend to attempt every eligible, switched-on tracker and keep a state per (torrent, tracker) pair; the cost is extra `.torrent` fetches, rechecks and seed obligations, never extra searches or quota units (the daily quota counts SEARCHES, not trackers tried per search) |
| 17 | **L16's `AcquisitionDownload` already carries `info_hash` per entry** (`docs/features/maquette-l16/DESIGN.md@f3d8fed01` § 2.1) | the identity F60 asks for is **already answered** by L16's own extension — this amendment adds nothing to the shape for it, and phase 1 says so rather than re-declaring a field that already exists |

---

## 1. What L17 builds on, and does not redraw

L16's re-drawn design is the base (`docs/features/maquette-l16/DESIGN.md@f3d8fed01`, plan `plan/INDEX.md@f3d8fed01`). This lot **adds to
it and never redraws it**. The extension points, each named by the L16 phase that creates it:

| L16 gives (file, per L16's plan) | L17 adds |
| --- | --- |
| the tracker's collapsed entry — `features/trackers/trackers-tab.tsx` (L16 phase 3): name, ratio, trend, volumes, the alert badge, the refused-identifier fact, the policy disclosure | one line: the cross-seed summary of THAT tracker, and the switch's second door (S1, S2) |
| the Torrents tab's row — `features/trackers/torrents-tab.tsx` (L16 phase 5): the title as a path, the tracker, the ratio on this tracker, the deadline, the origin colour, the obligation marks | the cross-seed MARK: a disclosure of every OTHER eligible tracker's state, on the ORIGIN row only (S3); the per-tracker cut and provoke gestures; « Ne plus partager ce titre » |
| « Retirer de qBittorrent » (L16 phase 6–7) | L17's own, narrower cut — one tracker's cross-seed entry, not the whole torrent — is the SAME KIND of gesture, drawn beside it, never confused with it |
| the obligation's mark (L16 phase 5) | a further mark and a path, when the obligation is a cross-seed's (S4) |
| the tracker summary read (L16 phase 1) | a `crossSeed` sub-object on the SAME read — the badge and the roster line keep ONE read (§ 13) |
| `trackersBadge` (L16 phase 10 in its plan) | the second term (S6) |
| `features/trackers/live.ts` (L16 phase 10) | the two cross-seed events, and a search-outcome event (S6) |
| `mocks/handlers/trackers.ts` (L16 phase 1) | the cross-seed fields — in that file if it stays under 400 non-blank lines, or a `mocks/handlers/cross-seed.ts` by SUBJECT (the `staging.ts` / `pipeline.ts` precedent); the opening measure decides |
| the `acquisitionLiveExemptions` residue (L16 phase 10) | the last two names leave it |

**What L17 does NOT need from L16 and must not assume:** the policy panel, the ranking editor, the alert threshold.
**What L17 does not draw at all, held for L18** (OPEN 1 = B): the media sheet's block, its route, its role gate — §
7.1 lists exactly what L18 takes.

---

## 2. The contract (D7) — and it comes FIRST

D7: the maquette declares the contract its interface REQUIRES, and every divergence from the backend's is a demand.
A demand is filed by EDITING THE CONTRACT (`frontend/maquette/contract/openapi.json`) and regenerating
`docs/reference/frontend-backend-demands.md` (`python3 scripts/compare-contracts.py --write`, then `--check`); the
register is « COMPUTED, NEVER WRITTEN ». This section says what the surfaces of § 3 read.

### 2.1 What is drawn

| Surface | Reads / acts through | Declared today |
| --- | --- | --- |
| S1 — the roster's line; S2's entry | the tracker summary read (L16), **extended**: per tracker `crossSeed{enabled, engineEnabled, active, failed, lastInjectedAt}` | L16's, not yet declared — the sub-object is new |
| S3 — the torrent's cross-seed mark, on the Torrents tab's ORIGIN row | the downloads read (L16), **extended**: `crossSeed: CrossSeedTrackerState[]` on the origin entry only — one row per OTHER eligible tracker, `{tracker, state, reason\|null, at\|null, stoppedAt\|null, stopCause\|null, excluded, searching}` | L16's, not yet declared — the array is new |
| S4 — an obligation's origin | the obligations read (L16), **extended** with `crossSeedOf{infoHash, title, media\|null}` | L16's, not yet declared — the field is new |
| the off switch (S2) | the EXISTING `PUT /api/config/files/{name}` (`updateConfigurationFile`), body `tracker:tracker.providers.<name>.cross_seed` — **no new operation**; its confirmation is drawn, its answer is the write's own | yes |
| the per-tracker cut (S3) | `POST /api/torrents/{infoHash}/cross-seed/{tracker}/cut` — `cutCrossSeed` (new): removes the entry, closes any running obligation there « libérée », marks the pair « stoppé » with its date | no |
| « provoke » (S3) | `POST /api/torrents/{infoHash}/cross-seed/search` — `searchCrossSeed` (new), body `{tracker}`: one torrent, one tracker, one call, an answer that is a visible « en file », never « occupé » | no |
| the exclusion (S3-bis) | `PUT` / `DELETE /api/torrents/{infoHash}/cross-seed/exclusions` — `writeCrossSeedExclusion` / `undoCrossSeedExclusion` (new): a pair, or the whole title | no |
| S6 — the badge | the tracker summary read (`crossSeed.failed`) | extended, as S1 |
| S6 — the stream | `CrossSeedInjected`, `CrossSeedRejected`, and a search-outcome event, through `/ws/events` | emitted; whether relayed is disputed (fact 10) |

**Held for L18** (OPEN 1 = B): `GET /api/media/{provider}/{providerId}/cross-seed` (`readMediaCrossSeed`) and the
`readAccount` admin fact — neither is filed here. § 7.1 names what L18 inherits.

### 2.2 The shapes' closed sets — drawn from the engine, not invented

- **The six states**, as the operator wrote them: « actif », « stoppé », « tracker sans cross-seed », « erreur de
  cross-seed », « sans correspondance » (OPEN 5 = A), « pas encore cherché » (round 10 Q5 = A). Their English
  identifiers (`active`, `stopped`, `trackerWithout`, `error`, `noMatch`, `notSearched`) are a proposal; the words
  live in `fr.json`. **« stoppé » is read by HISTORY, never by cause** (OPEN 6 = B): the pair RAN and was stopped —
  by the per-tracker switch cut (with its « couper aussi les cross-seeds en cours » option checked), by the
  per-torrent cut (S3's own gesture), or by the origin torrent's removal from qBittorrent (L16's) — and carries
  `stoppedAt` and a closed `stopCause` (`switch` | `removed`). **The engine being globally off is never a stop
  cause and never the word « stoppé »** (M6): it is a SEPARATE fact, read where the switch itself is (§ 3.1, § 3.2).
  « pas encore cherché » carries its own reason WHEN the backend has one (« en téléchargement », « en attente du
  quota ») — demand B supplies it, never invented by the mock beyond the seed's own cases.
- **The reason**, on a refusal (« erreur de cross-seed »): the engine's twelve codes (fact 3), grouped by the KIND
  of trouble, because § 19 point 1 asks that a layout mismatch is not read as a policy refusal. **The grouping now
  ALSO decides what counts in the badge (OPEN 8 = A, F22)**:
  - **the files are not the same** — `piece_length_mismatch`, `file_list_mismatch`, `root_name_mismatch`,
    `v2_hybrid`, `self_candidate` (the candidate is the source itself) — an ORDINARY outcome of a search, drawn on
    the row, **never counted in the badge**;
  - **the attempt failed** — `fetch_failed`, `verify_timeout`, `recheck_failed` (reserved — fact 3, unreachable
    today), `magnet_not_supported`, `parse_failed` — **counted**;
  - **the engine could not finish** — `inject_failed`, `obligation_write_failed` — **counted**;
  - **reserved, not built** — one slot for a future upload-to-tracker or tracker-side torrent-creation failure
    (round 8 Q18 = B): the closed set NAMES the slot so the badge's derivation needs no amendment when that lot
    lands, but no code path emits it today and this lot draws nothing for it.

  Each code has ONE sentence in clear French in `fr.json` (NE-DOIT-PAS-4: no bare code, no machine English);
  R-L17-a holds that every code the contract declares has one, and that the badge's derived count (demand A's
  `failed`) reads only the two counted families. **The tracker POLICY case has no code** (fact 3): the design draws
  it as the STATE (« stoppé » when the operator's switch is off, « tracker sans cross-seed » when the tracker takes
  none), never as a reason. **« sans correspondance » counts in NEITHER the row's refusal reading nor the badge**:
  the engine looked and found nothing, which is not a failure of anything.
- **How a search's own outcomes fold into ONE state per pair.** A search against one tracker may try several
  candidates before it stops; the pair's `state` and `reason` read the LAST attempt's own result — the same « one
  row, its current state » discipline every other surface in this codebase holds (§13) — and a reason counts toward
  the badge only when THAT last attempt's own code is a failure-kind code (the two families above), never when an
  earlier, ordinary mismatch in the same search happened to precede it.

### 2.3 The mocks — INVENTED, and each must MOVE (D7: « a mock that answers without moving certifies nothing »)

There is nothing to seed from, so the seed is written by the lot from the CASES below, chosen so that every state,
every family of reason and every gate of § 3 is reachable, and **no more**. The phase that writes it (phase 2) picks
the titles from the mock's own library seeds; the trackers are the roster's.

**The DEFAULT scenario shows the LIVE states — reversed from this document's first reading (round 9 Q9).** The
first drawing read the operator's live configuration (every switch off) as his OWN setting and made it the mock's
default, so every row read « stoppé ». **The operator's own words on 2026-09-27 supersede that reading**: « les «
non » … sont des valeurs d'exemple jamais touchées, pas son choix » — the fresh install ships them off, and his own
instance turns cross-seed active by default AT THE SWITCHOVER (demand H), never before. **The mock's default
scenario therefore shows the switches ON and the six states populated as an ordinary library would**: an « actif »
pair or two, a « stoppé » one by history, one « tracker sans cross-seed », some ordinary refusals, one failure, one
« sans correspondance », one « pas encore cherché ». **« le moteur est coupé » (the engine's own switch, OPEN 7 = A)
becomes a NAMED SCENARIO the operator reaches through `window.__go`, never the default** — the same discipline that
already gives every other surface in this codebase a reachable-but-not-default edge case.

| Case (invented) | What it must make reachable |
| --- | --- |
| a title cross-seeding on two OTHER trackers, injected on two dates | « actif » on the mark, twice, with their dates; the obligation's origin (S4); one of the two ALSO has its own active row (ruling 18: an active cross-seed is its own qBittorrent entry) |
| a pair stopped by the per-tracker switch (its « couper aussi les cross-seeds en cours » option was taken) | « stoppé », `stopCause: "switch"`, its date |
| a pair stopped by S3's own per-torrent cut | « stoppé », `stopCause: "removed"`, its date, and the pair excluded from future passes (S3-bis) |
| a tracker that takes no cross-seed for a kind of media | « tracker sans cross-seed » |
| three refusals, one per family of § 2.2, plus one candidate that failed on transport | « erreur de cross-seed » with a sentence per family; one of the three counts in the badge, two do not |
| a title with no candidate found anywhere | « sans correspondance » |
| a torrent never searched on an eligible tracker, with a reason | « pas encore cherché », its reason drawn |
| an excluded pair, and a title excluded whole | S3-bis's own state, and its undo reachable |
| an identified title AND an unidentified torrent | NE-DOIT-PAS-9: a sheet link by provider ID, and the resolution path for the torrent with none |
| one obligation that IS a cross-seed's, one that is not | S4's mark, and its absence |

**What each mock must MOVE.**

- the switch write (the existing `updateConfigurationFile`) moves the settings row AND what the summary read and
  every mark project — one seed, several projections (L16 fact 7: the handler already moves `raw` and
  `displayedValue`);
- the per-tracker cut (`cutCrossSeed`) REMOVES the matching entry from the downloads seed (if it was itself active
  there), moves the pair to `stopped`/`stoppedAt`/`stopCause: "removed"` on the origin's `crossSeed` array, closes
  any running obligation as `released_at` set, and adds the pair to the exclusion seed — in the SAME call, so every
  reader agrees in the answering render;
- a search (`searchCrossSeed`) moves the pair from `notSearched` or `noMatch` to `active`, `error` or `noMatch`
  again, and answers `queued: true` under the scenario's throttle;
- the extended obligations read answers `crossSeedOf` from the SAME rows as the mark (an obligation that a
  cross-seed created is a row of S3 too);
- an emitted `CrossSeedRejected` moves the pair's `failed` contribution and adds its row; a search-outcome event
  (F59) resolves a `queued` pair within the SAME visit, so a provoked search that finds nothing is seen to end.

### 2.4 The stream

`docs/reference/frontend-backend-demands-stream.md` § 3 already lists the two events as « claimed by no rule ». L17
claims them in `features/trackers/live.ts` (the file L16 creates), each rule refreshing the summary read and the
downloads read (never a third, media-block key — held for L18, F25); the two names leave
`acquisitionLiveExemptions`, which keeps `TrackerAuthFailed` (the system feature's) with a rewritten `because`. A
THIRD, new event — a search's own outcome (F59, demand I extended) — resolves a `queued` pair without a refetch, so
NE-DOIT-PAS-5 applies to a search that ends in nothing found exactly as it does to one that ends in an injection.

---

## 3. The surfaces, drawn

Copy is given in « guillemets » as `fr.json` will carry it, with the English key where one is proposed; a key that
exists is REUSED, never retyped. **The operator's six state words are verbatim.** The feature is named « Cross-seed »
EVERYWHERE (round 9 Q10) — the mark, the switch, the button (« Chercher un cross-seed »), and Réglages' own row,
whose « Partage croisé » label is RENAMED in the same phase (§ 7.1: this reverses the first drawing's own choice to
leave it alone). `data-part` names are English (D4).

### 3.0 The addresses (D1)

**L17 adds no page and no path.** The cross-seed is drawn INTO surfaces that already have an address: `/trackers`
(the roster's line, on the Trackers tab), `/trackers?tab=torrents` (the mark, on a torrent's own row). **What DIES
at the amendment**: `/trackers/$name` never existed to begin with on this head, and the first drawing's own
`§ 3.0` line about it is corrected here rather than left standing — L16's redraw killed the address before L17
could use it (`docs/features/maquette-l16/DESIGN.md@f3d8fed01` § 3). A FEED (OPEN 4) would have been a second view of
`/trackers`; it is not drawn (OPEN 4 = A).

### 3.1 S1 — The roster's line (Trackers tab)

**Its place.** L16's collapsed tracker entry (`features/trackers/trackers-tab.tsx`). One line beneath the ratio, on
its own row of the entry's grid so that it never shares a line with the ratio (DOIT-9).

**What is on the screen.** The tracker's cross-seed at rest, in one sentence assembled from the summary read:
« Cross-seed : actif — 4 torrents » / « Cross-seed : stoppé — interrupteur coupé » / « Cross-seed : tracker sans
cross-seed » (`screens.trackers.crossSeed*`). The count equals the number of pairs the mark answers for this tracker
in state `active` (R-L17-b). The line is PART OF the entry's own row, not a second control (F63 — corrected from
the first drawing's « a path to the section », which no longer exists to path to). **When the engine's own switch is
off (OPEN 7 = A), the line says so FIRST** — « Cross-seed : le moteur est coupé » — and the tracker's OWN switch
state, if different, is said SECOND on the same line (M6: the two are distinct facts and neither hides the other).

`data-part`: `trackers/cross-seed`. **Named states:** `trackers-cross-seed` (the roster, each line reading its
tracker's state), and `trackers-cross-seed-engine-off` (the engine's own switch off, a named scenario per § 2.3, not
the default).

### 3.2 S2 — The tracker's entry: the switch, with its second door

**Its place.** L16's tracker entry (Trackers tab), inside the disclosure DOIT-3 already opens for the policy fields
— the cross-seed switch is a FOURTH row there, through the SAME `Disclosure` (never a second panel kind, § 13).

**What is on the screen.** The switch's state in words (« Cross-seed actif sur ce tracker » / « Cross-seed coupé sur
ce tracker »), a control that flips it (OPEN 2 = A), and — after a change — « pris en compte à la prochaine passe »
(the config file takes effect on the next engine run, never at once — NE-DOIT-PAS-1). **The confirmation (F44,
round 9 Q5)**: flipping the switch OFF opens a confirmation naming the tracker, offering **« couper aussi les
cross-seeds en cours pour ce tracker »**, UNCHECKED by default. Left unchecked, the switch cuts only NEW cross-seeds
— every pair already `active` there keeps seeding, its row unchanged (M6: the global fact never touches what runs).
Checked, every pair `active` on this tracker moves to `stopped`, `stopCause: "switch"`, with its own date, and the
confirmation names each running obligation this would end (M4, round 9 Q7's own naming discipline carried here).
**Two halves move on two different clocks** (F20): the Réglages row, this entry's own switch line and the summary's
`enabled` field all move in the SAME render the write answers — but a pair's OWN move to `stopped` (when the option
was checked) moves only when the mock's write answers it, which this design draws as the SAME call, never a second,
delayed one the operator would have to wait a render for.

**When the engine's own switch is off**, this entry's own switch line is not hidden: it still reads the tracker's
setting, and a SEPARATE line above it says « le moteur est coupé » (M6 again — the two facts, never one hiding the
other).

`data-part`: `tracker/cross-seed-switch`. **Named states:** `tracker-cross-seed-switch-off` (this tracker's own
switch off, every pair here reading « stoppé » only if it was cut with the option checked — otherwise still
`active`, corrected from the first drawing's blanket reading); `tracker-cross-seed-switch-confirm` (F44, the
confirmation, transient, no URL).

### 3.3 S3 — The torrent's cross-seed mark (Torrents tab)

**Its place.** On the ORIGIN row of the Torrents tab ONLY (`features/trackers/torrents-tab.tsx`, L16's) — a
disclosure, `data-region="torrents/cross-seed"`, that a torrent already cross-seeding on another tracker does NOT
need repeated on its own SEPARATE active row there (that row already reads `active` for ITS OWN tracker, marked as a
cross-seed of the origin, S4). **This replaces the first drawing's standalone section outright** (ORGANISATION
RULING 19 killed the page it would have opened on): the mark is now a MARK, not a screen, and it is reached wherever
the origin's own row is — filtering the Torrents tab to another tracker does not re-surface it (§ 3.0 says why:
ruling 18's filter narrows by a row's OWN active-entry tracker, and a torrent's cross-seed mark is read on ITS OWN
row, not synthesised into a second, virtual one under a filter no ruling asks for).

**What is on the screen, opened.** One row per OTHER tracker eligible for this torrent's cross-seed: the tracker's
name, the state in the operator's word on the `chip` (`actif` → `success`, `stoppé` → `waiting`, `tracker sans
cross-seed` → `neutral`, `erreur de cross-seed` → `danger`, `sans correspondance` → `neutral`, `pas encore cherché` →
`waiting` — the word carries the meaning, the tone only helps, fact 13), the date the state took (« injecté le … »
on « actif », « stoppé le … » on « stoppé »), and, on an « erreur de cross-seed » row, its reason IN FULL (§ 2.2):
the sentence for its code, the kind of trouble, the candidate's tracker and the source torrent — never the bare
code. A « pas encore cherché » row carries its own reason when the backend has one. **The section's own row ORDER**
(F64, written here because it never was): the failures counted by the badge come FIRST, then the ordinary refusals,
then « actif », « stoppé », « tracker sans cross-seed », and « sans correspondance » / « pas encore cherché » LAST —
within each state, the newest date first. **Nothing is offered on a pair the engine does not allow** (§ 17 point 1),
and the mark's own read is folded into the SAME downloads call the row already answers from (R-L17-k: one read per
visit, never a second operation).

**« Chercher un cross-seed » (OPEN 3 = A).** Offered ONLY on a pair reading « sans correspondance », « erreur de
cross-seed » or « pas encore cherché » — never on `active`, `stopped` or `trackerWithout`, because nothing is
offered the engine would refuse to act on anyway (§ 17 point 1; this completes round 8 Q3's own act onto the sixth
word round 10 added afterward, a mechanical consequence, not a fresh choice). One tap asks ONCE
(`searchCrossSeed`, body `{tracker}`, `infoHash` in the path — fact 17, already answered by L16's own identity), a
throttled engine answers a visible « en file », never « occupé » (DOIT-4, NE-DOIT-PAS-3), and a second tap on the
same pair is the one refusal DOIT-4 allows (a duplicate). **A queued search resolves within the SAME visit** (F59):
a search-outcome event moves the pair from `queued` to whatever it becomes, so a search that finds nothing is SEEN
to end, never left reading « en file » forever.

**« Couper le cross-seed sur ce tracker » (round 9 Q5, Q8).** Offered on a pair reading « actif ». Confirmed, it
REMOVES the qBittorrent entry on that tracker (the entry's own row, if it was drawn separately, disappears from the
Torrents tab in the same render), WITHOUT its files (round 9 Q8 — the origin torrent keeps its own copy and keeps
seeding: the confirmation SAYS this, never lets « couper » read like a full removal), moves the pair to `stopped`,
`stopCause: "removed"`, its date, and closes the tracker's running obligation there « libérée » (M4 — the SAME
always-released discipline L16's own removal already holds, never left reading in breach even if it had crossed its
threshold). **The confirmation names the obligation this ends** whenever one is running (M4, round 9 Q7's naming
discipline). **The pair is EXCLUDED from the engine's future passes in the same gesture** (round 9 Q11, S3-bis).
Resuming a stopped pair is the SAME act as searching a fresh one — « Chercher un cross-seed » — which the exclusion
governs (below).

**« Ne plus partager ce titre » (S3-bis, round 9 Q11).** A gesture on the torrent's ORIGIN row (never on a single
tracker's own line, because it acts on every tracker at once): cuts every `active` pair on every tracker the SAME
way the per-pair cut does (M4's confirmation, naming every ending obligation), and EXCLUDES the whole title from
every future engine pass, on every tracker, not only the ones it was already cross-seeding on. **The origin torrent
itself is untouched** — it keeps seeding on its own tracker; the confirmation says so, the same discipline M4 asks
of the per-pair cut. **An exclusion undoes** — a per-pair exclusion, or a whole-title one — through the same act
reversed, at any time, no confirmation needed for the undo itself (undoing is never destructive).

`data-part`: `torrents/cross-seed`, `torrents/cross-seed-row`, `torrents/cross-seed-state`,
`torrents/cross-seed-reason`, `torrents/cross-seed-search`, `torrents/cross-seed-cut`, `torrents/cross-seed-exclude`.
`data-region="torrents/cross-seed"`.

**Named states.**

| id | What is on the screen |
| --- | --- |
| `torrents-cross-seed` | the origin row's mark opened, one row per other eligible tracker, in its state |
| `torrents-cross-seed-refused` | a refusal opened: its sentence, its kind of trouble, the candidate's tracker, the source |
| `torrents-cross-seed-search` | « Chercher un cross-seed » tapped on a `noMatch` / `error` / `notSearched` row |
| `torrents-cross-seed-search-queued` | the throttled answer, visible, never « occupé » |
| `torrents-cross-seed-cut-confirm` | the per-tracker cut's confirmation, naming a running obligation when one exists |
| `torrents-cross-seed-exclude` | a pair or a title excluded, and its undo reachable |

### 3.4 S4 — An obligation says where it came from

**Its place.** The obligation's mark in the Torrents tab row (L16's).

**What changes.** An obligation that a cross-seed CREATED (the engine persists the obligation on injection — fact
1's event docstring, « emit-after-persist ») gains a mark, « cross-seed de <torrent d'origine> » (round 9 Q10:
« Cross-seed » everywhere, the origin mark included), and a path to the origin's sheet by provider ID. § 19 point 2: without it the obligation of § 18 appears without its origin. An
obligation that is not a cross-seed's reads as it did — no mark, no empty slot.

`data-part`: `torrents/obligation-origin`. **Named state:** `torrents-obligation-cross-seed`.

### 3.5 Held for L18 — the media sheet's block

**§ 19 dictates it** (« un bloc par tracker, réservé au profil administrateur »), and OPEN 1 = B holds its drawing
for L18, whose rights model exists (§ 7.1 lists exactly what moves and why). **Nothing of it is drawn here**: no
route, no state, no gate. The route the first drawing proposed (`readMediaCrossSeed`) and the state names it
proposed (`media-cross-seed`, `media-cross-seed-hidden`) are DROPPED from this document, not merely deferred with a
stale name kept — L18's own design names them fresh, against its own model.

### 3.6 S6 — The badge's second term, and the stream

**The badge.** L16's `trackersBadge` counts the trackers under their alert threshold, the obligations in breach, and
the refused identifiers (L16's own three terms). **L17 adds the cross-seed FAILURES** (OPEN 8 = A, F22): the
function stays ONE function the feature exports and the frame names once; it reads the summary read's
`crossSeed.failed` — a count ALREADY narrowed to the two failure families (§ 2.2), never the ordinary mismatches and
never « sans correspondance ». **A failure is a STATE** (M5): it leaves the count the moment its pair's state
changes — a retry that succeeds, or a cut that reads it « stoppé » — with no « seen » gesture drawn, unlike L16's
own broken-obligations count, which DOES need one (a different fact, a different lot). No box collects it and no
line on Système repeats it (organisation ruling 12).

**The stream.** `CrossSeedInjected` and `CrossSeedRejected` are claimed by `features/trackers/live.ts`; a refusal
that arrives moves the mark and the badge without a refetch, like L16's own ratio events. **A third, new event** — a
search's own outcome (F59) — resolves a `queued` pair the same way.

**Named states:** `bar-trackers-refused` (the bar at its present buttons, the Trackers tab carrying a badge that
only a cross-seed failure justifies, beside L16's `bar-trackers-alert`).

---

## 4. The named states

**Measured before naming them at the amendment**: the count on `1d1282567` is L16's and L22's own, re-taken at
phase 1's opening (the command is unchanged from the first drawing, `docs/features/maquette-l22/DESIGN.md@232a908ca` § 4).
**L17 adds these unconditionally** — every OPEN question is ruled, so nothing here is conditional any more. Every
one is reachable by `window.__go("<id>")`, has an English id, and its French label is what the panel says. They live
in `harness/states/trackers.ts` (L16's file) while it stays under invariant 6's 400 lines, and in a new
`harness/states/cross-seed.ts` when it would not — the phase that crosses 400 measures and decides.

| # | id | Label (French, as the panel lists it) | Lands in phase |
| --- | --- | --- | ---: |
| 1 | `trackers-cross-seed` | « Trackers — la ligne cross-seed de chaque tracker » | 5 |
| 2 | `trackers-cross-seed-engine-off` | « Trackers — le moteur entier est coupé » | 5 |
| 3 | `tracker-cross-seed-switch-off` | « Tracker — l'interrupteur est coupé, les pairs déjà actifs continuent » | 9 |
| 4 | `tracker-cross-seed-switch-confirm` | « Tracker — confirmer la coupure, avec ou sans les cross-seeds en cours » | 9 |
| 5 | `torrents-cross-seed` | « Torrents — la marque cross-seed d'une ligne, chaque autre tracker » | 6, 7 |
| 6 | `torrents-cross-seed-refused` | « Torrents — un refus, sa raison en entier » | 7 |
| 7 | `torrents-cross-seed-search` | « Torrents — « Chercher un cross-seed » sur une paire » | 14, 15 |
| 8 | `torrents-cross-seed-search-queued` | « Torrents — la recherche est en file, dite » | 15 |
| 9 | `torrents-cross-seed-cut-confirm` | « Torrents — couper un cross-seed, l'obligation nommée » | 10 |
| 10 | `torrents-cross-seed-exclude` | « Torrents — une paire ou un titre exclu, l'annulation possible » | 11 |
| 11 | `torrents-obligation-cross-seed` | « Torrents — une obligation née d'un cross-seed, son origine » | 8 |
| 12 | `bar-trackers-refused` | « Barre — Trackers porte un échec de cross-seed » | 12 |

`torrents-cross-seed`'s loading and error states are the SAME two every surface of this codebase already needs
(`SkeletonLine`, `SurfaceError`) and are not separately numbered, per L22's own precedent (R90 walks them by a
per-surface list, not by name here).

**What has no named state and why.** The switch's flip, the two cuts, the exclusion's write and undo, the tap on
« Chercher un cross-seed » and the arrival of an event are ACTS, not surfaces: R-L17-e, R-L17-f, R-L17-i and R-L17-h
walk them by finger or through `window.__mocks.emit` and read the network and the render.

### 4.1 What the oracle will do (D8)

The new surfaces are NEW, so the reference RECORDS them and proves nothing about them. What the oracle is for here
is the other direction — **no existing state may diverge unless a phase names it**. The list below covers every
phase of the re-cut plan (§ INDEX), not only the ones this document first named (F61 — the first drawing stopped at
its own phase 13 and left every later phase unnamed):

| Phase | Existing states that WILL diverge | Reason (accepted by name, D8) |
| --- | --- | --- |
| 1–3 | none — a contract, a seed, a handler | — |
| 4 | none — the words' map and the reasons' sentences carry no surface yet | — |
| 5 | L16's `trackers-list` (each entry gains a line) and `tracker-alert-active` where it draws the roster | « L17 § 3.1: the entry's cross-seed line » |
| 6, 7 | L16's `torrents-list` and its variants (the origin row's mark) | « L17 § 3.3: the cross-seed mark » |
| 8 | L16's `torrents-list` again, where an obligation is a cross-seed's | « L17 § 3.4: the obligation's origin » |
| 9 | L16's `tracker-entry-open` (the disclosure gains a fourth row) | « L17 § 3.2: the switch » |
| 10 | L16's `torrents-list` again, where a pair is cut | « L17 § 3.3: the cut » |
| 11 | none by the oracle — an exclusion changes no rectangle it reads | — |
| 12 | none by the oracle — the badge's number is text | — |
| 13 | none — a live rule moves no rectangle | — |
| 14, 15 | none — a contract, then an act on an existing row | — |
| 16 | none by the oracle — a virtual window's geometry is declared, not read by a rectangle proof | — |
| 17, 18 | none — records and the close | — |

**The oracle's silence over the badge and over a removed row proves nothing, and this design says so before the
phase does**: the oracle reads a rectangle and a computed style, never a count or a missing element. **This lot is
held by § 5's rules or by nobody.**

The accessibility tier (`--a11y`) is re-read at phases 6, 7, 9, 10 and 15 over the states this lot adds.

---

## 5. The rules that bite

Numbers: the harness's highest rule number is re-taken against `origin/main` at the moment phase 4 runs (the first
phase that writes a rule), and every label below is bound to a consecutive free number then, the mapping written
into the report. A number chosen from this document without re-measuring is a collision. Each rule is written RED
FIRST; none of the surfaces exists on `main`, so each is red for that reason and needs no mutation to be seen red;
the mutation comes after the move.

| Rule | Phase | What it READS | The mutation that fells it |
| --- | ---: | --- | --- |
| **R-L17-a** — the six words, and no bare code (NE-DOIT-PAS-4) | 4 | every state chip the surface draws reads one of the operator's six words; every reason code the contract's `state`/`reason` enums declare has a sentence in `fr.json`, and no rendered text is a bare code | draw the code instead of its sentence → falls; remove one sentence → falls; add a seventh chip word → falls |
| **R-L17-b** — one derivation (§13, NE-DOIT-PAS-1, M6) | 5, re-aimed 6, 7, 12 | the state and the count drawn on the roster's line, on the mark's rows and in the badge equal the mock's own field, never a local computation; **when `engineEnabled` is false, every reader — the line, the tracker's entry — names it FIRST, and no pair reads « stoppé » from it alone** | compute a state or a count client-side → falls; draw a pair « stoppé » from the engine's own switch alone → the engine-off hold falls |
| **R-L17-c** — a refusal is readable with its reason (§ 19 point 1, DOIT-2) | 7 | on `torrents-cross-seed-refused`: the row draws the sentence of ITS code, its kind of trouble, the candidate's tracker and the source; a layout mismatch and a transport failure read differently | draw one constant sentence → the contrast hold falls; drop the reason → falls; draw the code → R-L17-a falls too |
| **R-L17-d** — an obligation says where it came from (§ 19 point 2) | 8 | a seeded obligation created by a cross-seed carries the mark and a path to the origin's sheet by provider ID; one that is not carries neither | drop the mark → falls; mark every obligation → the absence hold falls |
| **R-L17-e** — the switch, in two halves (§ 19, NE-DOIT-PAS-6, F20, round 9 Q5) | 9 | the flip is ANSWERED on the network; the Réglages row, the tracker's own switch line and the summary's `enabled` move in the SAME render; a pair's own move to `stopped` (the option checked) moves in the SAME call, never a delayed second one; the confirmation names every running obligation the option would end | make the control message without calling → the network hold falls; move the row and not the projections → the agreement falls; move a pair to `stopped` without the option checked → falls |
| **R-L17-f** — cutting one tracker's cross-seed (round 9 Q5, Q8; M4) | 10 | the operation CALLED; the entry gone from the Torrents tab if it was active there; the pair `stopped`, `stopCause: "removed"`, its date; any running obligation closed `released_at` set, NEVER left in breach; the confirmation names it; the pair excluded in the SAME call (R-L17-j reads the exclusion itself) | message without calling → the network hold falls; leave the obligation in breach → falls; skip the confirmation's obligation name → falls; leave the pair included after the cut → the exclusion hold (R-L17-j) falls |
| **R-L17-g** — the badge's second term, failures only (ruling 12, OPEN 8, M5) | 12 | the Trackers tab's number equals the trackers under threshold plus the obligations in breach plus the refused identifiers plus the cross-seed FAILURES (the two counted families only); an ordinary mismatch never moves it; « sans correspondance » never moves it; a failure leaves the count the moment its pair's state changes, with no « seen » gesture | count an ordinary mismatch → falls; count « sans correspondance » → falls; require a « seen » gesture to clear a resolved failure → falls |
| **R-L17-h** — the events are claimed, injection, refusal and search-outcome (R91's fan-out; B-145; F59) | 13 | `CrossSeedRejected`, `CrossSeedInjected` and the search-outcome event, each emitted through `window.__mocks.emit`, move the mark's rows and the badge WITHOUT a refetch; a `queued` pair resolves within the SAME visit; none of the three names is in `acquisitionLiveExemptions` any more | leave a rule out of `features/trackers/live.ts` → the state stops moving and falls; leave a `queued` pair unresolved past the visit → falls |
| **R-L17-i** — « provoke » is bounded, answered, visible and offered only where the engine allows it (DOIT-4, NE-DOIT-PAS-3, -8, § 17 point 1) | 15 | a tap asks ONCE; a throttling engine answers a visible « en file », never « occupé »; a second tap on the same pair is the one refusal (a duplicate); the quota is drawn; the act is offered ONLY on `noMatch`, `error` or `notSearched` rows, never on `active`, `stopped` or `trackerWithout` | let a double tap send two → falls; answer « occupé » → falls; offer the act on an `active` row → the offer hold falls |
| **R-L17-j** — the exclusion is remembered, and undoes (round 9 Q11) | 11 | a cut pair (R-L17-f) is excluded from the engine's future passes; « Ne plus partager ce titre » excludes the whole title, on every tracker; the exclusion answers back after an undo, no confirmation needed for the undo itself | leave a cut pair searchable again without an undo → falls; require a confirmation on the undo → the undo hold falls |
| **R-L17-k** — one read per visit (NE-DOIT-PAS-8) | 6 | opening the roster and the Torrents tab makes each operation ONE call, and a wait on the page makes none; the mark's own data is folded into the SAME downloads call, never a second operation | add a refetch interval → falls; declare a second read for the mark → falls |

**Seeds into existing rules, not new rules of their own** (L20's precedent): `harness/states.py` is seeded with
every new state; `screen_addresses.py` needs nothing (no address is added); `state_surfaces.py` (R90) takes the
loading and error states, which this lot names by no new id (§ 4). **Every state is proved at the phone's real
width** (`docs/reference/product-intent.md` § 12, DOIT-9).

### 5.1 Rules L16 wrote that this lot re-aims

R-L16-d (« one derivation for the alert, four readers ») reads the Trackers tab's badge; the cross-seed term makes
that count a sum of four (threshold, breach, refused identifier, cross-seed failure), so the rule is **re-aimed in
phase 12**, out loud, and its mutation re-run. R91 (`fanout.py`) is re-aimed in phase 13 for the three names that
leave the exemption. Neither is left green over a changed reading.

---

## 6. The register rows and the demands touched

### 6.1 The register rows

Read, not edited by this pull request (a documentation-only PR that touches nothing outside
`docs/features/maquette-l17/` and the two dated lines of `docs/reference/frontend-architecture.md` and
`docs/reference/backend-demands-architecture.md`):

| Row | State | What happens |
| --- | --- | --- |
| **B-145** — « 797 lines of engine that inject torrents at third parties, and no way to know it happened » | `open` | its READING half closes when the surfaces land; its backend half (a route, the events on the stream) stays owed. The close annotates the row and never closes it alone |
| **B-144** — the ratio's three operations | `open`, L16's | not this lot's |
| **B-539** — « no cross-seed join check exists » (a homonym, L13r's seed-correspondence guard) | `open` | noted so nobody reads it as owed here |

### 6.2 The demands PROPOSED (D7) — in the register's own form, not asserted

Nine rows, none invented outside `backend-demands-architecture.md` § 5 — each is a shape that section names, made
typed by the drawing. **C and J move to L18** (OPEN 1 = B); **F (the feed) is DROPPED** (OPEN 4 = A). The lot files
A, B, D in phase 1, and E, G, H, I, K in the phase that draws each (a demand is filed where its surface is drawn,
L22's precedent), by editing `frontend/maquette/contract/openapi.json` and regenerating the register; the
operationIds adjust.

| # | operation | operationId | what it is for | Filed in phase |
| --- | --- | --- | --- | ---: |
| A | the tracker summary read (L16's) | extended | per tracker: `crossSeed{enabled, engineEnabled, active, failed, lastInjectedAt}` — the roster's line, the entry and the badge read ONE answer (§13) | 1 |
| B | the downloads read (L16's) | extended | on the ORIGIN entry only, `crossSeed: CrossSeedTrackerState[]` — one row per OTHER eligible tracker, the six states, the reason, the date, the stop's date and cause, the exclusion flag. **The backend must attempt EVERY eligible, switched-on tracker** (fact 16, F26), not stop at the first verified injection, and **must KEEP a state** for the ones no event ever fires for (eight skip reasons emit nothing, fact 4) | 1 |
| D | the obligations read (L16's) | extended | `crossSeedOf{infoHash, title, media\|null}` — an obligation says which torrent's copy it is (§ 19 point 2) | 8 |
| E | `POST /api/torrents/{infoHash}/cross-seed/search` | `searchCrossSeed` (new) | one torrent, one tracker, one search, an answer that is a visible « en file » under throttle; bounded ONLY by the engine's daily quota and delay — never by the 3-day exclusion window, which governs the automatic sweep alone (F45) | 14 |
| F | ~~a feed of events~~ | — | **DROPPED** (OPEN 4 = A): S3's rows already carry the date and the reason, and organisation ruling 12 keeps Système's history as the only trace of the past | — |
| G | the config write | none new | the per-tracker switch is `tracker.providers.<name>.cross_seed` through the EXISTING `updateConfigurationFile` (fact 7) | — |
| H | engine defaults | not an operation | `TrackerProviderConfig.cross_seed` and `CrossSeedConfig.enabled` default to `False` today (fact 5); § 19 dictates « actif par défaut » at the switchover (round 9 Q9 — his OWN instance's current off values are untouched examples, not his choice); the backend follows the interface (§ 15), never before the switchover |
| I | the stream, and a search-outcome event | not an operation | the two engine events reach `/ws/events`, with `tracker` (not `source_tracker`, fact 2) and the reason; **a third event says when a search resolves** (F59), so a queued search that finds nothing is seen to end within the same visit |
| K | `PUT` / `DELETE /api/torrents/{infoHash}/cross-seed/exclusions` | `writeCrossSeedExclusion` / `undoCrossSeedExclusion` (new) | a pair, or the whole title, excluded from every future engine pass; undoable, no confirmation on the undo (round 9 Q11) |

**Cutting one tracker's cross-seed** (`cutCrossSeed`, § 2.1) is filed in phase 10, where it is drawn, per the same
« a demand is filed where its surface is drawn » discipline demand D already follows.

**Held for L18, not filed here** (OPEN 1 = B): `readMediaCrossSeed` (the media block's own route) and the `readAccount`
admin fact — § 7.1 names exactly what L18 inherits.

### 6.3 The clause-map row PROPOSED (the operator amends the map; this lot does not)

`docs/reference/product-intent-map.md`, **DOIT-14** — « rendre le cross-seed visible et décidable (§19) » — reads
`to draw`, owner **L17**. Proposed: the row reads **`partly`** at L17's close (surface `features/trackers` — the
roster's line, the mark, the obligation's origin, the badge — proof R-L17-a … k) and **`served`** only once L18
draws the media sheet's block on its rights model (OPEN 1 = B). The operator amends the map; the close reports
against the row.

---

## 7. What this design does NOT draw, and what is OPEN

### 7.1 Not drawn — and whose it is

- **The Trackers page itself, its two tabs, its bar entry and its ratio** — L16's. L17 draws into both tabs.
- **The rights model, the bar's composition by rights, the role on the account** — L18's (organisation ruling 11,
  § 17). L17 adds no role to the navigation table.
- **The media sheet's cross-seed block, its route (`readMediaCrossSeed`), its role gate, and the `readAccount`
  admin fact (demand J)** — **HELD FOR L18** (OPEN 1 = B, round 8 question 1). L18's § 6.2 takes the route, gated
  by a named ACL right (organisation ruling 17/20), refused with a 403 when forced, per L18's own two-halves
  convention; L18's state table owns `media-cross-seed` and `media-cross-seed-hidden` fresh, against its own model,
  never these names carried over from a design that never built them. L18's § 7.1 names that it draws them; this
  document's own § 3.5 says only that nothing is built here.
- **The upload-to-tracker lot** (round 8 Q18 = B) — a SEPARATE lot, proposed L23, after L18, drawn ahead of time in
  a later slot with its own questions (the publish gesture, a publication's own state, per-tracker publish rules).
  L17 keeps only the reserved failure-kind slot in the closed set (§ 2.2) so the badge's derivation needs no
  amendment when that lot lands; it draws nothing else for it.
- **A FEED of injections and refusals** (OPEN 4 = A) — S3's own rows already carry the date of an injection and the
  reason of a refusal; organisation ruling 12 keeps Système's history as the only trace of the past.
- **A tracker-policy REASON on a refusal** — the engine has no such code (fact 3). The design draws the policy case
  as a state (§ 2.2). If the operator wants a code, that is demand B's, and the words follow.
- **Push notification of a failure** — a platform demand (`backend-demands-architecture.md` § 4, the FCM channel),
  filed by L16 for the ratio; nothing here reads it.
- **The engine's own tuning** (`max_searches_per_day`, `min_delay_between_searches_s`, `exclude_recent_search_days`)
  — configuration, Réglages'; the surface may SHOW the quota and never sets it, and the 3-day exclusion window is
  never surfaced as a bound on a hand-provoked search (F45).
- **Anything the engine does** — the backend follows the interface (§ 15), after the freeze.

### 7.2 The eight OPEN questions, as ruled (kept as record, chosen nowhere else)

Every reading below is the operator's, dated 2026-09-27 (round 8, unless said otherwise). Nothing here reopens a
choice; this is the record the plan's re-cut is measured against.

**OPEN 1 — the media sheet's block, before L18's model exists — ruled B, HELD.** « le bloc « cross-seed » de la
fiche média, réservé à l'administrateur, attend L18 et son modèle de droits ; L17 dessine le reste ». Phases 10 and
11 of the first drawing (the block and its gate) leave the plan entirely (−22 points from the first count); § 3.5
and § 7.1 say what L18 inherits.

**OPEN 2 — where the off switch's CONTROL lives — ruled A.** « l'interrupteur de cross-seed d'un tracker se
manœuvre aussi depuis la page Trackers … par la même écriture de configuration que Réglages ; une seule écriture,
deux portes. » § 3.2 draws the control on the tracker's own entry; round 9 Q5 adds the confirmation and its option.

**OPEN 3 — what « provoke » means on the surface — ruled A.** « « Chercher un partage croisé » par torrent — une
recherche bornée par les limites du moteur (quota quotidien, délai) … une opération demandée au back-end. » § 3.3
draws it as « Chercher un cross-seed » (renamed, round 9 Q10), offered on the three eligible states (§ 5, R-L17-i).

**OPEN 4 — a feed of injections and refusals, or none — ruled A, none.** « pas de fil des injections et des refus ;
chaque ligne montre son dernier état … l'historique de Système reste la seule trace du passé. » § 7.1 and demand F's
row record it dropped.

**OPEN 5 — what a (torrent, tracker) pair reads when the engine looked and found NOTHING — ruled A, a fifth word.**
« un cinquième mot d'état, « sans correspondance » … chaque torrent cherché a sa ligne. » § 2.2 and § 4's table carry
it; round 10 Q5 adds a sixth.

**OPEN 6 — what « stoppé » and « tracker sans cross-seed » each mean — ruled B, by HISTORY.** « « stoppé » = un
cross-seed tournait et a été arrêté … avec sa date ; « tracker sans cross-seed » = aucun n'a jamais tourné et aucun
ne peut. » § 2.2 and § 3.3 carry `stoppedAt` and `stopCause`; round 9 Q5/Q8 name the two causes (`switch`,
`removed`).

**OPEN 7 — the engine's OWN switch — ruled A, said.** « quand l'interrupteur général du cross-seed est coupé, la
ligne de chaque tracker et la section disent « le moteur est coupé » … chaque tracker montre cette cause plutôt que
la sienne. » Corrected by M6 at the coherence round: the tracker's OWN cause is said TOO, never hidden by the
engine's — § 3.1 and § 3.2 say both.

**OPEN 8 — which refusals the badge counts, and when they leave it — ruled A, failures only.** « le badge de
Trackers compte les ÉCHECS de cross-seed seulement … et un échec d'UPLOAD … comptera comme un échec. » § 2.2's
grouping and § 3.6 carry it, with the reserved slot round 8 Q18 named.

### 7.3 Two DESIGN contradictions inherited from L16 — recorded, not chosen

Found by reader C16 (`review-archive/l16/round-1-C16/r1-C16.md`, finding C17 c, d), left unrepaired at L16's close
(the decided list did not take them). Neither asks anything of the backend, so neither belongs in
`backend-demands-architecture.md`; both land here because L17 is the next lot to touch their surfaces — **no
reading is chosen for either.**

- **`TrackerAuthFailed` vs « all four … through `live.ts` ».** L16's DESIGN § 4.5 claims all four of the ratio
  alert's components (threshold, breach, refused identifier, unseen broken obligation) are "refreshed through this
  lot's `live.ts`", while the SAME paragraph keeps `TrackerAuthFailed` — the event the refused-identifier component
  reads — named in `acquisitionLiveExemptions`, never live. The refused-identifier unit is therefore NOT live as
  claimed. L16's own text names the event's future owner as "L17's, and the system feature's" — this lot's phase
  that touches `features/trackers/live.ts` (§ 3.6) is where the reading is chosen: wire `TrackerAuthFailed` in, or
  correct § 4.5's claim.
- **The removal confirmation's checkbox cannot gate its own confirmation.** L16's DESIGN § 4.4 says the qBittorrent
  removal confirmation with its « Supprimer les fichiers » checkbox does not open at all when the checkbox WOULD
  read unchecked and nothing else is at stake — but the checkbox lives INSIDE that same confirmation, so its state
  cannot be read before the confirmation opens to show it. The two sentences cannot both be drawn. This lot's own
  cross-seed cut (§ 3.3, « Couper le cross-seed sur ce tracker ») confirms a different, checkbox-less act on the
  same Torrents tab; whoever next touches the qBittorrent removal flow chooses whether the checkbox moves outside
  the confirmation or the « no confirmation » clause is dropped.

---

## 8. What this design believes the contract gets wrong

Recorded as `docs/reference/frontend-architecture.md` § 7.1 asks; **no file outside `docs/features/maquette-l17/`
is edited for it, except the two dated lines under the L17 heading of `frontend-architecture.md` and in
`backend-demands-architecture.md` § 5** — the steward amends the plan and the architecture entry, and the operator
amends the constitution and the map.

1. **« Behind the served role the backend already exposes »** and **« a block in the media sheet's descriptor »** —
   both are L18's question now (OPEN 1 = B): no account carries a role in either contract (fact 11), and the sheet
   is a screen composed in a route, not a panel descriptor (fact 12 — L18's own drawing corrects this, not L17's).
2. **« Active by default »** is not what the engine does, nor what the live configuration says (facts 5, 6); round 9
   Q9 corrects WHEN it becomes true (at the switchover, never before) — demand H.
3. **« The two events reach the stream »** and « nothing relays them » are both written in the registers (fact 10):
   demand I, now extended with a third, search-outcome event (F59).
4. **§ 19 point 1 names a « rejet pour politique de tracker »** the engine cannot say (fact 3): the design draws the
   policy case as a state and the operator decides whether a code is owed.
5. **The engine tries only the FIRST verified tracker**, though § 19 wants a state on EVERY eligible one (F26,
   fact 16): demand B is extended to ask for an attempt per eligible, switched-on tracker.
