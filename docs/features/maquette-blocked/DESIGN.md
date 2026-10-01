# « À traiter » holds every block — every blocked tunnel, its cause, its lift, its door · DESIGN

Contract: the operator's rulings Q7, Q8 and Q9 of 2026-10-01 (`docs/reference/operator-method.md` § 3, lines
« 10-01 · Q7 », « Q8 », « Q9 »; `docs/reference/backend-brief.md` § 5 and § 6 K4). They are not reopened here.
Verbatim, the parts that draw:

- Q7: « UNE liste « À traiter » porte TOUT ce qui est bloqué et demande une intervention, dans l'app ou ailleurs
  (disque plein, ratio trop bas, tracker injoignable — « qui fait de la place sur le disque ? » — comme identité,
  correspondance Plex, erreur) ; chaque carte dit sa cause, ce qui la lève et où elle se règle (Système › Disques,
  « Voir le tracker », ses réglages) ; le pipeline REPREND DE LUI-MÊME dès que le moteur voit la cause levée, et la
  carte part ; le badge d'Acquisition compte toute la liste. AMENDE la décision 7 du 09-15 […] et déplace la carte
  différée d'« En cours » vers « À traiter ».
- Q8: « un tunnel dont le média a disparu (torrent retiré, fichiers absents) se ferme avec sa raison ; la carte le dit
  une fois dans « À traiter », écartée par « × » (= vu) ; rangé à la main ailleurs, il part simplement ; un média qui
  revient plus tard ouvre un nouveau tunnel. »
- Q9: « au rangement, le DERNIER CHOISI gagne […] une release choisie plus tôt qui arrive après n'est PAS rangée, son
  torrent continue de semer, son tunnel se ferme avec la raison « remplacé par un choix plus récent », dite une fois
  dans « À traiter », écartée par « × ». »

**Wording, binding on every sentence addressed to the operator**: « carte d'acquisition », never « carte » of an
episode alone (the season-recovery lot's rule, kept). In this English document « card » always means the
acquisition card, and « block » a tunnel stopped on a rung of its ladder.

This document is written for a session that has none of the context it was produced in. **Nothing under
`frontend/maquette/` was touched to write it** — no code, no rule, no mock, no seed, no harness run: prose and
numbers. Every figure carries what produced it, read from the worktree root.

**Written 2026-10-01, on `main` at `ca09123ee`**, branch `docs/maquette-blocked`. The code is built by the lot the
orchestrator names, after ONE operator round on § 5's OPEN questions. Rule numbers are reserved from **R500**.

---

## 0. What the lot owes, said once

| # | Subject | Source | Held at |
| --- | --- | --- | --- |
| 1 | every block that needs an intervention, in the app or ELSEWHERE, is a card of « À traiter » — none stays in « En cours » | Q7 | § 1.1, § 1.2 |
| 2 | each such card says its cause, what lifts it, and links where it is settled | Q7 | § 1.2, § 1.3 |
| 3 | an external cause lifted, the card leaves on its own and the tunnel resumes — no gesture | Q7; § 20 point 2 | § 1.4 |
| 4 | a tunnel whose medium vanished closes with its reason, said ONCE in « À traiter », dismissed by « × » | Q8 | § 1.5 |
| 5 | a release chosen earlier and arrived later is not filed; « remplacé par un choix plus récent », once, « × » | Q9 | § 1.6 |
| 6 | the deferred card moves from « En cours » to « À traiter » | Q7 | § 1.1 |
| 7 | the Acquisition badge counts the whole list | Q7 | § 1.7 |
| 8 | every element drawn by the one component that already draws it — no parallel component | the brief; principles 09-29 | § 1.8 |
| 9 | every case a named state; each change with the rule that bites and the backend demand it implies | orders 76, 77; brief K4 | § 3, § 4, § 6 |

### 0.1 As it is — « À traiter » and « En cours » on tm-design at 390 px

Read on `https://tm-design.iznogoudatall.xyz` (build of `ca09123ee`'s line), signed in, a 390 × 844 phone context,
each named state asked through `window.__go`. Captures under `/private/tmp/blocked-shots/` (never committed): one PNG
per state below, and `<state>-subject.png` scrolled to the subject card.

| Named state | « En cours » (count) | « À traiter » (count) — its sections and cards | Acquisition badge |
| --- | --- | --- | --- |
| `acq-now-loaded` (dense) | 6 — « En vol »: Silo · S03, This City Is Ours · S01E06, President Curtis, Furious, The Alabama Solution, Conclave | 3 | 3 |
| `acq-todo-loaded` (real) | — | 2 — « À résoudre »: Lucky · S02E07 (« Résoudre → »); « Une étape ne passe pas »: Top Chef Le Concours Parallèle (« Relancer », « Abandonner ») | 2 |
| `acq-todo-dense` | 6 | 3 — « À résoudre »: Lucky, Backrooms.2026.MULTi.2160p.WEB-DL, S.W.A.T. | 3 |
| `acq-todo-empty` | — | 0 — « Rien n'attend votre main. Ce qui avance sans vous est dans « En cours ». » | none |
| `acq-card-plex-disagrees` | — | 3 — « À résoudre » (Lucky), « Match Plex à confirmer » (Star Trek: Strange New Worlds, « Confirmer », « Corriger »), « Une étape ne passe pas » (Top Chef) | 3 |
| `acq-card-follow-error` | 5 | 4 — « À résoudre » × 3, « Une étape ne passe pas »: Furious · S01E01 (« Relancer », « Abandonner »), **no cause line** | 4 |
| `acq-card-set-aside` | — | 1 — « Une étape ne passe pas » (Top Chef); « Mis de côté » folded, 1 (Lucky, « Résoudre → », « Supprimer ») | 1 |
| `acq-card-deferred-ratio` | **6** — This City Is Ours: « Différé : le ratio sur c411 est sous son seuil de 1. », « Voir le tracker » | 3 | **3** |
| `acq-card-deferred-space` | **6** — This City Is Ours: « Différé : pas assez d'espace pour le recevoir. », **no link** | 3 | **3** |
| `acq-card-deferred-missing` | **6** — This City Is Ours: « Différé : une partie du contenu manque encore. », **no link** | 3 | **3** |
| `acq-card-waiting` | 6 — four cards « En file — ce passage attend que la maintenance en cours se termine. » | 3 | 3 |

Measurements that correct or fix the premises (paths under `frontend/maquette/design/src/`):

1. **The deferred card is in « En cours » by construction, twice over.** The deferral is POSED
   (`mocks/handlers/posed-deferral.ts:26`, `poseDeferral`) on « This City Is Ours », a row of `queue.inFlight`
   (`mocks/seeds/in-flight.json`, the fifth row), its rung « arrivé » set `waiting` with the cause token. « À traiter »
   reads `todoCards` (`lib/arrival-slots.ts:43`): `queue.blocked` and the ARRIVALS whose ladder holds a `blocked` rung
   (`:29`). A row of `queue.inFlight` never reaches it, whatever its ladder says; and a `waiting` rung is not
   `blocked`. Both must change for the card to move.
2. **The badge does not count a deferral.** `acquisitionBadge` (`features/acquisition/queries.ts:388–398`) counts
   `todoCards` filtered by `isOwn`: on every `acq-card-deferred-*` state it reads 3, as at rest. One derivation
   already (§ 13) — moving the card into `todoCards` moves the badge with it.
3. **The engine knows three deferral causes, and only three.** `personalscraper/ingest/deferral.py:39–41`:
   `ratio_below_threshold`, `content_missing` (« the client's `content_path` is unknown or absent », the volume
   unmounted — `:61`), `insufficient_space` (the STAGING disk, `:64`). Each is documented « self-healing »
   (`:15`): the engine already re-reads them every pass. No cause token exists for a tracker, a provider, Plex or
   qBittorrent that does not answer, nor for a library with no disk to receive a medium.
4. **Only the ratio cause has a door.** `features/acquisition/card-markup.ts:238–242` adds « Voir le tracker »
   (`data-go="trackers"`, `data-dial="trackers:<name>"`) for `ratio_below_threshold` alone. The space and missing
   causes draw no link. **Système has no landing door**: `fillLandingDoor` is filled by Acquisition
   (`features/acquisition/verbs.ts:136`) and Trackers (`features/trackers/verbs.ts:44`) only; Système's « Disques »
   and « Dépendances » are bare headings (`features/system/page.tsx:122`, `:132`). A setting has a panel address,
   `?panel=setting:<file>:<key>` (`features/settings/panel-setting.ts:10`, `:86`).
5. **Where the unreachable services would be read.** Système › Dépendances serves Redis, TMDB / TVDB and
   qBittorrent (`mocks/seeds/dependencies.json`) — **no Plex row**; a tracker's entry carries no reachability fact
   (`mocks/seeds/trackers.json` keys: `name`, `ratio`, `downloadedBytes`, `uploadedBytes`, `trend`,
   `alertThreshold`, `enabled`, `disabled`, `brokenObligations`).
6. **A card of « À traiter » without its cause exists today.** On `acq-card-follow-error`, Furious · S01E01 stands
   under « Une étape ne passe pas » with no reason line at all (capture `acq-card-follow-error-subject.png`): the
   posed tunnel error (`harness/states/tunnel.ts`, `poseTunnelError("Furious", "scrape")`) carries a failed step and
   no sentence. Q7's « chaque carte dit sa cause » makes it a defect (§ 6, register row).
7. **What waits behind a maintenance run is a queue, not a block.** `acq-card-waiting`'s « En file — … » cards lift
   with no intervention of anyone: Q7 names what « demande une intervention ». They stay in « En cours » (DOIT-4's
   visible queue), as R209 hold 4 reads today; the supervisor's own queue at `max_parallel` (Q5) is the same case.
8. **Q8 changes what the engine does today.** `requeue_missing` (`personalscraper/acquire/_wanted_store.py:585`)
   sends a row whose torrent vanished back to `pending`, its hash cleared — silently re-opened, the opposite of
   « se ferme avec sa raison ».
9. **Q9's choice date half exists.** `staging_provenance.grabbed_at` is kept per torrent hash
   (`personalscraper/acquire/_provenance_store.py:173`, `:325`). Nothing read links a file in the library to the
   hash that filed it — K4 checks it first, as the brief says.
10. **The « × » exists on a message, not on a card.** The message's close (`ui/toast.tsx:80–86`, `#toastx`,
    `icons.x`, `aria-label` `message.close`) is the A6 « × = vu » of 09-12; the card (`ui/card-markup.ts`) draws a
    foot of labelled buttons (`CardFoot`, `:60`) and no close.
11. **Near the ceiling.** `harness/states/tunnel.ts` is at 322 lines (`wc -l`), `features/acquisition/todo-tab.tsx`
    at 217, `lib/arrival-slots.ts` at 174: the new named states go in a file of their own
    (`harness/states/blocked.ts`), the season-recovery lot's precedent.

### 0.2 What the lot builds on, and does not redraw

| Landed | Read as |
| --- | --- |
| L22 — the acquisition card (`ui/card-markup.ts`, `features/acquisition/card-markup.ts`), its eight-rung ladder | every new card, unchanged in anatomy: the cause and the lift are its reason line, the door is its foot |
| Ruling 10 / R209 — « À traiter » a tab of its own, sections by what unblocks, a pip and a count per section, an empty section not drawn | the tab's shape, kept; Q7 adds sections, amends ruling 7's « ce que seule sa main débloque » |
| Ruling 16 / R226 — « Mis de côté » folded last, outside every count | kept, last |
| R265 — the three deferral causes said on the card, the ratio cause naming its tracker and THAT tracker's threshold | kept, MOVED to « À traiter » |
| The named landing — `trackers:<name>`, `now:<acquisition>` | the doors' shape; Système gains one, ADAPTED (§ 1.3) |
| A6 (09-12) — « × » = « vu » | the dismissal of a closure card (§ 1.5, OPEN 2) |
| R236 — the badge observed from any page; live events invalidate the queue | the auto-resume is read through it (§ 1.4) |

### 0.3 Conformity to the operator's principles (`operator-method.md` § 1, 09-29)

| Principle, his words | Where this design holds it |
| --- | --- |
| « Il faut uniformiser les comportements. Sauf exception volontaire de ma part. » | every block is ONE card in ONE list with ONE anatomy — cause, lift, door; every external cause behaves the same: posed, said, linked, lifted, gone. No exception declared |
| « on crée pas de nouveau composant on adapte » | § 1.8: nothing new; two adaptations written — Système's landing door, the card foot's « × » option |
| « seule une maquette montrant tout les cas possibles est utile. » | § 3: one named state per cause, per lift, per closure, per door, plus the dense and the empty |
| « tout doit être responsive » | the cause and the lift share the reason line (wraps, never truncated, DOIT-9); two feet at most per card; checked at 320 px by R-conformity-a in CI |
| « une différence entre film et série » | every cause holds for a film and an episode alike; Q9 says « pour TOUS les médias, films compris »: § 3 poses one superseded FILM |
| § 16 — Retour replays the arrival path | every door is a link inside a page: it stacks; Retour from the landing gives « À traiter » back (§ 1.3) |

---

## 1. The surfaces

Copy is given in « guillemets » as `fr.json` will carry it; the key proposed beside it. Every string is extracted,
never typed in code.

### 1.1 The move — the deferred card leaves « En cours »

**The rule.** A tunnel stopped on a rung for a cause that needs an intervention is a card of « À traiter », wherever
the queue's answer holds it (in flight, arrival, blocked). « En cours » keeps what moves and what waits in a visible
queue (§ 0.1 item 7); it draws no block.

**Where it is decided — once.** In `lib/arrival-slots.ts`, never in a tab: `todoCards` reads EVERY list of the
answer and takes each card whose current rung is a block or whose tunnel is closed and not yet seen (§ 2's fields);
`inFlightCards` excludes exactly those. « En cours », « À traiter », their counts, the badge and `tabHolding` (the
season pointer's landing) read the same two functions — the pointer of an absorbed episode whose season card is
deferred then lands on « À traiter » with no change of its own.

**The three deferral causes move as they are**, words kept (`surfaces.ladder.reasons.*`), the ratio card keeping
« Voir le tracker » and its threshold wording (R265 holds 1, 5, 6, 7 unchanged).

**The note of « En cours »** (`screens.acquisition.nowNoteRest`) ends « … ce qui attend votre main est « À
traiter » »: it becomes « … ce qui est bloqué est « À traiter » ». The empty « À traiter » (`todoEmptyTitle`,
`todoEmptyBody`) becomes « Rien n'est bloqué. » / « Ce qui avance est dans « En cours ». » — the old sentence says
« votre main », which Q7 amended.

### 1.2 The external causes — each one a card, its cause, its lift

**Its component: the acquisition card, unchanged** — `mediumCardMarkup` over `cardMarkup`. Its strip stops on the
rung the tunnel stopped on; its chip names that rung (in the tone OPEN 3 settles); its **reason line carries two
sentences**: the cause, then what lifts it. Its foot carries the door (§ 1.3). Its body opens the medium's panel, its
poster the sheet — as every card.

| Cause token (engine) | Rung | Cause sentence (`surfaces.ladder.reasons.<token>`) | Lift sentence (`surfaces.ladder.lifts.<token>`, proposed) | Door (§ 1.3) |
| --- | --- | --- | --- | --- |
| `ratio_below_threshold` (exists) | arrivé | « Différé : le ratio sur {{tracker}} est sous son seuil de {{minimum}}. » (kept) | « Il repart seul dès que ce ratio dépasse {{minimum}}. » | « Voir le tracker » → `trackers:<name>` (exists) |
| `ratio_below_threshold`, no threshold (exists) | arrivé | « Différé : le ratio sur {{tracker}} est trop bas, et ce tracker n'a aucun seuil réglé. » (kept) | « Il repart seul dès que ce ratio remonte. » | « Voir le tracker » |
| `insufficient_space` (exists) | arrivé | « Différé : pas assez d'espace sur le disque de staging pour le recevoir. » (reworded: it names WHICH disk) | « Il repart seul dès que la place est faite. » | « Voir les disques » → Système › Disques |
| `content_missing` (exists — OPEN 4 = A) | arrivé | « Différé : le disque où qBittorrent l'a téléchargé n'est pas lisible. » | « Il repart seul dès que ce disque est de retour. » | « Voir les disques » |
| `library_full` (new) | rangé | « Aucun disque de la médiathèque n'a la place de le recevoir ({{size}}). » | « Il est rangé seul dès qu'un disque a la place. » | « Voir les disques » |
| `tracker_unreachable` (new) | attrapé | « {{tracker}} ne répond pas : le torrent ne peut pas être récupéré. » | « Il repart seul dès que {{tracker}} répond. » | « Voir le tracker » |
| `provider_unreachable` (new) | identifié | « {{provider}} ne répond pas : l'identification attend. » | « Elle reprend seule dès que {{provider}} répond. » | « Voir les dépendances » → Système › Dépendances |
| `plex_unreachable` (new) | vérifié dans Plex | « Plex ne répond pas : le match ne peut pas être vérifié. » | « La vérification reprend seule dès que Plex répond. » | « Voir les dépendances » |
| `client_unreachable` (new) | téléchargement | « qBittorrent ne répond pas : le téléchargement n'est plus suivi. » | « Le suivi reprend seul dès que qBittorrent répond. » | « Voir les dépendances » |

**A block that needs his JUDGEMENT keeps its card and its acts** — « Résoudre → », « Confirmer » / « Corriger »,
« Relancer » / « Abandonner »; Q7 adds one obligation to them: a cause line, always. The tunnel error with no
sentence (§ 0.1 item 6) reads the failed step's own words: « L'étape « {{step}} » a échoué. » (`surfaces.card.failedStep`,
proposed) when the engine serves no sentence — never nothing.

**One shared cause, many cards.** qBittorrent down blocks every tunnel at once: each tunnel is its own card (Q6: a
tunnel per release), each saying the cause. How they are grouped is OPEN 1.

**What is NOT an external block**: a maintenance run in progress, the supervisor's queue at its bound — both in
« En cours », « En file — … » (§ 0.1 item 7); a stalled download the re-switch handles (it moves on its own and says
so on its card in « En cours »).

### 1.3 The doors — where each cause is settled

**Its component: the card foot** (`actionButton({ kind: "cardFoot" })`), a `data-go` + `data-dial` pair the
document delegation already reads — « Voir le tracker »'s mechanism, GENERALISED from the ratio cause to every
external cause by one table in `features/acquisition/card-markup.ts` (cause token → page, dial, label), replacing the
single `ratioDeferralTracker` branch (`:145`, `:238–242`).

| Door | Lands on | Mechanism |
| --- | --- | --- |
| « Voir le tracker » (`screens.acquisition.ratioReasonTracker`, exists) | Trackers › « Trackers », the tracker's panel open | `trackers:<name>`, exists (R265 hold 6) |
| « Voir les disques » (`screens.acquisition.blockDisks`, proposed) | Système, its « Disques » heading in view and focused | `data-go="sys"` `data-dial="disks"` — **ADAPTED**: Système gains a landing door (`fillLandingDoor`) that scrolls to the named section; no dial is stored (the page has no tabs) |
| « Voir les dépendances » (`screens.acquisition.blockDependencies`, proposed) | Système, « Dépendances » in view, the dependency's row named | `data-dial="dependencies"`, the same door |

**What the landing shows must say the same cause** (§ 13: two surfaces, one truth): the « Disques » section already
says « nearly_full » per disk; « Dépendances » gains a **Plex** row (seed and demand BK6) and each row says
« ne répond pas depuis {{time}} » when it does not; the tracker's panel gains the fact « Joignable » / « Ne répond
pas depuis {{time}} » (`screens.trackers.reachability`, proposed; demand BK6). A door that lands on a page saying
nothing of the cause is a broken promise — R502 reads both ends.

**Its settings** (Q7, « ses réglages »): the ratio threshold is settled on the tracker's panel already (DOIT-13, the
policy beside the figure); no second door is drawn. A card offers at most TWO feet (320 px; § 0.3).

**Navigation (§ 16).** Each door is a link inside a page: it STACKS. Retour from Système or Trackers gives « À
traiter » back, its scroll kept — walked by finger (R502).

**Rights (§ 17).** A door is navigation, not an act: an account that may only read the card still sees it when it
may open the page landed on; where it may not (Système is `system.view`), the door is not drawn and the cause and
lift lines still are (DOIT-12: the cause is visible, the door absent is not a lie — the page is not his).

### 1.4 The auto-resume — the card leaves on its own

**What he sees.** On « À traiter », This City Is Ours stands under its cause. The engine sees the cause lifted (the
disk has room, the ratio passed, the service answers): a live event invalidates the queue; the card leaves « À
traiter » with no gesture, the section goes with its last card, the tab's count and the badge drop by one, and the
card stands again in « En cours » at the rung it stopped on, the rung now `now`. Nothing else is drawn (OPEN 5).

**Where it reads.** The queue's answer and its live invalidation (R236's observer); the interface computes nothing
— the engine decides the lift (BK2). Its journey (the panel) keeps the trace: the rung's history reads « bloqué —
{{cause}} » then « repris » with their times (the journey's existing rung lines; field in § 2).

**One cause lifted for many cards** (qBittorrent back): every card it held leaves together; a card held by another
cause stays.

### 1.5 The vanished medium (Q8) — closed, said once, « × »

**Its component: the acquisition card.** The strip stops where the tunnel was; the chip reads « clos »
(`surfaces.ladder.closed`, proposed) in the neutral tone; the reason line says why:

- torrent removed — « Le torrent a été retiré de qBittorrent : ce parcours est clos. »
  (`surfaces.card.closure.torrent_removed`);
- files absent — « Ses fichiers ont disparu du disque de qBittorrent : ce parcours est clos. »
  (`surfaces.card.closure.files_absent`).

The lift line reads « S'il revient, un nouveau parcours s'ouvrira. » (`surfaces.card.closure.reopens`). Its foot: «
Voir la fiche » where a sheet stands behind it (`panels.journey.seeSheet`, exists), then « × » — dismissal = « vu »
(A6), where OPEN 2 places it. A tap on « × » removes the card everywhere for that account, at once (optimistic, the
error said and the card restored if the write fails — NE-DOIT-PAS-5), and it does not come back on a reload (the
seen mark is the engine's, BK5).

**Filed by hand elsewhere** — the medium appears in the library by its provider identifiers: the tunnel ends with no
card at all (« il part simplement »). **A medium that comes back** opens a new tunnel: a fresh card in « En cours »;
the closed one, if not yet seen, still says its own once.

### 1.6 The superseded release (Q9) — not filed, still seeding, said once, « × »

**Its component: the acquisition card.** Strip stopped on « rangé », not done; chip « clos »; reason line:
« Remplacé par un choix plus récent : {{winner}} est en place. » (`surfaces.card.closure.superseded`, `winner` the
release line of the file in place); lift line: « Son torrent continue de semer. » (`surfaces.card.closure.seeding`).
Foot: « Voir la fiche » (the library holds the winner), then « × ». The torrent stays a row of Trackers › « Torrents »,
seeding — no change there, and none is drawn (the row is honest already).

**For every medium, films included**: the same card for a season pack that came after a later-chosen episode, and
for a film whose 2160p arrived after the later-chosen 1080p (§ 3 poses both).

**The pack superseded ONE episode only.** The tunnel is per release (Q6): the pack is filed, save the episode whose
file in place was chosen later; the pack's card goes on to « rangé »; the one episode is named in the pack's journey
(« S03E07 — gardé : choisi plus récemment », `panels.journey.keptNewer`, proposed). No card for it: nothing was
closed — the pack's tunnel went to its end. The superseded card exists only when a WHOLE release is not filed.

### 1.7 The badge

The Acquisition badge is `todoCards`' count for the account (§ 1.1) — every section of « À traiter », the external
blocks and the unseen closures included, « Mis de côté » excluded (ruling 16 stands). No new derivation: the move
of § 1.1 moves it. On a page that draws nothing of Acquisition it follows the live events (R236).

### 1.8 The design system, element by element

| Element | The one component that draws it | New? |
| --- | --- | --- |
| A blocked card, any cause | `mediumCardMarkup` → `cardMarkup` | no |
| The cause and the lift | the card's reason line, two sentences | no |
| The stopped rung | `ladderMarkup`'s strip and chip (`features/acquisition/card-markup.ts:150`) | no |
| A door | `actionButton({ kind: "cardFoot" })` + `data-go` / `data-dial`, the ratio door generalised | no |
| Système's landing | `fillLandingDoor` (`lib/shell-doors.ts:176`), as Trackers fills it | **adapted**: a door for a page without tabs |
| « × » on a closure card | a `CardFoot` option drawing `icons.x` with an `aria-label`, the message close's icon and its word | **adapted**: the foot option takes an icon |
| A section of « À traiter » | `sectionInnerMarkup(pip, title, count, inner)` (`todo-tab.tsx`) | no |
| The reachability fact on a tracker's panel, the Plex row | the panel's `faits` block; Système's fact list | no |
| The auto-resume | nothing drawn — the card's own leaving | no |

**Nothing new is drawn.** Two adaptations, written here as the office asks.

---

## 2. The contract and the mocks

**The contract first** (`scripts/compare-contracts.py --check` refuses a field apart from its schema).

- The rung's `reason` keeps carrying the cause token (`contract/types.d.ts:2016`); its token set grows by
  `library_full`, `tracker_unreachable`, `provider_unreachable`, `plex_unreachable`, `client_unreachable`. The rung
  gains `resumes: "auto" | "hand" | null` — who lifts it, the ENGINE's classification (never the interface's guess
  from the token), and `blockedSince: number | null` (epoch). `tracker` / `minimumRatio` (exist) are joined by
  `provider: string | null` and `size: number | null` (bytes, for `library_full`).
- The card gains `closure: { reason: "torrent_removed" | "files_absent" | "superseded"; at: number; winner: string |
  null } | null` — present until the account has seen it.
- A new operation `dismissClosure` (`POST`, the acquisition's key) — `200 {ok}`, idempotent; declares `403`.
- `readAcquisitionQueue` answers blocks wherever they stand; `todoCards` reads `resumes` and `closure`, never a token
  list of its own.

**The mocks.** Posed, never seeded where the real world has none (RULINGS 7): `poseBlock(title, token, details)`
generalises `poseDeferral`; `liftBlock(title)` lifts it AND emits the live event that invalidates the queue (the
auto-resume's subject); `poseClosure(title, reason, winner?)`; the mock's `dismissClosure` handler forgets the closure
in every world. Système's dependencies seed gains a Plex row; the trackers seed gains `reachable` (+ `since`).

---

## 3. Named states — every case

Ids PROPOSED, declared in `frontend/maquette/design/src/harness/states/blocked.ts` with their French label (§ 0.1
item 11). Loading and error of the tab are `acq-todo-loading` and `acq-todo-error`, kept.

**Moved** (re-aimed to « À traiter », ids kept): `acq-card-deferred-ratio` · `acq-card-deferred-space` ·
`acq-card-deferred-missing`.

**External causes**: `acq-block-ratio-no-threshold` (tr4ker) · `acq-block-library-full` · `acq-block-tracker-unreachable`
· `acq-block-provider-unreachable` · `acq-block-plex-unreachable` · `acq-block-client-unreachable` (EVERY card in
flight held at once — OPEN 1's subject) · `acq-block-film` (a film held by `library_full`, the film variant).

**Doors**: `acq-block-door-disks` (after the finger on « Voir les disques ») · `acq-block-door-dependencies` ·
`acq-block-door-tracker` (the tracker's panel saying « ne répond pas ») · `acq-block-door-reserved` (an account
without `system.view`: cause and lift drawn, no door) · `system-dependency-plex-down`.

**Auto-resume**: `acq-block-lifted` (after `liftBlock`: gone from « À traiter », back in « En cours ») ·
`acq-block-lifted-many` (qBittorrent back: every card it held leaves, the one under another cause stays) ·
`acq-block-lifted-journey` (the panel's « bloqué … » / « repris » lines).

**Closures (Q8)**: `acq-closure-torrent-removed` · `acq-closure-files-absent` · `acq-closure-seen` (after « × »:
gone, badge −1, gone after a reload) · `acq-closure-dismiss-failed` (the write refused: card restored, error said)
· `acq-closure-filed-by-hand` (no card) · `acq-closure-medium-back` (a new card in « En cours », the old one still
unseen).

**Superseded (Q9)**: `acq-superseded-episode` (S03E07 chosen before the pack, arrived after it) ·
`acq-superseded-film` · `acq-superseded-seen` · `acq-superseded-pack-keeps-newer` (the pack filed, one episode kept,
no card).

**The list whole**: `acq-todo-every-cause` (one card per section, the order OPEN 1 settles, the badge reading them
all) · `acq-todo-external-only` (only external blocks — the empty note NOT drawn) · `acq-todo-empty` (kept, its new
words).

**Counted** (`` sed -n '/^## 3/,/^## 4/p' docs/features/maquette-blocked/DESIGN.md | grep -o -E '`(acq|system)-[a-z0-9-]+`' | sort -u | wc -l ``):
**33** ids printed — 27 new, 3 moved, 3 kept (`acq-todo-empty` with its new words; `acq-todo-loading`,
`acq-todo-error` unchanged).

---

## 4. The rules that bite

Every rule is red on today's maquette (`ca09123ee`), for the reason in the last column.

| Rule | What it READS | Red today because |
| --- | --- | --- |
| **R500** — « À traiter » holds every block; « En cours » none | on each moved and external state: the subject card is in « À traiter », under its cause's section, and no « En vol » card carries a block rung; « En cours »' count is the « En vol » cards drawn; `acq-card-waiting`'s « En file » cards stay in « En cours » | the deferred card is drawn in « En vol » (§ 0.1: « En cours » 6 on `acq-card-deferred-*`) |
| **R501** — each card says its cause and its lift | on every state of « À traiter »: every card has a reason line holding the cause sentence its served rung (or failed step, or closure) names AND, for a block the engine lifts, the lift sentence; none empty | no lift sentence exists; Furious' error card has no reason line (§ 0.1 item 6) |
| **R502** — each door lands where the cause is settled, and says it | a finger on each door: lands on the named page / tab / section, the target in the viewport, and the landed surface says the same cause (Plex row, « ne répond pas », the disk's state); the history grows by one; Retour gives « À traiter » back | space and missing causes draw no door; Système has no landing door |
| **R503** — the card leaves on its own | from `acq-card-deferred-space`, `liftBlock`: with no gesture, within the live event's settling, the card is gone from « À traiter », present in « En cours » with the rung `now`; the tab's count and the badge −1; on `acq-block-lifted-many` the card under another cause stays | the card is not in « À traiter » to leave; no lift exists in the mock |
| **R504** — a vanished medium is said once, « × » = seen | `acq-closure-*`: the closure card with its reason and « × »; a finger on « × » removes it, the badge −1, a reload does not bring it back; filed by hand → no card; the medium back → a new card in « En cours » | no closure exists; the mock re-opens a vanished row |
| **R505** — a superseded release is said once, its torrent still seeding | `acq-superseded-*`: the card says « remplacé par un choix plus récent » with the winner's line, offers « Voir la fiche » and « × »; its torrent is a seeding row of « Torrents »; the film case alike; the pack-keeps-newer case draws no card | no superseded card exists |
| **R506** — the badge counts the whole list | on every state of § 3: the Acquisition badge equals the cards of « À traiter » the account owns, « Mis de côté » excluded, read from a page that draws nothing of Acquisition (R236's walk) | the badge reads 3 on `acq-card-deferred-*` while 4 blocks exist |
| **R507** — the design system is reused | every card of « À traiter » is a `card` part of the one markup; every door is a `card/foot` with `data-go`; the « × » is a `card/foot` drawing the message close's icon; no `features/*` variant is named for blocks | (bites on a regression; red on today's maquette only for the « × », which is not drawn) |

**Re-aimed out loud** in the same lot (a rule broken by an intended change is updated): **R209** (`todo_holds.py`,
« only what his hand unblocks » → « every block »; hold 4 kept on the maintenance queue); **R265**
(`deferred_reason.py`, hold 4 « no other card of « En vol » names a deferral » → the card is in « À traiter »); **R224**
(`now_holds_in_flight.py`, the note's new words); **R-navigation-a** (`navigation_edges.py`, its ratio landing read
from « À traiter »); **R236** (`badges_observed.py`, the seeded count). Navigation (R502) and dismissal (R504) are
proved by a finger walk, never by a posed state alone.

---

## 5. What the lot does NOT draw, and the OPEN questions

**Not drawn**: a push notification of a block (Q10's FCM project is its own); a « forcer » act that bypasses a cause
(none was asked); a change to « Mis de côté »; the supervisor's levers (Système › « Pipeline », K4's own surface); a
global banner « qBittorrent ne répond pas » (one list, ruled).

Each OPEN question in `/orchestrator:decide`'s shape: what is on the screen, the choices with their cost and gain,
ONE recommendation. None reopens Q7–Q9.

### OPEN 1 — How « À traiter » groups its cards, and in what order

*On the screen*: today three sections (« À résoudre », « Match Plex à confirmer », « Une étape ne passe pas ») and
« Mis de côté » folded. Q7 adds up to six external causes and the closures. On `acq-block-client-unreachable`,
qBittorrent down puts every card in flight (6 in the dense world) in the list at once.

- **A — one section per thing to do, as today, plus ONE « Repart seul » section** holding every external block
  (each card says its cause), then « Clos — à lire » (Q8, Q9), then « Mis de côté ». *Gain*: four new copy keys, the
  tab stays short; *cost*: a disk full and a tracker down sit side by side under one title; ≈ 2 points.
- **B — one section per CAUSE**: « À résoudre », « Match Plex à confirmer », « Une étape ne passe pas », then « Disque
  plein », « Ratio trop bas », « Service injoignable » (tracker, TMDB/TVDB, Plex, qBittorrent), then « Clos — à
  lire », then « Mis de côté ». Each section says the cause in its title; the six qBittorrent cards read as one
  outage. *Gain*: « qui fait de la place sur le disque ? » answered by a title; *cost*: up to eight sections; ≈ 3
  points.
- **C — one flat list, newest block first**, no sections. *Gain*: simplest; *cost*: breaks ruling 10's « a section
  says what unblocks it », R209's frame; ≈ 3 points and a ruling amended.

**Recommendation: B** — the section a card sits in already says what unblocks it (ruling 10); with external causes
the cause IS what unblocks it, and an outage reads once by its title. Order: what needs his judgement first (the
three of today), then the external causes, then the closures, then « Mis de côté ».

### OPEN 2 — Where the « × » of a closure card sits

*On the screen*: the Q8 / Q9 card, dismissed by « × ». The card is a button (its body opens the panel); its foot holds
labelled buttons.

- **A — in the foot, last, icon-only** (`icons.x`, `aria-label` « Marquer comme vu », 44 px), after « Voir la fiche ».
  *Gain*: no button inside the card's tap area, the 44 px target of the foot; *cost*: the foot option takes an icon
  (an adaptation, ≈ 1 point).
- **B — in the card's top-right corner**, the message's « × » as it is drawn. *Gain*: the gesture he knows from the
  message; *cost*: a button nested over the card's body tap (the gesture arbitration's ground, `lib/press-arbitration.ts`)
  and the title's line shortened at 320 px; ≈ 3 points.

**Recommendation: A.**

### OPEN 3 — The tone of a rung stopped by an external cause

*On the screen*: the strip's cell and the chip of a card in a « Repart seul » / cause section. Today the deferral's
rung is `waiting` (a neutral chip, the waiting cell — capture `acq-card-deferred-ratio-subject.png`); a block for
his hand is `blocked` (the danger red: « identifié » in red on Lucky).

- **A — waiting**, as the deferral today: red stays what needs HIS judgement, the waiting tone says « it will go on
  by itself ». *Gain*: the eye sorts the list by colour; *cost*: none, the cell exists; ≈ 0 points.
- **B — blocked (danger)**, like every other card of the tab. *Gain*: one tone for one tab; *cost*: an outage paints
  the whole tab red although nothing is his to judge; ≈ 0 points.

**Recommendation: A.**

### OPEN 4 — « content missing »: a block or a vanished medium?

*On the screen*: the engine's `content_missing` (`deferral.py:61`: « content_path unknown or absent » — the volume
unmounted) and Q8's « fichiers absents ». Both read as files the engine cannot see.

- **A — split by the volume**: the volume itself absent (unmounted) is a BLOCK (« Différé : le disque où
  qBittorrent l'a téléchargé n'est pas lisible. », « Voir les disques », auto-resume); the volume present and the
  files gone is Q8's CLOSURE, said once. *Gain*: an unplugged disk does not close twenty tunnels; *cost*: the engine
  tells the two apart (BK3); ≈ 2 points.
- **B — every « files not found » is a closure** (Q8 read wide). *Gain*: one case; *cost*: a disk remounted an hour
  later finds every tunnel closed and reopened as new ones; ≈ 1 point.

**Recommendation: A.**

### OPEN 5 — Does the auto-resume say anything as it happens?

*On the screen*: the card leaving « À traiter » on its own (§ 1.4).

- **A — nothing**: the card leaves, it is back in « En cours », the journey keeps « bloqué … / repris ». *Gain*: no
  noise for what needs nothing; *cost*: a card he was looking at disappears under his eyes; ≈ 0 points.
- **B — a message when he is on « À traiter »**: « This City Is Ours est reparti » (the existing toast), nothing
  elsewhere. *Gain*: the disappearance explained; *cost*: one message per card — six at once when qBittorrent comes
  back (one message per lift then, « 6 acquisitions sont reparties »); ≈ 2 points.

**Recommendation: B**, one message per lift, only on « À traiter » — NE-DOIT-PAS-2: nothing vanishes unsaid on the
screen he is reading.

### OPEN 6 — Does an external block offer an act beside its door?

*On the screen*: the foot of a « Disque plein » or « Ratio trop bas » card: today one door, room for two feet.

- **A — the door alone**; « Abandonner » stays in the card's panel (its journey acts). *Gain*: the card says one
  thing to do, where it is done; *cost*: abandoning a blocked tunnel is one tap further; ≈ 0 points.
- **B — the door and « Abandonner »**, as the tunnel error offers it. *Gain*: one tap; *cost*: a destructive act at
  the thumb on a card that will resolve by itself; ≈ 1 point.

**Recommendation: A.**

---

## 6. The register rows and the demands

**Defects to file** (`BUGS.md` is not edited here; the lot files them):

| Defect | Escaped from | Why | Family repaired by |
| --- | --- | --- | --- |
| A deferred card stands in « En cours » and the badge ignores it | R265 (drawn under ruling 7) | ruling 7 put it there; Q7 amends it | R500, R506 |
| A tunnel error card in « À traiter » says no cause (Furious, `acq-card-follow-error`) | `poseTunnelError` / RULINGS 26 | the posed error carries a step and no sentence; no rule reads the reason line of every card | R501 |
| The space and missing deferrals offer no door | R265 hold 5 (« neither other cause does ») | only the ratio cause had a page to go to | R502, Système's door |

**Backend demands — K4 of the brief** (`docs/reference/backend-brief.md` § 6), in its shape; said to the
orchestrator, who owns the brief:

| Demand | What the engine must do | Why |
| --- | --- | --- |
| **BK1 — every block classified** | a tunnel stopped for an external cause records its token (the three of `deferral.py` and the five new), its rung, `resumes: auto`, its time and its details (tracker, threshold, provider, size); a block for his judgement `resumes: hand`; served on the rung | Q7 « chaque carte dit sa cause »; § 0.1 item 3 |
| **BK2 — a watch per cause's lift** | free space ≥ the need (staging, then the library's disks), the torrent's ratio ≥ the tracker's own threshold, the tracker / provider / Plex / client answering — each lift resumes the persisted step under the supervisor (Q5) and emits the live event that invalidates the queue; the journey records block and resume | Q7 « REPREND DE LUI-MÊME »; the brief's « Cost: each external cause needs a watch on its own lift » |
| **BK3 — a vanished medium closes** | `requeue_missing` (`_wanted_store.py:585`) no longer re-opens silently: the tunnel closes with `torrent_removed` or `files_absent` (the volume present — OPEN 4 = A; the volume absent stays the `content_missing` block); a medium found filed by hand (by provider id) ends with no closure; a medium back opens a new tunnel | Q8 |
| **BK4 — the last chosen wins at filing** | first verify that the engine knows, at filing, the choice date of the release whose file is in place (`staging_provenance.grabbed_at` per hash exists, `_provenance_store.py:173`; the file → hash link is not measured); a file with no known date is older than anything; an older-chosen release is not filed, its torrent seeds, its tunnel closes `superseded` with the winner's release line; a pack files every episode but the ones held by a later choice, named in its journey | Q9 |
| **BK5 — seen is stored** | `dismissClosure` records that the account saw the closure; the queue answers `closure` until then, per account (the badge counts the account's own cards, R-L18-g) | Q8, Q9 « une fois », A6 |
| **BK6 — reachability served** | Plex as a dependency of `readDependencies`; `reachable` and `since` per tracker on `readTrackers`; « ne répond pas depuis » on every dependency | § 1.3: the door lands on a page that says the same cause |

**`docs/reference/product-intent-map.md`**, read, not edited: the lot adds proofs under DOIT-2 (each « rien » says
why — R501), DOIT-5 (the resume seen — R503), § 20 point 2 (a block ends the execution and resumes — R503) and
NE-DOIT-PAS-2 (no waiting invisible — R500); proposed to the operator at the close.

---

## 7. A first cut of the phases — after his round

One phase is one surface (`docs/reference/method.md`). Each phase's gate is the CLAUDE.md phase gate; the harness
rules run in CI on the pull request.

| Phase | Surface | What | Rules |
| --- | --- | --- | --- |
| **1 — the slot** | the derivation | the contract fields of § 2 in the maquette's contract (`frontend/maquette/contract/`); `todoCards` / `inFlightCards` read `resumes` and `closure` over every list; `poseBlock` / `liftBlock` / `poseClosure`; the deferred card moves; the badge follows; « En cours »' note and the empty words | R500, R506; re-aim R209, R224, R236, R265 |
| **2 — « À traiter » whole** | the tab | the sections and their order (OPEN 1), the tone (OPEN 3), the cause + lift lines for every token, the failed step's words, the five new causes posed, `harness/states/blocked.ts` | R501 |
| **3 — the doors** | Système, Trackers | the generalised door table, Système's landing door, the Plex dependency row, the tracker's reachability fact, the reserved door | R502; re-aim R-navigation-a |
| **4 — the auto-resume** | the live path | `liftBlock`'s live event, the many-cards lift, the message (OPEN 5), the journey's block / resume lines | R503 |
| **5 — the closures** | the closure card | Q8 and Q9 cards, the « × » foot option (OPEN 2), `dismissClosure` and its failure, filed-by-hand, medium back, the film and the pack cases | R504, R505, R507 |

The lot's reading at 390 px on tm-design closes it (method: ONE independent reader, one round).
