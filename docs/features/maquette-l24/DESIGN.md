# L24 — the orphans: what no lot draws · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L24 — the orphans, what no lot draws` (its
« Where it lives » and « Done when » lines). It is not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. **Nothing under
`frontend/maquette/` was touched to write it** — no code, no rule, no mock, no seed, no harness run: prose and
numbers.

**Written 2026-09-29, on `main` at `e65130ab1`; amended the same day, on `77e7b8436`, on the operator's six rulings
of 2026-09-29; amended a second time, same day, on the operator's second round** (§ 5,
`docs/features/maquette-l24/rulings-2026-09-29.md`) **— all nine OPEN questions are now RULED.** The version before the
rulings is `docs/features/maquette-l24/DESIGN.md@e6d63bffe`. The plan's order is `L14 · L19 · L21 · L13 · L20 · L22 ·
L16 · L17 · L18 · L23`; L24 opens after L23, and the desktop milestone (§ 1.6) follows L24. Unlike L16–L23, nothing
here was decided by the constitution for this document to transcribe: the subjects below are what the mission of
2026-08-19 says must be redrawn and no lot names. Where a reading splits and no ruling answers it, it is an OPEN
question in § 5, never a choice made here (auditor's order 72) — the six the operator ruled first, and the three the
rulings themselves raised (OPEN 7–9), ruled in the second round.

---

## 0. What L24 owes, said once

| # | Subject | Its source | Surface or proof | Held for |
| --- | --- | --- | --- | --- |
| a | Production's « Décisions » tab (`/media`, third tab) — every decision, its state, its outcome | mission 2026-08-19; § 15 « la maquette doit TOUTES les pages que la production sert » | **S1** — a settled decision lives on its medium's card: a block of the journey sheet and of the Médiathèque sheet (surface; OPEN 1 = C) | § 1.1 |
| b1 | Contrôle's « Santé » (disks, index, Redis, providers) | `IMPLEMENTATION.md`, the « Next » row | **S2** — Système's sections that say their own read failed, and a filling disk on the menu's badge (surface; OPEN 2 = A) | § 1.2 |
| b2 | Contrôle's « Activité scraping » (what is being identified now, how many wait) | same | **S3** — per medium, a PROOF (OPEN 3 = A) | § 1.3 |
| b3 | The addresses `/control`, `/pipeline` and the other former production paths | § 15; § 16 rule 3; D1 | **S4 DIES** — a former address answers not-found, no successor, no alias (PROOF only; OPEN 4 = A, OPEN 9 = A + the no-backward-compatibility PRINCIPLE) | § 1.4 |
| c | The seven owed halves of `partly` rows whose owner has merged (DOIT-1, 5, 7, 9, 11, NE-DOIT-PAS-1 — L19; NE-DOIT-PAS-6 — L15) | `docs/reference/product-intent-map.md` | one surface (**S5**, DOIT-7, « Corriger »), one unfold (DOIT-1, OPEN 5 = B) and five proofs | § 1.5 |
| d | DOIT-9's desktop half — « le desktop reste pleinement fonctionnel » | DOIT-9; § 12 | a PROOF over every named state (OPEN 6 = A); the desktop layouts are a milestone after the drawn lots | § 1.6 |

### 0.1 A measurement that corrects the premise

`IMPLEMENTATION.md`'s « Next » row once said « Santé » had « no maquette equivalent anywhere, verified by grep on
2026-09-28 ». The grep it cited searched French and English words (`Santé`, `disk usage`, `index health`) that the
maquette's code never spells — its names are `useDisks`, `useIndexHealth`, and its copy lives in `fr.json`.
Measured:

    grep -n "useDisks\|useIndexHealth\|useDependencies\|useServices" frontend/maquette/design/src/features/system/page.tsx

reads four reads imported (lines 26–30) and drawn (lines 44–50) by Système's page, under the headings `fr.json` names
« Services », « Disques », « Index de la médiathèque », « Dépendances » — and the seeds carry exactly production's
four domains: disks with their free space (`mocks/seeds/disks.json`, « Disk2 — bientôt plein »), the index
(`index-health.json`, « 1 863 titres », « Anomalies relevées »), Redis and the providers' circuit
(`dependencies.json`, « Redis — connecté », « TMDB / TVDB — aucun disjoncteur ouvert »). R67
(`harness/machine.py:112–113`) already reads the disks and index rows. **« Santé » is drawn in substance, on
Système**, where the cut of 2026-08-19 puts it (« a machine in trouble is Système »). What is NOT drawn is what
production's compact card did that Système's page does not: each domain saying ITS OWN read failed (« Disques — état
indisponible », « API injoignable »). § 1.2 draws that.

### 0.2 What L24 builds on, and does not redraw

| Lot (landed) | L24 reads it as |
| --- | --- |
| L20 — Système's « Pipeline » section, the levers, the history, `/run/$runUid` | the HOME of `/pipeline`'s successor (S4) |
| L22 — Acquisition's four tabs, « À traiter », the one ladder, the candidates screen `/resolution/$folder`, « Réglées récemment » | the HOME of the decisions a medium is waiting on — pending decisions stay « À traiter » cards |
| L19/L21 — the journey sheet, its verbs, the producers; the Médiathèque sheet | the two sheets S1's block is drawn on, and the surface DOIT-1 and DOIT-5 read |
| L15 — the frame, the drawer, the dialog layer | the surface NE-DOIT-PAS-6's and the desktop proofs read |

---

## 1. What each subject dictates, and the surface that serves it

### 1.1 (a) A settled decision on its medium's card — S1

**Ruled (OPEN 1 = C, 2026-09-29).** The operator: « Les décisions ne peuvent t'elle pas vivre sur la carte d'un
média d'acquisions ? », then « C ». No global list, no « Décisions » screen, nothing on Système. Organisation ruling
12 (« l'historique de Système seule trace ») is NOT amended by this — a decision is read on its medium, not as a
history.

**What production offers** (`frontend/src/pages/MediaLibrary.tsx:56–68, 330–460`, `components/decisions/`): a flat
list of every scrape decision, four states — « En attente », « Réglée », « Laissée telle quelle », « Remplacée
depuis » — each detail addressed by `?decision=<id>`; a settled detail says its outcome and, for « Réglée », the
« Correspondance retenue » (provider, id, « recherche manuelle » or « sélection »). Every one of those facts is
kept; only the list dies.

**What the maquette already has.** The pending half is served: « À traiter » lists what waits on the hand, and
`/resolution/$folder` is the arbitration (L22). The settled half is six rows under « Réglées récemment » at the foot
of the candidates screen (`features/acquisition/resolution-screen.tsx:177–186`, `.slice(0, 6)`) — kept as it is. The
vocabulary exists (`screens.resolution.decisionState`, one word per settled state).

**What S1 draws — one block, on two sheets.** The block says, for the medium's latest settled decision: **what was
chosen** (the title and the provider, the « Correspondance retenue »), **among how many candidates**, **by whom** —
the operator (« sélection », « recherche manuelle ») or the engine (an identification it made alone) — **when**, and
the act **« Corriger »** (§ 1.5, DOIT-7). A « Laissée telle quelle » or « Remplacée depuis » decision reads its own
sentence (`decisionStateDetail`) in the block's place of the choice. It is drawn:

- on the **journey sheet** (`features/acquisition/panel-journey.ts`) from the rung « identifié » onward, while the
  medium is in Acquisition;
- once the medium leaves Acquisition, **the same block** on its **Médiathèque sheet** (`features/media/`) — one
  component, one derivation, the same words (§ 13 « une seule dérivation par question »).

While the decision is PENDING the block is not drawn: the medium is an « À traiter » card and its card opens the
arbitration (L22), unchanged. The block lives in one module of `features/acquisition/` that `features/media/`
imports (its fan-in is read at the phase's opening against `check-frontend-boundaries.py`'s ceiling of four).

**What it reads** — § 2 demand D: the settled decisions read carries each decision's id (the ruling keeps it, for
« Corriger »), its candidates' count, and who settled it; an identification the engine made alone is a settled
decision on that read, with `engine` as its author. Today's `SettledDecision` carries none of the three.

### 1.2 (b1) « Santé » — S2

Per § 0.1, served in substance. **What S2 draws**: each of Système's machine sections — « Services », « Disques »,
« Index de la médiathèque », « Dépendances » — whose OWN read failed draws one row saying so, in the same fact shape
(`Fact`: a label, the tone `alert`, the value « indisponible », a secondary line naming what could not be read),
while the other sections stay drawn. Today `const { data: DISKS = [] } = useDisks()` (`features/system/page.tsx:48`)
draws the heading over nothing when the read fails: an empty section is the « rien ne se passe » without reason § 8
forbids, and the whole-page `system-error` state covers only the case where everything failed.

**Ruled (OPEN 2 = A, 2026-09-29, verbatim « A »).** A disk « bientôt plein » and a library-index anomaly COUNT in the
menu button's badge (Système), beside the maintenance facts and faults (round 5 Q8): two terms in `systemBadge()`,
each read on the fact's own `tone`, never on its words — one state, `system-disk-filling`, and one rule.

### 1.3 (b2) « Activité scraping » — S3, a proof

**Ruled (OPEN 3 = A, 2026-09-29, verbatim « A »).** No global « en ce moment »: identification activity reads on
each card (§ 20 point 3), and L24 carries its PROOF only. Demand C (`GET /api/decisions/activity`) is not declared —
recorded as served differently, by the cards; the states `system-scraping-now` and `system-scraping-idle` are
dropped.

**What production offers** (`components/decisions/ScrapeActivityPanel.tsx`): « Scrapes en cours » — each folder
being identified now with its elapsed time, and the count of pending decisions. **What the maquette has**: a card at
« identifié » while its identification runs reads « en cours depuis 4 min » on the journey sheet
(`mocks/seeds/journey-stages.json`, rung `identified`, state `now`), and the pending count is « À traiter »'s own tab
count. **What S3 owes is the PROOF**: the identification in progress is read on the card's rung from the per-medium
journey, never from a global list.

### 1.4 (b3) The former addresses — S4

Measured: `grep -n "\"/control\|\"/pipeline" frontend/maquette/design/src/lib/addresses.ts` reads nothing;
`destinationOf` answers any path outside `PAGE_PATHS` and the screen table with the not-found page
(`addresses.ts:357`). Production routes eight pages and seven redirects (`frontend/src/router.tsx`); its own rule is
written there: « A rename that 404s the address it renamed is a break wearing a rename's clothes » — the addresses
live in the operator's bookmarks and in the PWA's cache.

**S4 DIES as drawn.** It proposed a table of former addresses each answering a named successor (a soft redirect).
**RULED (operator, 2026-09-29, OPEN 9 = A + PRINCIPLE, verbatim « A, pas de gestion de rétro-compatibilité ! »)**:
the new version handles **NO backward compatibility of former addresses or links — no alias, no redirect**
(precedents `/arrivals`, the French addresses of OPEN 4 = A). Every dead production path answers the not-found page,
with no successor named anywhere in code or in this design.

| Former address | Lands on | Why |
| --- | --- | --- |
| `/control`, `/pipeline`, `/pipeline?run=<uid>`, `/maintenance?run=<uid>`, `/config`, `/scraping`, `/registry`, `/medias`, `/systeme`, `/controle` | **none — the not-found page** | the operator's principle (2026-09-29): a former address answers not-found, never a named successor. `destinationOf` ALREADY does this today for every path outside `PAGE_PATHS` (`lib/addresses.ts:357`, measured) — nothing is added |
| `/media?media=<id>`, `/system?tab=<name>`, `/media?decision=<id>` | the same LIVE path, the query dropped | these are not former addresses — `/media` and `/system` exist today; the dials production had there are not the maquette's, an unknown dial is ignored, never an error (D1). OPEN 9 = A places `/media?decision=<id>` here: the id is ignored, the journal it once opened no longer exists (OPEN 1 = C) |

No table, no module under `lib/`: the not-found fallback `destinationOf` already gives every dead path is the whole
of S4 now. `lib/addresses.ts` stays at **395** non-blank lines against the 400-line ceiling
(`grep -cv '^\s*$' frontend/maquette/design/src/lib/addresses.ts`) — nothing is added to it.

### 1.5 (c) The seven owed halves, row by row

| Row | Owed half, as the map writes it | Re-read on `77e7b8436` | Surface or proof |
| --- | --- | --- | --- |
| **DOIT-1** (L19) | the pipeline's own states, per medium, in the tunnel | the journey sheet draws the eight rungs and, under « rangé », three steps « trié · enrichi · rangé » (L22 OPEN 4 = B, 2026-09-26) | **Ruled OPEN 5 = B** (2026-09-29, verbatim « B »): on the journey sheet « enrichi » unfolds into **métadonnées**, **posters récupérés**, **bande-annonce**, each with its state; the card ladder keeps its eight rungs (round 5 Q4 unchanged) — one seed shape, one state `sheet-journey-enriched-unfolded`, one rule, which also reads every rung and step word from the one ladder's vocabulary |
| **DOIT-5** (L19) | the continuation's progress to the library | after « Choisir », the message says « le pipeline reprend jusqu'à la médiathèque » (`verbs.acquisition.resolved`); no rule reads the CARD advancing afterwards | **PROOF**: after a choice, the card leaves « À traiter » and its rung passes « identifié », read on the card within the visit — walked from « À traiter » and from « Corriger » |
| **DOIT-7** (L19) | the step that CREATES a decision with its candidates (`POST /api/staging/media/{id}/enqueue`) is uncalled | `grep -rn "enqueue" frontend/maquette/design/src/features` → nothing; the contract declares no such operation | **SURFACE — S5, « Corriger »**, the act of S1's block (the ruling's own word): **RULED OPEN 7 = A** — ONE act for both authors: on a medium the engine identified alone, it creates the decision (`enqueueForResolution`) and opens `/resolution/$folder` with candidates, or the pre-filled manual search when none (§ 3's invariant); on an operator-settled decision, the SAME act re-opens that choice by its id (demand D); no third act on the journey sheet, R126 unchanged. **RULED OPEN 8 = A** — « Corriger » is drawn on the Médiathèque sheet of a shelved medium too, re-opening its decision by id; the re-identification of a shelved medium is recorded as a demand on the engine (mission point 4) |
| **DOIT-9** (L19) | § 12's card composition (title alone on line 1) is read by a print in an unnumbered script | `harness/follows.py:28` still PRINTS « title alone » over four follow cards | **PROOF**: a rule over every card of every gallery and list |
| **DOIT-11** (L19) | the sheet's CONTENT is unproved; « complétude par saison » — `GET /api/acquisition/followed/{id}/completeness` is uncalled | the hero draws year and trailer with their failure words (`media-hero.tsx:69–74, 149`); R119 (`harness/priming.py`) reads the sheet's parts in flight, R63 (`content.py`) the library rows' synopsis — no rule reads DOIT-11's fields on the sheet at rest | **PROOF** for the content; the completeness half is NE-DOIT-PAS-1's source change, below |
| **NE-DOIT-PAS-1** (L19) | the executable completeness the backend answers is uncalled | `grep -rn "completeness\"" frontend/maquette/design/src/mocks` → nothing; the sheet computes its own | **SOURCE CHANGE + PROOF**: for a followed medium, the season figures read the completeness operation, and the sheet and the follow sheet agree (§ 13) |
| **NE-DOIT-PAS-6** (L15) | the dialog's back rung (B-229) and z-order (B-237) | both read `fixed #528` in `BUGS.md`'s index; `harness/selection.py:131–134` ASSERTS the bulk dialog names the ticked media | **PROOF**: what no rule reads is the clause over EVERY destructive verb — six features raise the dialog (`git grep -ln "dialog?\.open" -- frontend/maquette/design/src/features`), one rule reads the library alone |

### 1.6 (d) DOIT-9's desktop half

The desktop navigation question is ruled: **the drawer alone, at every width, not frozen** (2026-08-30, Q1; B-235
« ANSWERED »). The map's DOIT-9 row still reads « Open: the desktop half is B-235 / Q1 » — stale, the operator's to
amend. `harness/states.py:18` opens every named state at 390 × 844, mobile, touch; no rule walks the states at a
desktop width.

**Ruled (OPEN 6 = A, with a milestone, 2026-09-29).** The operator, verbatim: « A dans un premier temps, mais prévoir
une phase final d'adaptation des écrans pour une utilisation plus agréable sur desktop. On en décidera des contours
en temps et en heure quand la maquette sera prête ». **L24 owes the PROOF only**: every named state at 1280 × 800,
pointer and no touch, renders content with no horizontal overflow and no JS error, the galleries widen (container
queries, invariant 12), and every page is reached through the drawer. No desktop layout is drawn here. **The
desktop adaptation of the screens is a milestone after the drawn lots**, written into
`docs/reference/frontend-architecture.md`'s lot order and `IMPLEMENTATION.md`'s freeze projection: no points, no
phases, its contour the operator's to decide when the maquette is ready.

---

## 2. The contract (D7) — and it comes FIRST

**Measured on `77e7b8436`**:
`python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
→ **68** operations; the decision paths declared are `/api/decisions/` and its `resolve`, `dismiss`, `search`;
`DecisionState` is `resolved | dismissed | superseded`; `PendingDecision` and `SettledDecision` carry no id, and
`SettledDecision` no candidates' count and no author.

| Demand | Operation | Owed as | For |
| --- | --- | --- | --- |
| **A** | `POST /api/staging/media/{mediaId}/enqueue` — `enqueueForResolution` (new) | declared; the engine has it (`frontend/src/api/schema.d.ts`, `/api/staging/media/{media_id}/enqueue`) | S5 |
| **B** | `GET /api/acquisition/followed/{followedId}/completeness` — `readFollowCompleteness` (new) | declared; the engine answers `CompletenessResponse` (seasons, `source: cache | unknown`, `provider_catalog_empty`) | NE-DOIT-PAS-1, DOIT-11 |
| **C** | `GET /api/decisions/activity` | **not declared — OPEN 3 = A**: served differently, by each card's rung | — |
| **D** | `GET /api/decisions/` — `SettledDecision` gains `id`, `candidatesCount`, `settledBy: operator | engine`; a settled row reading `dismissed` joins the seed | a shape EDIT, recorded as a demand on the backend (D7): the engine's list has `id` and `candidates_count` (`DecisionListItem`); an identification the engine made alone is not a decision row today — that is the divergence | S1, and the id for « Corriger » (ruled: the demand stays) |

**Nothing is declared for S2 and S4**: a section's failed read is a mock scenario over reads already declared, and
former addresses are the interface's alone.

---

## 3. Named states

Every id is PROPOSED; none exists. **Twenty-one were proposed at `@e6d63bffe`; fourteen are removed by the
rulings** (the original nine, plus the five S4 former-address states `former-control`, `former-pipeline`,
`former-pipeline-run`, `former-config`, `former-decision` — OPEN 9's no-backward-compatibility PRINCIPLE kills the
whole family, the not-found state answering in their place) **and four are new, for twelve** — `media-sheet-decision-corrected`
now RULED IN unconditionally (OPEN 8 = A), no longer conditional.

| # | id | What is on the screen | Ruling |
| --- | --- | --- | --- |
| 1 | `sheet-journey-decision-operator` | the journey sheet's block: a choice the operator made, among N candidates, when, « Corriger » | OPEN 1 = C (new) |
| 2 | `sheet-journey-decision-engine` | the same block, the engine's own identification | OPEN 1 = C (new) |
| 3 | `sheet-journey-decision-dismissed` | the block of a « Laissée telle quelle » decision, its sentence | OPEN 1 = C (new) |
| 4 | `media-sheet-decision` | the same block on the Médiathèque sheet | OPEN 1 = C (new) |
| 5 | `system-disks-unavailable` | « Disques » says its read failed; the other sections drawn | — |
| 6 | `system-index-unavailable` · `system-dependencies-unavailable` | the same, per section | — |
| 7 | `system-disk-filling` | a disk « bientôt plein » counted in the menu's badge | OPEN 2 = A (kept) |
| 8 | `acq-resolution-enqueued` · `acq-resolution-enqueue-failed` | S5: the screen opened on a freshly created decision; the creation refused, its reason | — |
| 9 | `sheet-journey-enriched-unfolded` | « enrichi » unfolded into métadonnées, posters, bande-annonce | OPEN 5 = B (kept) |
| 10 | `media-sheet-decision-corrected` | « Corriger » on the Médiathèque sheet, the arbitration opened on a shelved medium | OPEN 8 = A (kept, unconditional) |

**Removed, each with its ruling**:

| id | Removed by |
| --- | --- |
| `decisions-all` · `decisions-filtered` · `decisions-empty` · `decisions-loading` · `decisions-error` · `decision-dismissed-open` | OPEN 1 = C — no global list, no « Décisions » screen; replaced by states 1–4 |
| `system-scraping-now` · `system-scraping-idle` | OPEN 3 = A — no global « en ce moment » |
| `former-french-alias` | OPEN 4 = A — the French addresses answer the not-found page, whose state `not-found` already exists |
| `former-control` · `former-pipeline` · `former-pipeline-run` · `former-config` · `former-decision` | OPEN 9 = A + the no-backward-compatibility PRINCIPLE — S4's whole redirect-table premise dies; every former address answers `not-found`, the same state `former-french-alias` already used |

The desktop proof (§ 1.6) adds no state: it walks the existing ones at another width.

---

## 4. The rules that bite

Labels, never numbers: they bind to the range the steward reserves in the lot's launch brief.

| Rule | What it READS | The mutation that fells it |
| --- | --- | --- |
| **R-L24-a** — a settled decision is read on its medium (OPEN 1 = C, NE-DOIT-PAS-1) | on the journey sheet: the choice, the candidates' count, the author, the date and « Corriger », each from the one settled read; nothing drawn while the decision is pending | draw the count as a fixed figure → falls |
| **R-L24-b** — one block, two sheets (§ 13) | the Médiathèque sheet's block says the same words as the journey sheet's for the same decision | retype the author word in the Médiathèque sheet → falls |
| **R-L24-c** — a Système section says its own read failed (NE-DOIT-PAS-5) | the failed section draws one `alert` row; every other section still draws its rows | default the failed read to `[]` → falls |
| **R-L24-d** — a former address answers its successor (DOIT-10, § 16) | by a finger walk and a cold load: the successor drawn, the history REPLACED, Back per § 16; `/controle` answers the not-found page | push instead of replace → the Back hold falls |
| **R-L24-e** — « Corriger » arrives with candidates (§ 3, DOIT-7) | on a medium the engine identified alone, the act calls `enqueueForResolution` BEFORE the screen opens, and the screen shows candidates or the pre-filled search | open the screen without the call → the network hold falls |
| **R-L24-f** — the continuation is seen (DOIT-5) | after « Choisir », the card leaves « À traiter » and its rung passes « identifié », read on the card | answer the choice without moving the seed → falls |
| **R-L24-g** — the title alone on line 1, every card (§ 12, DOIT-9) | every card of every gallery and list: `card/title` above `card/meta`, nothing beside the title | put the state word on the title's line → falls |
| **R-L24-h** — the sheet says what the medium is (DOIT-11) | title, year, synopsis, director, trailer — or each one's failure words; for a series its seasons, episodes, status | drop the director row → falls |
| **R-L24-i** — one completeness (NE-DOIT-PAS-1, § 13) | the sheet's and the follow sheet's season figures come from `readFollowCompleteness` and agree | compute one locally → falls |
| **R-L24-j** — no destruction without consent (NE-DOIT-PAS-6) | every destructive verb raises the dialog before any write; cancelling writes nothing, read on the network | fire the write before the dialog → falls |
| **R-L24-k** — the desktop is fully functional (DOIT-9, OPEN 6 = A) | every named state at 1280 × 800, pointer: content, no overflow, no JS error; every page reached through the drawer | clip a gallery's container at desktop width → falls |
| **R-L24-l** — identification in progress is read on the card (OPEN 3 = A) | the rung « identifié » drawn `now` from the per-medium journey while the seed says so | draw it done while the seed says `now` → falls |
| **R-L24-m** — a filling disk speaks on the badge (OPEN 2 = A) | the badge counts a « bientôt plein » disk and an index anomaly, read on their `tone` | drop the disk term → falls |
| **R-L24-n** — the ladder's words, and « enrichi » unfolded (DOIT-1, OPEN 5 = B) | every rung and step word from the one vocabulary, on the card and the sheet; « enrichi »'s three sub-steps each with its state | retype a step word in the sheet → falls |

---

## 5. What L24 does NOT draw, and the questions

**Owned elsewhere, one line each**: a grab deferred for SPACE (a disk full) — **L16** (DOIT-2's row); who may see
Système, « À traiter » and a decision's « Corriger » — **L18** (§ 17); the Trackers « Retirer de qBittorrent » dialog —
**L16** (R-L24-j reads it once it exists, draws nothing of it); the media sheet's cross-seed block — **L18**; the
global event feed and the configuration validation — **not redrawn**, D12. **Not drawn at all**: a decisions list or
screen anywhere (OPEN 1 = C); a global « en ce moment » (OPEN 3 = A); a desktop layout (OPEN 6 = A — the milestone
after the drawn lots owns it); a desktop navigation rail (Q1, ruled); a Pipeline tab or badge (Q6, ruled);
production's eight-stage `FlowBoard` (§ 20); anything the engine does (§ 15).

### The six rulings of 2026-09-29

**OPEN 1 — where the decisions journal lives. RULED (operator, 2026-09-29): C** — the operator's own proposal,
verbatim « Les décisions ne peuvent t'elle pas vivre sur la carte d'un média d'acquisions ? », then « C ». A settled
decision lives on the medium's card (§ 1.1); refused: A (a `/decisions` screen), B (Système's history). Consequence:
the journal and its six states are removed (§ 3), S1 is a block of the journey sheet and of the Médiathèque sheet,
pending decisions stay « À traiter » cards, organisation ruling 12 is untouched, and the demand « the decisions read
carries each decision's id » stays, for « Corriger » (§ 2, D).

**OPEN 2 — does a filling disk speak on the menu's badge? RULED (operator, 2026-09-29): A**, verbatim « A ». A disk
« bientôt plein » and a library-index anomaly count in the badge (§ 1.2); refused: B. Consequence:
`system-disk-filling` kept, one badge term, R-L24-m.

**OPEN 3 — a global « en ce moment » for identification. RULED (operator, 2026-09-29): A**, verbatim « A ». No global
figure; the activity reads on each card and L24 carries its proof (§ 1.3); refused: B. Consequence: demand C not
declared; `system-scraping-now` and `system-scraping-idle` removed; R-L24-l.

**OPEN 4 — the three French former addresses. RULED (operator, 2026-09-29): A**, verbatim « A ». `/medias`,
`/systeme`, `/controle` die at the switchover and answer the not-found page, no redirect (precedent `/arrivals`);
refused: B. Consequence: `former-french-alias` removed; R-L24-d holds that `/controle` is not redirected.

**OPEN 5 — does « enrichi » unfold? RULED (operator, 2026-09-29): B**, verbatim « B ». On the journey sheet
« enrichi » unfolds into metadata, posters fetched, trailer, each with its state; the card ladder keeps its eight
rungs (round 5 Q4 unchanged); refused: A. Consequence: `sheet-journey-enriched-unfolded` kept, one seed shape,
R-L24-n.

**OPEN 6 — what « se laisse respirer sur grand écran » asks. RULED (operator, 2026-09-29): A, with a milestone** —
verbatim « A dans un premier temps, mais prévoir une phase final d'adaptation des écrans pour une utilisation plus
agréable sur desktop. On en décidera des contours en temps et en heure quand la maquette sera prête ». Consequence:
L24's desktop half is the proof R-L24-k alone; the desktop adaptation is a milestone after the drawn lots (§ 1.6).

### Three questions the rulings raised — ALL THREE NOW RULED (operator, 2026-09-29, second round;
`docs/features/maquette-l24/rulings-2026-09-29.md`)

**OPEN 7 — RULED = A** (~11:0x, verbatim « A »). The block's « Corriger » (OPEN 1 = C) and the journey sheet's act
for a doubted engine match (S5, proposed at `@e6d63bffe` as a third act « Choisir un autre média ») answered the
same doubt with two readings; **A chosen**: ONE act — « Corriger » is S5, on the block, for both authors: on an
engine identification it creates the decision (`enqueueForResolution`), on an operator's choice it re-opens that
decision by its id (demand D); no third act on the journey sheet, R126 (`harness/journey_verbs.py`) unchanged.
**Refused: B** (two acts, R126 re-aimed to three). **Consequence**: 12 points (phase 7's reading A), no STOP C left
in that phase.

**OPEN 8 — RULED = A** (~11:3x, verbatim « A »). The candidates screen is addressed by a STAGING folder
(`/resolution/$folder`), which a shelved medium no longer has, and no declared operation re-identified one; **A
chosen**: « Corriger » is drawn on the Médiathèque sheet too, opening the arbitration on the medium's decision by
its id; the re-identification of a shelved medium is recorded as a demand on the engine (mission point 4).
**Refused: B** (the Médiathèque block reads without « Corriger », the phase dropped). **Consequence**: 8 points
(phase 8's reading A), the state `media-sheet-decision-corrected` unconditional, no STOP C left in that phase.

**OPEN 9 — RULED = A + PRINCIPLE** (~11:4x, verbatim « A, pas de gestion de rétro-compatibilité ! »). Where
`/media?decision=<id>` lands, its successor the journal's root OPEN 1 = C removed; **A chosen**: the query dropped,
`/media` (Médiathèque), exactly as for `/media?media=<id>` (D1 — an unknown dial is ignored). **Refused: B** (the id
read, landing on the decision's medium). **GENERAL PRINCIPLE, stated with it**: the new version handles NO backward
compatibility of former addresses or links — no alias, no redirect (precedents `/arrivals`, the French addresses).
**Consequence for S4** (§ 1.4): the whole redirect-table premise dies with its five states `former-control`,
`former-pipeline`, `former-pipeline-run`, `former-config`, `former-decision` — a former address answers not-found,
which `destinationOf` already does today; phase 10 is now a PROOF, not a surface, and carries no STOP C.

---

## 6. The register rows and the demands touched

**`BUGS.md`**, read, not edited: **B-235** (`open` in the index, « ANSWERED » in its body — the index is the
steward's to mend); **B-229**, **B-237** (`fixed #528`, cited by NE-DOIT-PAS-6's row as owed).

**`docs/reference/product-intent-map.md`**, read, amended by the operator: the DOIT-1, 5, 7, 9, 11, NE-DOIT-PAS-1 and
NE-DOIT-PAS-6 rows name L24 as their owner once this lot enters the plan; DOIT-7's row still names
`GET /api/decisions/activity` as unproved, which OPEN 3 = A makes served differently; DOIT-9's « Open: B-235 / Q1 »
is stale (§ 1.6) — proposed to the operator by the pull request that wrote this amendment, never written.

**`docs/reference/backend-demands-architecture.md`**, not edited. Demand D is a contract divergence, filed by the
regenerated `docs/reference/frontend-backend-demands.md` at the plan's first phase (D7).
