# L16 — §18, the ratio · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L16 — §18, the ratio`. It is
not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every
figure carries the command that produces it, every decision carries its reason, every screen
carries its named states. **Nothing under `frontend/maquette/design/` was touched to write it** —
the lot opens after L13c, and this is the design read before it does.

---

## 0. What L16 owes, said once

`product-intent.md` § 18, « Ce que l'opérateur a tranché » (dictated 2026-08-30), gives L16 five
things, and none of them is a decision left to draw:

| # | The thing | The operation | Its clause |
| --- | --- | --- | --- |
| 1 | the ratio, read **per tracker**, never averaged into one figure | `GET /api/acquisition/obligations`, `/stalled-grabs`, `/downloads` — answering, called by nothing | DOIT-13 |
| 2 | **release an obligation early** — including a HANDLED case when the stop is an external removal in qBittorrent | none: a write, absent from both contracts | § 18, DOIT-2 |
| 3 | a **per-tracker ratio alert**, a threshold the operator sets (push is a platform demand, not this lot's) | none: a write and a read, absent from both contracts | § 18 |
| 4 | the **ranking follows the ratio** — a release on a low-ratio tracker may lose points | `POST /api/acquisition/ranking/preview` — answering, called by nothing; the ratio TERM itself does not exist on the scored release | § 18, and B-298 |
| 5 | what is shown **beyond the ratio**: Download / Upload volumes, the trend, and per ACTIVE torrent its deadline and its ratio | none of the three existing reads carries it | § 18 |

And one register row this lot is named against directly: **DOIT-2**'s ratio half — « a torrent
deferred for ratio or space » — is Arrivées' stuck queue, already partly served (R66), never
drawing the ratio-specific reason. **No proposed decision anywhere in this design**: § 18's own
words, « l'interface expose ; l'opérateur juge », hold for every screen below.

---

## 1. What §18 dictates, clause by clause, and the surface that serves it

1. **« Le ratio se lit PAR TRACKER, jamais en un seul chiffre. »** Served by **S1 — the trackers
   list** (§ 4.1): one row per tracker, its own ratio, never an average. No surface in this design
   computes a mean across trackers.
2. **« Une obligation de seed est un rien qui a sa raison » (§ 8, DOIT-2).** Served by **S2 — a
   tracker's detail** (§ 4.2), which lists the tracker's obligations with `reason`-shaped rows —
   deadline, ratio owed, ratio observed — and by **S6 — the stuck queue's ratio reason** (§ 4.6),
   which names the same fact where DOIT-2 already lives, Arrivées.
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
   on the tracker's own row and detail. **Push (FCM, iOS, Android) is NOT drawn here** — § 5 names
   it as a platform demand this lot files and does not build.
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
| `POST /api/acquisition/ranking/preview` | `preview_ranking_...` | `RankingPreviewResponse{ranked: RankingPreviewRelease[], known_trackers: string[]}` from a POSTed `RankingConfig{criteria, bonuses, min_seeders, size_thresholds_by_type}` | `RankingCriterion.field` is read by `getattr(TrackerResult, field)` (`personalscraper/api/tracker/_ranking.py:99`) — `provider` exists on `TrackerResult` (categorical, scorable today) but **no ratio-derived field does** (§ 6) |

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

`frontend/maquette/design/src/mocks/handlers/acquisition.ts` is **338 non-blank lines**
(`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts`),
comfortably under the 400 ceiling — the phase that adds handlers measures again before deciding
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
| the policy panel (min_ratio, min_seed_time, alert threshold) | screen state | `/trackers/$name?panel=setting:policy` — the existing panel parameter's `<kind>:<subject>` shape (L20 precedent) |
| the release confirmation | transient | **no URL** — D1b rule 1, adjusting a surface, never arriving; a confirmation carries no address anywhere else in this codebase |
| the ranking editor | content | its own path under the settings page — `/settings/ranking` (D1: it is identified, and DOIT-10 owes it a URL; « under the settings page » is the objective's own phrase in `frontend-architecture.md`'s L16 entry) |

**Why the tracker detail is a SCREEN and not a panel.** The same reasoning L20 wrote for a run's
detail (`docs/features/maquette-l20/DESIGN.md@60c6d9b1d` § 2) applies verbatim: a tracker is
identified by its name, is shareable and reloadable, and D1's content tier is exactly this.
`SCREEN_PARENTS` (`lib/addresses.ts`) gains `"/trackers/$name": "trackers"` once the host page's id
is settled (§ 5, open question).

**Why the policy panel carries no path of its own but the ranking editor does.** The panel is a
SETTING of the tracker's own screen (D1b rule 1 — adjusting replaces); the ranking editor is a
distinct SUBJECT — the weights that rank every release, not one tracker's — and DOIT-10 owes a
subject its own door.

---

## 4. The surfaces, drawn

Copy is given in « guillemets » exactly as `fr.json` will carry it, with the English key beside it
where one is proposed; none is retyped where a key already exists.

### 4.1 S1 — The trackers list

**Its place.** A new page, `features/trackers/page.tsx`. Whether it sits in the bottom bar or the
drawer is OPEN (§ 5) — this design draws the list itself identically either way; only the
navigation row's `inBar` value and its group differ.

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
| `tracker-detail-alert` | the threshold crossed — the alert drawn on this screen too (S5), never only on the list |
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

**Its place.** A badge on S1's row, a block on S2's detail, and its threshold lives in S3's panel
(one derivation, three readers — the same shape R-L20-g held for the lock and its levers).

**What is on the screen.** When a tracker's ratio falls under its threshold: « Ratio sous le seuil
— <tracker> » (`screens.trackers.alertBelowThreshold`), the ratio itself, and the threshold it
crossed. **No push notification is drawn** — FCM / iOS / Android is a platform demand
(`backend-demands-architecture.md` § 4), filed and not built; this lot's own surface IS the
in-app signal DOIT-1 already asks every state to carry.

**Named state.** `tracker-alert-active` — read at both S1 (badge) and S2 (block) from the same
field; no second state for the badge alone (§ 13).

### 4.6 S6 — The stuck queue's ratio reason (DOIT-2's ratio half)

**Its place.** Arrivées' existing stuck queue (`features/arrivals`), which already draws a
deferred torrent with a reason (R66) — this lot does not create a new list, it names the reason
`stalled-grabs` answers when the cause is ratio, and cross-references the tracker (`crossReference()`,
the same helper L20's locks block uses toward Maintenance).

**What changes.** A row whose `reason` names a ratio cause gains a path to `/trackers/$name` — «
Voir le tracker » — instead of reading as an unexplained stall. **Invariant 7 holds**: Arrivées
does not import `features/trackers`; the path is an address (`lib/addresses.ts`), not a component.

**Named state.** `stalled-ratio-reason` — one state, on Arrivées' existing region, naming the
divergence it adds there.

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
| **R-L16-e** — §13, one derivation for the alert | the threshold read from ONE field by S1's badge, S2's block and S3's panel; changing it in S3 moves what S1 and S2 draw | disagree the badge from the block → the agreement falls |
| **R-L16-f** — the ranking preview | the criteria POSTed, the rows drawn compared against `RankingPreviewResponse.ranked`, the `excluded` flag honoured (sunk last, still visible) | draw a constant ranking → the comparison falls. Hide excluded rows → falls too |
| **R-L16-g** — DOIT-2's ratio reason | Arrivées' stuck row naming a ratio cause, its path to `/trackers/$name`, read on the URL after a tap | drop the path → falls |
| **R-L16-h** — the addresses (D1) | `/trackers/$name` declared with the list page as its `SCREEN_PARENTS` entry; opening it PUSHES (`history.length`); the policy panel ADJUSTS and pushes nothing | make the panel push → the `history.length` hold falls |

**Every one is seen RED against `main` with no mutation needed** — none of these surfaces exists
there. The report records the red reading per rule, as every prior lot's has.

---

## 5. What is NOT drawn

- **Push notifications** (FCM, iOS, Android) — a platform demand (`backend-demands-architecture.md`
  § 4), filed here and built by whichever lot L11's entry points are extended for. This design
  draws the in-app alert only.
- **Cross-seed** — §19, L17's, which depends on L16 and follows it.
- **A tracker's account settings** (API key, passkey, enable/disable) — those already live in
  `tracker.json5`'s `providers.<name>.enabled` / credentials, unrelated to the ratio, and stay
  wherever the trackers' activation surface already is or will be drawn; this lot's policy panel
  is `economy` only.
- **A mean or global ratio figure anywhere** — § 1 clause 1 forbids it outright.

### Open design questions — the operator's round of 2026-09-15 evening

- **The trackers domain's placement: bar or drawer.** The bottom bar holds the four places one goes
  to SEE what is happening (`app/navigation.ts`'s own comment, quoted at L20's entry); a tracker's
  ratio is exactly that kind of thing to watch, which argues for the bar — but the bar is at four
  slots already and a fifth was refused once for the pipeline (D12, the operator's Q6). Two
  readings, no choice made here:
  - **Reading A — a fifth bar tab.** `inBar: true`, alongside `acq` / `lib` / `arr` / `sys`. Argues
    for it: the ratio is watched, not merely configured, the same distinction the table's comment
    draws between the bar and Réglages/Maintenance.
  - **Reading B — the drawer, beside Réglages and Maintenance.** `inBar: false`, a fifth row in the
    drawer's currently-four (`grep -c "inBar: false" frontend/maquette/design/src/app/navigation.ts`
    → 4). Argues for it: a tracker is acted on rarely — set a policy, release an obligation — closer
    to Réglages' own cadence than to Acquisition's; and D12's Q6 refusal of a fifth bar slot for the
    pipeline is a precedent against growing the bar again.

  **The steward relays the operator's word the minute it lands; this line is amended in place, one
  dated line under the question, never a rewrite of § 4.1.**

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
  design's § 4.6 is the ratio half; the space half is not this lot's and the row says so when
  amended.
- **DOIT-3** row — `partly`, « to draw: the tracker policy set from the ratio surface — L16 » — § 4.3.

**`docs/reference/backend-demands-architecture.md` § 4**, already carrying the prose this design
makes concrete (§ 2.3): the policy write, the release verb, the external-removal reconciliation,
the alert threshold and its push channel, the ranking input, the per-tracker volumes/trend/deadline
reads. **Nothing in § 2.3 is a NEW clause** — every item there is this design's typed shape of a
sentence § 4 already carries; none invents a demand the register does not already owe.

**`docs/reference/frontend-backend-demands.md`**, computed, not edited by this PR — the phase that
opens the contract (§ 2) regenerates it with `scripts/compare-contracts.py --write` and reads its
counters before and after, as every prior lot's phase 1 has.
