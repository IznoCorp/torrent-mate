# L16 — §18, the ratio · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L16 — §18, the ratio`. It is
not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every
figure carries the command that produces it, every decision carries its reason, every screen
carries its named states. **Nothing under `frontend/maquette/design/` was touched to write it** —
the lot opens after L22b (the plan's order is L13 · L22 · L16 · L17 · L18), and this is the design
read before it does.

**Written 2026-09-15 on `08400a22a`; re-read 2026-09-26 on `dafe29ec1`** against the operator's
organisation rulings 10–15 of 2026-09-26 and his ruling on L22's OPEN 2 (`docs/features/maquette-l22/DESIGN.md`
§ 7.2), which the first drawing could not know: it was written before he paused the drawings. The
re-read rewrites what those rulings contradict — it does not annotate it — and § 0.1 says which
sentences moved. The figures that moved with the tree (L13c and the lots after it merged between the two
heads) carry their new value and the command.

**Where L16 opens in the order, and why.** L16 lands **after L22b**, never between the two sub-lots:
L22b's phase 19 takes Système out of the bar, and L22b's phase 25 deletes the `arr` row
(`docs/features/maquette-l22/plan/INDEX.md`; L22a = phases 1–14, L22b = phases 15–27). Before that the
bar holds `acq`, `lib`, `arr` and `sys` — four buttons, the constitution's maximum — and a Trackers row
in the bar would be a fifth. After it the bar holds `acq` and `lib` and draws two; L16's page is the third.

---

## 0. What L16 owes, said once

`product-intent.md` § 18, « Ce que l'opérateur a tranché » (dictated 2026-08-30), gives L16 five
things, and none of them is a decision left to draw:

| # | The thing | The operation | Its clause |
| --- | --- | --- | --- |
| 1 | the ratio, read **per tracker**, never averaged into one figure | `GET /api/acquisition/obligations`, `/stalled-grabs`, `/downloads` — answering, called by nothing | DOIT-13 |
| 2 | **release an obligation early** — including a HANDLED case when the stop is an external removal in qBittorrent | none: a write, absent from both contracts | § 18, DOIT-2 |
| 3 | a **per-tracker ratio alert**, a threshold the operator sets, **spoken where it lives — on the Trackers page and as a badge on the Trackers tab of the bar** (push is a platform demand, not this lot's) | none: a write and a read, absent from both contracts | § 18, § 17 point 4 |
| 4 | the **ranking follows the ratio** — a release on a low-ratio tracker may lose points | `POST /api/acquisition/ranking/preview` — answering, called by nothing; the ratio TERM itself does not exist on the scored release | § 18, and B-298 |
| 5 | what is shown **beyond the ratio**: Download / Upload volumes, the trend, and per ACTIVE torrent its deadline and its ratio | none of the three existing reads carries it | § 18 |

And one register row this lot is named against directly: **DOIT-2**'s ratio half — « a torrent
deferred for ratio or space ». Its surface is the acquisition card, not Arrivées: after L22 the page
Arrivées does not exist, and the map's proposed DOIT-2 surface is `features/acquisition` — « a card says why
it waits » (`docs/features/maquette-l22/DESIGN.md` § 6.3). The card never draws the ratio-specific reason
today. **No proposed decision anywhere in this design**: § 18's own words, « l'interface expose ;
l'opérateur juge », hold for every screen below.

### 0.1 The rulings this design is read against, and what each moved

The rulings are the operator's and are not reopened here. « Organisation ruling N » is his entry of
2026-09-26 (10–15) or 2026-09-15 (1–9) in `docs/reference/operator-method.md`, numbered as
`docs/features/maquette-l22/DESIGN.md` § 0 numbers them; his ruling on L22's OPEN 2 is in that design's § 7.2.

| Organisation ruling | What it dictates | What it moved in this design |
| --- | --- | --- |
| 11 | the place Arrivées frees in the bottom bar goes to « Trackers » (ratio, cross-seed, the tracker); the bar is composed by rights (§ 17 point 4) | § 4.1 (the page is a bar row, `inBar: true`) and § 5 (the placement question is ruled; three new ones are open) |
| 12 | every thing speaks where it lives, a badge on the bar tab that carries it — ratio and cross-seed on Trackers; no notifications box | § 4.5 (the alert gains its fourth reader, the tab's badge; no box, no Système line), § 1 clause 6 |
| 13, 15 | Système keeps the machine and the pipeline's levers, and leaves the bar for the drawer, its badge on the menu button | no lever and no sentence of the first drawing pointed at Système for the ratio (`git show 27f6480eb:docs/features/maquette-l16/DESIGN.md \| grep -c 'Système'` reads 0; its one `sys` was a bar row in Reading A of the placement question) — so nothing moves to Trackers; § 4.5 says the alert has no line there and the ordering paragraph above says where L16 opens |
| 14 | accounts are managed in Réglages or a first-level drawer entry; Profil is the connected account | nothing: accounts have no relation to Trackers (L18's) |
| OPEN 2 of L22 | the bar draws only the buttons present, in equal shares of 1/n, n from 2 to 4, never an empty slot | § 4.1: the bar reads three buttons once the page lands |
| 2 and 7 (2026-09-15, through L22) | the page Arrivées dies; what stagnates reads on its card in « En cours » with its reason | § 4.6 (the ratio reason is drawn on the card, and the R66 stuck queue it named is gone) |

---

## 1. What §18 dictates, clause by clause, and the surface that serves it

1. **« Le ratio se lit PAR TRACKER, jamais en un seul chiffre. »** Served by **S1 — the trackers
   list** (§ 4.1): one row per tracker, its own ratio, never an average. No surface in this design
   computes a mean across trackers.
2. **« Une obligation de seed est un rien qui a sa raison » (§ 8, DOIT-2).** Served by **S2 — a
   tracker's detail** (§ 4.2), which lists the tracker's obligations with `reason`-shaped rows —
   deadline, ratio owed, ratio observed — and by **S6 — the stuck queue's ratio reason** (§ 4.6),
   which names the same fact where DOIT-2 lives after L22, the acquisition card.
3. **« Agir là où l'on observe » (DOIT-3).** Served by **S3 — the policy panel** (§ 4.3): the
   tracker's `min_ratio` / `min_seed_time` are set from the same screen that shows its ratio,
   never from a settings file the interface only relays.
4. **« Ce que l'application ne fera jamais pour améliorer un ratio : maltraiter le tracker »
   (NE-DOIT-PAS-8).** No surface in this design offers a retry, a burst, or any automation over a
   tracker call — every read here is a single call per screen visit, like every other surface.
5. **« L'action retenue : libérer une obligation », et le retrait externe est un cas GÉRÉ.** Served
   by **S4 — the obligation's release verb** (§ 4.4): a confirmation (NE-DOIT-PAS-6 — destroying a
   commitment without consent), and an obligation closed by an external qBittorrent removal reads
   « released by removal », never a silent anomaly (NE-DOIT-PAS-5).
6. **« L'alerte de ratio. »** Served by **S5 — the ratio alert** (§ 4.5): a per-tracker threshold,
   set from the same policy panel (§13 — one derivation, not a second control), and the alert shown
   where it lives: on the tracker's own row and detail, and as a **badge on the Trackers tab of the
   bottom bar** (ruling 12). There is no notifications box and no line on Système. **Push (FCM, iOS,
   Android) is NOT drawn here** — § 5 names it as a platform demand this lot files and does not build.
7. **« Le ranking suit le ratio. »** Served by **S7 — the ranking editor** (§ 4.7): the screen
   `RankingPanel`'s production twin, with the live preview already computed server-side, and a
   ratio-aware criterion this design proposes as a demand (§ 2, § 6) because the scored release
   carries no such field today.
8. **« Ce qui est montré d'un tracker, au-delà du ratio : Download / Upload, la tendance, et par
   torrent actif son échéance et son ratio. »** Served by **S2** for the per-torrent half and by
   **S1**'s row for the tracker-level volumes and trend.
9. **« Le ratio affiché est celui que le tracker reconnaît » (NE-DOIT-PAS-1).** No surface computes
   a ratio; every ratio drawn is the mock's own field, read verbatim — held by R-L16-a (§ 4.8).

---

## 2. The contract (D7) — and it comes FIRST

The maquette's own contract declares **none** of the four operations this lot needs, though the
backend answers three of them already:

    python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted(p for p in d['paths'] if 'obligation' in p or 'stalled' in p or 'download' in p or 'ranking' in p or 'tracker' in p))"

reads `[]`. The backend's own contract answers all four:

    python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(p for p in d['paths'] if 'obligation' in p or 'stalled' in p or 'download' in p or 'ranking' in p))"

reads `/api/acquisition/downloads`, `/api/acquisition/obligations`,
`/api/acquisition/ranking/preview`, `/api/acquisition/stalled-grabs` — and **no path contains
`tracker`** in either contract: there is no tracker-level read or write anywhere today.

### 2.1 What each existing operation answers, read from the backend's own schemas

| Operation | operationId | Answers | What it is missing for this lot |
| --- | --- | --- | --- |
| `GET /api/acquisition/obligations` | `get_obligations_...` | `ObligationsResponse{items: ObligationItem[]}` — `source_tracker`, `min_ratio`, `min_seed_time_s`, `observed_ratio`, `added_at`, `breached_at`/`satisfied_at`/`released_at`, `title` | nothing — it is the obligation itself, tracker-scoped already |
| `GET /api/acquisition/stalled-grabs` | `get_stalled_grabs_...` | `StalledGrabsResponse{items: StalledGrabItem[]}` — `reason` in clear French, `since`, `title`, `kind`/`season`/`episode` | no tracker or ratio field at all — the `reason` string is the only place a ratio cause could show, and today nothing writes a ratio-specific one (§ 6) |
| `GET /api/acquisition/downloads` | `get_acquisition_downloads_...` | `AcquisitionDownloadsResponse{downloads: AcquisitionDownload[], client_available}` — per torrent: `state`, `progress`, `eta_seconds`, `size_bytes`, `info_hash`, `kind`, `title` | **no tracker, no ratio, no deadline field on `AcquisitionDownload`** — § 18's « par torrent actif son échéance et son ratio » cannot be drawn from this shape as it stands (§ 6) |
| `POST /api/acquisition/ranking/preview` | `preview_ranking_...` | `RankingPreviewResponse{ranked: RankingPreviewRelease[], known_trackers: string[]}` from a POSTed `RankingConfig{criteria, bonuses, min_seeders, size_thresholds_by_type}` | `RankingCriterion.field` is read by `getattr(TrackerResult, field)` (`personalscraper/api/tracker/_ranking.py:100`) — `provider` exists on `TrackerResult` (categorical, scorable today) but **no ratio-derived field does** (§ 6) |

Read at `frontend/openapi.json`'s `components/schemas` for the four names above, and at
`personalscraper/api/tracker/_ranking.py` and `personalscraper/api/tracker/_base.py` for `rank()`
and `TrackerResult`.

**No tracker-level aggregate exists anywhere.** `config.example/tracker.json5` names exactly two
providers today (`c411`, `tr4ker`), each with `enabled`, `cross_seed`, and an optional `economy:
{target_ratio, min_ratio, min_seed_time, hit_and_run_grace}` (`personalscraper/conf/models/api_config.py:216`,
`:276`) — the config the policy write edits. Nothing reads a tracker's current DOWNLOAD / UPLOAD
volume or its trend; `ObligationItem` carries `observed_ratio` per OBLIGATION, not per tracker, and
only for a torrent still owing seed time — a tracker with no open obligation has no field anywhere
answering its own ratio.

### 2.2 What is declared as owed (three existing, seeded from the backend's shapes — D7)

`GET /api/acquisition/obligations`, `/stalled-grabs`, `/downloads` are added to the maquette's
contract with the shapes § 2.1 measured, **seeded from the running backend** (D7 — a contract
diverges deliberately only where the experience needs more; here it does not, for these three).
`POST /api/acquisition/ranking/preview` likewise, unchanged.

### 2.3 What is proposed as a NEW demand (§ 6 carries the register form)

Four gaps § 2.1 measured have no operation in either contract to extend, and none is asserted here
— each is a row this design PROPOSES:

1. **A tracker-level summary read.** Name, ratio, Download / Upload volumes, the trend, the alert
   threshold — nothing existing answers a tracker as its own subject.
2. **The tracker policy write**, already named in `backend-demands-architecture.md` § 4 in prose:
   `min_ratio`, `min_seed_time` (and the alert threshold, folded into the same write — § 13, one
   derivation) writable per tracker.
3. **`AcquisitionDownload` extended** with the active torrent's tracker, its ratio, and its
   deadline (its `min_seed_time` horizon) — or a tracker-keyed join the summary read (item 1)
   carries instead. The design does not choose which; § 6 files both readings as one demand and
   names the shape the interface needs, per D7.
4. **A ratio-derived field on `TrackerResult`**, so a `RankingCriterion` with `field:
   "tracker_ratio_state"` (or equivalent) can score it exactly as `field: "provider"` already
   does — `rank()`'s `getattr(r, c.field, None)` (§ 2.1) needs nothing else.
5. **The obligation's release verb.** `POST /api/acquisition/obligations/{id}/release` (or
   equivalent) — absent from both contracts, named already in `backend-demands-architecture.md` §
   4's « a verb to RELEASE an obligation early ».

### 2.4 The mocks, and what each must MOVE (D7 — « a mock that answers without moving certifies nothing »)

`frontend/maquette/design/src/mocks/handlers/acquisition.ts` is **359 non-blank lines**
(`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts`, on `dafe29ec1`;
it read 338 on `08400a22a`), 41 under the 400 ceiling — three read handlers and a write would not
fit, so the phase that adds handlers measures again before deciding
whether they land there or in a new `mocks/handlers/trackers.ts`, by SUBJECT (`staging.ts` /
`pipeline.ts` precedent, `frontend-architecture.md` § 4, L20 phase 1), not by size alone.

- `obligations` answers a list a **release** call REMOVES an item from (moved to `satisfied_at` /
  a released state), never a static seed.
- `stalled-grabs` answers a `reason` string; the ratio-specific reason is COMPOSED by the mock from
  the same obligation it is deferred against, never a second, disagreeing fact (§ 13).
- `downloads` answers the per-torrent list the tracker detail's obligations and the summary read
  must AGREE with — one seed, several projections.
- the tracker policy write moves the seed's `min_ratio` / `min_seed_time` / alert threshold, and
  the summary read projects the SAME fields back (§ 13 — R-L16-e's agreement).
- the release verb moves the obligation to `released_at` set, `breached_at` untouched, and — for
  the external-removal case — a SEPARATE seeded scenario answers `released_at` set with no verb
  ever called, so R-L16-c can prove the HANDLED read without a mutation that cannot exist against
  `main` (§ 4.8).

---

## 3. The addresses (D1)

| Surface | Tier | Address |
| --- | --- | --- |
| the trackers list | a page | `/trackers` — its own path, D1's content tier: a tracker is a thing being looked at |
| a tracker's detail | content | `/trackers/$name` — identified, shareable, reloadable, DOIT-10 |
| the policy panel (min_ratio, min_seed_time, alert threshold) | screen state | `/trackers/$name?panel=setting:policy` — the existing panel parameter's `<kind>:<subject>` shape (L20 precedent). **Provisional as written**: the kind `setting` is the settings feature's (`app/addressed-panels.ts` registers its producer, and its subject is a `<file>:<key>` identity), so whether this panel takes a kind of its own is measured at phase 6 and reported (STOP D), not improvised |
| the release confirmation | transient | **no URL** — D1b rule 1, adjusting a surface, never arriving; a confirmation carries no address anywhere else in this codebase |
| the ranking editor | content | its own path under the settings page — `/settings/ranking` (D1: it is identified, and DOIT-10 owes it a URL; « under the settings page » is the objective's own phrase in `frontend-architecture.md`'s L16 entry) |

**Why the tracker detail is a SCREEN and not a panel.** The same reasoning L20 wrote for a run's
detail (`docs/features/maquette-l20/DESIGN.md@60c6d9b1d` § 2) applies verbatim: a tracker is
identified by its name, is shareable and reloadable, and D1's content tier is exactly this.
`SCREEN_PARENTS` (`lib/addresses.ts`) gains `"/trackers/$name": "trackers"`: the host page's id is
`trackers`, the id of its navigation row (§ 4.1), and its path `PAGE_PATHS.trackers = "/trackers"`.

**Why the policy panel carries no path of its own but the ranking editor does.** The panel is a
SETTING of the tracker's own screen (D1b rule 1 — adjusting replaces); the ranking editor is a
distinct SUBJECT — the weights that rank every release, not one tracker's — and DOIT-10 owes a
subject its own door.

---

## 4. The surfaces, drawn

Copy is given in « guillemets » exactly as `fr.json` will carry it, with the English key beside it
where one is proposed; none is retyped where a key already exists.

### 4.1 S1 — The trackers list

**Its place.** A new page, `features/trackers/page.tsx`, and **a button of the bottom bar** (ruled,
§ 5): one navigation row in `app/navigation.ts` — `id: "trackers"`, `path: PAGE_PATHS.trackers`,
`inBar: true`, `group: "supervision"` (the group of the pages one goes to SEE — Acquisition and
Médiathèque), `root: "body"`, `region: "trackers/body"`, and, from the alert's phase, `badge:
trackersBadge` — a function the feature exports and the frame names once, never its counter
(`docs/features/maquette-l22/DESIGN.md` § 3.6). The row is the page's whole declaration; the bar
draws what the table says.

**The bar around it.** After L22b the bar holds Acquisition and Médiathèque and draws two buttons; this
page makes it three for an account that holds the right — two for one that does not, so the bar has two,
three or four places according to the account (organisation ruling 11) — **each button taking an equal
share, a third at three** — the frame rule the operator dictated on
2026-09-26 (« la barre du bas s'adapte toujours au nombre de boutons présents, chaque bouton prend
toujours le même ratio », L22's OPEN 2): the bar draws only the buttons present, in equal shares of 1/n,
n from 2 to 4, and never an empty slot. The rule is L22's (its R-L22-s, written at its phase 19); this lot
reads it at three and adds nothing to the frame. The fourth place stays free until a daily page
deserves it (§ 17 point 4). **The bar is composed by rights** — Trackers is shown to the accounts that
hold the right, Acquisition and Médiathèque to all — and the model that composes it is L18's, not this
lot's (§ 5, OPEN 2: what this lot draws before that model exists).

**What is on the screen.** Per tracker: its name, its ratio (`screens.trackers.ratio`), the trend
(`screens.trackers.trend` — up / stable / down, in words, never a bare arrow with no label,
NE-DOIT-PAS-4), Download / Upload volumes (`screens.trackers.volumes`), and — when the alert
threshold is crossed — the alert badge (S5). A row is a PATH to `/trackers/$name`.

**`data-part`** (English, D4): `trackers`, `trackers/row`, `trackers/ratio`, `trackers/trend`,
`trackers/volumes`, `trackers/alert`. `data-region="trackers/body"` for the oracle.

**Named states.**

| id | What is on the screen |
| --- | --- |
| `trackers-list` | the roster, each row with its ratio, trend, volumes |
| `trackers-empty` | no tracker configured — « Aucun tracker configuré. » (`screens.trackers.empty`), a real state (fresh install: `config.example/tracker.json5` ships two, but a config can hold zero) |
| `trackers-loading` | the phase dial's own loading skeleton |
| `trackers-error` | `SurfaceError` |

### 4.2 S2 — A tracker's detail

**Its place.** `/trackers/$name`, new file `features/trackers/tracker-screen.tsx`.

**What is on the screen.** The head repeats the ratio, the volumes and the trend (S1's row, at
rest — §13, one derivation, drawn twice from the same read). Then, per § 18's own list: **the
obligations** — each with its deadline and its ratio owed vs. observed, the release verb (S4) on
each; **the active torrents** on this tracker, each with its deadline and its own ratio (§ 2.3
item 3's demand); a path to the policy panel (S3); the alert threshold, and whether it is crossed
(S5).

**`data-part`**: `tracker`, `tracker/ratio`, `tracker/volumes`, `tracker/trend`,
`tracker/obligation`, `tracker/obligation-release`, `tracker/torrent`, `tracker/policy-link`,
`tracker/alert`. `data-region="tracker/body"`.

**Named states.**

| id | What is on the screen |
| --- | --- |
| `tracker-detail` | the head, the obligations, the active torrents |
| `tracker-alert-active` | the threshold crossed — S5's state, drawn on this screen too, never only on the list |
| `tracker-detail-empty-active` | no active torrent on this tracker right now — « Rien en cours sur ce tracker. » (`screens.tracker.emptyActive`), a real answer (§ 8) |
| `tracker-detail-loading` · `tracker-detail-error` | the two the contract requires of every surface |

### 4.3 S3 — The policy panel

**Its place.** `/trackers/$name?panel=setting:policy`, DOIT-3's own surface: the policy of the
tracker the operator is LOOKING AT, not a settings file relayed.

**What is on the screen.** `min_ratio` and `min_seed_time` (the deletion floor and the seed
obligation, `personalscraper/conf/models/api_config.py:216`'s own fields), and the ratio alert
threshold (S5) in the SAME panel — § 13, one derivation, one save. A guidance line names what
changing the floor costs: it is the point at which a torrent may be freed, not a target.

**`data-part`**: `policy`, `policy/min-ratio`, `policy/min-seed-time`, `policy/alert-threshold`,
`policy/save`. `data-region="tracker/policy"`.

**Named state.** `tracker-policy-panel` — one state; the panel reuses the settings feature's
existing field primitives (a `number` field, precedent: L20 § 8.3's bound), so it needs no loading
or error state of its own beyond what that primitive already carries (§ 13 — inventing a second
one would be the defect D9 rule 1 forbids by another name).

### 4.4 S4 — The obligation's release verb

**Its place.** On the obligation's row, wherever it is drawn (S2 primarily).

**What happens.** « Libérer l'obligation » (`screens.tracker.releaseObligation`,
`data-obligation-release`) opens a confirmation — NE-DOIT-PAS-6, destroying a seed commitment
without consent — naming what is lost: the ratio still owed, in words. Confirmed, the obligation
moves to released; the row updates in the SAME render the operation answers (§13).

**The external-removal case.** An obligation whose torrent the operator removed by hand in
qBittorrent reads `released_at` set with **no release call ever made from this interface** —
drawn as « Libérée — retrait externe » (`screens.tracker.releasedExternally`), never as an
anomaly, never as a silent disappearance from the list (NE-DOIT-PAS-5). The reconciliation itself
— the backend noticing the removal — is a demand (§ 6), not something this lot builds; the
INTERFACE'S job is to read the state honestly once the field says so.

**Named states.** `obligation-release-confirm` (the confirmation, transient, no URL — D1);
`obligation-released-externally` (the HANDLED read, on S2's list).

### 4.5 S5 — The ratio alert

**Its place.** Where the ratio lives, and nowhere else (ruling 12: every thing speaks where it lives,
and the bar tab that carries it takes a badge). Four readers, ONE derivation: **a badge on the Trackers tab
of the bottom bar** (the frame draws it from the row's `badge` function), a badge on S1's row, a block on
S2's detail, and the threshold in S3's panel — the same shape R-L20-g held for the lock and its levers,
with a fourth reader. **There is no notifications box** that collects it, **no alert line on Système**,
and no second place: Système's history (L20) stays the only trace of the past, and the maintenance and the
machine's faults are Système's own badge on the menu button (L22's OPEN 8), a different thing.

**What is on the screen.** When a tracker's ratio falls under its threshold: « Ratio sous le seuil
— <tracker> » (`screens.trackers.alertBelowThreshold`), the ratio itself, and the threshold it
crossed. On the bar, the Trackers tab carries the count (`tabBarBadge`, the badge's one visual language,
« this has something to say »); **what the count counts is OPEN** (§ 5, OPEN 3). The function reads the
tracker summary read (§ 2.3 item 1), which the stream's `RatioMeasured` events refresh through this lot's
`live.ts` — so the tab's badge moves without a refetch, like the row. Today those events are EXEMPTED
from every live rule, by name: `acquisitionLiveExemptions` (`features/acquisition/live.ts`) lists
`RatioMeasured` and the three `SeedObligation*` events as belonging to « a ratio surface that has no page
yet (B-144) » — this lot gives them that page, claims them in `features/trackers/live.ts`, and removes
those four names from the exemption (the cross-seed events and `TrackerAuthFailed` stay named there: L17's,
and the system feature's). **No push notification is drawn** —
FCM / iOS / Android is a platform demand (`backend-demands-architecture.md` § 4), filed and not built;
this lot's own surface IS the in-app signal DOIT-1 already asks every state to carry.

**Named states.** `tracker-alert-active` — read at S1 (badge) and S2 (block; § 4.2 lists it there, it is
the same state) from the same field; no second state for the badge alone (§ 13). `bar-trackers-alert` — the bar at three buttons, the Trackers tab
carrying its badge, in `harness/states/frame.ts` beside L22's `bar-todo-badge`; the same fact, read a
fourth time, on the frame's own region.

### 4.6 S6 — A card deferred for ratio names its tracker (DOIT-2's ratio half)

**Its place.** The acquisition card in « En cours » — `features/acquisition`. The first drawing put this
on Arrivées' stuck queue; **that page dies at L22b** (ruling 2 of 2026-09-15, L22's phase 25) and the map's
proposed DOIT-2 surface is `features/acquisition`: « a card says why it waits » (L22 § 6.3), and what
stagnates for a reason other than a decision reads on its card in « En cours » with its reason (ruling 7,
L22 § 3.3). **`stalled-grabs` is not the Arrivées queue**: it answers the acquisitions parked at « récupéré »
that never reached the library (the rollup's own docstring in `frontend/openapi.json`, `stalled_grabs`, says
« DISTINCT de `stuck` »), and the maquette has no consumer of it today
(`git grep -n -w 'stalled-grabs' -- frontend/maquette` reads one comment, in `features/acquisition/panel-more.ts`).
The card is where the operator already looks for a medium that waits; this lot does not create a list.

**What changes.** A card whose `reason` names a ratio cause gains a path to `/trackers/$name` — « Voir le
tracker » (`screens.acquisition.ratioReasonTracker`) — instead of reading as an unexplained wait, and its
reason names the cause in clear words, composed by the mock from the same obligation it is deferred against
(§ 2.4). **Invariant 7 holds**: `features/acquisition` does not import `features/trackers`; the path is an
address (`lib/addresses.ts`), not a component, and the helper is `crossReference()` (`ui/variants`), which
Système's locks block already draws toward Maintenance (`features/system/locks.tsx:146`) — the one
`features/acquisition/now-tab.tsx` draws toward Arrivées dies with that page (L22b's phase 21).

**The seed is a derivation, said as one.** No card of the mock's seeds is deferred for ratio, and § 13
forbids inventing data: the phase re-casts a real waiting card under the ratio reason its obligation
composes, or draws the state from its seed marked `x-unseeded` — the contract's own word for « nothing was
invented here » and « nobody looked » being different things — and the steward chooses (a STOP D at the
phase's opening, the precedent L22's phases 9 and 10 set).

**Named state.** `acq-card-ratio-reason` — one state, in `harness/states/acquisition.ts`, on Acquisition's
existing region, naming the divergence it adds there.

### 4.7 S7 — The ranking editor (B-298)

**Its place.** `/settings/ranking`, new files `features/settings/ranking-screen.tsx` (or a
`features/ranking/` feature the settings route composes — the plan's opening measure decides,
§ 5's phase). The settings rubric « Classement des releases » (`features/settings/page.tsx:305`,
`screens.settings.rankingTitle`) gains its path; the quality screen's `data-toast`
(`features/releases/quality-screen.tsx:283`, `screens.profile.rankingToast`) is REMOVED in the
same phase — B-298 closes when the promise it names is kept, not before.

**What is on the screen.** The criteria list `RankingConfig.criteria` already answers (field,
weight, values or thresholds, `prefer`), a live preview through `POST
/api/acquisition/ranking/preview` — `RankingPreviewResponse.ranked`, sorted, excluded rows
flagged and sunk last (the backend's own words, § 2.1) — and, once § 2.3 item 4 lands, a new
criterion the ratio can drive, using `known_trackers` (already answered) to populate a
tracker-keyed field the same way `provider` does today.

**Named states.** `ranking-editor` (the criteria, the live preview); `ranking-editor-loading` ·
`ranking-editor-error` (the two the contract requires).

### 4.8 The rules that bite

Numbers: the implementer binds `R-L16-a … R-L16-h` to the next free labels on the day, re-taking
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against the branch's
base at that moment (L20's own phase 1 precedent).

| Rule | What it READS | The mutation that fells it |
| --- | --- | --- |
| **R-L16-a** — NE-DOIT-PAS-1, the ratio is the tracker's | every ratio drawn (S1's row, S2's head, S2's per-torrent list) compared against the mock's own field, never a local computation | compute an average client-side → the comparison falls |
| **R-L16-b** — the release verb | the confirmation, the operation CALLED (`window.__mocks.answered()`), the obligation moved out of the open list in the SAME render | make the confirm button message without calling → the network hold falls |
| **R-L16-c** — the external-removal HANDLED case | a seeded obligation with `released_at` set and no release call anywhere in the walk — drawn as « retrait externe », never as still-open nor as an unexplained gap | draw it as still open → falls. Draw it with no explanation → falls too |
| **R-L16-d** — DOIT-3, the policy write | the panel's save calling the tracker policy operation; the tracker's OWN read (S1, S2) reflecting the new `min_ratio`/`min_seed_time` in the following render | message without calling → the network hold falls |
| **R-L16-e** — §13, one derivation for the alert (four readers, ruling 12) | the threshold read from ONE field by S1's badge, S2's block, S3's panel **and the Trackers tab's badge on the bar**; changing it in S3 moves what S1, S2 and the tab draw | disagree the badge from the block → the agreement falls. Disagree the tab's count from the row's → falls too |
| **R-L16-f** — the ranking preview | the criteria POSTed, the rows drawn compared against `RankingPreviewResponse.ranked`, the `excluded` flag honoured (sunk last, still visible) | draw a constant ranking → the comparison falls. Hide excluded rows → falls too |
| **R-L16-g** — DOIT-2's ratio reason | the acquisition card in « En cours » naming a ratio cause, its path to `/trackers/$name`, read on the URL after a tap | drop the path → falls |
| **R-L16-h** — the addresses (D1) and the tab | `/trackers/$name` declared with the list page as its `SCREEN_PARENTS` entry; opening it PUSHES (`history.length`); the policy panel ADJUSTS and pushes nothing; the Trackers tab is a bar button whose tap REPLACES (§ 16 point 2) and the bar reads three equal shares (L22's R-L22-s, re-run at three, not re-written) | make the panel push → the `history.length` hold falls. Make the tab push → falls too |

**Every one is seen RED against `main` with no mutation needed** — none of these surfaces exists
there. The report records the red reading per rule, as every prior lot's has.

---

## 5. What is NOT drawn

- **Push notifications** (FCM, iOS, Android) — a platform demand (`backend-demands-architecture.md`
  § 4), filed here and built by whichever lot L11's entry points are extended for. This design
  draws the in-app alert only.
- **Cross-seed** — §19, L17's, which depends on L16 and follows it. The Trackers tab's badge gains its
  term there (ruling 12: « the ratio and the cross-seed on Trackers »); L16 does not pre-write it.
- **The bar's composition by rights, and the accounts** — L18's (ruling 11's « by rights », ruling 14's
  « Comptes »). L16 adds no role and no flag to `app/navigation.ts` unless OPEN 2 below is ruled B.
- **A notifications box, or an alert line on Système** — none, by ruling 12.
- **A tracker's account settings** (API key, passkey, enable/disable) — those already live in
  `tracker.json5`'s `providers.<name>.enabled` / credentials, unrelated to the ratio, and stay
  wherever the trackers' activation surface already is or will be drawn; this lot's policy panel
  is `economy` only.
- **A mean or global ratio figure anywhere** — § 1 clause 1 forbids it outright.

### Ruled — the trackers domain's placement

**Ruled 2026-09-26 (operator, organisation ruling 11): the place Arrivées frees in the bottom bar goes to
a page « Trackers » — ratio, cross-seed, the tracker itself — and the bar is composed by rights (§ 17
point 4); the page is shown only to the accounts that hold the right** (his words: « La place sera pour la
gestion des trackers (ratio, cross-seed, tracker, ...), elle s'affichera que pour ceux qui y ont droits »).
The question the first drawing left
open, and its two readings, kept as they were written:

- **Reading A — a fifth bar tab.** `inBar: true`, alongside `acq` / `lib` / `arr` / `sys`. It argued that the
  ratio is watched, not merely configured, the same distinction the table's comment draws between the bar
  and Réglages/Maintenance.
- **Reading B — the drawer, beside Réglages and Maintenance.** `inBar: false`, a fifth row in the drawer's
  then four. It argued that a tracker is acted on rarely — set a policy, release an obligation — closer to
  Réglages' own cadence than to Acquisition's, and that D12's Q6 refusal of a fifth bar slot was a precedent
  against growing the bar.

**Neither is what he ruled.** A asked for a FIFTH place on a bar already at four; the ruling adds none — it
gives the page the place Arrivées frees (the `arr` row dies at L22b) and Système frees another (it leaves
the bar for the drawer), so the bar holds Acquisition, Médiathèque and Trackers, four at most, and D12's
precedent is not crossed. B put the page in the drawer because it is acted on rarely; the ruling reads the
other way — the ratio and the cross-seed are what one looks at every day, they take a badge on their tab
(ruling 12), and § 17 point 4 names Trackers in the bar for the accounts that hold the right, while
Système, which one consults on a doubt, is the one that goes to the drawer.

### OPEN design questions — for the operator, two readings each, no choice made here

What this re-read cannot decide from the rulings is listed here and only here. Each waits for his word,
and the plan's phases say which of them they read (`plan/INDEX.md`).

**OPEN 1 — whether the Trackers page ships with the ratio alone at L16, its bar row with it.** Ruling 11
gives the place to a page of « ratio, cross-seed, the tracker », and the cross-seed is L17's, after L16.
*Reading A*: the page ships at L16 with the ratio, its row in the bar from L16's phase 2 — the bar reads
three from then — and L17 adds the cross-seed to the same page and a second term to the same badge; a tab
of one subject before it is two. *Reading B*: L16 builds the page and every surface of it but lands its
row in the drawer (`inBar: false`, group « supervision »; its badge, by the frame's own sum over the rows
the bar does not hold, on the menu button), and L17 moves it into the bar once both subjects exist — the
tab is drawn once, whole, and the bar stays at two between the lots; the cost is one row edited in two lots,
and the ratio's badge speaking on the menu button, not on a tab, for that interval.

**OPEN 2 — which account right opens Trackers before L18's model exists.** The bar is composed by rights,
and the rights model is L18's; the mock has one account, the Operator. *Reading A*: the row carries no
right — L16 draws Trackers for the only account the mock has, adds no field to the navigation table (the
line L22's § 7.1 holds), and « shown only to the accounts that hold the right » is proved by L18, when a
second identity exists to prove it against; L16's rules read the tab shown for the Operator and say that the
hidden half is not yet provable. *Reading B*: the row names the right that opens it — one declared value, the
Operator's, read by the bar to draw or hide the tab — so a rule can prove the tab shown and hidden against a
second mock identity; the cost is a right field in the navigation table before L18's model, the small rights
model L22's OPEN 11 refused for the same reason.

**OPEN 3 — what the Trackers tab's badge counts.** Ruling 12 says the ratio speaks on its tab and does not
say by what number. *Reading A*: the trackers under their alert threshold — one per tracker whose ratio has
crossed it, S5's own fact, read four times from one field; the cross-seed's refusals join the count at L17.
*Reading B*: also the obligations in breach — those with `breached_at` set and neither satisfied nor
released (`ObligationItem`, § 2.1) — what a tracker will hold against the operator; B says more, and A keeps
the badge to what the alert dictates.

---

## 6. Register rows and demands touched

**BUGS.md**, read, not edited by this design (no BUGS.md edit — this PR is documentation only):

- **B-143** — §17, out of this lot's scope (L18's).
- **B-144** — « §18 (ratio per tracker) needs three operations the backend already answers and
  nothing calls » — this design's § 2.2 closes the READING half; § 2.3's demands close the rest.
- **B-145** — §19, out of scope (L17's).
- **B-257** — « Push notifications are declined for L11 and their consumer is §18's ratio alert,
  which is L16 » (`fixed #534`, closed already — L16 is the named consumer, § 5 above).
- **B-298** — « The ranking editor is a promise » — closes when S7 lands and the toast (§ 4.7)
  is removed.

**`product-intent-map.md`**, read, amended by the OPERATOR, not by this PR (the map's own header):

- **DOIT-13** row — `to draw`, owner `L16` — this design is that drawing; the phase that lands S1
  and S2 is what the closing phase reports against it.
- **DOIT-2** row — `partly`, « to draw: a torrent deferred for ratio or space — L16 (§18) » — this
  design's § 4.6 is the ratio half, drawn on the acquisition card, the surface L22 proposes for the row
  (its § 6.3), not on `features/arrivals`, which the row cites today and which dies at L22b; the space
  half is not this lot's and the row says so when amended.
- **DOIT-3** row — `partly`, « to draw: the tracker policy set from the ratio surface — L16 » — § 4.3.

**`docs/reference/backend-demands-architecture.md` § 4**, already carrying the prose this design
makes concrete (§ 2.3): the policy write, the release verb, the external-removal reconciliation,
the alert threshold and its push channel, the ranking input, the per-tracker volumes/trend/deadline
reads. **Nothing in § 2.3 is a NEW clause** — every item there is this design's typed shape of a
sentence § 4 already carries; none invents a demand the register does not already owe.

**`docs/reference/frontend-backend-demands.md`**, computed, not edited by this PR — the phase that
opens the contract (§ 2) regenerates it with `scripts/compare-contracts.py --write` and reads its
counters before and after, as every prior lot's phase 1 has.
