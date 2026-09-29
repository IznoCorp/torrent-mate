# Season recovery — a whole-season recovery, visible and exclusive · DESIGN

Contract: the operator's words of 2026-09-29 17:36 and his rulings Q5 and Q6 of the same evening
(`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` §§ Q5, Q6), read against the conformity
reading's § A.3 (`/Users/izno/dev/review-archive/conformity-80/REPORT.md`). Verbatim:

- 17:36: « Lors d'une récupération d'une saison entière sur une série suivit, on doit pouvoir voir qu'une
  récupération de saison à été lancé et est en cours, et on doit s'assuré qu'aucun téléchargement d'épisode de la
  saison se lance en parallèle »
- Q5, « A »: the row of a season whose whole recovery is launched says « Demandée » on the series sheet AND the follow
  sheet, followed or not, until the season reaches the library; the progress reads on the SEASON's card in
  « En cours ».
- Q6, « A »: while a whole season is recovered, the acquisition card of a single episode of that season in
  « En cours » is ABSORBED — it disappears, the season's card covers it, and its journey points to the season's card
  (constitution § 13, « suivre le pointeur »).

**Wording, binding on every interface word and every sentence addressed to the operator:** « carte d'acquisition »
or « carte d'« En cours » », never « carte d'épisode » alone — he read that as the episode dot of the season list,
which this lot does NOT touch. In this English document, « card » always means the acquisition card.

This document is written for a session that has none of the context it was produced in. **Nothing under
`frontend/maquette/` was touched to write it** — no code, no rule, no mock, no seed, no harness run: prose and
numbers. Every figure carries the command that produced it, run from the worktree root.

**Written 2026-09-29, on `main` at `b63a45438`.** The code is built by the next lot that touches Acquisition
(order 69: a ruling arriving during a lot goes to the next one); the orchestrator names it. Section 5's OPEN
questions go to ONE operator round before any code.

---

## 0. What the lot owes, said once

| # | Subject | Source | Surface | Held for |
| --- | --- | --- | --- | --- |
| 1 | a recovery launched and running is SEEN on the season's row, both sheets, followed or not, until the library | 17:36; Q5 | **S1** | § 1.1 |
| 2 | the progress reads on ONE acquisition card for the season, in « En cours » | Q5 | **S2** | § 1.2 |
| 3 | no acquisition card of an episode of that season is drawn in « En cours » while it runs | 17:36; Q6 | **S3** | § 1.3 |
| 4 | the absorbed episode's journey points to the season's card | Q6; § 13 | **S4** | § 1.4 |
| 5 | where the operator could launch that episode alone, the interface says it is refused, and why | 17:36 (« aucun téléchargement … en parallèle »); DOIT-2 | **S5** | § 1.5 |
| 6 | the end: the season reaches the library, the row leaves « Demandée » | Q5 | **S6** | § 1.6 |
| 7 | every case of every surface is a named state | orders 76, 77 | § 3 | § 3 |
| 8 | every element drawn by the one existing component that draws it | order 79; implementer office, principles of 2026-09-29 | § 1.8 | § 1.8 |

### 0.1 Measurements that correct the premises

Each read on `b63a45438`. Paths under `frontend/maquette/design/src/` are written from there.

1. **For a FOLLOWED series the ask queues no card.** The mock's `grabSeasonForFollow`
   (`mocks/handlers/acquisition-verbs.ts:181–224`) sets the whole follow to `acquiring` (`:201`) and pushes the
   one-off card only when `found === undefined` (`:209`) — a series nobody follows. On Silo, followed, the tap leaves
   « En cours » without any card of season 3.
2. **« Demandée » reads one list, one requester.** `askedSeasons` (`features/media/asked-seasons.ts:30–38`) reads
   `queue.inFlight` only, and skips every card whose `requester.via` is not `request` (`:33`). A followed series'
   cards carry `via: "follow"` (`mocks/handlers/staging.ts:42, 167`); an ARRIVAL (the season pack in the staging
   area, still on its way) is never read. « En cours » itself reads a third answer: `inFlightCards`
   (`features/acquisition/arrival-slots.ts:96–100`), which merges the in-flight rows and the arrivals — the one
   derivation of « what is on its way » (§ 13 « une seule dérivation par question »). Invariant 7 forbids
   `features/media` to import it.
3. **Nothing hides an episode card of the season.** `sameMedium` (`arrival-slots.ts:73–83`) compares the provider
   identifiers AND the episode token read off `secondaryLine`: « S03 » (empty token) and « S03E07 » (« S03E07 ») are
   two media, both drawn.
4. **The engine ALREADY absorbs part of it.** The season-grab route absorbs every OPEN episode wanted of that season —
   statuses `pending`, `searching`, `available` — into the season row, with a pointer column `absorbed_by`
   (`personalscraper/web/routes/acquisition_seasons.py:60–87, 191–196`; `personalscraper/acquire/_wanted_store.py:726–748`);
   the automatic season path does the same (`personalscraper/acquire/detect.py:751–778`, rule R5). What it does NOT
   cover: an episode already `grabbed` (its torrent in the client), and the per-episode path reads no open season row
   (`git grep -n 'kind="season"' -- personalscraper/acquire/detect.py` → lines **694, 726, 737**, all inside the season
   block that opens at `:655`). The route answers `absorbed_count` and `reused`; the maquette's contract carries
   `absorbedCount` (`contract/types.d.ts:2734–2735`) and the toast already says it (`features/media/season-grab.ts:162–176`).
5. **The queue card has no season, no episode, no pointer.** `QueueCard` (`contract/types.d.ts:1241–1266`): `title`,
   `secondaryLine`, `ids`, `requester`, `ladder`, … — the season is read off the line by a regular expression
   (`asked-seasons.ts:13–21`, « fragile », its own comment says).
6. **A journey is addressed by TITLE.** `journey:<title>` (`features/acquisition/panel-journey.ts:90`), opened from
   the follow panel's « Voir le parcours » with the follow's title (`features/acquisition/follow-actions.ts:128–130`),
   reopened from the address by title (`app/addressed-panels.ts:58–67`). An episode card of Silo and the season card
   of Silo share ONE journey address today. Its release is a constant (`panel-journey.ts:64`, a filed demand).
7. **Where an episode can be launched alone — the inventory.** Read in the code, every act that takes a release:
   - **the release picker** (« Chercher une autre release », `follow-actions.ts:131–135` → `features/releases/releases-screen.tsx:73–118`,
     `data-pick-release`): every release of the title, episode releases included. Silo's four seeded releases are
     all `S03E07` (`python3 -c "import json;print([r['name'] for r in json.load(open('frontend/maquette/design/src/mocks/seeds/releases.json')) if r['name'].startswith('Silo')])"`
     → **4** names, each `Silo.S03E07.…`). **This is the one surface that must draw the refusal.**
   - « Prendre maintenant » (`follow-actions.ts:52–55`, the follow's takeable claim): a takeable episode of the season
     is an `available` wanted, which the engine's absorption already closes (item 4) — it leaves with the ask, it is
     never drawn refused.
   - « Rechercher » (`features/acquisition/follows-tab.tsx:159`) searches the whole follow; the exclusion is the
     engine's (§ 6 demand). Nothing is drawn.
   - The episode dot of the season list opens its date; it launches nothing, and the operator excluded it (Q6).
8. **The subject.** Silo is followed, `pending`, season 3 **7** aired / **6** owned, no Silo card in any queue list:
   `python3 -c "import json;s='frontend/maquette/design/src/mocks/seeds/';print(json.load(open(s+'seasons.json'))['Silo'][2]);print(sum('Silo' in c.get('title','') for n in ['in-flight','moving','stuck','settled','blocked','takeable','stuck-loaded','settled-loaded'] for c in json.load(open(s+n+'.json'))))"`
   → `{'season': 3, 'aired': 7, 'owned': 6}` and **0**.
9. **The mark is a second drawing of the chip.** `queuedMark` (`features/media/variants.ts:198–202`) is the info
   chip's background mix and text colour without its dot — `chip({ tone: "info" })` already draws that
   (`ui/variants/surfaces.ts:60–80`). And the release picker (`features/releases`) may not import it (invariant 7).
10. **Near the 400-line ceiling** (`for f in lib/queue.ts features/media/season-list.tsx mocks/state.ts; do grep -cv '^\s*$' frontend/maquette/design/src/$f; done`):
    **390**, **390**, **393**. None of them grows here: the derivation lands in its own `lib/` module, the season
    list's marks are already drawn, the seeds are seed files.

### 0.2 What the lot builds on, and does not redraw

| Landed | Read as |
| --- | --- |
| R125 — « Récupérer la saison N » on both sheets (`season-list.tsx:378`, `panel-seasons.tsx:215–218`), `askForSeason` (`season-grab.ts:219–231`) | the act, unchanged; its answer now moves the world for a followed series too |
| R138 — « En file — pipeline en cours » (`queued-seasons.ts`) | kept; its order against « Demandée » is OPEN 4 |
| R158 — the one-off season card, via `request` | kept; it becomes one case of the general season card |
| L22 — the acquisition card (`ui/card-markup.ts`, `features/acquisition/card-markup.ts`) | the season's card, unchanged in anatomy |
| L15 — the bottom panel and its generic blocks (`note`, `faits`, `actions`) | the journey's pointer |
| The named landing — « Voir le tracker » lands on `trackers:<name>` (`features/acquisition/card-markup.ts:208–215`, `features/trackers/verbs.ts:38–45`) | the pointer's landing, ADAPTED to Acquisition |

---

## 1. The surfaces

Copy is given in « guillemets » as `fr.json` will carry it; a key is proposed beside new copy.

### 1.1 S1 — The season row, on the series sheet and on the follow sheet

**What it says.** While a recovery of the whole season is live — a season card on its way (§ 1.7) — the row reads
« Demandée » (`screens.media.seasonAskedOnce`, the existing word) in the act's place, on BOTH surfaces that draw the
row: the media sheet's season list (`season-list.tsx`) and the follow panel's seasons (`panel-seasons.tsx`). Followed
(Silo) or not (the one-off, R158): the same mark, the same reading. The act « Récupérer la saison N » is withdrawn
while it shows — a second tap would be a doublon (NE-DOIT-PAS-3's one legitimate refusal), and the engine reuses the
live row anyway (§ 0.1 item 4, `reused`).

**Until the library.** The mark reads the same derivation « En cours » draws (§ 1.7), so it lasts exactly as long as
the season's card is on its way — in flight, downloading, arrived in the staging area — and it also holds while the
card is STOPPED for his hand in « À traiter » (the season has not reached the library; the card is elsewhere, the
recovery still his). It goes when the card's rung « rangé » is done. The fraction then reads the library's new count
(`7/7` for Silo); nothing is remembered by the interface (§ 13).

**The word, and the key.** The key's name says « once » (`seasonAskedOnce`) and the fact is no longer « once »: the
key is renamed by `scripts/rename-identifiers.py --values` to `seasonRequested`, its French unchanged.

**The mark's drawing.** One component — the chip (§ 1.8, OPEN 7).

### 1.2 S2 — The season's acquisition card in « En cours »

**Its component: the acquisition card, unchanged** — `mediumCardMarkup` (`features/acquisition/card-markup.ts:198–258`)
over `cardMarkup` (`ui/card-markup.ts`). No new part.

**What it says, in § 12's order.** Line 1 — the title, whole (« Silo »). Line 2 — the figure and the rung, from its
ladder (« 2/8 · cherché »). The subtitle — « S03 », the season alone (the one-off's own line, `oneOff`,
`acquisition-verbs.ts:164–177`). The origin line — the requester, from the answer: « demandé par {{name}} » for a
followed series (`surfaces.card.requester.follow`), « demandé par {{name}}, pour cette saison » for the one-off
(`…request`). Its strip — the eight rungs of a season pack, the same ladder an episode walks.

**Its taps** — the card's own: the poster opens the medium's sheet; the body opens the medium's panel. **Its
journey** — its own sheet, addressed per acquisition, not per title (OPEN 1).

**ONE card per season** (R-season-recovery-e): a second ask queues nothing more (the one-off's rule, `:207–211`,
generalised); the season pack's arrival JOINS the card (`inFlightCards`' own merge, once the season is a field — § 2).

**Where it sits.** By its ladder, like every card (`slotArrivals`, `arrival-slots.ts:24–34`): « En cours » while on
its way, « À traiter » when stopped for his hand, gone when shelved.

### 1.3 S3 — The absorption of an episode's acquisition card

**The rule.** While a season card of a medium is on its way, no card of that medium whose episode belongs to that
season is drawn in « En cours ». The season's card covers it: its count is « En cours »' count, less the absorbed.

**Where it is decided — once.** In the one derivation (§ 1.7), never in the tab: « En cours », its count, the season
row and the pointer read the same answer. The engine's pointer is the fact read (`absorbedBy`, § 2, OPEN 5); the
derivation follows it.

**What the operator sees at the ask** (the finger walk of `season-recovery-before-ask` →
`season-recovery-absorbs-episode`): Silo « S03E07 » is a card in « En cours »; on the follow panel he taps
« Récupérer la saison 3 »; the toast says the answer (« … 1 épisode absorbé », `seasonAskedOne`, existing); the
« S03E07 » card is gone and « Silo · S03 » stands at the top of « En vol »; the row reads « Demandée ». The count of
« En vol » moves by zero (one card left, one came).

**What is NOT absorbed**: a card stopped for his hand in « À traiter » (the ruling names « En cours »; a file waiting
for him stays his to resolve); an episode of ANOTHER season; the fallback's episodes once the season journey has
CLOSED (§ 1.6) — they belong to no live recovery.

**The absorbed episode that was already downloading** (a `grabbed` wanted, § 0.1 item 4) — its torrent is in the
client; the Trackers page's « Torrents » tab still lists it, honestly. What the SEASON's journey says of it is OPEN 3.

### 1.4 S4 — The absorbed episode's journey points to the season's card

**Its component: the journey sheet** (`panel-journey.ts`, `ui/panel` blocks), unchanged in shape. Reached by its
address (a URL kept, the Back stack, a notification) — the card that led to it is gone.

**What it says.** Above its facts, a `note` block: « Cet épisode est couvert par la récupération de la saison 3. »
(`panels.journey.absorbedBy`, proposed). Its facts stop at the rung it had reached (never advanced by the season's
progress — that is the season's to say). Its first action, `primary`: « Voir la carte de la saison »
(`panels.journey.seeSeasonCard`) — the pointer, FOLLOWED (§ 13), never reported as the episode's own state.

**Where the pointer lands.** On the Acquisition tab that holds the season's card NOW — « En cours », or « À traiter »
if it is stopped — with that card scrolled into view and focused. The mechanism is the existing named landing
(`trackers:<name>`), ADAPTED: `data-go="acq"` with `data-dial="<tab>:<acquisition>"`, read by Acquisition's landing
door (`features/acquisition/verbs.ts:135–137`, `landingTab`, `features/acquisition/tab-memory.ts:50`) the way the
Trackers door reads a tracker. A landing is an arrival (§ 16: it stacks); the tab choice inside it is not a second
entry.

**When the target has ended** — the season reached the library: the note reads « La saison 3 est arrivée en
médiathèque. » (`panels.journey.absorbedEnded`) and the action becomes the card's own « Voir la fiche » (existing,
`panels.journey.seeSheet`). A pointer never lands on nothing.

### 1.5 S5 — The refusal in the release picker

**Its surface: the release screen, unchanged in layout** (`releases-screen.tsx`). While a recovery of season N is
live for the title, each release naming an episode of season N (`S03E07`) keeps its row, its tags and its score —
the operator still reads what exists — and in its foot's place draws:

- the chip `info` « Couvert par la saison 3 » (`screens.releases.coveredBySeason`), the same chip as the row's mark;
- the card foot action « Voir la carte de la saison » (`actionButton({ kind: "cardFoot" })`, existing), the same
  pointer as S4.

A release of the WHOLE season (`Silo.S03.…`, a pack) keeps its act: choosing another release for the recovery is
legitimate. A release of another season keeps its act. Before the ask, and after the season reached the library, the
episode releases take again. **Why visible, not hidden**: DOIT-2 (« chaque rien a sa raison affichée ») and DOIT-12's
« visible et expliqué plutôt que silencieusement absent »; a list quietly shorter than yesterday's is a lie by
omission. **When every release is an episode of the season**, the result count says it (« 4 candidats — tous couverts
par la saison 3 », `screens.releases.allCovered`), the empty note stays.

### 1.6 S6 — The end

- **Shelved.** The season card's rung « rangé » done → it leaves « En cours » (L22's rule), the rows read `7/7` and no
  mark, the release picker takes again, the absorbed journey's pointer says the season arrived (§ 1.4).
- **Closed short** (the incomplete-pack fallback, #542): the season journey closes, the engine re-enqueues the episodes
  it is still short of. The row reads its new fraction and its shortfall, no mark; the re-enqueued episodes are
  ordinary cards in « En cours » — not a violation (`docs/reference/backend-demands-architecture.md` § 14, third
  bullet).
- **Abandoned** (« Abandonner » on the season's journey, existing verb): the card goes, the mark goes, the absorbed
  episodes are not revived by the interface — what the engine does is its own (§ 6).

### 1.7 The one derivation — moved to `lib/`, not copied

« What is on its way » is ONE question with four readers: « En cours » and its count, the season row on two
surfaces, the pointer. Today the answer lives in `features/acquisition/arrival-slots.ts` (`inFlightCards`,
`sameMedium`), which `features/media` may not import (invariant 7). It is **MOVED**, unchanged in behaviour, into
its own `lib/` module (not `lib/queue.ts`, at 390 lines), and extended there with the absorption: the cards on their
way, less every episode card whose pointer names a live season card (OPEN 5: the pointer as a field, or the lines
compared). `askedSeasons` then reads that answer — every season card on its way, whatever its requester — instead
of `queue.inFlight` filtered on `request`.

### 1.8 The design system, element by element (order 79)

| Element | The one component that draws it | New? |
| --- | --- | --- |
| « Demandée » on the season row | `chip({ tone: "info" })` (`ui/variants/surfaces.ts:60`) — OPEN 7; today `queuedMark` (`features/media/variants.ts:198`) | adapted: no new part |
| « En file — pipeline en cours » | same as above | adapted |
| The season's card | `mediumCardMarkup` → `cardMarkup` (`ui/card-markup.ts`) | no |
| Its strip, figure and rung | `ladderMarkup` (`features/acquisition/card-markup.ts:139–167`) | no |
| Its origin line | `originLine` (`:180–184`), the `follow` / `request` words | no |
| The absorption | a function of the moved derivation (§ 1.7) — nothing drawn | no |
| The pointer's note | the panel's `note` block (`panel-journey.ts:104`) | no |
| « Voir la carte de la saison » | the panel's `actions` block, `ton: "primary"`; a `data-go` + `data-dial` target like « Voir le tracker » | no |
| The refusal on a release | `chip({ tone: "info" })` + `actionButton({ kind: "cardFoot" })` (the row's own foot) | no |
| The toast at the ask | the existing toast and its `seasonAsked*` words | no |
| The named landing on a card | Acquisition's landing door, ADAPTED to read `<tab>:<acquisition>` — the Trackers door's shape | adapted |

**Nothing new is drawn.** Two adaptations are written here, as the office asks: the landing door reads a named
acquisition; the mark is the chip (OPEN 7).

---

## 2. The contract and the seeds

**The contract (D7), first** — `scripts/compare-contracts.py --check` refuses a field apart from its schema.
`QueueCard` gains `season: int | null`, `episode: int | null` (read off the engine's wanted row, never the line) and
`absorbedBy: string | null` (the acquisition that covers this one — OPEN 5). The season-grab answer gains
`reused` (the engine's route answers it, `acquisition_seasons.py:160–171`; the maquette's inline answer schema,
`frontend/maquette/contract/openapi.json`, carries `season`, `absorbedCount`, `queued`, `runUid` and no `reused`). The journey read takes the acquisition, not the title (OPEN 1).

**The seeds — the DENSE world** (tm-design starts on it), every case one subject (order 77):

| Seed | What | Kind |
| --- | --- | --- |
| `in-flight.json` | « Silo » · `S03` — the season card, requester `follow`, ladder at « téléchargement » | composed, declared in the fixture register |
| `in-flight.json` | « Silo » · `S03E07 · 1080p · MULTi` — its episode card, strip at « téléchargement », `absorbedBy` the season card | composed |
| `releases.json` | `Silo.S03.MULTi.1080p.WEB-DL.DDP5.1.H264-FRATERNITY` — the season pack | composed |

At rest, the dense world therefore holds the recovery RUNNING: « Silo · S03 » in « En cours », no « S03E07 » card,
Silo's S03 row « Demandée » on both sheets, the picker refusing `S03E07`. The before-ask subject is POSED
(`season-recovery-before-ask` lifts the season card and the pointer), never seeded — RULINGS 7's standing rule. **The
real world keeps its rule**: its reel lists start empty and only a finger's ask fills them.

---

## 3. Named states — every case, per surface

Every id is PROPOSED, declared in `frontend/maquette/design/src/harness/states/acquisition.ts` (S2–S4, S6) or
`media.ts` (S1) with its French label. Loading and error of « En cours » itself are `acq-now-loading` and
`acq-now-error`, kept and not counted.

**S1 — the row**: `season-row-requested-sheet` (Silo S03 on the media sheet) · `season-row-requested-panel` (on the
follow panel) · `season-row-requested-one-off` (R158's subject, not followed) · `season-row-queued` (« En file »,
OPEN 4) · `season-row-queue-loading` (the act `aria-busy`, no mark asserted) · `season-row-queue-unread` (the queue's
read failed: no mark asserted — never a constant — the act offered; a re-ask answers `reused` and says « déjà
demandée ») · `season-row-ask-failed` · `season-row-ask-held` (offline).

**S2 — the season's card**: `season-card-requested` · `season-card-searched-nothing` (« cherché », no release yet) ·
`season-card-downloading` · `season-card-arrived` (the pack in the staging area, joined to the card) ·
`season-card-blocked` (in « À traiter »; the row still « Demandée ») · `season-card-one-off` · `season-card-journey`
· `season-card-automatic` (engine-minted — conditional on OPEN 6 = A).

**S3 — the absorption**: `season-recovery-before-ask` (posed: « S03E07 » in « En cours », the act offered) ·
`season-recovery-absorbs-episode` (after the finger's ask) · `season-recovery-absorbed-downloading` (conditional on
OPEN 3 = A: the season's journey names the episode whose torrent still runs).

**S4 — the pointer**: `absorbed-journey-pointer` · `absorbed-journey-pointer-blocked` (lands on « À traiter ») ·
`absorbed-journey-pointer-ended` (the season in the library).

**S5 — the refusal**: `releases-season-recovering` (`S03E07` refused, the pack takeable) ·
`releases-season-recovering-all-covered` (every release covered).

**S6 — the end**: `season-recovery-shelved-sheet` · `season-recovery-shelved-panel` · `season-recovery-closed-short`
· `season-recovery-abandoned`.

**Counted** (`` sed -n '/^## 3/,/^## 4/p' docs/features/maquette-season-recovery/DESIGN.md | grep -o -E '`(season|absorbed|releases)-[a-z0-9-]+`' | sort -u | wc -l ``):
**28** ids, all new; **2** conditional (`season-card-automatic`, `season-recovery-absorbed-downloading`), and one
whose drawing depends on OPEN 4 (`season-row-queued`).

---

## 4. The rules that bite

Labels, never numbers: they bind to the range the steward reserves in the lot's launch brief.

| Rule | What it READS | The mutation that fells it |
| --- | --- | --- |
| **R-season-recovery-a** — exclusive in « En cours » | at rest (dense) and after the finger's ask from `season-recovery-before-ask`: no card of « En cours » names an episode of a season whose season card of the same medium is on its way; « En vol »'s count equals the cards drawn | drop the absorption from the derivation → falls; count « En vol » before the absorption → falls on the count |
| **R-season-recovery-b** — « Demandée » on both sheets, until the library | Silo S03 (followed) and the one-off read « Demandée » on the media sheet AND the follow panel, act withdrawn; at `season-card-arrived` and `season-card-blocked` still; at `season-recovery-shelved-*` gone, fraction `7/7` | restore the `via === "request"` filter → falls; read `queue.inFlight` instead of the derivation → falls at `season-card-arrived` |
| **R-season-recovery-c** — the pointer is followed | the absorbed journey draws the note and « Voir la carte de la saison »; a finger on it lands on the tab holding the season card, that card in the viewport and focused; ended → the sheet | land on a fixed « En cours » → falls at `absorbed-journey-pointer-blocked`; drop the note → falls |
| **R-season-recovery-d** — the refusal is visible | during the recovery every `S03E07` release has no pick act, carries the chip and the pointer; the pack keeps its act; before the ask and after the library, `S03E07` takes again | keep the act → falls; refuse the pack → falls |
| **R-season-recovery-e** — one card per season | two asks, then the pack's arrival: « En cours » holds exactly one « Silo · S03 » | push a card per ask → falls |
| **R-season-recovery-f** — the design system is reused | the row's mark and the release's refusal are the SAME `ui` component (class set read); the pointer is a panel `note` + `actions`; no `features/*` variant is named for the recovery | draw the refusal with a feature's own variant → falls |

Navigation (R-c) is proved by a finger walk, never by a posed state alone (the office).

---

## 5. What the lot does NOT draw, and the OPEN questions

**Not drawn**: the episode dot of the season list (the operator's own exclusion, Q6); any change to « Rechercher » or
« Prendre maintenant » (§ 0.1 item 7); a push notification; a per-episode progress inside the season's card (the card
draws its ladder, one medium).

Each question below is one the rulings leave. Two readings, the cost of each, one recommendation — for ONE round.

**OPEN 1 — The journey's subject.** Today a journey is addressed by title (§ 0.1 item 6): Silo's episode and Silo's
season share one address, so « the episode's journey points to the season's card » has no episode journey to hold it.
**A** — a journey per ACQUISITION (`journey:<title>|S03`, `journey:<title>|S03E07`); the follow panel's « Voir le
parcours » opens the live recovery's while one runs, the medium's latest otherwise. Cost: the address, its reopen
test, the read's parameter (≈ 6 points) and a backend demand (the journey keyed by wanted row). **B** — keep one
journey per medium; the pointer lives only on the release picker and the season card's journey lists what it
absorbed. Cost: none now; the ruling's « son parcours pointe » is then met by the season's journey, not the
episode's. **Recommendation: A** — § 13's pointer needs a subject that holds it, and a series has several
acquisitions at once by construction.

**OPEN 2 — Where the pointer lands.** **A** — on the Acquisition tab holding the season's card, the card in view and
focused (the adapted named landing, § 1.4). Cost ≈ 5 points, one rule hold. **B** — straight onto the season card's
journey sheet (panel to panel). Cost ≈ 2 points; the operator never sees the CARD the ruling names. **Recommendation:
A** — the ruling says « pointe vers la carte de la saison ».

**OPEN 3 — An absorbed episode whose torrent already runs.** The engine absorbs only what is not yet grabbed (§ 0.1
item 4); a grabbed episode's download runs on. **A** — the season's journey lists each absorbed episode with its
state (« S03E07 — téléchargement déjà en cours »), each a path to its own journey (conditional state
`season-recovery-absorbed-downloading`). Cost ≈ 4 points and the demand of § 6. **B** — the count only, in the
toast, as today. Cost none; a download runs « en parallèle » with nothing on screen saying so. **Recommendation: A**
— the operator's sentence is about exactly that.

**OPEN 4 — « En file » and « Demandée » on one row.** An ask answered `queued` (pipeline busy) creates the season
row all the same (the route's 201). **A** — one mark at a time: « En file — pipeline en cours » while the ask waits,
then « Demandée ». Cost ≈ 1 point. **B** — both marks side by side. Cost none; two chips on a phone row at 320 px
compete with the fraction (§ 12). **Recommendation: A.**

**OPEN 5 — What the absorption reads.** **A** — the engine's pointer, served on the card (`absorbedBy`, `season`,
`episode`, § 2) — the engine already holds `absorbed_by` for open wanteds. Cost: the contract field (≈ 3 points) and
the demand extension of § 6. **B** — derived in the interface by comparing lines (« S03 » covers « S03E07 », same
provider identity). Cost none now; § 13's « suivre le pointeur » becomes the interface guessing a pointer the engine
holds, and it breaks on the first line that is not `SxxEyy`. **Recommendation: A.**

**OPEN 6 — An automatic season recovery.** The engine mints a season recovery by itself (R4: the season fully aired
≥ 7 days ago, owned ≤ half — `detect.py:655–740`). **A** — drawn exactly as a manual one: « Demandée », the season's
card, the absorption; its origin line says who (the follow). Cost: one state (`season-card-automatic`). **B** —
only the manual ask draws the mark; an automatic one shows its card only. Cost none; two recoveries doing the same
thing look different. **Recommendation: A** — the operator's sentence is about the recovery, not who launched it.

**OPEN 7 — The mark's component.** `queuedMark` redraws the info chip without its dot (§ 0.1 item 9) and cannot be
reached from the release picker. **A** — replace it by `chip({ tone: "info" })` everywhere: one component, the rows
gain the chip's dot. Cost ≈ 3 points, a visible change on « Demandée » and « En file ». **B** — move `queuedMark` to
`ui/` as it is and use it for the refusal too. Cost ≈ 3 points; two drawings of one tone stay in `ui/`.
**Recommendation: A** — « on crée pas de nouveau composant on adapte ».

---

## 6. The register rows and the demands

**Defects filed (order 57)** — the register rows come with the lot (`BUGS.md` is not edited here).

| Defect | Escaped from | Why | Family repaired by |
| --- | --- | --- | --- |
| A season asked of a FOLLOWED series draws no card and no mark | R125 / R158 (the one-off path drawn, the followed one not) | the mock's guard `found === undefined` was written for the one-off; no state poses a followed ask | R-season-recovery-b and -e |
| « En cours » draws an episode card beside the recovery of its season | L22's merge (`sameMedium`) | the episode token keeps them apart by design; no rule reads a season against its episodes | R-season-recovery-a, the derivation moved to `lib/` |
| « Demandée » reads a list « En cours » does not | R158 | two derivations of « on its way » (§ 13) | the one derivation, § 1.7 |
| `queuedMark` redraws the info chip | R138 | no layer reads design-system reuse on a feature variant | R-season-recovery-f (OPEN 7) |

**The demand of `docs/reference/backend-demands-architecture.md` § 14 lacks the absorption detail** — said to the
orchestrator, who owns that file; proposed rows in its shape:

| Demand | What the engine must do | Why |
| --- | --- | --- |
| **SR1 — the pointer on the card** | serve, on each queue card, `season`, `episode` and `absorbedBy` (the covering acquisition), from the wanted row's own columns | Q6: the card is absorbed and its journey points to the season's; the engine already holds `absorbed_by` |
| **SR2 — a grabbed episode at the ask** | decide and serve what a season ask does to an episode already `grabbed` (absorbed with its torrent left running, or cancelled), and mark it absorbed either way | 17:36 « aucun téléchargement … en parallèle »; R5 covers only open wanteds |
| **SR3 — the per-episode path refuses** | while a season wanted is open, the per-episode enqueue and grab paths skip that season's episodes — including an episode with no wanted row at the ask | § 14's own bullet, made precise: `detect.py`'s episode path reads no season row |
| **SR4 — a journey per acquisition** (OPEN 1 = A) | the journey read keyed by the acquisition (wanted row), not the title, with the release it followed | § 0.1 item 6 |

**`docs/reference/product-intent-map.md`**, read, not edited: the lot adds proofs under DOIT-2 (the refusal said,
R-d), DOIT-4's visible half (the mark, R-b) and § 13's pointer (R-c) — proposed to the operator at the close.
