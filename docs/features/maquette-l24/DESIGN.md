# L24 — the orphans: what no lot draws · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L24 — the orphans, what no lot draws` (its
« Where it lives » and « Done when » lines). It is not restated here; what follows is the drawing a later plan
executes, once the operator has answered § 5's open questions.

This document is written for a session that has none of the context it was produced in. **Nothing under
`frontend/maquette/` was touched to write it** — no code, no rule, no mock, no seed, no harness run: prose and
numbers, drawn ahead of the lot's own opening so the operator rules its questions in one round and the freeze date
stops lying by omission (`IMPLEMENTATION.md` § « Where the frontend work stands », the « Next » row).

**Written 2026-09-29, on `main` at `e65130ab1`.** The plan's order is `L14 · L19 · L21 · L13 · L20 · L22 · L16 · L17
· L18 · L23`; L24 opens after L23. Unlike L16–L23, **nothing here is already decided by the constitution for this
document to transcribe**: the four subjects below are what the mission of 2026-08-19 says must be redrawn and no lot
names. The drawing is therefore a judgment, and every place where a reading splits, or where the drawing meets an
operator ruling already written, is an OPEN question in § 5 — never a choice made here (auditor's order 72).

---

## 0. What L24 owes, said once

| # | Subject | Its source | Surface or proof | Held for |
| --- | --- | --- | --- | --- |
| a | Production's « Décisions » tab (`/media`, third tab) — every decision, every state, filtered, each with its outcome | mission 2026-08-19; § 15 « la maquette doit TOUTES les pages que la production sert » | **S1** — the decisions journal (surface) | § 1.1 |
| b1 | Contrôle's « Santé » (disks, index, Redis, providers) | `IMPLEMENTATION.md`, the « Next » row | **S2** — Système's sections that say their own read failed (surface) | § 1.2 |
| b2 | Contrôle's « Activité scraping » (what is being identified now, how many wait) | same | **S3** — per medium, a proof; globally, OPEN 3 | § 1.3 |
| b3 | The addresses `/control`, `/pipeline` and the other former production paths | § 15; § 16 rule 3; D1 | **S4** — the former addresses answer their successor (surface) | § 1.4 |
| c | The seven owed halves of `partly` rows whose owner has merged (DOIT-1, 5, 7, 9, 11, NE-DOIT-PAS-1 — L19; NE-DOIT-PAS-6 — L15) | `docs/reference/product-intent-map.md` | one surface (**S5**, DOIT-7) and six proofs | § 1.5 |
| d | DOIT-9's desktop half — « le desktop reste pleinement fonctionnel » | DOIT-9; § 12 | a proof over every named state | § 1.6 |

### 0.1 A measurement that corrects the premise

`IMPLEMENTATION.md`'s « Next » row says « Santé » has « no maquette equivalent anywhere, verified by grep on
2026-09-28 ». The grep it cites searches French and English words (`Santé`, `disk usage`, `index health`) that the
maquette's code never spells — its names are `useDisks`, `useIndexHealth`, and its copy lives in `fr.json`.
Measured on this tree:

    grep -n "useDisks\|useIndexHealth\|useDependencies\|useServices" frontend/maquette/design/src/features/system/page.tsx

reads four reads imported (lines 26–30) and drawn (lines 44–50) by Système's page, under the headings `fr.json` names « Services »,
« Disques », « Index de la médiathèque », « Dépendances » — and the seeds carry exactly production's four domains:
disks with their free space (`mocks/seeds/disks.json`, « Disk2 — bientôt plein »), the index (`index-health.json`,
« 1 863 titres », « Anomalies relevées »), Redis and the providers' circuit (`dependencies.json`, « Redis —
connecté », « TMDB / TVDB — aucun disjoncteur ouvert »). R67 (`harness/machine.py:112–113`) already reads the disks
and index rows. **« Santé » is drawn in substance, on Système, where the cut of 2026-08-19 puts it** (« a machine in
trouble is Système »). What is NOT drawn is what production's compact card did that Système's page does not: each
domain saying ITS OWN read failed (« Disques — état indisponible », « API injoignable »). § 1.2 draws that, and
nothing more; the steward's sentence is corrected by this lot's close, never here (Non-goals).

### 0.2 What L24 builds on, and does not redraw

| Lot (landed) | L24 reads it as |
| --- | --- |
| L20 — Système's « Pipeline » section, the levers, the history, `/run/$runUid` | the HOME of `/pipeline`'s successor and of any global scraping figure (S3, S4) |
| L22 — Acquisition's four tabs, « À traiter », the one ladder, the candidates screen `/resolution/$folder`, « Réglées récemment » | the HOME of the decisions a medium is waiting on, and the entry to S1 |
| L19/L21 — the journey sheet, its verbs, the producers | the surface DOIT-1 and DOIT-5's proofs read |
| L15 — the frame, the drawer, the dialog layer | the surface NE-DOIT-PAS-6's and the desktop proofs read |

---

## 1. What each subject dictates, and the surface that serves it

### 1.1 (a) The decisions journal — S1

**What production offers** (`frontend/src/pages/MediaLibrary.tsx:56–68, 330–460`, `components/decisions/`): a flat
list of every scrape decision, four states — « En attente », « Réglée », « Laissée telle quelle », « Remplacée
depuis » — as multi-select filter chips each carrying its count, a count whose read failed shown « ? » rather than
« 0 »; a row opens a detail addressed by `?decision=<id>`; a settled detail says its outcome in one sentence and, for
« Réglée », the « Correspondance retenue » (provider, id, « recherche manuelle » or « sélection »); a pending detail
is the arbitration itself.

**What the maquette already has.** The pending half is served: « À traiter » lists what waits on the hand, and
`/resolution/$folder` is the arbitration (L22). The settled half is six rows under « Réglées récemment » at the foot
of the candidates screen (`features/acquisition/resolution-screen.tsx:177–186`, `.slice(0, 6)`), not addressable,
not filterable, and reachable only by opening an unrelated pending decision. The vocabulary exists
(`screens.resolution.decisionState`, three words, one per settled state).

**What S1 draws.** One list of every decision, newest first, each row the folder in the mono face (a decision is a
FOLDER, `frontend/maquette/README.md` § « A decision is a FOLDER »), its state word, its date; a state filter as the
query (`?state=`, D1 — a filter is a dial, never the path), each filter showing its count. Production read one query
per state and so could fail one count alone (hence its « ? »); the maquette reads ONE list (`GET /api/decisions/`),
so the four counts are one derivation of it (§ 13) and a failed read is the journal's error phase — never four
counts reading « 0 » (NE-DOIT-PAS-1). A row leads where its state says: a pending one to `/resolution/$folder`; a
« Réglée » one to the chosen medium's sheet `/media/$provider/$id` (NE-DOIT-PAS-9 — an identified medium offers its
path), with the « Correspondance retenue » line; a « Laissée telle quelle » or « Remplacée depuis » one unfolds its
own sentence (`decisionStateDetail`) in place — no destination of its own, because a settled decision is not a
second place to act (production's own sentence: « cette décision est clôturée »). Entered from « Réglées récemment »
(« Tout voir »). **Its host — a screen of Acquisition, or Système's history — is OPEN 1.**

### 1.2 (b1) « Santé » — S2

Per § 0.1, served in substance. **What S2 draws**: each of Système's machine sections — « Services », « Disques »,
« Index de la médiathèque », « Dépendances » — whose OWN read failed draws one row saying so, in the same fact shape
(`Fact`: a label, the tone `alert`, the value « indisponible », a secondary line naming what could not be read),
while the other sections stay drawn. Today `const { data: DISKS = [] } = useDisks()` (`features/system/page.tsx:48`)
draws the heading over nothing when the read fails: an empty section is the « rien ne se passe » without reason § 8
forbids, and the whole-page `system-error` state covers only the case where everything failed. **Whether a disk
« bientôt plein » or index anomalies reach the menu's Système badge is OPEN 2.**

### 1.3 (b2) « Activité scraping » — S3

**What production offers** (`components/decisions/ScrapeActivityPanel.tsx`): « Scrapes en cours » — each folder
being identified now with its elapsed time and a pulse, and the count of pending decisions; nothing when idle.

**What the maquette already has.** The per-medium half: a card at « identifié » while its identification runs reads
« en cours depuis 4 min » on the journey sheet (`mocks/seeds/journey-stages.json`, rung `identified`, state `now`),
and the pending count is « À traiter »'s own tab count. **What S3 owes for certain is a PROOF**: the identification
in progress is read on the card's rung from the per-medium journey, never from a global list. `GET
/api/decisions/activity` stays uncalled under that reading. **Whether Système also draws a global « en ce moment »
figure is OPEN 3.**

### 1.4 (b3) The former addresses — S4

Measured: `grep -n "\"/control\|\"/pipeline" frontend/maquette/design/src/lib/addresses.ts` reads nothing;
`destinationOf` answers any path outside `PAGE_PATHS` and the screen table with the not-found page (`addresses.ts:357`).
Production routes eight pages and seven redirects (`frontend/src/router.tsx`); its own rule is written at `router.tsx`
« A rename that 404s the address it renamed is a break wearing a rename's clothes » — the addresses live in the
operator's bookmarks and in the PWA's cache. On the day of the switchover every one of them reaches the maquette.

**What S4 draws: a table of former addresses, each answering its successor.** The navigation REPLACES (a redirect is
not an arrival, § 16 rule 1), and the successor's parent is synthesised as for any cold link (§ 16 rule 3).

| Former address | Successor | Why |
| --- | --- | --- |
| `/control` | the account's entry page (§ 16 rule 2, 2026-09-27) | Contrôle was the home; the home is now the entry page. « À traiter » opens there by default when not empty (organisation ruling 10), which is what Contrôle's first panel was |
| `/pipeline` | `/system` | the levers and the history live in Système's « Pipeline » section (operator, 2026-09-12, Q1 = B) |
| `/pipeline?run=<uid>`, `/maintenance?run=<uid>` | `/run/$runUid` | the passage's own screen (L20) |
| `/config` | `/settings` | the same page, renamed |
| `/media?decision=<id>` | S1, the journal's root | the maquette's decisions read carries no id (§ 2); the id is dropped, and the drop is said in the table's own comment |
| `/media?media=<id>`, `/system?tab=<name>` | the same path, the query dropped | the dials production had there are not the maquette's; an unknown dial is ignored, never an error (D1) |
| `/scraping`, `/registry` | `/media`, `/system` | production's own aliases, carried one hop further |
| `/medias`, `/systeme`, `/controle` | OPEN 4 | French literals, and route paths are not exempt from the language rule |

The table lives beside the address model, not in it: `lib/addresses.ts` holds **395** non-blank lines against the
400-line ceiling (`grep -cv '^\s*$' frontend/maquette/design/src/lib/addresses.ts`), so the table is its own module
under `lib/`, read by `destinationOf` before it falls to the not-found page.

### 1.5 (c) The seven owed halves, row by row

| Row | Owed half, as the map writes it | Re-read on `e65130ab1` | Surface or proof |
| --- | --- | --- | --- |
| **DOIT-1** (L19) | the pipeline's own states, per medium, in the tunnel | the journey sheet draws the eight rungs and, under « rangé », three steps « trié · enrichi · rangé » (L22 OPEN 4 = B, ruled 2026-09-26). DOIT-1's own words — « posters récupérés, trailer » — are folded into « enrichi » | **PROOF**: every rung and step word is read from the one ladder's vocabulary, on both the card and the sheet. Whether « enrichi » unfolds is **OPEN 5** |
| **DOIT-5** (L19) | the continuation's progress to the library; `GET /api/pipeline/stages` and the journeys list are uncalled | after « Choisir », the message says « le pipeline reprend jusqu'à la médiathèque » (`verbs.acquisition.resolved`); no rule reads the CARD advancing afterwards | **PROOF**: after a choice, the card leaves « À traiter » and its rung passes « identifié », read on the card within the visit, never on the message. The journeys-as-a-whole half is served differently — the cards are the journeys — and `stages`' global form has no subject under § 20 point 3 |
| **DOIT-7** (L19) | the step that CREATES a decision with its candidates (`POST /api/staging/media/{id}/enqueue`) is uncalled | `grep -rn "enqueue" frontend/maquette/design/src/features` → nothing; the contract declares no such operation | **SURFACE — S5**: a third act on the journey sheet, beside « Remettre en file » and « Re-scraper » (`features/acquisition/panel-journey.ts:114–122`) — proposed « Choisir un autre média » — for a medium identified AUTOMATICALLY and not yet « rangé » (a match the operator doubts; « Envoi manuel » in production's trigger words): it creates the decision, then opens `/resolution/$folder` with candidates, or the pre-filled manual search when none — § 3's invariant |
| **DOIT-9** (L19) | § 12's card composition (title alone on line 1) is read by a print in an unnumbered script | `harness/follows.py:28` still PRINTS « title alone » over four follow cards | **PROOF**: a numbered rule over every card of every gallery and list |
| **DOIT-11** (L19) | the sheet's CONTENT is unproved; « complétude par saison » — `GET /api/acquisition/followed/{id}/completeness` is uncalled | the hero draws year and trailer with their failure words (`media-hero.tsx:69–74, 149`); R119 (`harness/priming.py`) reads the sheet's parts while its read is in flight, R63 (`content.py`) the library rows' synopsis — no rule reads DOIT-11's fields on the sheet at rest | **PROOF** for the content; the completeness half is NE-DOIT-PAS-1's source change, below |
| **NE-DOIT-PAS-1** (L19) | the executable completeness the backend answers is uncalled | `grep -rn "completeness\"" frontend/maquette/design/src/mocks` → nothing; the sheet computes its own | **SOURCE CHANGE + PROOF**: for a followed medium, the season figures read the completeness operation, and the sheet and the follow sheet agree (§ 13 « une seule dérivation par question ») |
| **NE-DOIT-PAS-6** (L15) | the dialog's back rung (B-229) and z-order (B-237) | both read `fixed #528` in `BUGS.md`'s index; `harness/selection.py:131–134` now ASSERTS the bulk dialog names the ticked media | **PROOF**: the half L15 owed is discharged; what no rule reads is the clause over EVERY destructive verb — six features raise the dialog (`git grep -ln "dialog?\.open" -- frontend/maquette/design/src/features`), one rule reads the library alone |

### 1.6 (d) DOIT-9's desktop half

The desktop navigation question is ruled: **the drawer alone, at every width, not frozen** (2026-08-30, Q1; B-235
« ANSWERED »). The map's DOIT-9 row still reads « Open: the desktop half is B-235 / Q1 » — stale by a month, the
operator's to amend. What no instrument reads is « pleinement fonctionnel »: `harness/states.py:18` opens every
named state at 390 × 844, mobile, touch; no rule walks the states at a desktop width. **What (d) owes for certain
is a PROOF**: every named state at 1280 × 800, pointer and no touch, renders content with no horizontal overflow and
no JS error, and every page is reached through the drawer. **Whether « se laisse respirer sur grand écran » (§ 12)
also asks for layouts drawn for the desktop is OPEN 6.**

---

## 2. The contract (D7) — and it comes FIRST

**Measured today**:
`python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
→ **68** operations; the decision paths declared are `/api/decisions/` and its `resolve`, `dismiss`, `search`;
`DecisionState` is `resolved | dismissed | superseded`; `PendingDecision` and `SettledDecision` carry no id.

| Demand | Operation | Owed as | For |
| --- | --- | --- | --- |
| **A** | `POST /api/staging/media/{mediaId}/enqueue` — `enqueueForResolution` (new) | declared; the engine has it (`frontend/src/api/schema.d.ts`, `/api/staging/media/{media_id}/enqueue`) | S5 |
| **B** | `GET /api/acquisition/followed/{followedId}/completeness` — `readFollowCompleteness` (new) | declared; the engine answers `CompletenessResponse` (seasons, `source: cache | unknown`, `provider_catalog_empty`) | NE-DOIT-PAS-1, DOIT-11 |
| **C** | `GET /api/decisions/activity` — `readScrapingActivity` (new) | declared ONLY under OPEN 3 reading B; the engine answers `in_progress[]` and `pending_count` | S3 |
| **D** | `GET /api/decisions/` — a settled row reading `dismissed` | no shape change: the enum has it, the seed has none (`settled-decisions.json`: `resolved`, `superseded` only) | S1 |

**Nothing is proposed for S2 and S4**: a section's failed read is a mock scenario over reads already declared, and
former addresses are the interface's alone. **One PROPOSED demand, never asserted** (§ 6): the decisions read
carrying the decision's id on every row, so a former `?decision=<id>` could land on its own row rather than the
journal's root.

---

## 3. Named states

Every id is PROPOSED; none exists. Those conditional on a reading name it.

| # | id | What is on the screen | Conditional on |
| --- | --- | --- | --- |
| 1 | `decisions-all` | the journal, every state, the four counts | host: OPEN 1 |
| 2 | `decisions-filtered` | one state filter on, its rows only | — |
| 3 | `decisions-empty` | no decision at all, said in a sentence | — |
| 4 | `decisions-loading` · `decisions-error` | the two non-ready phases | — |
| 5 | `decision-dismissed-open` | a « Laissée telle quelle » row unfolded, its sentence | — |
| 6 | `system-disks-unavailable` | « Disques » says its read failed; the other sections drawn | — |
| 7 | `system-index-unavailable` · `system-dependencies-unavailable` | the same, per section | — |
| 8 | `system-disk-filling` | a disk « bientôt plein » counted in the menu's badge | OPEN 2, reading A |
| 9 | `system-scraping-now` · `system-scraping-idle` | Système's « en ce moment » figure, and its idle form | OPEN 3, reading B |
| 10 | `former-control` · `former-pipeline` · `former-pipeline-run` · `former-config` · `former-decision` | each former address, landed on its successor with its parent under it | — |
| 11 | `former-french-alias` | `/controle` landed on the entry page | OPEN 4, reading B |
| 12 | `acq-resolution-enqueued` · `acq-resolution-enqueue-failed` | S5: the screen opened on a freshly created decision; the creation refused, its reason | — |
| 13 | `sheet-journey-enriched-unfolded` | « enrichi » unfolded into DOIT-1's words | OPEN 5, reading B |

The desktop proof (§ 1.6) adds no state: it walks the existing ones at another width.

---

## 4. The rules that bite

Labels, never numbers: they bind to the range the steward reserves in the lot's launch brief.

| Rule | What it READS | The mutation that fells it |
| --- | --- | --- |
| **R-L24-a** — the journal is every decision, counted from the read (NE-DOIT-PAS-1) | each filter's count equals the rows the one read carries for that state; under the error phase no count is drawn | draw the counts as `0` when the read fails → falls |
| **R-L24-b** — a row leads where its state says (NE-DOIT-PAS-9, DOIT-2) | pending → `/resolution/$folder`; « Réglée » → `/media/$provider/$id`; the two others unfold their sentence | point a « Réglée » row at the resolution screen → falls |
| **R-L24-c** — a Système section says its own read failed (NE-DOIT-PAS-5) | the failed section draws one `alert` row; every other section still draws its rows | default the failed read to `[]` → falls |
| **R-L24-d** — a former address answers its successor (DOIT-10, § 16) | by a finger walk and a cold load: the successor drawn, the history REPLACED, Back per § 16 | push instead of replace → the Back hold falls |
| **R-L24-e** — a resolution arrives with candidates (§ 3, DOIT-7) | on a medium with no pending decision, the journey sheet's act calls `enqueueForResolution` BEFORE the screen opens, and the screen shows candidates or the pre-filled search | open the screen without the call → the network hold falls |
| **R-L24-f** — the continuation is seen (DOIT-5) | after « Choisir », the card leaves « À traiter » and its rung passes « identifié », read on the card | answer the choice without moving the seed → falls |
| **R-L24-g** — the title alone on line 1, every card (§ 12, DOIT-9) | every card of every gallery and list: `card/title` above `card/meta`, nothing beside the title | put the state word on the title's line → falls |
| **R-L24-h** — the sheet says what the medium is (DOIT-11) | title, year, synopsis, director, trailer — or each one's failure words; for a series its seasons, episodes, status | drop the director row → falls |
| **R-L24-i** — one completeness (NE-DOIT-PAS-1, § 13) | the sheet's and the follow sheet's season figures come from `readFollowCompleteness` and agree | compute one locally → falls |
| **R-L24-j** — no destruction without consent (NE-DOIT-PAS-6) | every destructive verb raises the dialog before any write; cancelling writes nothing, read on the network | fire the write before the dialog → falls |
| **R-L24-k** — the desktop is fully functional (DOIT-9) | every named state at 1280 × 800, pointer: content, no overflow, no JS error; every page reached through the drawer | clip a gallery's container at desktop width → falls |

A reading of OPEN 2, 3, 5 or 6 that draws adds one rule each, labelled at the plan's phase.

---

## 5. What L24 does NOT draw, and the open questions

**Owned elsewhere, one line each**: a grab deferred for SPACE (a disk full) — **L16** (DOIT-2's row); who may see the
journal, Système and « À traiter » — **L18** (§ 17); the Trackers « Retirer de qBittorrent » dialog — **L16** (R-L24-j
reads it once it exists, draws nothing of it); the media sheet's cross-seed block — **L18**; the global event feed
and the configuration validation — **not redrawn**, D12. **Not drawn at all**: a desktop navigation rail (Q1, ruled);
a Pipeline tab or badge (Q6, ruled); production's eight-stage `FlowBoard` (§ 20: « une page Pipeline qui montrerait
le run global n'a plus de sujet »); anything the engine does (§ 15).

**The open questions — each with its two readings, and NO choice.**

**OPEN 1 — where the decisions journal lives.** *Reading A*: a screen of Acquisition (`/decisions`, parent `acq`),
entered from « Réglées récemment » — a decision is a folder an arrival card carried, and the candidates screen is
Acquisition's (L22). *Reading B*: a section of Système's history — organisation ruling 12 (2026-09-26) makes
« l'historique de Système seule trace » of the past, and a settled decision is past. **Cost**: A is one new screen
address and no Système change; B puts a medium's past on the machine's page, which R67 (`machine.py`: « no blocked
medium on Système ») reads against, and needs its re-aim. **The finding meets ruling 12, so it is not decided here.**

**OPEN 2 — does a filling disk speak on the menu's badge?** *Reading A*: yes — a disk « bientôt plein » and index
anomalies count in `systemBadge()`, beside services, dependencies and locks (§ 17 point 4: « le bouton du menu porte
son badge quand il a quelque chose à dire »). *Reading B*: no — the badge counts faults only; a disk filling is a
state read on visiting. **Cost**: A is one badge term, one named state, one rule; B is nothing.

**OPEN 3 — a global « en ce moment » for identification.** *Reading A*: none — § 20 point 3 (« il n'y a plus un
pipeline à regarder ») and D12's reasoning (a list with no axis) leave the activity on each card; `decisions/activity`
is recorded served differently. *Reading B*: one fact row in Système's « Pipeline » section — « N identifications en
cours, M en attente » — each leading to its card, reading demand C. **Cost**: A is a proof; B is a declared
operation, a mock, two states, one rule. **The finding meets D12 and § 20 point 3, so it is not decided here.**

**OPEN 4 — the three French former addresses.** *Reading A*: `/medias`, `/systeme`, `/controle` die at the switchover
and answer the not-found page — already aliases of aliases in production. *Reading B*: they are carried, each literal
wearing a `french-ok` pragma, which `CLAUDE.md` § Language does not list among the allowed literals (« Route paths are
NOT exempt either »). **Cost**: A costs nothing; B needs the operator to extend the language rule's list. **The
finding meets the language rule, the operator's, so it is not decided here.**

**OPEN 5 — does « enrichi » unfold?** *Reading A*: the fold stands (L22 OPEN 4 = B, 2026-09-26: « le journey sheet
keeps the three steps in detail »); DOIT-1 is served by the three steps, and the owed half is a proof. *Reading B*:
on the journey sheet « enrichi » unfolds into DOIT-1's own words — « posters récupérés », « bande-annonce » — each
with its state. **Cost**: A is a proof; B is one seed shape, one state, one rule. **The finding meets the ladder's
ruling, so it is not decided here.**

**OPEN 6 — what « se laisse respirer sur grand écran » asks.** *Reading A*: the proof alone (§ 1.6) — the drawing is
the phone's, and container queries let the galleries widen (invariant 12). *Reading B*: the list-and-detail
surfaces — the journal (S1), « À traiter », the settings — draw a two-pane layout above a container width, as
production's « Décisions » did side by side. **Cost**: A is one rule; B is a layout per surface, one state per
surface, a phase each. **Q1 (the drawer alone) is not re-opened by either reading.**

---

## 6. The register rows and the demands touched

**`BUGS.md`**, read, not edited: **B-235** (`open` in the index, « ANSWERED » in its body — the index is the
steward's to mend); **B-229**, **B-237** (`fixed #528`, cited by NE-DOIT-PAS-6's row as owed).

**`docs/reference/product-intent-map.md`**, read, amended by the operator: the DOIT-1, 5, 7, 9, 11, NE-DOIT-PAS-1 and
NE-DOIT-PAS-6 rows name L24 as their owner once this lot enters the plan, and DOIT-9's « Open: B-235 / Q1 » is stale
(§ 1.6) — both proposed to the operator by this PR's body, never written.

**`docs/reference/backend-demands-architecture.md`**, not edited. **PROPOSED demand, never asserted**: « the
decisions read carries each decision's id » — the engine's own list has it (production reads `?decision=<id>` and
calls `/api/decisions/{decision_id}`, `frontend/src/api/decisions.ts`); the maquette's `PendingDecision` and
`SettledDecision` dropped it (the settled `choice` already carries provider, id and via); filed by the steward, if
at all, after OPEN 1 is ruled.
