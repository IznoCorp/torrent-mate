# L22 — Arrivées dans Acquisition · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L22 — Arrivées dans Acquisition`
(its « Where it lives » and « Done when » lines). It is not restated here; what follows is the drawing the
plan executes.

This document is written for a session that has none of the context it was produced in. Every figure
carries the command that produces it, every decision carries its reason, every screen carries its named
states. **Nothing under `frontend/maquette/design/` was touched to write it** — it is prose and numbers,
written on `origin/main` at `94a369879` (2026-09-26), and the lot itself opens after this pull request
merges and the operator has read it.

**Its spine is not mine.** Fifteen organisation rulings dictate this lot: nine of 2026-09-15 (22:47 →
23:1x) in `docs/reference/operator-method.md`, six of 2026-09-26 (13:2x → 14:0x) that are not yet in the
committed method file. This document transcribes them. Where a ruling left a hole this document said OPEN and
drew no choice; **the eleven holes were ruled by the operator on 2026-09-26 (round 5, § 7.2) and each ruling is
carried into the body where it bites.**

---

## 0. What L22 owes, said once

The Arrivées page and the Acquisition page describe one thing twice. A folder the sort could not name is
listed « Ça coince » on the first and « À traiter » on the second (README § « A decision is a FOLDER »:
« they are two views of one thing »), and an operator who wants to know where a medium stands must ask
two pages, because three ladders exist for it (§ 3.2). §20 asks for the opposite: **the pipeline is
followed per medium, through the acquisition tunnel**. L22 makes that true of the arrivals — an arrival
is an acquisition card — and lets the destination that described them die.

**The constitution sentences this lot draws on are the AMENDED ones, and they are on `main`** —
`docs/reference/product-intent.md` was amended by #611 (`455d3ab7e`), « dicté le 2026-09-26 »: § 20 point 3
— « l'onglet « À traiter » d'Acquisition dit ce qui attend la main de l'opérateur, et pourquoi — un média
sans identité, un match Plex à confirmer, une erreur qui attend relancer ou abandonner » (with « une
arrivée est une carte d'acquisition, la page Arrivées et sa barre de lancement n'existent plus »); § 16
point 3 — « la médiathèque sous une fiche média, Acquisition sous une résolution »; § 17 point 4 — « La
barre du bas se compose par droits (dicté le 2026-09-26) », Système hors de la barre, « le bouton du menu
porte son badge quand il a quelque chose à dire ». This branch has not merged `main`, so the sentences
read with `git show origin/main:docs/reference/product-intent.md`. **This design draws on the rulings and
on those sentences, never on the old one.**

### The fifteen rulings, by number

| # | Date | What it dictates, in one line | Clause it serves |
| --- | --- | --- | --- |
| 1 | 09-15 | an arrival creates a PUNCTUAL acquisition (film, episode, season), never a follow; « Suivre » is PROPOSED on the card of an unfollowed series, never done unasked; arrivals classed « other » (not a medium) never enter the acquisitions | §5, §20-4 |
| 2 | 09-15 | arrivals become acquisition cards (requester = the known account, else the Plex owner); « À traiter » shows only what awaits his hand; the candidates screen opens from the card; **the Arrivées page dies**, and its batch launch bar with it (revises L20's Q1 = B) | §20-3, §2 |
| 3 | 09-15 | a film's follow ends by itself when the film is CONFIRMED in the library (Plex match validated) and leaves « Suivis » without a trace there — the trace lives on the media sheet and in the tunnel's history; a series' follow never ends by itself | §5, §4 |
| 4 | 09-15 | ONE ladder on the card, from the wish to Plex (proposed: demandé → cherché → attrapé → téléchargement → arrivé → identifié → trié → enrichi → rangé → vérifié dans Plex; the rungs' names adjust to the drawing); the tunnel's state (waiting, blocked + reason) reads on the current rung; a card born of a manual arrival starts at « arrivé » | §20-3, §2, §13 |
| 5 | 09-15 | a folder nobody recognised has a card WITHOUT identity (the folder's name for a title, no poster, « identifié » pending with its reason); the candidates screen offers « Ce n'est pas un média » — the folder is reclassified « other » (software…), filed where the sort files that category, and its card leaves the acquisitions | §3, NE-DOIT-PAS-9 |
| 6 | 09-15 | « Laisser tel quel » means LATER: the card stays in acquisition, « identifié » pending, reason « mis de côté par vous, le … », out of « À traiter » but visible in « En cours », the file stays in transit; it disappears only by his own reclassification | §3, DOIT-2 |
| 7 | 09-15 | « À traiter » = what only his hand unblocks: to resolve (no candidate, a tie), a Plex match to confirm (§3), a tunnel error awaiting a decision (relaunch / abandon); « set aside by you » is NOT in it; what stagnates for another reason reads on its card in « En cours », with its reason | §20-2, DOIT-2 |
| 8 | 09-15 (revised) | after a resolution one RETURNS to « À traiter »; the « Suivant » button disappears from the candidates screen (the first reading, A, was overturned by his own words two minutes later) | §16 |
| 9 | 09-15 | a card born of a direct add in qBittorrent carries the Plex owner as requester, shown « ajouté par Izno, dans qBittorrent », reassignable to another account from the card (the Operator's right) | §17 |
| 10 | 09-26 | « À traiter » is a FOURTH TAB of Acquisition, with its count; the bottom bar's badge counts that tab alone; the tab opened by default is « À traiter » when it is not empty, otherwise « En cours » | §20-3, §12 |
| 11 | 09-26 | the place Arrivées frees in the bar goes to a « Trackers » page (ratio, cross-seed, the tracker); the bar is composed BY RIGHTS (§17): an account without those rights sees Acquisition and Médiathèque only | §17-4 |
| 12 | 09-26 | every thing speaks where it lives, and the bar tab that carries it takes a badge — ratio and cross-seed on Trackers, the card on « À traiter », maintenance on Système; Système's history (L20) stays the only trace of the past; NO notifications box | §8, §13 |
| 13 | 09-26 | Système keeps the machine's state and the pipeline's levers; Maintenance stays a page of its own, reached from Système, at the same rights; the two sentences of Système that send the reader to Arrivées are rewritten in THIS lot | §17 |
| 14 | 09-26 | accounts are managed in a « Comptes » rubric of Réglages OR a first-level entry of the drawer (L18's drawing decides); Profil = the connected account, for everyone | §17 |
| 15 | 09-26 | Système LEAVES the bar and is reached from the drawer, at its right; the MENU BUTTON carries its badge when Système has something to say; the bar holds Acquisition, Médiathèque and Trackers (by rights), the fourth place free | §17-4, §12 |

Rulings 11 and 14 are not this lot's drawing: 11's Trackers page belongs to L16 and L17, and both 11's
composition by rights and 14's accounts to L18 (§ 7). L22 owes them the DEMANDS they leave (§ 6) and
nothing else. Ruling 15 IS this lot's: it is why § 3.6 exists.

**The round of 2026-09-26 (§ 7.2) moved the reading of six of the fifteen**, and the table above is the
rulings as dictated, not as read after it: ruling 2 — « Lancer » and « Arrêter » a pass die with the bar
(OPEN 6); ruling 4 — the ladder has eight rungs, not ten (OPEN 4); ruling 7 — the Plex-match card offers
« Confirmer » and « Corriger », and « Abandonner » quarantines (OPEN 9, 10); ruling 9 — the reassign gesture
is L18's, L22 draws the requester line (OPEN 11); ruling 10 — the four tabs read « Suivis · En cours · À
traiter · Découvrir » (OPEN 1); ruling 15 — the bar draws only the buttons present, in equal shares
(OPEN 2). The four others of the eleven (OPEN 3, 5, 7, 8) bear on rulings 1, 2, 8 and 12 in the same way.

### What this design reads

`docs/reference/product-intent.md` § 20 whole, § 17 whole, § 16 point 3, and §§ 2, 3, 4, 6, 12, 13 for what
they say of a card, a match to confirm, a queue, mobile and real data; the fifteen rulings above and the
eleven answers of § 7.2;
`docs/reference/frontend-architecture.md` § « L22 », decisions D1–D12 and the § 3 invariants;
`docs/reference/backend-demands-architecture.md` §§ 1, 2 and 9; the six rows of
`docs/reference/product-intent-map.md` that name `features/arrivals`; `docs/reference/frame-model.md`
for the bar and the drawer; and the tree at `94a369879`, cited by command where a figure comes from it.

---

## 1. What dies, what moves, what survives

Measured on this head; each line carries its command.

### 1.1 The Arrivées feature

    ls frontend/maquette/design/src/features/arrivals/                 →  11 files
    for f in frontend/maquette/design/src/features/arrivals/*; do grep -cve '^[[:space:]]*$' "$f"; done   →  1 486 non-blank lines

| File | Lines | Fate |
| --- | ---: | --- |
| `page.tsx` | 311 | **dies** — the page, its pilot's bar, « Dernier passage », the three sections |
| `arrival-card.tsx` | 124 | **dies** — the card every Arrivées list draws; the acquisition card (`card-markup.ts`, `ui/card.tsx`) replaces it |
| `variants.ts` | 64 | **dies** — `pilotBar`, `pilotHead`, `pilotGauge`, `pilotActions`, `pilotQualifier`, `pilotTitle` |
| `live.ts` | 108 | **moves, and NOT whole** — five rules and one exemption. The decisions and staging rules (`ItemProgressed`, `ItemDispatched`, `PipelineEnded` → staging and decisions) become Acquisition's. **The pipeline-status rule (`PipelineStarted`, `PipelineEnded`, `PipelinePaused`, `PipelineResumed`, `StepStarted`, `StepCompleted`, `StepErrored` → `/api/pipeline/status`) becomes SYSTÈME's — see the finding below** |
| `queries.ts` | 123 | **splits** — `useStaging`'s twin and `usePipeline` die with the page; `useDecisions`, `installDecisionLookup` and `pendingDecisions` move to Acquisition; `arrivalsBadge` dies with the row |
| `types.ts` | 31 | **moves** — `PendingDecision`, `SettledDecision`, `DecisionCandidate`, `DecisionChoice` go with the candidates screen; `Pipeline*` die |
| `verbs.ts` | 141 | **splits** — `take`, `resolution`, `resolve`, `leave`, `manual` move; `next` and `pipe` die (§ 1.2, ruling 8) |
| `resolution-screen.tsx` | 210 | **moves, and is drawn again** — the candidates screen SURVIVES under Acquisition (S4) |
| `resolution-cards.tsx` | 242 | **moves** — the candidate cards |
| `decision-vocabulary.ts` + `.test.ts` | 81 + 51 | **moves** — the reason and state vocabulary |

**A finding, and a trap the page was holding for someone else.** Système's levers read the pipeline's state
through `usePipelineState` (`features/system/queries.ts:107`), whose key is `["/api/pipeline/status"]` —
and the rule that refreshes that key on a server event lives ONLY in `features/arrivals/live.ts`:

    grep -n 'PIPELINE_KEY\|pipeline/status' frontend/maquette/design/src/features/arrivals/live.ts frontend/maquette/design/src/features/system/live.ts
    →  arrivals/live.ts: the key and the rule; system/live.ts: no reference to that key (its rules refresh the schedulers, the history and the locks)

Delete the page and its live table with it, and the levers keep drawing the state they had at their last
read while a pass starts and ends under them — the § 8 defect (« rien en silence »), introduced by a
deletion that no rule about Arrivées would ever read. The rule therefore MOVES to `features/system/live.ts`
in the phase BEFORE the one that deletes the page's table (phase 24, then phase 25); **R-L22-r reads it** (an event emitted through
the mock relay moves the lever). It is the species the L13c report recorded for the opening measure of a
behaviour change: read the readers of what the phase removes, not only its writers.

The survivors are one surface (the candidates screen and what it is built from — 4 of the 11 files, 584
lines of 1 486). Invariant 7 — « two features never import each other » — is the reason they move rather
than stay: Acquisition cannot import `features/arrivals/` for the screen its own cards open, and the
resolution route (`routes/resolution.tsx`) already composes it from outside. Phase 2 does the move alone,
with nothing redrawn.

### 1.2 The launch bar dies — and its two acts die with it (OPEN 6, ruled)

The pilot's bar emits `data-pipe="start"` and `"stop"`; its verb asks `POST /api/pipeline/run` and
`POST /api/pipeline/kill`.

    git grep -n -E 'data-pipe([^l]|$)' -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine'
    →  the emitters are all in `features/arrivals/page.tsx` (lines 120, 149, 152, 171; line 12 is a comment); the verb is `features/arrivals/verbs.ts:129`

The bare prefix `data-pipe` also matches Système's `data-pipeline-pause` and `data-pipeline-resume`
(`features/system/levers.tsx:75,80`): those are the levers, NOT the bar, and they survive. The regular
expression above keeps the two families apart.

**Ruling 2 says the bar dies with the page « (leviers à Système › Pipeline depuis L20) ». Measured, the
levers L20 drew are not those two acts.**

    git grep -n 'registerVerb(' -- frontend/maquette/design/src/features/system/
    →  pipeline-pause, pipeline-resume, watcher, bound (lever-verbs.ts); watch-now (watch-run.ts); run (run-verbs.ts, a run's DETAIL)

Système's « Le pipeline » section pauses and resumes everything, turns the automatic trigger on and off,
relaunches the veille and points at the parallelism bound. **It does not start a pipeline pass and it does
not stop one.** So when the bar dies, « Lancer le pipeline » and « Arrêter » have NO surface — and §1
(« lancer / stopper ») and DOIT-3 (« Lancer/stopper le pipeline … depuis le poste de contrôle ») name those
two acts. This was § 7.2's OPEN 6, drawn with both readings.

**Ruled 2026-09-26 (OPEN 6, reading A): « Lancer » and « Arrêter » a pass die with the bar, and no phase is
added.** §20 makes the pipeline a tunnel per medium: a pass « now » is what the levers' « Relancer la veille »
and each card's « Récupérer maintenant » / « Relancer » already are, and §1's « lancer / stopper » reads as the
levers' pause and resume. No lever is added to Système. **The cost the operator accepted is in the harness**
(§ 1.5): the four rules that started a pass by a finger on the bar re-aim onto another path, and the phase that
does it SAYS the re-aim out loud — where it went, and which of the rule's holds survive it.

`data-pipe`'s own defect history is what made this not a formality: B-371 (« En file » unreachable by a
hand) and B-531 (« Lancer ensuite » enabled during a run) were both about this bar (§ 6).

### 1.3 The `arr` row, the route, the address

    git grep -n '"arr"' -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine'
    →  app/navigation.ts:128 (the row), lib/addresses.ts:74 (`"/resolution/$folder": "arr"`), lib/addresses.test.ts:52,
       harness/states/arrivals.ts (8 states), harness/states/acquisition.ts:211, and three `data-go="arr"` emitters

- the row: `app/navigation.ts` `id: "arr"`, path `/arrivals`, region `arrivals/body`, badge `arrivalsBadge`, `inBar: true`;
- the route: `routes/arrivals.tsx`, registered in `app/router-tree.tsx`; `PAGE_PATHS.arr` in `lib/addresses.ts:23`;
- **the address `/arrivals` is NOT redirected (OPEN 5, ruled A).** Ruled 2026-09-26: with the route gone it is an
  unknown address like any other — the not-found page (`app/not-found.tsx`, `NOT_FOUND_ROW` in
  `app/navigation.ts:200`), no redirect, no second address to keep; R68 (`harness/address.py`) already reads that an
  unknown address breaks nothing, and R-L22-o reads that this one is drawn as such and stays as typed;
- the regions: `arrivals/pilot-bar` and `arrivals/body` in `frontend/maquette/regions.json`;
- the badge function and the `arrivalsLiveRules` registration in `app/live-updates.ts:29,79`;
- the verbs import in `app/panel-contributions.ts:32`, and `installDecisionLookup` in `app/shell.tsx:73`.

### 1.4 The interface text

    python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(len(d['screens']['arrivals']), len([k for k in d['verbs']['arrivals']]))"
    →  36 7

- **`screens.arrivals` — 36 keys — dies whole.** Its only reader in the source is `features/arrivals/page.tsx`
  (`git grep -n 'screens\.arrivals' -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine'`
  outside that file → no line); the resolution screen reads `screens.resolution`. One harness rule reads
  the group whole (`queued_by_hand.py`, § 1.5).
- **`verbs.arrivals` — 7 keys — splits**: `taken`, `resolved`, `left` are read by the verbs that move
  (`take`, `resolve`, `leave`); `pipelineStarted`, `pipelineQueued`, `pipelineAlreadyRunning`,
  `pipelineStopped` die with `pipe` (OPEN 6, ruled A: nothing moves).
- **`navigation.pages.arr`** (« Arrivées ») dies with the row.
- **`screens.acquisition.crossref*` — 8 keys** (`crossrefFromAcquisition` … `crossrefLink`): the sentence
  of « En cours »'s cross-reference, § 1.6.

### 1.5 The harness's readers of the page, counted

The brief's own command, and what it does not see:

    git grep -l 'arrivals\|arr-' -- 'frontend/maquette/harness/*.py' | wc -l                           →  33
    git grep -l -E 'data-page="arr"|PAGE_PATHS\["arr"\]' -- 'frontend/maquette/harness/*.py'            →  4 more: back.py, common.py, locks.py, url_state.py

**Thirty-seven files name the page; twenty-eight read it in code; nine only share the word** (comments, or
the mock layer's unrelated `arrivalsByKey` counter: `busy.py`, `chrome_pixels.py`, `content.py`,
`machine.py`, `outbox.py`, `screen_addresses.py`, `seeds_at_rest.py`, `transition.py`, `two_picks.py`).
The twenty-eight, by what they read:

| Reads | Files | Count |
| --- | --- | ---: |
| the candidates screen's states (`arr-resolution`, `arr-decision`) | `actions.py`, `attrs.py`, `bugs.py`, `cards.py`, `decision.py`, `hiding.py`, `load_more_scale.py`, `message_over_layers.py`, `persistence.py`, `resolution_card.py` | 10 |
| the page's own states (`arr-idle`, `arr-loaded`, `arr-queued`, `arr-error`, `arr-loading`, the `arr-{s}` template) | `add_screen_opens_fresh.py`, `audit.py`, `fanout.py`, `ident.py`, `paths_to_sheets.py`, `resolution_window.py`, `scen.py`, `state_surfaces.py`, `touch.py`, `panel_label_once.py` | 10 |
| the page's id, its address, its tab in the bar, its strings | `back.py`, `common.py`, `locks.py`, `page_host.py`, `queued_by_hand.py`, `sweep.py`, `url_state.py`, and `arrivals.py` itself (R66) | 8 |

`decision.py` (R57) is the largest single reader (six sites). **Four files START the pipeline by a finger on
the bar's `data-pipe` buttons** —

    git grep -c 'data-pipe' -- 'frontend/maquette/harness/*.py'
    →  arrivals.py 6 (R66), locks.py 2 (R-L20-g), page_host.py 11 (the page's own delegation block), queued_by_hand.py 3 (R185)

— and none survives the bar as written; `queued_by_hand.py` is the one whose whole premise is that
finger (B-371: « no path a hand can take »). **Ruled (OPEN 6, A): they re-aim, and each phase that does it says
so out loud.** `arrivals.py` (R66) dies with the page (phase 25) and its report says, hold by hold, where each of
its holds went; `locks.py` (R-L20-g), `page_host.py` and `queued_by_hand.py` (R185) re-aim in phase 23 — R185 onto
the path a hand still has (a maintenance command holding the lock, then a season asked: the `season/queued`
pastille, § 6.1). **Two more files name the page only by its accented word** and are
missed by the brief's command as well as by mine: `queued_ask_mark.py` (R138 — its docstring describes the
walk from Arrivées, the very claim B-514 says it can no longer keep) and `selection_survives_the_tab.py`; and
`machine.py` (R67) carries the sentence « a medium in trouble is Arrivées » as its premise (§ 6.3).

**A count made by the word alone would have said 33 and been wrong in both directions**: it misses four
readers of the page's identity and counts nine that read nothing. The plan's phases 22 and 23 are cut by
the table above, not by the 33.

**One reader more than the table counts**, found when the plan was re-measured on 2026-09-26:
`harness/journey.py:90,419` reads the page's path through the `ARRIVALS` constant (`harness/common.py:518`) — an
uppercase spelling that neither the brief's command nor the supplement above matches
(`git grep -n -E 'data-page="arr"|PAGE_PATHS\["arr"\]|ARRIVALS' -- 'frontend/maquette/harness/*.py'` finds it). It
re-aims with that constant, in phase 23; the totals above are left as written.

### 1.6 The cross-references to a page that stops existing

The brief names Système's two sentences (ruling 13). The tree has more emitters:

    git grep -n -F 'data-go="arr"' -- frontend/maquette/design/src
    →  features/acquisition/now-tab.tsx:106    « En cours »'s own cross-reference « Arrivées → »
       features/system/run-list.tsx:183         « Le pipeline se pilote depuis Arrivées… Arrivées → »   (screens.system.toArrivals, toArrivalsLink)
       features/system/run-screen.tsx:268       a run's detail « Voir les arrivées »                     (screens.run.leftBehindLink)
    python3 … screens.system.introRest  →  « … c'est une décision du pipeline, et elle est dans Arrivées. »
    python3 … verbs.maintenance.started →  « Commande lancée — suivez-la dans « Arrivées ». »

**Five sentences send a reader to a page that will not exist, not two**: the two ruling 13 names
(`introRest`, `toArrivals`+`toArrivalsLink`), Acquisition's own cross-reference (which dies with its
reason to exist — the arrivals it counted ARE now cards in « À traiter »), a run's detail link, and the
Maintenance toast. The plan's phase 21 rewrites all of them; ruling 13 authorised two.

### 1.7 What does NOT die

- the media sheet's route and its `SCREEN_PARENTS` entry (`/media/$provider/$id` → `lib`) — untouched;
- Système's history and the run's detail (L20) — the past stays where ruling 12 puts it;
- `lib/queue.ts` and the staging resource — a shared resource that Acquisition's own readers keep (its own header says why it is in `lib/`);
- the « ⋮ » more control and its « Veille et obligations » panel on Acquisition's tab bar.

---

## 2. The contract (D7) — and it comes FIRST

D7: the maquette declares the contract its interface REQUIRES, and every divergence from the backend's is a
demand. **A demand is filed by EDITING THE CONTRACT** (`frontend/maquette/contract/openapi.json`) and
regenerating `docs/reference/frontend-backend-demands.md` (`python3 scripts/compare-contracts.py
--write`); the register is « COMPUTED, NEVER WRITTEN ». This section says what the surfaces of § 3 read,
which of it the contract already declares, and which it does not. **It invents no shape**: what the design
needs and the register lacks is PROPOSED in § 6 as a new row, in the register's own form, and the lot files
it by editing the contract in phase 1 once the operator has read the design.

### 2.1 What the surfaces read, and what already exists

    python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted((m.upper(),p) for p,v in d['paths'].items() for m in v if any(x in p for x in ('to-handle','journeys','decisions','staging','followed')) ))"

| Surface | Reads / acts through | Declared today |
| --- | --- | --- |
| « En cours », « À traiter » — the cards | `GET /api/acquisition/to-handle` (`readAcquisitionQueue`) — five families: takeable, blocked, inFlight, notFound, doneToday | yes — **no family for an arrival nobody requested, no requester** (`git grep -ci requester` over the contract and `design/src` → no match) |
| the card's ladder | `QueueCard.strip` (five positions, `minItems` = `maxItems` = 5) and `GET /api/acquisition/journeys/{infoHash}` (`readJourney`, five stages) | yes — **two sources, five rungs each, and the pipeline has nine steps** (§ 3.2) |
| the candidates screen | `readDecisions`, `resolveDecision`, `dismissDecision`, `searchForDecision` | yes |
| « Laisser tel quel » | `dismissDecision` | yes — its meaning changes (§ 3.4), its operation does not |
| « Relancer » on a tunnel error | `requeueJourney` | yes |
| « Abandonner » on a tunnel error | `discardStagedMedia` — it quarantines the folder (OPEN 10, ruled B), § 3.3 | yes in name, **not in shape**: the maquette's contract calls it « Leave a staged item where it is » and answers `{ok}`; the backend's operation answers `detail`, `journaled`, `media_id`, `quarantine_path` (`docs/reference/frontend-backend-demands.md:105`) — the operation is re-declared by the phase that draws « Abandonner » (phase 11, § 6.2), and its register row shrinks rather than a row appearing |
| « Ce n'est pas un média » | — | **no operation** — proposed, § 6 demand C |
| « Suivre » on an arrival | `createFollow` | yes |
| the bar's places | `readAccount` answers `name`, `email`, `avatar` — no role, no right | **no** — L18's (§ 6 demand D) |
| Système's badge on the menu button | `readLocks`, `readServices`, `readDependencies` (`GET /api/maintenance/locks`, `/api/system/services`, `/api/system/dependencies`) — the maintenance facts AND the machine's faults (OPEN 8, ruled B) | yes — all three are declared and `features/system/live.ts` refreshes all three keys |
| the Plex confirmation (the ladder's last rung) | — | **nothing in the contract or the mocks names Plex** (`git grep -ci plex -- frontend/maquette/contract/openapi.json frontend/maquette/design/src/mocks/handlers` → no match) — the last rung is demand B's |
| « Confirmer » / « Corriger » on a Plex match | — | **no operation** — proposed, § 6 demand E (OPEN 9, ruled B) |

The candidates screen's data is the maquette's own and stays: three pending decisions and ten settled ones
are seeded (`python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/pending-decisions.json'))), len(json.load(open('frontend/maquette/design/src/mocks/seeds/settled-decisions.json'))))"` → `3 10`).

### 2.2 What the maquette mocks meanwhile — the seed, derived from real rows

The lot needs three cards the seeds do not have today. Each is derived from a row the real system has
(§13 — no invented data). **The gate is `python3 scripts/check-mock-seeds.py`, run in the same commit**: its
`schema` arm holds every seed against the contract schema of the operation that names it (so a new field is
declared in the contract FIRST — which is why the contract is phase 1), and its `provenance` arm holds the
four-way correspondence between `frontend/maquette/fixture-register.json`, the seed files and each
operation's `x-seeded-from` / `x-unseeded`. There is no seed builder to run: the seeds are edited by hand
and the guard is what reads them (an earlier lot's plan cites a `build-mock-seeds.py` that no longer exists).

1. **A card born of a torrent nobody requested.** The staging seeds already hold five media moving
   through the pipeline and seven settled ones (`moving.json`, `settled-loaded.json`); none is tied to a
   request. Each becomes an acquisition card at its rung, with a requester. This is demand A's seed.
2. **A card without identity.** Real: `stuck.json` holds **« Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto »**
   — reason « Aucun fichier vidéo dans le dossier : c'est un jeu, pas un média » — and `stuck-loaded.json`
   holds « Backrooms.2026.MULTi.2160p.WEB-DL », « S.W.A.T. » and « doc_fr_2026_final » (`ids` is `null` on
   all five). The game is the case ruling 5 was dictated for, and it is the seed of « Ce n'est pas un
   média » — a rule proved on it proves the ruling on the operator's own data.
3. **The requester « ajouté par Izno, dans qBittorrent ».** No field carries it. The seed adds one to the
   cards that are arrivals; the account is the mock's single account (`seeds/account.json`), which is the
   Plex owner by construction (§ 17: « les demandes existantes … sont attribuées au compte propriétaire du
   serveur Plex »).

The mocks MOVE (D7 — « a mock that answers without moving certifies nothing »): a resolution removes the
card from « À traiter » and adds it to the ladder at its next rung; a reclassification removes it from the
acquisitions; « Laisser tel quel » moves it to « En cours » with its reason; « Confirmer » on a Plex match moves the
card off « À traiter » (§ 3.3); « Abandonner » removes it from « À traiter » and answers its `quarantine_path`; a followed film reaching the last rung leaves the follows read (§ 3.5). One source each: the list and the count of the tab read the same
answer (§ 3.1).

### 2.3 The stream

`docs/reference/frontend-backend-demands-stream.md` § 1 already asks for per-media progress events carrying
the media's identity. L22 adds two things it does not name, PROPOSED there by hand rather than here: **the
birth of a card** (an event, so « À traiter » and the bar's badge move without a refetch — NE-DOIT-PAS-8
allows no poll) and **a rung's change of state** (the ladder reads it). `features/arrivals/live.ts`'s rules
move with their `because:` sentences: the staging and decisions rules to Acquisition's `live.ts`, and the
pipeline-status rule to Système's (§ 1.1's finding).

---

## 3. The surfaces, drawn

Copy is given in « guillemets » as `fr.json` will carry it; a key that exists is REUSED, never retyped
(a retyped string renders correctly while the reference is broken). Where this document proposes a
wording, it says so and the lot adjusts it at the drawing.

### 3.0 The addresses (D1)

| Surface | Tier | Address |
| --- | --- | --- |
| Acquisition and its four tabs | page + state | `/acquisition?tab=<id>`, `<id>` ∈ `follows` · `now` · `todo` · `discover` (the order the row draws them, OPEN 1); **absent = the default rule (ruling 10, S1)** |
| the candidates screen | content | `/resolution/$folder` — its parent in `SCREEN_PARENTS` moves from `arr` to `acq` (D1b rule 3: a cold link renders the real parent beneath) |
| a card's journey | panel | `journey:<title>` — unchanged (`sheet-journey`) |
| the « Ce n'est pas un média » choice | transient | no URL; Back closes it (D1's transient tier) |
| `/arrivals` | — | **not found** (OPEN 5, ruled A): an unknown address like any other, no redirect (§ 1.3) |

**The tab is a setting of the page, so choosing one REPLACES** (`acqtab` verb, `features/acquisition/verbs.ts`,
already so); the candidates screen is content, so opening it PUSHES (D1b rule 1). Nothing here needs a new
tier.

**Why the candidates screen keeps its path and its name.** A path is a NAME (`lib/addresses.ts` header):
`/resolution/$folder` names what the screen IS — a resolution of a folder — and that has not changed;
only what sits beneath it has. Renaming it would be a conversion of a working address for no ruling.

### 3.1 S1 — Acquisition's four tabs, and the default-tab rule (ruling 10)

> **Amended 2026-09-26 (operator, round 7 — § 7.3):** the default-tab rule below is REPLACED: « Suivis » on the
> first opening, then the last tab opened, kept in local storage on the device (read and write under try/catch,
> « Suivis » when the storage is empty or unreadable). The rest of ruling 10 holds (the fourth tab, its count, the
> bar's badge = « À traiter » alone).

**What is on the screen.** The segmented control of `features/acquisition/acquisition-tabs.tsx` gains a
fourth tab, and the four read in this order: « Suivis » (`tabFollows`), « En cours » (`tabNow`), « À traiter »
(`screens.acquisition.blocked` already reads exactly this word — as the title of a SECTION of « En cours »
today; § 3.3), « Découvrir » (`tabDiscover`). Each tab may carry a count; the « ⋮ » more control stays beside
the control.

**The order of the four is ruled (OPEN 1).** Ruling 10 dictates a fourth tab and its rule, not its place; the
operator's answer, verbatim, is « Suivis, En cours, A traiter, Découvrir » — outside both readings the design had
offered — and **the default-tab rule below stays whole**: the tab opened by default is derived, wherever it stands
in the row, so it may be the third. **A consequence, measured**: the three tabs that exist REORDER
(`features/acquisition/acquisition-tabs.tsx` draws `now`, `follows`, `discover` today), so « Suivis » becomes
the first tab of the row and « En cours » the second. The harness names a tab by its value
(`[data-acqtab="follows"]`), never by its position, with ONE site that reads the DOM order —
`harness/journey.py:117-118`, « the first tab whose value is not `now` », which answers « Suivis » under the old
order and under the new one — and every state of § 4 is independent of the order (`git grep -n -B3 -A6
"querySelectorAll('\[data-acqtab\]')" -- 'frontend/maquette/harness/*.py'`).

**The counts — one derivation each (§13).** « À traiter »'s count is the number of cards drawn in it; the
bottom bar's Acquisition badge is that same number (ruling 10: « le badge … compte ce seul onglet »);
the count on « En cours » is what it draws today minus what left it. Today:

    frontend/maquette/design/src/features/acquisition/queries.ts:339   acquisitionBadge()  →  takeable.length + blocked.length
    frontend/maquette/design/src/features/acquisition/acquisition-tabs.tsx                    the « En cours » count →  takeable + blocked

**Consequence of the ruling, stated because it moves a number the operator sees**: `takeable` (« À
récupérer », the media he can take with « Récupérer maintenant ») stops reaching the bar. The badge says
« something waits for your HAND to be unblocked », the ruling 7 definition, and « À récupérer » is a
shortcut on a medium the system is already looking for, not an unblock.

**The default-tab rule.** Today:

    frontend/maquette/design/src/app/arrival.ts:21                       INITIAL_STATE.acqTab = "now"
    frontend/maquette/design/src/features/acquisition/verbs.ts:109-111    fillLandingDoor(page → acq): store.write({ acqTab: "now" })
                                                                          (comment, line 103: « ARRIVING AT THIS PAGE OPENS ITS FIRST TAB, whoever asked for it »)
    frontend/maquette/design/src/features/acquisition/verbs.ts:73         the « complete » verb lands on « En cours » (deliberate)
    frontend/maquette/design/src/features/acquisition/add-screen.tsx:117  toFollows(): lands on « En cours » (deliberate)

The rule replaces the FIRST TWO — the two DEFAULTS — and leaves the two deliberate destinations alone (an
act that says where it takes you is not a default):

1. **An explicit `?tab=<id>` always wins.** A link, a bookmark, a cross-reference and the acts above say
   where they go.
2. **With no `tab`, on ARRIVING at the page** (a cold load, a switch from another page, the return from a
   screen that hides it), the tab is derived: « À traiter » if its count is not zero, otherwise « En cours ».
3. **While the count has not been read, nothing is chosen.** A default is an answer, and drawing
   « En cours » first and jumping when the count lands is a lie of a second kind (§13, « aucun état
   affiché n'est une constante »). The tab bar draws; the body draws its skeleton; the derivation happens
   once, when the count arrives. Named state `acq-entry-todo` is the arrival with the count read and not zero.
4. **Evaluated at arrival only.** A count that changes while the operator reads « Suivis » never moves him,
   and when he resolves the last card he is RETURNED to « À traiter » (ruling 8) and finds it empty: the
   empty state is drawn (§ 3.3), not skipped, so the return is the same gesture whether one card or many
   were waiting.

**Cost accepted by the operator (ruling 10):** four labels in the segmented control at 390 px — proved at
the harness (R-L22-e) — and a default-tab rule written and mutated (R-L22-a).

### 3.2 S2 — The card, and its ONE ladder (ruling 4)

**What the card is.** An acquisition card is drawn by `features/acquisition/card-markup.ts` (the list
cards) on `ui/card.tsx` (`Card`, `CardTitle`, `CardStrip`…), which « knows no domain ». L22 does not create
a second card; the Arrivées card (`features/arrivals/arrival-card.tsx`) is the one that dies. **One card,
one behaviour** (README): the poster opens the media sheet, the body opens the panel, the panel carries
every action, an inline action exists only where a section exists for it.

**Composition (§12, « une information par rôle »).** Line 1 — the title, alone, the full width. Line 2 —
the progress figure first, then the state: for a card on the ladder, « <n> sur 8 » then the current rung's
name. Then the reason (in full, never truncated — a stuck card's reason is what the operator decides on),
then the requester line where the card is an arrival (S2.4), then the ladder's strip, then a foot where a
section exists for an act.

**S2.1 The ladder — EIGHT rungs (OPEN 4, ruled B).** Ruling 4 proposed ten:

    demandé → cherché → attrapé → téléchargement → arrivé → identifié → trié → enrichi → rangé → vérifié dans Plex

**Ruled 2026-09-26 (OPEN 4, reading B): « trié · enrichi · rangé » merge into ONE rung, « rangé », and the card's
ladder has eight:**

    demandé → cherché → attrapé → téléchargement → arrivé → identifié → rangé → vérifié dans Plex

**The card reads « n sur 8 », and the journey sheet keeps the three steps in detail**: it opens the « rangé » rung
into « trié », « enrichi » and « rangé », from the same source the card reads (below). The names still adjust to
the drawing (ruling 4 said so); the number is ruled. What is measured today is why the ladder is a drawing problem
and not a copy problem:

    frontend/maquette/contract/openapi.json  →  components.schemas.PipelineStrip          5 positions (minItems = maxItems = 5), read by QueueCard.strip
    frontend/maquette/design/src/mocks/seeds/journey-stages.json                          5 stages
    frontend/maquette/design/src/mocks/seeds/pipeline.json                                9 steps  (ingest, sort, clean, scrape, cleanup, enforce, verify, trailers, dispatch)

**Three sources and three lengths** answer the question « where is this medium ». Ruling 4's ladder is ONE
list; the card's strip and the journey sheet's rows are two readers of it, never two lists (§13 — « une
seule dérivation par question »; R-L22-f reads their agreement, the sheet's detail under « rangé » included).
The backend owes the one source (§ 6 demand B); the maquette's mock derives both readers from ONE seed meanwhile.

**Drawn at 390 px.** The strip today labels each of its five steps under its dot
(`stripDot`, `stripLabel`, `stripStep` in `ui/card.tsx`). Eight labelled steps do not fit a phone either (§12 —
« Rien d'essentiel n'est tronqué »). The drawing this design proposes:

- the strip draws **eight cells and no per-cell label**; the CURRENT rung is named in words on line 2, where
  it has the full width;
- the **journey sheet** (`sheet-journey`) is the ladder in full — the eight rungs, each with its state and its
  time (which is what it already is at five), and under « rangé » its three steps in detail;
- `ui/card.tsx`'s strip gains « label optional » and two cell states (below): a primitive change with no
  domain word (invariant 10). **It is measured to need it**: the grid is written for five cells
  (`frontend/maquette/design/src/ui/variants/card.ts:99`, `grid-cols-[repeat(5,minmax(0,1fr))]`). It is its own phase
  (4), unchanged at five labelled cells, so the ladder's phase (5) moves no primitive.

**S2.2 The tunnel's state, on the current rung** (§20-2: « un blocage … termine l'exécution en
enregistrant son état »). One rung is current; its state is one of:

| State | Reads as | Where the card sits | Its reason |
| --- | --- | --- | --- |
| `now` | in motion | « En cours » | — |
| `waiting` | queued behind the parallelism bound or a maintenance run (DOIT-4 « En file », §6: never « occupé ») | « En cours » | « en file — pipeline en cours » (`screens.system.pipelineQueued`'s sentence family) |
| `blocked` | waits for HIS hand — to resolve, a Plex match to confirm, a tunnel error to decide | « À traiter » | in full |
| `aside` | set aside by him (ruling 6) | « En cours » | « mis de côté par vous, le … » |
| `done` / `pending` | passed / not reached | — | — |

**`waiting` and `aside` are two states the strip does not have** (`StripState` = done · now · blocked ·
pending). They are added as domain-free cell states. **Where a card sits is a function of its state, not of
its origin**, which is ruling 7 said as one rule (R-L22-h reads it).

**S2.3 A card without identity (ruling 5).** The folder's name is the title (in the mono face and never
cleaned up — README § « A decision is a FOLDER »), there is no poster (a folder icon, `CardFolder`, the
`data-nonmedia` marker R46 already defines), the ladder rests on « identifié » with `blocked` and its
reason, and its foot is « Résoudre → ». **NE-DOIT-PAS-9's exception is honoured**: an unidentified medium
« doit alors mener à la résolution, jamais à un lien mort ni à une fiche inexistante » — the card has no
sheet to open, so it leads to the candidates screen. It offers no « Suivre » (nothing to follow yet).

**S2.4 The requester (ruling 9).** A card born of a direct add in qBittorrent reads **« ajouté par
Izno, dans qBittorrent »**; a card born of a request reads its requester's name, the ordinary case (§ 17:
« Toute acquisition a un demandeur »). Where the line sits: the card's last text line, so it never competes
with the title, the figure or the reason (§12). **The line is composed from the answer's requester and its
origin, never a constant** (§13; R-L22-k mutates the seed's requester and reads the line follow). **The
gesture that REASSIGNS a request is not drawn here (OPEN 11, ruled B): L22 draws the requester LINE only.**
Ruling 9 dictates the gesture « depuis la carte » and it is an Operator's right (§ 17), whose offer belongs to the
rights model — the gesture is born with L18 (§ 7.1). Offering a right-dependent act before that model exists is
the small rights model the non-goals forbid.

### 3.3 S3 — « À traiter »: what it holds (rulings 6, 7)

**Ruling 7 in one sentence: « À traiter » holds what only his hand unblocks.** Three kinds, drawn as three
sections — the language « En cours » already speaks (a pip of colour per section, a counter that IS its own
link, a section with no card not drawn at all):

| Section | What a card in it is | Its act |
| --- | --- | --- |
| to resolve | no candidate, or a tie the score does not settle (`below_threshold`, `mid_band`, `ambiguous`, `manual`) — including a card without identity | « Résoudre → » → the candidates screen (S4) |
| a Plex match to confirm | the pipeline finished and Plex's match is not the one the identity says (§4 v3, « un média dispatché DOIT devenir visible dans le lecteur ») | « Confirmer » · « Corriger » on the Plex match itself (OPEN 9, ruled B) — **a verb no contract declares: demand E** |
| a tunnel error awaiting a decision | a step failed and only he can say relaunch or abandon (§20-2) | « Relancer » (`requeueJourney`) · « Abandonner » — the folder is quarantined, after a confirmation that names the medium (OPEN 10, ruled B) |

**What the two acts do (OPEN 9 and OPEN 10, both ruled B on 2026-09-26).**

- **« Confirmer » / « Corriger »** are offered on the Plex match itself: the card says which match Plex made
  and which identity the pipeline holds, and the two verbs act on THAT match — « Confirmer » says the match is
  the medium, « Corriger » says it is not. The operator is not sent through the candidates screen for a
  match he can already judge. **The verb exists in no contract**: nothing in the contract or the mocks names
  Plex (§ 2.1), so the row is PROPOSED as a fifth demand (§ 6.2, E), and its mock MOVES the card off « À traiter »
  (§ 2.2). How « Corriger » names the right match is the drawing's, at the phase that draws the card; it is not
  decided here and adjusts there.
- **« Abandonner »** quarantines the folder: `discardStagedMedia` (`POST /api/staging/media/{mediaId}/discard`,
  declared today, mocked at `mocks/handlers/staging.ts:108`), journaled, answering the `quarantine_path` — **after a
  confirmation that NAMES the medium** (NE-DOIT-PAS-6, « Détruire sans consentement. Confirmation explicite +
  identité par provider-ID »). The card leaves « À traiter ». The confirmation is a dialog of the maquette's own kind — the library's delete dialog
  (`features/library/delete-dialog`) names the medium it deletes, and the shape is the same — and it is a
  NAMED STATE (§ 4, `acq-abandon-confirm`); nothing is sent before the operator confirms. « Relancer » keeps
  its meaning. The other reading (abandon the TUNNEL, leave the files where they are) was refused.

**Seeds: two of the three kinds have no real row today** (§13 forbids inventing data). The ten real runs the
seeds hold carry no errored step and no unmatched item
(`python3 -c "import json;d=json.load(open('frontend/maquette/design/src/mocks/seeds/pipeline-runs.json'));print(sum(s.get('errorCount',0) for r in d for s in r['steps']))"` → 0),
and nothing names a Plex mismatch. « To resolve » has real rows (the five stuck folders); the other two sorts do
not. Phase 9 (the tunnel-error section) and phase 10 (the Plex-match section) therefore each report a **STOP D at its
opening** rather than improvising a seed: the steward decides whether the section is seeded by re-casting a real stuck row under another reason (a derivation, shown as
one), or drawn from their states with their seeds marked `x-unseeded`, the contract's own word for « nothing was
invented here » and « nobody looked » being different things.

**Not in « À traiter »** (ruling 7): what he set aside (ruling 6 — `aside`), a card queued behind a
maintenance run (`waiting`), a release nobody has (« Cherché, rien trouvé »), a stalled download. Each reads
on its own card in « En cours » with its reason, and at Système for the levers.

> **Amended 2026-09-26 (operator, round 7 — § 7.3):** « En cours » keeps « En vol » ALONE, queue included, and
> says « rien en cours » when nothing moves; « À récupérer », « Rangé aujourd'hui » and « Cherché, rien trouvé »
> leave it; « Mis de côté » is a FOLDED section at the end of « À traiter », outside its count and badge (ruling
> 16). The paragraph below is the first drawing, kept for the record.

**« En cours » keeps its five sections and gains one.** Today: « À récupérer », « À traiter » (the
`blocked` family — **the section this tab REPLACES**), « En vol », « Cherché, rien trouvé », « Rangé
aujourd'hui » (`fr.json` `screens.acquisition.takeable/blocked/inflight/notfound/doneToday`). After: the
`blocked` section leaves for its own tab; a card born of an arrival joins the section its rung says
(« En vol » while it moves, « Rangé aujourd'hui » for what Arrivées called « Arrivé dans les 24 h »); and a
new section, **« Mis de côté »** (a pip of the « waiting » tone), holds what he set aside. **The section's
name and place adjust to the drawing**; that it EXISTS follows from ruling 6 (« hors de « À traiter » mais
visible dans « En cours » »).

**Where the three Arrivées lists go**, so nothing is left without a home: « Ça coince » → « À traiter »
(to resolve); « Ça avance » → « En vol »; « Arrivé dans les 24 h » → « Rangé aujourd'hui ». The « Dernier
passage » block — the nine steps of the last run — is Système's history since L20 and is not carried.

**The empty state (DOIT-7, § 3 invariant: never an empty screen).** « À traiter » with nothing draws a
sentence saying nothing awaits his hand and where things are (« En cours »), never a blank body — the same
trait as `nowEmptyTitle`. It is drawn by named state `acq-todo-empty`.

**The « En cours » cross-reference dies** (`now-tab.tsx:106`, `screens.acquisition.crossref*`): it said
« N médias à traiter sont entrés sans suivi. Arrivées → ». Those N ARE cards in « À traiter » now, and the
count on the tab and the badge in the bar say so.

### 3.4 S4 — The candidates screen under Acquisition (rulings 5, 6, 8)

**The screen is the one that exists**: the folder in the mono face, the reason as a chip and a sentence,
the candidates (the score printed ONLY when it separates — README), the manual search, and the exits. It
moves to Acquisition (phase 2, nothing redrawn) and is redrawn by phases 14, 15 and 16. What changes:

| Exit | Today | After (ruling) | The card |
| --- | --- | --- | --- |
| pick a candidate | `resolveDecision`; the screen goes Back; an « Annuler » toast holds the send | unchanged, **and the landing is « À traiter »** (ruling 8) | leaves « À traiter », continues on the ladder from « identifié » |
| search by hand | replaces the screen with the add screen in `identify` mode | unchanged | unchanged |
| **« Laisser tel quel »** | `dismissDecision`; the folder leaves the queue | **means LATER** (ruling 6) | stays in acquisition, `aside`, in « Mis de côté »; the file stays in transit |
| **« Ce n'est pas un média »** | does not exist | **new** (ruling 5): a choice among the non-media destinations the sort files into — **configuration, never hard-coded**: the shipped example declares five (`config.example/patterns.json5`, `staging_dirs` whose `file_type` is not a movie or a show: `ebooks`, `audio`, `apps`, `android`, `autres`), which is the ruling's « logiciel, autre… » in the operator's own layout; the folder is reclassified and filed where the sort files that category | leaves the acquisitions; he does not see it again; an « Annuler » window (§ 6 demand C carries its inverse, as `docs/reference/backend-demands-architecture.md` § 9 asks of every resolve) |
| ~~« Suivant »~~ | `data-next`, the `next` verb, `screens.resolution.next` | **dies** (ruling 8 revised) | — |

**« Laisser tel quel » changes MEANING, not operation.** Today the `leave` verb (`features/arrivals/verbs.ts`)
says « the automatic result stands and the folder leaves the queue, because the operator has answered »:
`lib/queue.ts`'s `leave` calls `settle(title, "left")`, whose first act is `takeOutOfQueue` — the folder is
removed from BOTH lists (staging and the acquisition queue) — and the send is `dismissDecision`. The
operation stays; what the interface does with the answer changes: the card is KEPT and lands `aside`, so
the optimistic write the layer makes is a different one. R-L22-i reads that the card is absent from
« À traiter », present in « En cours » with its reason, and — the mock's job — still there after a re-read.

**« Ce n'est pas un média » on real data.** `stuck.json` carries « Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto » —
« c'est un jeu, pas un média » — the operator's own case. The rule (R-L22-j) is walked on it and reads the
NETWORK: the reclassification operation answered, then the card gone.

**The return (ruling 8, D1b).** After any exit the operator is back on « À traiter », the tab open,
whichever way the screen was reached. Opened from the list, that is the pop of D1b rule 1; opened cold, the
floor is the rendered parent (D1b rule 3) — Acquisition, whose default tab is « À traiter » BY CONSTRUCTION
while a decision is pending. R-L22-d reads the address and `history.length`, not the picture.

**What ruling 8 removes and does not name — ruled (OPEN 7, A).** The screen also draws a progression, « 1 sur 2
en attente » (`screens.resolution.outOf`, `screens.resolution.waiting`), that existed to serve « Suivant » (the
README says so: what the desktop deck's shortcuts were for — going through several in a row — « survives as a
plain progression », next to « Passer à la suivante »). **Ruled 2026-09-26: « n sur m en attente » dies with
« Suivant »** — a count that leads nowhere is noise on a phone, and « À traiter »'s tab count (§ 3.1) carries the
number. What goes: the two keys, and the `rank` line and its two words in `resolution-screen.tsx` (lines 102 and
152-153 on this head, before phase 2 moves the file); no harness rule reads either
(`git grep -n -i -E 'en attente|outOf' -- 'frontend/maquette/harness/*.py'` → no match). `screens.run.count.waiting`,
another key with the same word, is a run's count and stays. R-L22-d reads the progression's absence with
« Suivant »'s.

### 3.5 S5 — « Suivre », proposed; and a film's follow ending alone (rulings 1, 3)

**« Suivre » (ruling 1).** On the card of an arrival that is an IDENTIFIED SERIES nobody follows, the
interface PROPOSES the follow and does not make it: a foot action « Suivre » on the card (an inline action
where a section exists for it — the ladder card in « En cours ») and the same action in the card's panel
(the panel carries every action). Nothing is followed until it is tapped; a tap creates the follow through
the existing operation (`createFollow`), the proposal disappears, and the follow is a follow like any
other (« Suivis », its seasons, its « Ne plus suivre »). **No proposal on**: a film (ruling 3 — a film's
follow is not a thing an arrival implies), a card without identity (there is nothing to follow yet), a
series already followed. R-L22-l reads that an arrival changes the follows list by NOTHING, and that the
tap changes it by exactly one.

**A card born of an arrival is never in « Suivis » (OPEN 3, ruled A).** Ruled 2026-09-26: a follow and an
acquisition are different things (ruling 1: « jamais un suivi »); « Suivis » lists follows only. A card born of an
arrival — **an episode of a followed series included** — lives in « En cours » or « À traiter » and never appears
in « Suivis »; a follow appears there only when the operator taps « Suivre ». The other reading (the arrival shown
under its follow row as news) was refused. R-L22-l holds it on real subjects the seeds already carry:

    python3 -c "import json;b='frontend/maquette/design/src/mocks/seeds/';f={x['title'] for x in json.load(open(b+'follows.json'))};print(sorted(r['title'] for n in ('moving','settled','settled-loaded') for r in json.load(open(b+n+'.json')) if r['title'].split(' (')[0] in f))"
    →  ['Furious', 'President Curtis', 'Star Trek: Strange New Worlds (2022)']

« President Curtis » and « Star Trek: Strange New Worlds (2022) » are arrivals of series `follows.json` follows;
« Furious » is B-549's seed (a film carrying a series' identifiers, not this lot's) and is not used as a subject.

**A film's follow ending alone (ruling 3) — DRAWN HERE, in its own phase (18), and its half on the media
sheet is NOT.** The reason for drawing the list side here: it is the one place where the ladder's LAST
rung has an effect outside the card, and a ladder whose last rung changes nothing observable cannot be
proved. It is Acquisition's own list (the follows read), so no feature imports another (invariant 7), and
it is one kind of change — a lifecycle rule on a list — so it does not share a phase with the proposal.
The rule (R-L22-m): a followed film stays in « Suivis » until its ladder reaches « vérifié dans Plex »,
leaves at that moment with no trace in « Suivis »; a followed series never leaves by itself.
**The other half — « sa trace vit sur sa fiche média (acquis le …, release, demandeur) » — is not drawn
here**, and the reason is measured: the media sheet is `features/media/`, outside the « Where it lives »
of L22's contract line (« the Acquisition page — the card, its one ladder, and the candidates screen »);
the sheet draws no « acquis le » or requester today (`git grep -ci 'acquis le' -- frontend/maquette/design/src/i18n/fr.json`
→ no match); and its content needs the requester the rights model owns. It is a debt the plan names in phase 27,
for the steward to assign — not silently dropped.

### 3.6 S6 — The bar and the drawer after Arrivées (rulings 11, 12, 15)

**The bar is the table's.** `app/navigation.ts` is « the only declaration of what pages exist »; the bar
draws the rows with `inBar: true` (`app/tab-bar.tsx` — `NAVIGATION.filter((row) => row.inBar)`) and the
drawer groups the rows that carry a `group`. Today:

    acq  inBar  badge acquisitionBadge     lib  inBar     arr  inBar  badge arrivalsBadge     sys  inBar
    maint · cfg · profile · 404  not in the bar

**At the end of L22:**

| Row | Bar | Drawer | Badge |
| --- | --- | --- | --- |
| `acq` Acquisition | yes | supervision | the « À traiter » count (S1) |
| `lib` Médiathèque | yes | supervision | — |
| `arr` | **row deleted** | — | — |
| `sys` Système | **no** (ruling 15) | group « system », at the right that opens it | its own function, exported by the system feature: it counts the maintenance facts AND the machine's faults (OPEN 8, ruled B) |
| `maint` Maintenance | no | group « system » — and reached from Système, both cross-references already exist (`features/system/page.tsx:107`, `locks.tsx:146`) | — |
| `cfg`, `profile` | no | unchanged | — |

**The bar at the end holds two places, and it draws two.** L16 draws Trackers, whose place ruling 11 gives it; the
fourth is « libre jusqu'à ce qu'une page quotidienne la mérite ». **L22 does NOT draw a placeholder for a page it
does not draw** and does not compose the bar by rights (L18's model): it draws the bar it HAS.

**How a bar with two filled places is drawn — ruled (OPEN 2, reading A, as a general FRAME rule).** The operator's
answer, verbatim: « A, la barre du bas s'adapte toujours au nombre de boutons présents, chaque bouton prend
toujours le même ratio. 2 boutons (50/50), 3 boutons (33/33/33), 4 boutons (25/25/25/25). 4 boutons c'est le max,
2 boutons le min. » **The bar draws ONLY the buttons present, in equal shares of 1/n, n from 2 to 4, and never
an empty slot** — two now, three when Trackers lands, four at most. The rule names no page, so it holds every bar
the app will ever draw (invariant 10: the frame names no domain word). **Measured, the code already keeps it**:
`tabBarButton` (`ui/variants/frame.ts`) is `flex … min-w-0 flex-1 basis-0`, so each present button takes an equal
share whatever their number, and nothing draws a fixed slot. **The rule is therefore NOT red today** — stated, not
staged — and is proved by its mutation (a fixed share, which leaves a slot empty at three and at two): R-L22-s
(§ 5), written with the phase that first draws a bar of other than four buttons (phase 19), and read again at every count
the lot reaches (three when Système leaves, two when Arrivées dies).

**The badges (ruling 12).** A badge is a function the row points at, exported by the feature that knows
what it counts (`app/navigation.ts` head comment): the frame names the feature once and never its counter.
The bar shows the badge of every bar row that has one — Acquisition's here; Trackers' at L16. **The menu
button (ruling 15)** shows the badge of the rows the bar does NOT hold: the frame sums `badge()` over
`NAVIGATION.filter((row) => !row.inBar)` — a derivation that names no domain word, so invariant 10 is not
touched — and the drawer's own entries already draw the same function (`app/drawer.tsx`: `row.badge()`),
so the button, the drawer entry and the page's own reading are ONE derivation (§13, R-L22-c). **What Système's
function counts is ruled (OPEN 8, reading B): the maintenance facts AND the machine's faults** — the first are what
L20's locks section already names (`readLocks`: a stale lock, leftover temporary entries, a sweep that did not
finish), the second a service that stopped answering or a dependency that is down (`readServices`,
`readDependencies`); the reading that kept the badge to maintenance alone was refused. All three reads are declared
and refreshed by `features/system/live.ts` (§ 2.1), so the badge moves without a refetch.

**The menu button is not React today.** It is static markup in the document:

    frontend/maquette/design/index.html:231-234   <button class="burger …" aria-label="Ouvrir le menu de navigation" data-drawer="1">

with `data-drawer` answered by the frame's verb (`app/frame-verbs.ts`). A badge on it needs a mount:
either a small component portalled into the static header (the way `app/page-host.tsx` portals into
`#view`) or the header's conversion. **Phase 20 measures both and takes the one that leaves the button's id,
its `data-drawer` and its accessible name where they are** — the first is the smaller change and is the
one this design assumes. The badge's look is the tab bar's (`tabBarBadge`): one visual language for « this
has something to say ».

**No notifications box (ruling 12).** Nothing collects the badges into one place; each speaks on its own
tab. Système's history (L20) stays the only trace of the past.

### 3.7 S7 — The sentences that send the reader to Arrivées (ruling 13)

Ruling 13 authorises the two of Système; § 1.6 counts five. The wordings below are PROPOSED; the lot
adjusts them at the drawing (French only inside « guillemets »):

| Sentence | Today | Proposed |
| --- | --- | --- |
| `screens.system.introRest` | « … c'est une décision du pipeline, et elle est dans Arrivées. » | names « À traiter », in Acquisition |
| `screens.system.toArrivals` + `toArrivalsLink` | « Le pipeline se pilote depuis Arrivées, où l'on voit ce qu'il fait aux médias. » / « Arrivées → » | says that the levers are HERE (« Système ») and that what the pipeline does to a medium reads on its card; the link leads to Acquisition |
| `screens.run.leftBehindLink` | « Voir les arrivées » | leads to « À traiter » (what the run left behind) |
| `screens.acquisition.crossref*` | « Arrivées → » | **dies** (§ 3.3) |
| `verbs.maintenance.started` | « Commande lancée — suivez-la dans « Arrivées ». » | names Système — a maintenance run appears in its history (`features/system/run-list.tsx` lists `kind: "maintenance"`) |

A cross-reference that leads to Acquisition lands on the default tab, so « À traiter » when something
waits: a link never sends the operator to a tab it knows to be empty.

---

## 4. The named states

**Measured before naming them**: 114 states exist, summed across the eleven files `harness/states/` holds
(the counting command of L20's DESIGN § 5, unchanged):

    python3 -c "import re,glob;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open(f).read(), re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"   →  114

`harness/states/arrivals.ts` holds eight of them (`arr-idle`, `arr-running`, `arr-queued`, `arr-loaded`,
`arr-loading`, `arr-error`, `arr-resolution`, `arr-decision`); `harness/states/acquisition.ts` holds 26 (258
non-blank lines, under invariant 6's 400). **Six of the eight die with the page; two SURVIVE under new
ids** (`arr-resolution` → `acq-resolution-none`, `arr-decision` → `acq-resolution-tie`), so the count
moves: **114 − 8 + 23 = 129**. Every new state is reachable by `window.__go("<id>")`, has an English id, and
its French label is what the panel says.

**Where they live.** `harness/states/acquisition.ts` would leave invariant 6's 400 lines with 23 more
entries (258 + about 210). The new states go in a NEW file, `harness/states/tunnel.ts`, composed by
`harness/index.ts` beside the others (the way L13a's move made every surface a file); the two survivors are
declared there in phase 3 and the file dies nowhere. `harness/states/arrivals.ts` dies in phase 25.

| # | id | Label (French, as the panel lists it) | Lands in phase |
| --- | --- | --- | ---: |
| 1 | `acq-resolution-none` | « Résolution — aucun candidat » (was `arr-resolution`) | 3 |
| 2 | `acq-resolution-tie` | « Résolution — candidats à égalité » (was `arr-decision`) | 3 |
| 3 | `acq-card-rungs` | « Carte — une par cran de l'échelle » (eight cards, one on each rung) | 5 |
| 4 | `acq-card-blocked` | « Carte — arrêtée sur « identifié », sa raison en entier » | 5 |
| 5 | `acq-card-waiting` | « Carte — en file derrière une maintenance » | 6 |
| 6 | `acq-card-no-identity` | « Carte — un dossier sans identité » (from the seed's game folder) | 6 |
| 7 | `acq-card-requester` | « Carte — ajouté par Izno, dans qBittorrent » | 7 |
| 8 | `acq-todo-empty` | « À traiter — rien n'attend votre main » | 8 |
| 9 | `acq-todo-loaded` | « À traiter — chargé » (the three sorts of card, the Plex match with its « Confirmer » and « Corriger » among them) | 9 · 10 |
| 10 | `acq-abandon-confirm` | « À traiter — confirmation avant d'abandonner » (a dialog that names the medium; nothing is sent yet) | 11 |
| 11 | `acq-todo-loading` | « À traiter — chargement » | 13 |
| 12 | `acq-todo-error` | « À traiter — erreur » | 13 |
| 13 | `acq-entry-todo` | « Acquisition — arrivée, quelque chose attend » (opens on « À traiter ») | 13 |
| 14 | `acq-entry-clear` | « Acquisition — arrivée, rien n'attend » (opens on « En cours ») | 13 |
| 15 | `acq-card-set-aside` | « Carte — mis de côté par vous » | 15 |
| 16 | `acq-resolution-not-media` | « Résolution — « Ce n'est pas un média » : le choix de la catégorie » | 16 |
| 17 | `acq-card-follow-offer` | « Carte — « Suivre » proposé sur une série arrivée » | 17 |
| 18 | `acq-follows-film-confirming` | « Suivis — un film suivi dont le dernier cran vient » | 18 |
| 19 | `drawer-system` | « Tiroir — Système à sa place, hors de la barre » | 19 |
| 20 | `bar-todo-badge` | « Barre — Acquisition porte le compte de « À traiter » » | 19 |
| 21 | `bar-clear` | « Barre — rien à dire » | 19 |
| 22 | `menu-system-badge` | « Bouton du menu — Système a quelque chose à dire » | 20 |
| 23 | `menu-clear` | « Bouton du menu — rien à dire » | 20 |

**Amended 2026-09-26 (RULINGS 2):** `acq-card-rungs` holds the SIX rungs the queue's real rows reach; the eight are held whole on `sheet-journey`.

**A named state that already exists and is not new**: `drawer-navigation` (« Tiroir de navigation
(hamburger) », `harness/states/frame.ts`). It draws the drawer with nothing to say; `drawer-system` and the
two `menu-*` states are what add Système's badge to it.

**The four tabs at rest and loaded**: « À traiter » by #8–#10; « En cours » by `acq-now-idle` and
`acq-now-loaded`, which EXIST and are re-seeded (phases 5, 6, 9); « Suivis » and « Découvrir » by their
existing `acq-follows-*` and `acq-discover*` states, which the fourth tab's width moves (§ 4.1).

**`acq-todo-loading` and `acq-todo-error` ARE named** although the `phase` dial can drive them, for the
reason `acq-now-loading` and `acq-now-error` already are: `harness/state_surfaces.py` (R90) walks a
per-surface list of loading and error states with the sentence each says
(`"arr-error": "ce qui arrive"`), and it loses its Arrivées entries in phase 22; « À traiter » takes
their place there, not the dial alone.

**What has no named state and why.** The return to the list after each exit, the card's leaving after
« Ce n'est pas un média », and its leaving after the confirmed « Abandonner », are ACTS, not surfaces: R-L22-d,
R-L22-j and R-L22-u walk them by finger and read the address and the network. A state is a place one can `__go` to
— which is why the CONFIRMATION before « Abandonner » is one (`acq-abandon-confirm`), as the library's delete
dialog is (`Médiathèque — dialogue de suppression`), and the tap that answers it is not.

### 4.1 What the oracle will do (D8)

The new surfaces are NEW, so the reference RECORDS them and proves nothing about them: a state that did not
exist cannot have a divergence. What the oracle is for here is the other direction — **no existing state
may diverge unless a phase names it**. Named, with their reasons:

| Phase | Existing states that WILL diverge | Reason (accepted by name, D8) |
| --- | --- | --- |
| 1, 4 | none — the contract moves no surface, and the strip at five labelled cells is unchanged | — |
| 2, 3 | none expected (`arr-resolution`, `arr-decision` re-keyed to their new ids and re-measured; geometry must be identical — **if it differs, that is a finding and not an acceptance**, because nothing was redrawn) | the move touches ownership, not pixels |
| 5 | every state that draws a card strip: `acq-now-idle`, `acq-now-loaded`, `arr-*` cards, `sheet-journey`, and their `acq-follows-*` neighbours if any drew one | « L22 § 3.2: eight cells and one named rung replace five labelled steps » |
| 6, 7 | `acq-now-idle`, `acq-now-loaded` (and `arr-idle`, `arr-loaded`: the same rows, two readers) | « L22 § 3.3: the arrivals join « En cours » » |
| 8, 9 | every state that draws Acquisition's tab bar (`acq-now-*`, `acq-follows-*`, `acq-discover*`, `acq-add-*` behind their screens) on `acquisition/tabs`; `acq-now-*` on `acquisition/body` | « L22 § 3.1: a fourth tab, and the row's new order; § 3.3 the `blocked` section leaves » |
| 10 | `acq-todo-loaded` — recorded at phase 9, it gains its third section, the Plex match with « Confirmer » and « Corriger » | « L22 § 3.3: the Plex-match section and its two verbs » |
| 11 | `acq-todo-loaded` — the tunnel-error card gains « Abandonner » | « L22 § 3.3: « Abandonner » on a tunnel error » |
| 12 | every state that draws the count on « En cours »'s tab and the bar's Acquisition badge (`acq-now-*`, `acq-follows-*`, `acq-discover*`) | « L22 § 3.1: the counts follow ruling 10 » |
| 13 | none expected — every named state reaches its tab explicitly (the walks that land unnamed are rules, not states) | — |
| 14 | `acq-resolution-tie` on `screen-resolution/body` (the only resolution state that offered « Suivant » and drew « n sur m en attente », both being drawn when several wait) | « L22 § 3.4: « Suivant » and its progression die » |
| 15, 18 | only the state each adds; anything else is STOP A | behaviour phases |
| 16 | `acq-resolution-none`, `acq-resolution-tie` on `screen-resolution/body` (a new exit under the manual search) | « L22 § 3.4: a new exit » |
| 17 | `acq-now-idle`, `acq-now-loaded` (an arrival series card gains a foot) | « L22 § 3.5: the proposal » |
| 19 | none by the oracle (see below) | — |
| 20 | none (the button's own rect is not a region root) | — |
| 21 | `system`, `system-outage`, `system-loading`, `system-error` and the run-detail states, on `system/body` if a sentence wraps differently | « L22 § 3.7: five sentences rewritten » |
| 24, 25 | none (a live rule moves; a dead page's code goes) | — |
| 26 | the six remaining `arr-*` records leave the reference; nothing else may move | the page's records go |

**The oracle's silence over the bar proves nothing, and this design says so before the phase does.** D8
reads the rectangle and the computed style of the element ITSELF, never a descendant. The bar's `<nav>`
has the same rectangle with two places or four; only a named rule reads the buttons. Phase 19's oracle
will be green over a bar that lost a place (**R-L22-q reads them, R-L22-s reads their shares**; the bar loses its
next place in phase 25, with the row that held it), and the same holds for the
menu button's badge in phase 20 — L20 § 7 wrote the same warning about behaviour lots, and L11 is the
measured case: no divergence over 2 958 measurements while four adversarial rounds found ~40, 13, 7 and 0
defects. **This lot is held by § 5's rules or by nobody.**

The accessibility tier (`--a11y`) is re-read at phases 3, 8, 11, 19 and 26: the two survivors carry recorded
debts under their old ids (`a11y-debt.json`, `a11y-light-debt.json`) that move WITH their ids in phase 3
and are never re-recorded lower; the six dead ids leave the three a11y files in phase 26.

---

## 5. The rules that bite

Numbers: the harness's highest rule number is re-taken by phase 1 against `origin/main` at the moment it
runs — `grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` — and every label
below is bound to a consecutive free number then, the mapping written into the report. **A number taken
from this document without re-measuring is a collision** (L20's phase 1 says the same in the same words).
Each is written RED FIRST, and where the surface does not exist on `main` it is red for that reason, with no
mutation needed; where it changes behaviour that exists, it is red against the code as it stands and the
mutation comes after the move.

| Rule | Phase | What it READS | The mutation that fells it |
| --- | ---: | --- | --- |
| **R-L22-a** — the default tab (**amended 2026-09-26, § 7.3**: « Suivis » first, then the last tab opened from local storage, « Suivis » on an empty or throwing storage — the cells below are the first drawing) | 13 | a cold entry on `/acquisition` with no `tab`: « À traiter » is open when its count is not zero and « En cours » when it is zero (both states `acq-entry-todo` / `acq-entry-clear`); an explicit `?tab=follows` wins over a non-zero count; **while the count is unread no tab is selected and none is printed** (§13) | derive the default from a constant → falls; invert the comparison → falls; choose before the count lands → the « nothing selected while unread » hold falls |
| **R-L22-b** — the count in the badge (**R16's successor**: `audit2.py` asserts `takeable + blocked` on the bar's badge AND on « En cours »'s tab today, and is re-aimed, not left green over a reversed behaviour) | 12 | the bar's Acquisition badge equals the number drawn on the « À traiter » tab equals the number of cards in it, on `acq-todo-loaded` and `acq-todo-empty` (badge absent, not `0`) | make the badge count `takeable` too (the old derivation) → falls |
| **R-L22-c** — the menu button's badge | 20 | the button carries a badge exactly when the rows out of the bar have something to say, its number equal to the drawer entry's own count; absent, not `0`, otherwise; **Système's number moves under a seeded maintenance fact AND under a seeded service or dependency fault** (OPEN 8, ruled B) | drop the wiring → falls; print a constant → falls under a seeded change; count the maintenance facts alone (the refused reading) → the fault hold falls |
| **R-L22-d** — the return to the list | 14 | after each exit (pick, « Laisser tel quel », and later « Ce n'est pas un média »): the address is `/acquisition` with « À traiter » open; `history.length` did not grow (a pop, not a push); **no « Suivant » and no progression (« n sur m en attente »)** anywhere on the screen (OPEN 7, ruled); and the same on a COLD `/resolution/<folder>` | restore the `next` verb → the absence hold falls; restore the progression → it falls; make an exit push → the length hold falls |
| **R-L22-e** — four labels at 390 px, in their order | 8 | at the real phone width: the four tabs' labels and counts are not truncated (`scrollWidth ≤ clientWidth` per label), the control does not overflow horizontally, the « ⋮ » control stays reachable, each target ≥ the touch minimum; **and the four read, in the DOM, « Suivis » · « En cours » · « À traiter » · « Découvrir »** (OPEN 1, ruled) | lengthen a label past the budget → falls; drop a tab's `min-width: 0` → falls; swap two tabs in the row → the order hold falls |
| **R-L22-f** — one ladder | 5 | the card's ladder draws the journey's rungs in the journey's order and its current rung equals the journey sheet's; the current rung's NAME is drawn whole (not truncated) at 390 px on `acq-card-rungs`; eight cells, no horizontal overflow; the journey sheet opens « rangé » into its three steps, from the same source | read the old five-position strip for the card → falls; swap two rungs in the seed → falls; give the sheet a list of its own for the three steps → the agreement hold falls |
| **R-L22-g** — a card without identity | 6 | the card born of the game folder exists in acquisition: the folder's name for a title, no poster, `data-nonmedia`, the ladder resting on « identifié » with `blocked` and the reason in full, **no sheet link and no « Suivre »**, a way to the candidates screen (NE-DOIT-PAS-9's exception) | give it a sheet link → falls; drop its reason → falls |
| **R-L22-h** — « À traiter » holds only what his hand unblocks | 9 | on `acq-todo-loaded`: every card in the tab is `blocked` in one of the three kinds; a card `aside` and a card `waiting` are NOT in it and ARE in « En cours » with their reasons | put an `aside` card in the tab → falls; put a `blocked` card in « En cours » → falls |
| **R-L22-i** — « Laisser tel quel » is later | 15 | walked by finger on a real stuck folder: the card is absent from « À traiter », present in « Mis de côté » with « mis de côté par vous, le … », and still present after a re-read (the mock's state, not the screen's) | restore the old behaviour (the card leaves) → falls |
| **R-L22-j** — « Ce n'est pas un média » | 16 | walked on the game folder: the choice offers the sort's non-media categories; the reclassification is ANSWERED on the network (`window.__mocks.answered()`), the card leaves the acquisitions and is not in « À traiter » or « En cours »; the « Annuler » window brings it back | make the verb toast without calling → the network hold falls |
| **R-L22-k** — the requester, from the answer | 7 | on `acq-card-requester`: the line reads « ajouté par <name>, dans qBittorrent » and the name is the seed's requester — the seed changed to another name, the line follows | print a constant → falls |
| **R-L22-l** — « Suivre » proposed, never done | 17 | an arrival of an identified series changes the follows list by NOTHING; the offer is on the card and in its panel; a tap changes the list by exactly one follow and the offer goes; no offer on a film, on a card without identity, on a series already followed; **no card born of an arrival is drawn in « Suivis », even the episode of a followed series** (OPEN 3, ruled A: « President Curtis », « Star Trek: Strange New Worlds (2022) ») | follow on arrival → falls; offer it on a film → falls; draw an arrival card in « Suivis » → the new hold falls |
| **R-L22-m** — a film's follow ends alone | 18 | on the seed's five followed films: present in « Suivis » until the ladder reaches « vérifié dans Plex », absent after (no trace in « Suivis »); a followed series is there after; NOT ended at the rung before | end it one rung early → falls; end series too → falls |
| **R-L22-n** — the addresses | 2 | `/resolution/$folder` declared with `acq` as its parent; opening the screen PUSHES (asserted on `history.length`); a cold `/resolution/<folder>` renders Acquisition beneath | leave the parent at `arr` → falls |
| **R-L22-o** — Arrivées is gone | 25 | no `arr` row in the bar or the drawer; no `data-go="arr"` in the source; `screens.arrivals` absent from the resources; the shipped source names no `features/arrivals`; **the address `/arrivals` draws the not-found page and is not redirected** (the address stays as typed; OPEN 5, ruled A) | re-add the row → falls; add a redirect from `/arrivals` → the address hold falls |
| **R-L22-p** — the sentences | 21 | no rendered sentence on Système, its run detail, Acquisition or the Maintenance toast names Arrivées; each cross-reference LANDS (address read) on Acquisition with « À traiter » open when something waits | restore one `data-go="arr"` → falls |
| **R-L22-q** — the bar's places | 19 | the bar draws exactly the rows the table marks `inBar`, each tappable at 44 px; Système is NOT among them and IS in the drawer's system group; a tap on its drawer entry lands on `/system` | put `inBar: true` on `sys` back → falls |
| **R-L22-r** — the levers stay live | 24 | Système's levers draw the pipeline's state, and it MOVES when `PipelineStarted`, `PipelinePaused` and `PipelineEnded` arrive through the mock relay — read while Arrivées' live table still exists AND after the rule left it (§ 1.1's finding: the page was holding the only rule that refreshes `/api/pipeline/status`) | leave the status rule out of `features/system/live.ts` → the lever stops moving and the hold falls |
| **R-L22-s** — the bar's shares (a FRAME rule, OPEN 2 ruled A) | 19 | on every state that draws the bar, at the count it has (four before Système leaves, three after, two when Arrivées dies): the bar draws exactly the buttons the table marks `inBar`, each of width 1/n of the bar (within a pixel of rounding), n between 2 and 4, and the buttons tile the bar's width whole — **no empty slot**. **Green at once** (§ 3.6: `flex-1 basis-0` already shares equally), proved by its mutations | give the buttons a fixed share (`basis-1/4`) → the tiling hold falls at three and at two; drop `flex-1` → falls; put a fifth row `inBar: true` → the « n ≤ 4 » hold falls |
| **R-L22-t** — « Confirmer » / « Corriger » on the Plex match (OPEN 9, ruled B) | 10 | on `acq-todo-loaded`: the Plex-match card offers « Confirmer » and « Corriger » on the match itself; a tap on « Confirmer » is ANSWERED on the network (`window.__mocks.answered()`, the operation of demand E) and the card leaves « À traiter »; the same for « Corriger » through its own answer | make the verb toast without calling → the network hold falls; leave the card in the tab after the answer → falls |
| **R-L22-u** — « Abandonner » quarantines, after a confirmation that names the medium (OPEN 10, ruled B) | 11 | walked by finger on the tunnel-error card: a tap opens `acq-abandon-confirm`, whose text contains the card's title, and NOTHING is sent yet; confirming sends `discardStagedMedia` (answered on the network, with its `quarantine_path`) and the card leaves « À traiter »; cancelling sends nothing and the card stays | skip the confirmation → the « nothing sent yet » hold falls; confirm without naming the medium → the name hold falls; send on cancel → falls |

**Phase 4 lands with a unit test, not a rule**: the strip's grid follows its cell count and a five-cell
labelled strip is unchanged (`frontend/maquette/design/src/ui/variants.test.ts` is the home of that family of
tests). A primitive with no consumer of the new shape yet is a primitive no harness rule can hold, which is L20's own
reason for building its disclosure primitive beside its only consumer — here the consumer is the next phase.

**Seeds into existing rules, not new rules of their own** (L20's own precedent for DOIT-9): `harness/states.py`
is seeded with all 23 states (it asserts each renders content, has no horizontal overflow at 390 px and
raises no JS error); `screen_addresses.py` and `back.py` take R-L22-n's addresses; `state_surfaces.py` (R90)
takes `acq-todo-loading` and `acq-todo-error`.

**Mutations are run with `scripts/mutate.sh <file> <expression> <rule…>`, after the commit** (L20's plan: commit
BEFORE every mutation), never by hand — a hand edit leaves the served copy of the previous build in place
(B-303). A guard's exit code is read by hand (B-273).

### 5.1 Rules that ASSERT a behaviour this lot reverses

The opening measure of L13c learned it the hard way: `virtual.py` asserted the OPPOSITE of the ruling its phase
landed and the phase's own measure — which read the writers — had not listed it. The reversals of this lot, and
the rule that asserts each today, found by reading the assertions and not by grepping the word:

| Behaviour reversed | The rule asserting the old one | Phase that re-aims it |
| --- | --- | --- |
| the bar's badge and « En cours »'s count are `takeable + blocked` | **R16**, `harness/audit2.py:244` — on `acq-now-idle` and `acq-now-loaded`, both the badge and the first tab's count | 12 (it IS R-L22-b) |
| a blocked arrival is « drawn on the same tab » as the takeable one | **R128**, `harness/seeds_at_rest.py:236-239` | 9 |
| a cold boot and an at-rest read see « En cours » first | **R128** again (« the boot alone fills the arrivals », the takeable arrival « is DRAWN ») — and the sixteen walks that arrive at Acquisition without naming a tab (`git grep -l -E 'data-page=.?"?acq|nav button\[data-page=.acq|\[data-go=.acq|PAGE_PATHS\["acq"\]|HOME\b|/acquisition"|"acquisition"' -- 'frontend/maquette/harness/*.py' | wc -l` → 16) | 13 |
| « a folder among several offers « Suivant » » and opens the next, replacing its entry | **R57**, `harness/decision.py:171-190` | 14 |
| « answering empties the queue, on BOTH lists », `[data-leave]` included | **R57**, `harness/decision.py:197-215` (its `arr-idle` / `stuck` / `[data-leave]` half) | 15 |
| the bar holds Système, and the pipeline is started from Arrivées by a finger | **R-L20-g** (`locks.py`), **R185** (`queued_by_hand.py`), **R66** (`arrivals.py`), and `page_host.py`'s delegation block | 19, 23, 25 — each re-aim said out loud where it is made (OPEN 6, ruled A) |

A phase whose row is in this table says so in its own « Found », and its « Red today » is written against the
assertion as it stands.

---

## 6. The register rows and the demands touched

### 6.1 The register rows

| Row | State | What happens |
| --- | --- | --- |
| **B-515** — « Réessayer » on the Arrivées error asks again with no pending or busy sign | `open` | **dies with the page** (its surface is `arr-error`). It is a trait of the retry, not of the page: `acq-todo-error` carries the same shape, so phase 13 says whether the new tab reproduces it; the close records the reading |
| **B-531** — « Lancer ensuite » enabled during a run | `fixed #603` | **loses its subject with the bar, and the guarded behaviour with it** (OPEN 6, ruled A: the two acts die, so no lever exists on which an inactive action could look active); the close annotates the row, never reopens it |
| **B-371** — the « En file » pastille reachable by no hand | `fixed #603` | closed history; its rule (R185, `queued_by_hand.py`) starts from Arrivées' launch button and is re-aimed in phase 23, out loud — see below |
| **B-514** — R138 lost its screen half and still claims it (« the arrivals bar draws « Au repos » while the layer runs ») | `open` | the arrivals bar dies, so the claim has no page to be about; the queued reading lives at Système's levers since L20 (`levers-queued`). Phase 23 re-points R138's screen half at the levers or drops the claim, and closes the row |
| **B-037**, **B-038** — `arrivals.py`'s own debts | `open` | **die with the rule** (phase 25 removes `harness/arrivals.py`, R66) |
| **B-538** — a running history row's second line | `open` | **NOT this lot's** (Système's history, a behaviour wave on Système) |
| **B-549** — the seed gives a film a series' identifiers | `open` | **NOT this lot's** (a fixture-identity defect; L22's seeds are derived from rows that do not carry it) |

**Where the queued pastille lives once the launch bar is gone.** The reading B-371 and B-514 protect —
« a pass asked for during a maintenance run is QUEUED, visibly, and never refused » (DOIT-4, §6) — has two
hand paths: Système's levers (`levers-queued`, drawn in L20) and, where a season is asked while a
maintenance command holds the lock, the `season/queued` pastille (R138). **Neither needs the launch bar**:
the second is reached by starting a maintenance command from Maintenance, then asking a season. R185 is
re-aimed on that path in phase 23 (OPEN 6, ruled A: the launch buttons are not on Système either).

### 6.2 The demands PROPOSED (D7) — in the register's own form, not asserted

Five rows the register lacks, each named by the rulings. **They are proposals: the lot files them by
editing `frontend/maquette/contract/openapi.json` and regenerating the register** (`--write`, then
`--check`): demands A–C in phase 1; **demand E in the phase that draws the Plex-match card (phase 10), its first act** (a
sixteenth point in phase 1 would have broken the plan's ceiling, and a demand is filed where its surface is drawn);
demand D in L18's own first phase (L22 draws no rights, however small). The operationIds are proposals and adjust.

| # | operation | operationId | what it is for |
| --- | --- | --- | --- |
| A | `GET /api/acquisition/to-handle` | `readAcquisitionQueue` (re-shaped) | A card for a medium nobody requested: a finished media torrent the sort classified becomes an acquisition card at « arrivé », carrying WHO asked (the account, or the Plex owner for a direct add) and WHERE it came from. Ruling 2; `backend-demands-architecture.md` § 2 |
| B | `GET /api/acquisition/journeys/{infoHash}` | `readJourney` (re-shaped) | One card's ladder from the wish to Plex: ONE list of rungs joining acquisition's stages and the pipeline's nine steps, each with its state (in motion, waiting, blocked with a reason, done), its time, and the current rung; the card's compact position (eight rungs, OPEN 4 ruled B; « rangé » carries its three steps as detail) is read from the same list and `QueueCard.strip` retires. Includes the last rung, « vérifié dans Plex » (nothing in the contract or the mocks names Plex today). Ruling 4 |
| C | `POST /api/staging/media/{mediaId}/reclassify` | `reclassifyStagedMedia` (new) | Put a folder that is not a medium where the sort files its category, and take its card out of the acquisitions; **the destinations it may be filed into are the sort's non-media ones (configuration), so the read that lists them belongs to this demand**; with its inverse, as every resolve needs one (`backend-demands-architecture.md` § 9). Ruling 5 |
| E | `POST /api/acquisition/journeys/{infoHash}/plex-match` | `resolvePlexMatch` (new) | The confirm/correct verb on the Plex match itself: a card in « À traiter » that says « match Plex à confirmer » offers « Confirmer » (the match is the medium) and « Corriger » (it is not) on THAT match, and the answer moves the card. Nothing in the contract or the mocks names a Plex match today (§ 2.1); the match the card names is read by demand B's last rung. OPEN 9 (ruled B); § 20 point 3 |
| D | `GET /api/auth/me` | `readAccount` (re-shaped) | Which places of the application THIS account may open — the input the bottom bar and the drawer compose from. **The shape is L18's**; L22 files the row's existence and nothing else. Rulings 11, 15; § 17 point 4 as dictated on 2026-09-26 |

> **Amended 2026-09-27 (L22b phase 18, RULINGS 14):** a demand OWED, beside the rows above — the engine ends a film's follow when the film is CONFIRMED in the library (the last rung « vérifié dans Plex » done, ruling 3), not at detection as `FilmAcquired` does today (`personalscraper/acquire/detect.py:446`), and it signals that rung's move to done; the maquette's layer carries it on `ItemProgressed` meanwhile.

**Not a sixth row: `discardStagedMedia` already has one** (`docs/reference/frontend-backend-demands.md:105` — the
backend answers `detail`, `journaled`, `media_id`, `quarantine_path`; the maquette declares `{ok}` and calls it
« Leave a staged item where it is »). « Abandonner » (OPEN 10, ruled B) quarantines, so the phase that draws it
RE-DECLARES the operation (phase 11) to what the interface requires — its summary and the two fields the card and its toast
read — and the register's row shrinks instead of a row appearing.

And two by-hand rows in `docs/reference/frontend-backend-demands-stream.md` (§ 2.3): the **birth of a
card** and **a rung's change of state**, as stream events — the operator amends that file, not this lot.

### 6.3 The clause-map rows PROPOSED (the operator amends the map; this lot does not)

Six rows of `docs/reference/product-intent-map.md` name `features/arrivals`
(`grep -n 'features/arrivals' docs/reference/product-intent-map.md`). Each clause keeps its PROOF and changes
its SURFACE; the proposal per row, for the operator:

| Clause | Surface, proposed | Proof it keeps or gains |
| --- | --- | --- |
| **DOIT-1** | `features/acquisition` — the card at each rung, « À traiter » | R63 (a card says what the engine knows) stays; R66's « Arrivées says what really happened » has no page to run on — its live-database half has no successor here and the row says so; R-L22-f gains |
| **DOIT-2** | `features/acquisition` — a card says why it waits, sets aside or is blocked | R57 (a decision with its candidates) at its new home; R-L22-h, R-L22-i |
| **DOIT-3** | `features/system` — the levers (R178, R179); **the launch bar's half has NO surface, BY RULING** (OPEN 6, ruled A: « Lancer » and « Arrêter » a pass die) | R178, R179 stay; the row's wording (« lancer / stopper ») is the operator's to amend — this lot proposes it reads as the levers' pause and resume |
| **DOIT-4** | `features/system` (`levers-queued`, R185 re-aimed) and `features/acquisition` (`acq-card-waiting`, the « En file » season pastille, R124, R138) | R185 re-aimed, R138's screen half re-pointed (§ 6.1) |
| **DOIT-5** | `features/acquisition` — the ladder to Plex, the candidates screen | R57, `ident.py`, R-L22-d, R-L22-f |
| **NE-DOIT-PAS-2** | `features/acquisition` — a card that waits says what it waits for | R-L22-h; R66's live-database bound is gone with it |

**The README's cut table also needs the operator's word.** `frontend/maquette/README.md` § « The cut is by
the nature of the trouble » reads « A medium in trouble → **Arrivées** ». After this lot a medium in trouble
is Acquisition › « À traiter ». The lot's close rewrites the table (phase 27); the sentence is a directive,
so it changes in the same move as the decision (`frontend-architecture.md` § 2, the paragraph that opens it).

---

## 7. What this design does NOT draw, and what was OPEN

### 7.1 Not drawn — and whose it is

- **The Trackers page** — ratio, cross-seed, the tracker itself. **L16 and L17 draw it.** L22 draws no
  placeholder for it.
- **The rights model, and the bar's composition by rights** — **L18's**, the model (ruling 11, § 17 point 4).
  L22 adds no field to the navigation table, no role, no flag.
- **Accounts** — the « Comptes » rubric or the drawer entry (ruling 14) — **L18**. The section « Les autres
  comptes » of Profil leaves Profil there, not here.
- **The engine** — the tunnel per media, the ladder's one source, the birth of a card, the reclassification,
  the requester — **after the freeze of the interface** (§ 20 « Ce que cela impose »; D7). This lot draws
  what the backend owes and mocks it.
- **The media sheet's trace of a film** (« acquis le …, release, demandeur ») — § 3.5: named for the steward
  to assign; not silently dropped.
- **The parallelism bound, pause and resume, the veille** — L20's, drawn; L22 only stops pointing at the page
  that used to point at them.
- **The reassign gesture** — ruling 9's request « réaffectable depuis la carte », an Operator's right — **L18's**,
  born with the rights model (OPEN 11, ruled B); L22 draws the « ajouté par … » line only.
- **« Lancer » and « Arrêter » a pass** — drawn nowhere: they die with the Arrivées bar (OPEN 6, ruled A), and no
  lever takes them over.

### 7.2 The eleven OPEN design questions — RULED

**All eleven are ruled, by the operator, on 2026-09-26 (round 5, relayed by the auditor); nothing below is open.**
Each keeps its number, its question and its two readings as they were written, with NO choice made by this
document; the operator's answer follows in one line, and is carried into the body where it bites (the section
named at the end of the line).

**OPEN 1 — the ORDER of the four tabs.** Ruling 10 dictates a fourth tab and a default rule, not a place.
*Reading A*: « À traiter » first, so the tab that opens by default is also the leftmost — the reading order
follows urgency, as the sections of « En cours » do. *Reading B*: « En cours » stays first and « À traiter »
takes the second place — the operator's existing habit of a tab bar that starts where it always started.
Nothing else in this design depends on it (§ 4 is order-independent; R-L22-e reads all four whatever their
order).

**Ruled 2026-09-26 (operator): « Suivis, En cours, A traiter, Découvrir » — outside both readings: the tabs read « Suivis · En cours · À traiter · Découvrir », and the default-tab rule of ruling 10 stays whole (§ 3.1, R-L22-e).**

**OPEN 2 — how a bar with two filled places and two free ones is drawn before L16.** *Reading A*: two
places sharing the bar's width, like a two-tab control — the free places are not drawn at all (a page that
does not exist has no slot). *Reading B*: the four-slot geometry is kept and two slots are empty — the bar
does not change shape when Trackers arrives (§ 12: a persistent chrome, `frame-model.md` P1). Ruling 15
says the fourth place is « libre jusqu'à ce qu'une page quotidienne la mérite », which reads either way.

**Ruled 2026-09-26 (operator): « A, la barre du bas s'adapte toujours au nombre de boutons présents, chaque bouton prend toujours le même ratio. 2 boutons (50/50), 3 boutons (33/33/33), 4 boutons (25/25/25/25). 4 boutons c'est le max, 2 boutons le min. » — reading A, as a general frame rule: only the present buttons are drawn, in equal shares of 1/n, n from 2 to 4, no empty slot; a rule written and mutated (§ 3.6, R-L22-s).**

**OPEN 3 — whether a card born of an arrival appears in « Suivis » at all.** *Reading A*: never — a follow
and an acquisition are different things (ruling 1: « jamais un suivi »), « Suivis » lists follows only, and
the card lives in « En cours » / « À traiter » until it is shelved; a follow appears there only when the
operator taps « Suivre ». *Reading B*: a series' card that has been followed shows under its follow row
as « un épisode vient d'arriver » — the follow row is where the operator looks for a series, and an arrival
of a followed series is news about that row.

**Ruled 2026-09-26 (operator): reading A — a card born of an arrival NEVER appears in « Suivis », even an episode of a followed series; it lives in « En cours » or « À traiter »; reading B refused (§ 3.5, R-L22-l).**

**OPEN 4 — the rungs' names and number.** Ruling 4 proposes ten names and says they adjust. *What the
drawing may change*: **A** — keep ten rungs and shorten a name so it fits on line 2 at 390 px; **B** — merge
adjacent rungs the operator never distinguishes (« trié / enrichi / rangé » are three steps of the same
place in the pipeline) into fewer, and let the journey sheet keep the fine detail. The count on the card
(« n sur 10 ») follows whichever is taken.

**Ruled 2026-09-26 (operator): reading B — « trié · enrichi · rangé » merge into one rung « rangé »: the card's ladder has eight rungs (demandé → cherché → attrapé → téléchargement → arrivé → identifié → rangé → vérifié dans Plex), the card reads « n sur 8 », and the journey sheet keeps the three steps in detail; reading A refused (§ 3.2, R-L22-f).**

**OPEN 5 — what `/arrivals` does once the page is gone.** *Reading A*: it is an address nobody serves — the
not-found page, like any other (`app/not-found.tsx`; `NOT_FOUND_ROW`), and a bookmark or an installed
app's restored tab lands there. *Reading B*: a redirect onto `/acquisition` with « À traiter » open — the
page's job moved and the address follows it. DOIT-10 (« retrouvable ») is served by B for a stale link;
A carries no code and no second address to keep.

**Ruled 2026-09-26 (operator): « A, l'app n'est utilisée que par 2 personnes pour l'instant. » — reading A: `/arrivals` becomes an unknown address like any other, the not-found page, no redirect; reading B refused (§ 1.3, R-L22-o).**

**OPEN 6 — the launch and the stop of a pipeline pass have no home.** § 1.2: the two acts live only on the
pilot's bar, which dies (ruling 2), and Système's levers (L20) do not carry them. *Reading A*: they die too
— §20 makes the pipeline a tunnel per medium, a pass « now » is what the levers' « Relancer la veille » and
each card's « Récupérer maintenant » / « Relancer » already do, and §1's « lancer / stopper » is read as
the levers' pause and resume. The cost of A is in the harness: the four rules that start a pass by finger
(§ 1.5) lose their finger and re-aim onto the maintenance path or the mock's own door, so B-371's shape —
no `__go` between the hand and the pastille — holds for the season path only. *Reading B*: they move to Système's « Le pipeline » section as two more levers
— DOIT-3 says « agir là où l'on observe » and the levers section is where global acts live since L20.
The plan costs either the same: phase 25 deletes the bar; reading B adds two buttons and their rule to an
existing section, as ONE added phase, and reading A adds nothing.

**Ruled 2026-09-26 (operator): reading A — « Lancer » and « Arrêter » a pass die with the Arrivées bar, no phase added; the cost accepted is that the four rules that started a pass by finger re-aim onto another path, and the phase that does it says the re-aim out loud; reading B refused (§ 1.2, § 1.5).**

**OPEN 7 — the progression « n sur m en attente » on the candidates screen.** It existed to serve
« Suivant », which dies. *Reading A*: it dies with its button — a count that leads nowhere is noise on a
phone. *Reading B*: it stays as information (« 1 sur 2 en attente »): it tells the operator how many others
await, and « À traiter »'s tab carries the same figure.

**Ruled 2026-09-26 (operator): reading A — « n sur m en attente » dies with « Suivant » on the candidates screen, and the « À traiter » tab count carries the number; reading B refused (§ 3.4, R-L22-d).**

**OPEN 8 — what Système's badge on the menu button counts.** Ruling 12 says « la maintenance parle sur
Système ». *Reading A*: maintenance facts only — a stale lock, leftover temporary entries, a sweep that did
not finish (what L20's locks section already names). *Reading B*: also the machine's faults — a service that
stopped answering, a dependency that is down (`readServices`, `readDependencies`). B says more; A keeps
the badge to what the operator can DO from Maintenance.

**Ruled 2026-09-26 (operator): reading B — Système's badge on the menu button counts the maintenance facts AND the machine's faults (`readServices`, `readDependencies`); reading A refused (§ 3.6, R-L22-c).**

**OPEN 9 — what a Plex-mismatch card asks of the hand.** Ruling 7 names « un match Plex à confirmer »
(§ 3). *Reading A*: the card offers « Résoudre → » only — the operator re-identifies through the candidates
screen and the engine's own guard repairs the Plex side afterwards. *Reading B*: it offers a confirm or a
correct on the match itself — a verb that exists in no contract today, so a fifth demand row.

**Ruled 2026-09-26 (operator): reading B — the « match Plex à confirmer » card offers « Confirmer » and « Corriger » on the Plex match itself, and a FIFTH demand row (the confirm/correct verb on the match) is PROPOSED in § 6.2; reading A refused (§ 3.3, R-L22-t).**

**OPEN 10 — what « Abandonner » does on a tunnel error.** Ruling 7 says « relancer / abandonner ».
*Reading A*: abandon the TUNNEL — stop following the medium and leave its files where they are, for
Maintenance to see. *Reading B*: quarantine the folder (`discardStagedMedia` — journaled, with
`quarantine_path`) after an explicit confirmation naming the identity (NE-DOIT-PAS-6).

**Ruled 2026-09-26 (operator): reading B — « Abandonner » quarantines the folder (`discardStagedMedia`, journaled, `quarantine_path`) after a confirmation naming the medium (NE-DOIT-PAS-6), and the card leaves « À traiter »; reading A refused (§ 3.3, R-L22-u).**

**OPEN 11 — where the reassign gesture is drawn.** Ruling 9 dictates a card reassignable to another account
from the card, an Operator's right. *Reading A*: L22 draws it, against the mock's single Operator account —
the gesture is on the card the ruling names, and L18 later gates its OFFER. *Reading B*: L22 draws the
requester LINE only and the gesture is L18's — offering a right-dependent act before the rights model exists
is the small rights model the non-goals forbid.

**Ruled 2026-09-26 (operator): reading B — L22 draws the « ajouté par … » requester line only, and the reassign gesture is born with L18; reading A refused (§ 3.2, § 7.1).**

---

### 7.3 The operator's rulings of 2026-09-26, evening (rounds 6 and 7) — they SUPERSEDE the sentences they name

Relayed by the auditor, written in `docs/reference/operator-method.md`; each is carried at the site it changes by a
dated line, and the plan by phase 13's amendment, the new phase 14-bis and phase 15's amendment.

1. **The default tab** (replaces ruling 10's opening rule), verbatim: « Suivis par défaut, puis le dernier onglet
   ouvert (mémoire locale) ». First opening → « Suivis »; afterwards → the last tab opened, kept in local storage on
   the device, read and written under try/catch, « Suivis » when it is empty or unreadable. The fourth tab, its count
   and the bar's badge = « À traiter » alone hold. → phase 13 (R-L22-a re-written: empty storage → « Suivis »,
   storage « À traiter » → « À traiter », a throwing storage → « Suivis »).
2. **« À récupérer » leaves « En cours »** (A). « Récupérer maintenant » stays on the follow's sheet, which says
   « trouvé, récupéré à la prochaine passe, à <heure> ». → phase 14-bis.
3. **« Rangé aujourd'hui » and « Cherché, rien trouvé » leave « En cours »** (A), which keeps « En vol » ALONE, its
   queue included, and says « rien en cours » when nothing moves. What arrived reads in the Médiathèque's
   « Récents »; what was not found reads on the follow (out, not grabbed), and a live search confirms it with
   « aucun torrent trouvé ». The contract's `notFound` and `doneToday` families lose their consumer: noted, not
   removed (the engine's side is not this lot's). → phase 14-bis.
4. **Ruling 16 — « Mis de côté »** (revises ruling 6's place), verbatim: « comme pour les suivis stoppés c'est une
   section repliée en fin de À traiter avec les mis de côté, oui ça ne disparaît pas car de vrais fichiers sont sur
   la machine et doivent être traités. Mais via cette section pliée en fin de À traiter je peux : 1) les voir pour
   pas les oublier. 2) les supprimer via cette section avec un message de confirmation un peu comme quand on
   supprime de la médiathèque (même précaution), 3) les supprimer directement du disque et ils disparaissent de
   "mis de côté", 4) les traiter. » A folded section at the END of « À traiter », outside its count and the bar's
   badge. → phase 15 (L22b).
5. **Consequence for what L22a already built** (read on its branch, 2026-09-26): phase 5's `acq-card-rungs` reached
   six rungs through the takeable, not-found and done-today rows (ruling 2 of `RULINGS.md` is re-read at 14-bis);
   phase 6 files arrivals into « Rangé aujourd'hui »; phase 7's requester lines sit on those cards; phase 10 moved
   one row out of « Rangé aujourd'hui »; phase 12's « En cours » count reads `takeable`. Phase 14-bis REMOVES; a
   phase that removes is cheaper than one that adds.

