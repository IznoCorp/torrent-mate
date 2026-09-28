# L16 — §18, the ratio · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L16 — §18, the ratio`. It is
not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every
figure carries the command that produces it, every decision carries its reason, every screen
carries its named states. **Nothing under `frontend/maquette/design/` was touched to write it** —
the lot opens after L22b (the plan's order is L13 · L22 · L16 · L17 · L18), and this is the design
read before it does.

**Written 2026-09-15 on `08400a22a`; re-read 2026-09-26 on `dafe29ec1`; RE-DRAWN 2026-09-27 on
`5e5ecd052`** against the coherence audit of 2026-09-27 (`review-archive/coherence-2026-09-27.md`,
its triage `review-archive/coherence-2026-09-27-triage.md` § C) and the operator's rounds 7 to 9 of
2026-09-26/27 (`docs/reference/operator-method.md`) — chiefly **organisation ruling 18** (a
tracker's active torrents, their marks, « Retirer de qBittorrent »), **ruling 19** (the Trackers
page is two tabs, « Torrents » and « Trackers »), **ruling 20** (the bar's four places, Trackers
before Découvrir), round 9 Q1 (a refused identifier), Q2 (the alert threshold is its own setting),
and Q7 (a shared-files removal names its consequence and takes every entry with it). This is a
**design pass, not a line-by-line amendment**: ruling 19 replaces the surface the first two
readings drew (a list page plus a per-tracker detail screen) with one page in two tabs, and most of
what follows is redrawn from that surface down, not patched. § 0.1 says what moved and why; every
audit fix this redraw answers is named where it lands, and any the redraw makes moot is said so
explicitly rather than silently dropped.

**Read again, same day, against the auditor's rulings-coherence round**
(`review-archive/rulings-coherence-2026-09-27.md`, relayed by the orchestrator) — **M4** (a removal or
a cross-seed cut done IN THE APP and confirmed always closes the obligation as « libérée », never as
still in breach; the confirmation is owed whenever a RUNNING obligation would end, not only when
files are deleted; an external removal's own trace — Système's history, L20's — reads « Libérée —
retrait externe », a naming fact for that lot's own demand, not a Trackers-page state this lot
draws), **M5** (a refused identifier is ONE unit in the badge, per tracker, never one per torrent it
touches — a cross-seed failure's own contribution to the badge is L17's), and **round 10 Q3 = B**
(« Libérer » is not a gesture of its own: the seed stops through « Retirer de qBittorrent » or a
cross-seed cut, each already confirmed and each closing the obligation « libérée »; there is no
separate release operation — **F15's finding is REPLACED, not merely corrected**: the first two
readings' verb never had an id, a cause or an event because it never should have existed as its own
operation) and **Q4 = A** (an obligation the ENGINE broke, whose torrent has already left
qBittorrent, is not lost: it reads on the tracker's own entry, in the « Trackers » tab, as « N
obligations rompues », a list — title, date — that unfolds, and a per-row « vu » (the same « × »
elsewhere in this codebase) clears it from the badge; the « vu » field is a new demand). Neither
M4 nor Q3 changes a surface this redraw had not already drawn — they CONFIRM it and correct one
gap (the confirmation's own trigger); M5 and Q4 add, respectively, a counting rule and a new
sub-surface, both folded into § 4.2 and § 4.5 below.

**Where L16 opens in the order, and why.** L16 lands **after L22b**: L22b's phase 19 takes Système
out of the bar, its phase 25 deletes the `arr` row, and its own porting of round 8's Q20 puts
Découvrir in the bar as the third button (`docs/features/maquette-l22/plan/INDEX.md@232a908ca`; L22a = phases
1–14, L22b = phases 15–27). **At that point the bar already reads `acq · lib · discover`, three
buttons** — this is the tree L16 opens on, corrected from the first two readings, which believed
the bar stood at two (F10). L16 **inserts Trackers between Médiathèque and Découvrir**: an account
holding the right reads `acq · lib · trackers · discover`, four buttons in equal shares (ruling 20);
an account without it keeps the three L22b already draws.

---

## 0. What L16 owes, said once

`product-intent.md` § 18, « Ce que l'opérateur a tranché » (dictated 2026-08-30), gives L16 five
things, and none of them is a decision left to draw:

| # | The thing | The operation | Its clause |
| --- | --- | --- | --- |
| 1 | the ratio, read **per tracker**, never averaged into one figure | `GET /api/acquisition/obligations`, `/downloads` — answering, called by nothing | DOIT-13 |
| 2 | **release an obligation early** — including a HANDLED case when the stop is an external removal in qBittorrent | none: a write, absent from both contracts | § 18, DOIT-2 |
| 3 | a **per-tracker ratio alert**, a threshold the operator sets, **spoken where it lives — on the Trackers page and as a badge on the Trackers tab of the bar** (push is a platform demand, not this lot's) | none: a write and a read, absent from both contracts | § 18, § 17 point 4 |
| 4 | the **ranking follows the ratio** — a release on a low-ratio tracker may lose points | `POST /api/acquisition/ranking/preview` — answering, called by nothing; the ratio TERM itself does not exist on the scored release, and the criteria the preview scores are neither read nor saved anywhere today (F16) | § 18, and B-298 |
| 5 | what is shown **beyond the ratio**: Download / Upload volumes, the trend, and per ACTIVE torrent its deadline and its ratio | none of the existing reads carries it | § 18 |

**Ruling 18 reshapes thing 2.** « Release an obligation early » is no longer a verb on the
obligation itself: the operator's own words give the gesture a torrent, not an obligation — «
Retirer de qBittorrent », with an option to delete the files, defaulting on. Removing a torrent from
qBittorrent IS how an obligation on it ends early; the HANDLED external-removal case survives
unchanged in substance (a torrent the operator removed BY HAND in qBittorrent, outside this
interface, must read as gone, never as an anomaly) but its surface changes: § 4.4 says how.

And one register row this lot is named against directly: **DOIT-2**'s ratio half — « a torrent
deferred for ratio or space ». Its surface is the acquisition card, not Arrivées: after L22 the page
Arrivées does not exist, and the map's proposed DOIT-2 surface is `features/acquisition` — « a card
says why it waits » (`docs/features/maquette-l22/DESIGN.md@232a908ca` § 6.3). The card never draws the
ratio-specific reason today, and the audit found the first drawing's own answer wrong in its source,
not only in its surface (F14, § 4.6). **No proposed decision anywhere in this design**: § 18's own
words, « l'interface expose ; l'opérateur juge », hold for every screen below.

### 0.1 The rulings this design is read against, and what each moved

The rulings are the operator's and are not reopened here. « Organisation ruling N » is his entry in
`docs/reference/operator-method.md`, numbered as `docs/features/maquette-l22/DESIGN.md@232a908ca` § 0 numbers
1–15 and this design's own re-read continues from 16.

| Ruling / question | What it dictates | What it moved in this design |
| --- | --- | --- |
| 11 (2026-09-26) | the place Arrivées frees in the bar goes to « Trackers » (ratio, cross-seed, the tracker); the bar is composed by rights | § 4.1: the page is a bar row, `inBar: true` |
| 12 (2026-09-26) | every thing speaks where it lives, a badge on the bar tab that carries it; no notifications box, no line on Système | § 4.5 (the alert's readers); § 1 clause 6; the obligation's own trace lives in Système's history, not on a second Trackers list (§ 4.4) |
| 20 (2026-09-27, round 7 Q… superseded by round 8 Q20, F10) | the bar's four places, once L22b lands: Acquisition, Médiathèque, **Trackers**, Découvrir — Trackers is INSERTED between the second and the fourth, not appended after a free slot | the ordering paragraph above, § 4.1's bar text, `bar-trackers-alert`'s own description (now « the bar at four », never « the fourth place stays free ») — **F10, C10** |
| round 9 Q1 (2026-09-27) | a refused tracker identifier (an expired key or passkey) is said on the Trackers page, and counts in its badge | § 4.2 gains a header fact per tracker entry; § 4.5's derivation gains a third component; § 2.3 files a health-read demand |
| round 9 Q2 (2026-09-27) | the alert threshold is its own per-tracker setting, distinct from the floor (`min_ratio`) and the target (`target_ratio`) | § 2.3 item 2, § 4.2 — F11(b) |
| round 9 Q3 (2026-09-27) | a tracker's own page draws ONE list — the torrents active on it, each carrying its obligation as a MARK — never two lists doubling each other | kills the old « obligations list » and « active torrents list » pair outright; replaced by § 4.3's single roster |
| ORGANISATION RULING 18 (2026-09-27) | a tracker's torrents ACTIVE in qBittorrent (cross-seeds included), one row each, with marks (obligation open / done, cross-seed, the ratio ON THIS TRACKER computed on the torrent's size, never a division by zero), a colour for the origin tracker; a row leaves when the torrent leaves qBittorrent, its trace in Système's history; the gesture **« Retirer de qBittorrent »**, files deleted by default, decheckable, a confirmation when files ARE deleted | § 4.3 (the Torrents tab, in full), § 4.4 (the removal gesture, replacing the release verb) — **F12, F13, F15, F18 re-read against it, F43 dropped as moot** |
| ORGANISATION RULING 19 (2026-09-27) | the Trackers page is TWO TABS: « Torrents » (every active torrent, once, filterable by tracker) and « Trackers » (one entry per tracker — form left to the drawing, accordion recommended, a dedicated page only if too long) | replaces S1 (the roster page) and S2 (the tracker-detail screen) of the first two readings outright with § 4.1 (the shell) + § 4.2 (« Trackers ») + § 4.3 (« Torrents »); **the `/trackers/$name` content-tier address DIES** — **C9, C10, C11 read against it** |
| round 9 Q7 (2026-09-27) | « supprimer les fichiers » stays checked by default; when files are shared, the confirmation says every share ends and removes EVERY qBittorrent entry using them, naming each tracker with a running obligation | § 4.4's confirmation copy |
| round 9 Q8–Q11 | cutting ONE tracker's cross-seed on a torrent (not the whole removal), the cross-seed vocabulary, and the exclusion memory | **L17's**, not drawn here; § 5 names where the Torrents tab leaves room for them |
| 13, 15 (2026-09-26) | Système keeps the machine and the pipeline's levers, and leaves the bar for the drawer | nothing moves to Trackers; unchanged from the prior read |
| 14 (2026-09-26) | accounts are managed in Réglages or a first-level drawer entry | nothing: accounts have no relation to Trackers (L18's) |
| 2 and 7 (2026-09-15, through L22) | the page Arrivées dies; what stagnates reads on its card in « En cours » with its reason | § 4.6 — and F14 finds the first two readings' OWN reason source wrong, corrected there |
| round 10 M4 (2026-09-27, rulings-coherence) | a removal or a cross-seed cut, confirmed in the app, always closes an obligation « libérée », never in breach; the confirmation is owed whenever a running obligation would end, not only when files are deleted | § 4.4 (broadened confirmation trigger, the always-released hold), § 4.8 (R-L16-c's new mutations) |
| round 10 M5 (2026-09-27, rulings-coherence) | a refused identifier is one unit per tracker in the badge, never one per torrent; a cross-seed failure leaves the badge as a state change, L17's own rule | § 4.5 (the counting rule), § 4.8 (R-L16-d) |
| round 10 Q3 = B (2026-09-27, rulings-coherence) | « Libérer » is not a gesture of its own: the seed stops through « Retirer de qBittorrent » or a cross-seed cut, each confirmed and each closing « libérée »; no separate release operation | confirms § 4.4 and § 2.3 item 5 as already drawn; **F15 is REPLACED**, not merely corrected |
| round 10 Q4 = A (2026-09-27, rulings-coherence) | an obligation the engine broke, its torrent already gone from qBittorrent, reads on its tracker's own entry as « N obligations rompues », a list that unfolds, cleared row by row by a « vu » | § 4.2 (the new sub-surface), § 4.5 (the badge's fourth component), § 2.3 item 7 (the demand) |

---

## 1. What §18 dictates, clause by clause, and the surface that serves it

1. **« Le ratio se lit PAR TRACKER, jamais en un seul chiffre. »** Served by **S2 — the « Trackers »
   tab** (§ 4.2): one entry per tracker, its own ratio, never an average. No surface in this design
   computes a mean across trackers.
2. **« Une obligation de seed est un rien qui a sa raison » (§ 8, DOIT-2).** Served by **S3 — the
   « Torrents » tab** (§ 4.3), whose rows carry the obligation as a MARK (ruling 18, round 9 Q3 —
   never a second, doubling list), and by **S6 — the stuck queue's ratio reason** (§ 4.6), which
   names the same fact where DOIT-2 lives after L22, the acquisition card.
3. **« Agir là où l'on observe » (DOIT-3).** Served by **S2's own entry** (§ 4.2): the tracker's
   `min_ratio` / `min_seed_time` / alert threshold are set from the same row that shows its ratio —
   through the SAME settings write Réglages already offers for these fields (F11), never a second
   one that could disagree.
4. **« Ce que l'application ne fera jamais pour améliorer un ratio : maltraiter le tracker »
   (NE-DOIT-PAS-8).** No surface in this design offers a retry, a burst, or any automation over a
   tracker call — every read here is a single call per screen visit, like every other surface.
5. **« L'action retenue : libérer une obligation », et le retrait externe est un cas GÉRÉ.** Served
   by **S4 — « Retirer de qBittorrent »** (§ 4.4, ruling 18): a confirmation when files are deleted
   (NE-DOIT-PAS-6 — destroying a commitment without consent), naming every shared consequence (round
   9 Q7); an obligation ended by removing its torrent BY HAND in qBittorrent, outside this
   interface, is read the same way — its row is simply gone, its trace in Système's history (ruling
   12), never a silent anomaly (NE-DOIT-PAS-5) and never a second « released » list.
6. **« L'alerte de ratio. »** Served by **S5 — the ratio alert** (§ 4.5): a per-tracker threshold,
   set from the same entry that shows the ratio (§13 — one derivation, not a second control), spoken
   where it lives: on the tracker's own entry, on the Torrents tab's rows in breach, and as a
   **badge on the Trackers tab of the bottom bar** (ruling 12). There is no notifications box and no
   line on Système. A refused identifier (round 9 Q1) joins the same derivation. **Push (FCM, iOS,
   Android) is NOT drawn here** — § 5 names it as a platform demand this lot files and does not build.
7. **« Le ranking suit le ratio. »** Served by **S7 — the ranking editor** (§ 4.7): the screen
   `RankingPanel`'s production twin, reading and saving through the SAME configuration-file
   operation production already uses (F16), with the live preview already computed server-side, and
   a ratio-aware criterion this design proposes as a demand (§ 2, § 6) because the scored release
   carries no such field today.
8. **« Ce qui est montré d'un tracker, au-delà du ratio : Download / Upload, la tendance, et par
   torrent actif son échéance et son ratio. »** Served by **S2** for the tracker-level volumes and
   trend, and by **S3**'s rows for the per-torrent half.
9. **« Le ratio affiché est celui que le tracker reconnaît » (NE-DOIT-PAS-1).** No surface computes
   a ratio; every ratio drawn is the mock's own field, read verbatim — held by R-L16-a (§ 4.8).

---

## 2. The contract (D7) — and it comes FIRST

The maquette's own contract declares **none** of the operations this lot needs, though the backend
answers most of them already:

    python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted(p for p in d['paths'] if 'obligation' in p or 'download' in p or 'ranking' in p or 'tracker' in p))"

reads `[]`. The backend's own contract answers three of the four operations this redraw needs:

    python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(p for p in d['paths'] if 'obligation' in p or 'download' in p or 'ranking' in p))"

reads `/api/acquisition/downloads`, `/api/acquisition/obligations`,
`/api/acquisition/ranking/preview` — and **no path contains `tracker`** in either contract: there is
no tracker-level read or write anywhere today. `/api/acquisition/stalled-grabs` answers too, but
**this redraw does not declare it**: F14 found the first two readings wrong to make it the ratio
card's reason source (§ 2.5 says why), and nothing else in this design needs it.

### 2.1 What each existing operation answers, read from the backend's own schemas

| Operation | operationId | Answers | What it is missing for this lot |
| --- | --- | --- | --- |
| `GET /api/acquisition/obligations` | `get_obligations_...` | `ObligationsResponse{items: ObligationItem[]}` — `source_tracker`, `min_ratio`, `min_seed_time_s`, `observed_ratio`, `added_at`, `breached_at`/`satisfied_at`/`released_at`, `title`, `info_hash` | nothing — it is the obligation itself, tracker-scoped already, and its three terminal fields (`breached_at`, `satisfied_at`, `released_at`) are exactly the marks ruling 18 wants read on the torrent's own row (never a second list, round 9 Q3) |
| `GET /api/acquisition/downloads` | `get_acquisition_downloads_...` | `AcquisitionDownloadsResponse{downloads: AcquisitionDownload[], client_available}` — per torrent: `state`, `progress`, `eta_seconds`, `size_bytes`, `info_hash`, `kind`, `title` | **no tracker, no ratio, no deadline field on `AcquisitionDownload`** — § 18's « par torrent actif son échéance et son ratio » and ruling 18's « le ratio du torrent sur CE tracker calculé sur la taille du torrent » cannot be drawn from this shape as it stands (§ 2.3 item 1) |
| `POST /api/acquisition/ranking/preview` | `preview_ranking_...` | `RankingPreviewResponse{ranked: RankingPreviewRelease[], known_trackers: string[]}` from a POSTed `RankingConfig{criteria, bonuses, min_seeders, size_thresholds_by_type}` | `RankingCriterion.field` is read by `getattr(TrackerResult, field)` (`personalscraper/api/tracker/_ranking.py:100`) — `provider` exists on `TrackerResult` (categorical, scorable today) but **no ratio-derived field does** (§ 2.3 item 4) |
| `GET` / `PUT /api/config/files/{name}` | `readConfigurationFiles` / `updateConfigurationFile` | **already declared and mocked** in the maquette (`mocks/handlers/configuration.ts:50,71`) — a file's raw content, `SHA-256` precondition on the write (`412` on conflict); production's own `RankingPanel.tsx` already calls both, on `ranking.json5` | this lot's ranking editor never calls either (F16) — see § 2.5 |

Read at `frontend/openapi.json`'s `components/schemas` for the first three names above, and at
`personalscraper/api/tracker/_ranking.py` and `personalscraper/api/tracker/_base.py` for `rank()`
and `TrackerResult`.

**No tracker-level aggregate exists anywhere.** `config.example/tracker.json5` names exactly two
providers today (`c411`, `tr4ker`), each with `enabled`, `cross_seed`, and an optional `economy:
{target_ratio, min_ratio, min_seed_time, hit_and_run_grace}` (`personalscraper/conf/models/api_config.py:216`,
`:276`). **This block is ALREADY a Réglages topic** — `mocks/seeds/settings.json:593-710` seeds a row
per key, `file: "tracker"`, e.g. `key: "tracker.providers.c411.economy.min_ratio"` — read through
`GET /api/config/schema` and written through `updateConfigurationFile` exactly like every other
setting (F11). Nothing reads a tracker's current DOWNLOAD / UPLOAD volume, its trend, or whether its
identifier is refused; `ObligationItem` carries `observed_ratio` per OBLIGATION, not per tracker, and
only for a torrent still owing seed time — a tracker with no open obligation has no field anywhere
answering its own ratio.

### 2.2 What is declared as owed (two existing, seeded from the backend's shapes — D7)

`GET /api/acquisition/obligations` and `/downloads` are added to the maquette's contract with the
shapes § 2.1 measured, **seeded from the running backend** (D7 — a contract diverges deliberately
only where the experience needs more; here it does not, for these two). `POST
/api/acquisition/ranking/preview` likewise, unchanged in its own shape (§ 2.5 covers what surrounds
it).

### 2.3 What is proposed as a NEW demand (§ 6 carries the register form)

1. **A tracker-level summary read.** Name, ratio, Download / Upload volumes, the trend — nothing
   existing answers a tracker as its own subject. **Round 9 Q1 adds a health fact**: whether the
   tracker's identifier (API key, passkey) is refused, and since when. **Round 10 Q4 adds a
   `broken_obligations` array**: one entry per obligation the engine broke whose torrent has already
   left qBittorrent — title, `broken_at`, `seen` — folded into the SAME read, never a second
   operation.
2. **The alert threshold, as its own setting.** Round 9 Q2 rules it distinct from `min_ratio` (the
   floor) and `target_ratio` (the moteur's own target): a new key in the SAME `economy` block
   (`tracker.providers.<name>.economy.alert_threshold`, or equivalent — the config-shape half of
   F11(b)), so it is written and read through the SAME mechanism the two existing keys already use,
   never a second write path.
3. **`AcquisitionDownload` extended** with, for the torrent's own entry on the tracker it is active
   ON: the tracker's name, its ratio ON THIS TRACKER computed on the torrent's SIZE (ruling 18 —
   « comme si on l'avait téléchargé sur le tracker », so a cross-seeded entry never divides by
   zero), the obligation's deadline, and whether this entry is the torrent's ORIGIN grab or a
   cross-seed of it (the colour ruling 18 asks for). A torrent cross-seeded onto several trackers has
   ONE ROW PER ENTRY — the shape `AcquisitionDownload` already has, per active qBittorrent entry, not
   per underlying file — so this is an EXTENSION of an existing field set, not a new list.

   **Amended 2026-09-27 18:1x (L23 round 11, OPEN 5 = B):** the origin-colour mark gains a THIRD value,
   « publié par vous », beside « the original grab » and « a cross-seed of it » — read on a torrent this
   application itself created and published on that tracker (`docs/features/maquette-l23/DESIGN.md` § 7 OPEN 5;
   `review-archive/l23/rulings-round11.md`).
4. **A ratio-derived field on `TrackerResult`**, so a `RankingCriterion` with `field:
   "tracker_ratio_state"` (or equivalent) can score it exactly as `field: "provider"` already
   does — `rank()`'s `getattr(r, c.field, None)` (§ 2.1) needs nothing else.
5. **« Retirer de qBittorrent ».** A write that removes one or more qBittorrent entries (an original
   grab and every cross-seed of the same files, per round 9 Q7's grouped removal) — with a boolean
   for deleting the underlying files, checked by default — and answers which trackers still held a
   running obligation on what was removed, so the confirmation can name them WHENEVER one is running,
   whatever the file-deletion boolean reads (round 10 M4). **There is no separate release
   operation** (round 10 Q3 = B): the write itself closes every running obligation it touches as
   `released_at` set — never left reading `breached_at` alone — the SAME write a cross-seed cut
   (L17's) also calls for its own, narrower case. This REPLACES the first two readings' `POST
   .../obligations/{id}/release` OUTRIGHT, not merely corrects it (F15 is REPLACED): the gesture the
   operator described works on the torrent's entries in qBittorrent, never on an obligation id, and
   its consequence — the obligation ends, always as a release — follows from the removal itself, not
   from a second call this design no longer asks the backend for.
6. **A stream event for a removal**, own or external, so a torrent's row disappears from the Torrents
   tab and the trackers' badges move without a refetch: whatever reconciles an external qBittorrent
   removal today (the backend's own housekeeping) must emit it too, never only the interface's own
   gesture — the SAME NE-DOIT-PAS-5 discipline § 18 already asks for the obligation's own read. The
   event's own cause (this interface, a hand removal reconciled clean, or the engine's own break) is
   what item 7 and § 4.2's « rompues » list read apart.
7. **A « vu » write for a broken obligation** (round 10 Q4). One boolean per broken-obligation row
   (`breached_at` set, `released_at` never set, its torrent already gone), on the tracker's own
   summary read — the same shape the app's other « × » gestures already write, never a delete of the
   row itself (NE-DOIT-PAS-5: seen is not gone).

**Dropped from the first two readings' list: the obligation's release verb**, REPLACED, not merely
corrected, by item 5 above (ruling 18, round 10 Q3 = B) **and `GET /api/acquisition/stalled-grabs`**
as this lot's operation (F14, § 2.5).

### 2.4 The mocks, and what each must MOVE (D7 — « a mock that answers without moving certifies nothing »)

`frontend/maquette/design/src/mocks/handlers/acquisition.ts` is **395 non-blank lines**
(`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts`, on
`5e5ecd052`; it read 359 at the prior re-read), 5 under the 400 ceiling — no read handler of this
lot's fits there, so every one of them opens a new `mocks/handlers/trackers.ts`, by SUBJECT
(`staging.ts` / `pipeline.ts` precedent, `frontend-architecture.md` § 4, L20 phase 1), the same
choice the first two readings already made.

- `obligations` answers a list a **removal** REMOVES the matching rows from (the torrent's obligation
  ends when its entry leaves qBittorrent), never a static seed.
- `downloads` answers the per-entry list the Torrents tab and the tracker summary read must AGREE
  with — one seed, several projections; a torrent cross-seeded onto two trackers seeds as TWO
  entries of the same underlying title, one marked as the origin.
- the tracker policy AND the alert threshold move the SAME seed keys `settings.json` already answers
  under `tracker.providers.<name>.economy.*` — this lot's mock does not duplicate that seed, it reads
  it (§ 4.2).
- the removal moves the obligation to `released_at` set (`breached_at` untouched) and REMOVES the
  torrent's entry (and every entry sharing its files, per the grouped removal) from the downloads
  seed, in the SAME mock call, so both reads agree in the answering render.
- a SEPARATE seeded scenario answers a torrent already gone from the downloads seed with its
  obligation's `released_at` set and no removal call ever made in the walk, so R-L16-c can prove the
  external-removal HANDLED read without a mutation that cannot exist against `main` (§ 4.4).

### 2.5 F16 and F14 — two gaps the first two readings did not see

**F16 — the ranking editor can neither read nor save.** The first two readings drew a criteria list
and a live preview and called it done; neither ever loads what the operator last saved nor writes a
change back. Production's own `RankingPanel.tsx` answers how: `useConfigFile` / `usePutConfigFile`
on `ranking.json5`, the SAME `GET` / `PUT /api/config/files/{name}` the settings feature already
declares and mocks (§ 2.1). This design corrects itself here rather than shipping the same gap
twice: § 4.7 draws the editor against that read, and its save against that write, with the `SHA-256`
precondition production already carries (a save the editor issued without first reading the file's
current hash is not this design's problem to invent an answer for — it reuses the settings feature's
own conflict handling, never a second one).

**F14 — the card's ratio reason does not come from `stalled-grabs`.** The first two readings composed
the card's reason from `StalledGrabItem.reason`, a French sentence the backend rolls up for
acquisitions parked at « récupéré » that never reached the library — **a different rollup, answering
a different question**, and one the mock would have had to invent a matching sentence for anyway
(§ 2.4 already said this: « composed by the mock », never read from a second, disagreeing field). The
audit reads this as inventing the source rather than drawing it: a ratio-deferred card's reason is a
fact of ITS OWN CARD (L22's single ladder, DOIT-2), not of a rollup that exists for an unrelated
purpose. **This design proposes a new demand instead**: the pipeline's own `classify_deferrals` (read
by the watcher today, exposed by no web route) is what actually computes why a torrent stays
deferred — ratio, insufficient space, or missing content — and this lot asks for it on a route the
card's query can call, naming the reason KIND and, for a ratio cause, the tracker's name and the
obligation's own `min_ratio` (never `ingest.min_ratio`, a legacy top-level key that reads `0.0` on
the operator's own host and that no card names — `personalscraper/ingest/deferral.py:12,39`). § 4.6
draws the card against that demand, generalised across the three causes DOIT-2 names, not the ratio
one alone.

---

## 3. The addresses (D1)

Ruling 19 removes the content-tier screen the first two readings gave the trackers domain: there is
**one page**, its tabs and filters are SCREEN-STATE dials (the same mechanism `acqTab` already is,
`lib/addresses.ts`'s `DIALS` table), and nothing here PUSHES once the page itself is open.

| Surface | Tier | Address |
| --- | --- | --- |
| the Trackers page | a page | `/trackers` — its own path, D1's content tier: a tracker is a thing being looked at |
| the tab (« Torrents » / « Trackers ») | screen state | `/trackers?tab=torrents\|trackers` — a new DIAL, `{ parameter: "tab", field: "trackersTab", of: "trackers" }`, `acqTab`'s own precedent |
| the tracker filter, on « Torrents » | screen state | `/trackers?tab=torrents&tracker=$name` — a second dial, `{ parameter: "tracker", field: "trackersFilter", default: "", of: "trackers" }`; a tracker's own « Voir les torrents » (§ 4.2) sets both dials in one navigation |
| a tracker's entry, opened, on « Trackers » | screen state | the SAME `tracker` dial reused: `/trackers?tab=trackers&tracker=$name` opens that entry's disclosure — S6's cross-reference (§ 4.6) lands here |
| « Retirer de qBittorrent »'s confirmation | transient | **no URL** — D1b rule 1, adjusting a surface, never arriving; a confirmation carries no address anywhere else in this codebase |
| the ranking editor | content | its own path under the settings page — `/settings/ranking` (D1: it is identified, and DOIT-10 owes it a URL; unchanged from the prior read) |

**Amended 2026-09-28 (L16 phase 2b, RULINGS 1):** the maquette writes the tab's parameter as `list` — `/trackers?list=torrents|trackers&tracker=$name` — where this table names `tab`, because the address model holds « one parameter, one page » (`lib/addresses.test.ts`) and `tab` is Acquisition's.

**What DIES here.** `/trackers/$name` and its `SCREEN_PARENTS` entry, drawn by the first two
readings' phase 4, never land: ruling 19's two-tab page answers everything the content-tier screen
would have, without a second address to keep in agreement with the first. This ALSO helps `lib/addresses.ts`,
already at **395 non-blank lines** (`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/lib/addresses.ts`,
5e5ecd052) against F38's 400-line ceiling: two new dials cost far less than a new `SCREEN_PARENTS`
row and the address test's matching case would have (§ 6 notes the ceiling explicitly, per F38).

**Why the ratio's own controls carry no address of their own.** The first two readings gave the
policy panel a query-parameter address of a KIND (`setting`) that belongs to the settings feature,
and found at their own phase's opening that `policy` was not a `<file>:<key>` subject that kind can
hold (a STOP D). **This redraw resolves it rather than re-asking it**: § 4.2's entry embeds the
settings feature's own field primitive directly — the SAME `min_ratio` / `min_seed_time` /
`alert_threshold` rows Réglages already draws, read from the SAME cache — so there is no second
panel kind to invent and no second address to keep honest against the first (§13). Whether that
embedding opens through the existing bottom-panel mechanism (a new subject the `setting` kind can
hold — the tracker's whole `economy` block, not one key) or through a small block the Trackers
feature registers itself on `ui/panel`'s own extensible map (the `field` block's own precedent,
`features/settings/panel-field.tsx`) is the ONE STOP D this redraw still carries, moved from « what
address » to « what composes three settings rows drawn twice » — § 4.2 names it.

---

## 4. The surfaces, drawn

Copy is given in « guillemets » exactly as `fr.json` will carry it, with the English key beside it
where one is proposed; none is retyped where a key already exists.

### 4.1 S1 — The Trackers page, and its two tabs

**Its place.** A new page, `features/trackers/page.tsx`, and **a button of the bottom bar** (ruled,
§ 5): one navigation row in `app/navigation.ts` — `id: "trackers"`, `path: PAGE_PATHS.trackers`,
`inBar: true`, `group: "supervision"` (the group of the pages one goes to SEE — Acquisition,
Médiathèque, Découvrir), `root: "body"`, `region: "trackers/body"`, and, from the alert's phase,
`badge: trackersBadge` — a function the feature exports and the frame names once, never its counter
(`docs/features/maquette-l22/DESIGN.md@232a908ca` § 3.6). The row is the page's whole declaration; the tabs
draw what the two dials say.

**The bar around it (ruling 20, F10).** Once L22b lands, the bar already reads `acq · lib ·
discover`, three buttons (Découvrir having taken the fourth place round 8's Q20 frees). **This lot
inserts Trackers BETWEEN Médiathèque and Découvrir** for an account holding the right: `acq · lib ·
trackers · discover`, four buttons, each an equal quarter — the frame rule the operator dictated on
2026-09-26 (« la barre du bas s'adapte toujours au nombre de boutons présents, chaque bouton prend
toujours le même ratio »), re-run at four (L22's `R-L22-s`, not re-written). An account without the
right keeps the three L22b already draws — the bar never grows past four (D12's own ceiling) and
never leaves an empty slot for one it does not hold. **The bar is composed by rights** — the model
that composes it is L18's, not this lot's (§ 5, OPEN 2, ruled A: this lot declares no right, the tab
is drawn for the mock's single account).

**The two tabs (ORGANISATION RULING 19).** « Torrents » lists every torrent active in qBittorrent
ONCE, whichever tracker it runs on, filterable by tracker; « Trackers » gives one entry per tracker.
Neither sub-divides the other — the operator's own words rule out per-tracker sub-tabs on the
torrents side (« je veux voir tous les torrents peu importe le tracker »). The strip itself is the
settings/acquisition tab precedent (`segment()`, `role="tablist"`), reading and writing the
`trackersTab` dial.

**`data-part`** (English, D4): `trackers`, `trackers/tabs`, `trackers/tab`. `data-region="trackers/body"`
for the oracle.

**Named states.**

| id | What is on the screen |
| --- | --- |
| `trackers-page` | the shell: the tab strip, the active tab's content |
| `trackers-loading` | the phase dial's own loading skeleton |
| `trackers-error` | `SurfaceError` |

**OPEN 4 — which tab opens by default.** Ruling 19 names « Torrents » first in its own prose but
rules no default; nothing else in the operator's rounds says it either. *Reading A*: « Torrents »
opens first — it is the broader view (« tous les torrents peu importe le tracker »), the one the
operator reached for when he asked for the two-tab form, and the one a first-time visitor most likely
wants (is anything running, on any tracker). *Reading B*: « Trackers » opens first — the page's OWN
subject (the domain § 18 names, « le ratio, tracker par tracker ») is the tracker, and a torrent-level
list without first knowing which trackers exist reads as a detail before an orientation; this also
matches the Acquisition precedent, whose own default tab (« Suivis ») is the page's SLOWEST-MOVING
list, not its busiest.

**Ruled C, 2026-09-27** (after #623 merged): the same rule as Acquisition's — « Trackers » opens on
first entry, then the last tab opened, kept in this device's local storage under try/catch, falling
back to « Trackers » when storage is empty, refused or holds a tab the page no longer draws. **ONE
rule for every tabbed page**: it reuses the mechanism Acquisition's `features/acquisition/tab-memory.ts`
already carries (a `STORAGE_KEY` per feature, `rememberedTab()` / `rememberTab()`), never a second one.
Neither reading A nor reading B, as first written above, is chosen as such.

### 4.2 S2 — The « Trackers » tab: one entry per tracker

**Its place.** `features/trackers/trackers-tab.tsx`, drawn when `trackersTab === "trackers"`
(default per OPEN 4). One row per configured tracker, in the roster's own order
(`config.example/tracker.json5`'s declaration order — never re-sorted by ratio or alert, which would
move a row the operator is reading).

**The collapsed row.** Name, ratio (`screens.trackers.ratio`), the trend
(`screens.trackers.trend` — up / stable / down, in words, never a bare arrow with no label,
NE-DOIT-PAS-4), Download / Upload volumes (`screens.trackers.volumes`), the alert badge when
crossed (S5), and, when its identifier is refused (round 9 Q1), « Identifiant refusé depuis le … »
(`screens.trackers.identifierRefused`) — the header fact a tracker's OWN row carries, never a
Système dependency line (ruling 12 stands: Système is the machine, not a tracker's own health).

**The disclosure, opened.** `ui/disclosure.tsx` (`<Disclosure summary={…}>`, the precedent already
built for `features/media/panel-seasons.tsx` and `features/acquisition/add-screen.tsx`) folds away,
by default, the fields DOIT-3 asks to be set from this same row: `min_ratio`, `min_seed_time`, the
alert threshold — the SAME three settings rows Réglages already draws
(`mocks/seeds/settings.json:593-710`), through the SAME `updateConfigurationFile` write, never a
second one (F11 — one derivation, R-L16-b). **Its own STOP D** (§ 3): whether the three rows compose
by opening the existing settings bottom panel at a NEW, coarser subject (the tracker's whole
`economy` block, alongside the `<file>:<key>` subject the `setting` kind already holds) or by the
Trackers feature registering its own block kind on `ui/panel`'s block map, the way `panel-field.tsx`
registers `field` — the phase that draws this measures both against `Disclosure`'s own contract
(« it knows no domain », `ui/disclosure.tsx`'s own header) and reports which it took, before moving.
A tracker with no policy set at all (`c411` and `tr4ker` both ship commented out,
`config.example/tracker.json5:16,26`) reads its own named state: « Aucune politique réglée pour ce
tracker. » (`screens.trackers.policyUnset`), never a blank form — the same real-answer discipline § 8
already holds elsewhere. **A guidance line names what the floor means**, corrected against the audit
(F57): « Le ratio à partir duquel un torrent peut être retiré sans dette envers le tracker — un
plancher, pas une cible. » (`screens.trackers.floorGuidance`) — the release verb's own word,
« libérer », is gone from the maquette entirely (ruling 18 replaces it, § 4.4) and this line does not
use it either.

**« Voir les torrents ».** A path (`crossReference()`) that sets BOTH dials —
`?tab=torrents&tracker=$name` — landing on § 4.3 filtered to this tracker.

**« N obligations rompues » (round 10 Q4 = A).** An obligation the ENGINE broke — never through this
lot's own gesture nor a hand removal it can read (§ 4.4) — whose torrent has already left
qBittorrent is never lost: it reads on ITS TRACKER's own collapsed row as a count,
« N obligations rompues » (`screens.trackers.brokenObligations`), and unfolds into a SECOND
disclosure (title, date, one row each) nested under the entry's own. A per-row « vu »
(`data-obligation-seen`, the same « × » this codebase already uses elsewhere) clears it from the
badge (§ 4.5) without deleting the row — it stays legible, marked seen, until the operator's own
housekeeping decides otherwise (out of this design's scope, per NE-DOIT-PAS-5: seen is not gone). The
« vu » write is a NEW demand (§ 2.3 item 7); the list itself is answered by the same tracker summary
read, extended with a `broken_obligations` array (title, `broken_at`, `seen: bool`) — never a second
operation.

**`data-part`**: `trackers/entry`, `trackers/ratio`, `trackers/trend`, `trackers/volumes`,
`trackers/alert`, `trackers/identifier-refused`, `trackers/broken-obligations`,
`trackers/broken-obligation-row`, `trackers/broken-obligation-seen`, `trackers/policy`,
`trackers/policy-min-ratio`, `trackers/policy-min-seed-time`, `trackers/policy-alert-threshold`,
`trackers/policy-save`, `trackers/see-torrents`. `data-region="trackers/body"`.

**Named states.**

| id | What is on the screen |
| --- | --- |
| `trackers-roster` | the entries, collapsed, each with its ratio, trend, volumes |
| `trackers-roster-empty` | no tracker configured — « Aucun tracker configuré. » (`screens.trackers.empty`), a real state (fresh install ships two, but a config can hold zero) |
| `trackers-entry-open` | one entry's disclosure open, its policy fields drawn |
| `trackers-policy-unset` | the open entry, no policy set (`policy.min_ratio` absent) |
| `tracker-alert-active` | the entry's own alert reader — S5's state, drawn here too, never only elsewhere |
| `tracker-identifier-refused` | the entry names its refused identifier |
| `tracker-broken-obligations` | the collapsed count, at least one unseen broken obligation |
| `tracker-broken-obligations-open` | the nested disclosure unfolded, its rows drawn |

### 4.3 S3 — The « Torrents » tab: every active entry, once

**Its place.** `features/trackers/torrents-tab.tsx`, drawn when `trackersTab === "torrents"`. **One
row per qBittorrent entry active on ANY tracker** — a torrent cross-seeded onto two trackers is TWO
rows, never folded into one (ruling 18: « je veux voir tous les torrents peu importe le tracker »).
The `tracker` dial, when set, FILTERS the rows client-side to that tracker; it never re-fetches (the
same list answers filtered or not). *(2026-09-28, STOP D 5b = B, steward [79475d]: when set, a line « Filtré sur <tracker> · Tout voir »
(`torrents/filter`, `torrents/filter-clear`) says it above the rows, and « Tout voir » lifts it through the same
`trackers-filter` verb given no tracker — RULINGS 3.)*

**What a row carries (ORGANISATION RULING 18, replacing the first two readings' two lists —
round 9 Q3).** The title, as a PATH to `/media/:provider/:id` (or to `/resolution/$folder` when the
title is not yet identified — NE-DOIT-PAS-9, F18: a torrent's own row is never a dead end); the
deadline and the ratio on THIS TRACKER, computed on the torrent's OWN SIZE (never the tracker's
download volume — the exact rule that keeps a cross-seeded entry from a division by zero, ruling
18's own phrase); a colour marking whether this entry is the torrent's ORIGIN grab or a cross-seed of
it (§ 2.3 item 3); and, as MARKS, never a second list: **« obligation en cours »** (an open
obligation on this entry — `breached_at`, `satisfied_at` and `released_at` all unset),
**« obligation terminée »** (`satisfied_at` set, the torrent still active — it kept seeding past its
own requirement), and, when `breached_at` is set and neither of the other two is, **« en infraction
depuis le … »** (a danger chip, S5's third reader). **The « cross-seed » mark itself is NOT drawn
here**: it is L17's, added to the same row once the cross-seed feature exists (§ 5) — this lot draws
the row's SHAPE and the marks its own data already answers.

**Retirer de qBittorrent.** Every row carries the gesture — § 4.4.

**`data-part`**: `torrents`, `torrents/row`, `torrents/title`, `torrents/tracker`, `torrents/ratio`,
`torrents/deadline`, `torrents/origin`, `torrents/obligation-open`, `torrents/obligation-done`,
`torrents/obligation-breached`, `torrents/remove`. `data-region="trackers/body"`.

**Named states.**

| id | What is on the screen |
| --- | --- |
| `torrents-list` | the rows, unfiltered |
| `torrents-list-filtered` | the rows, filtered to one tracker (the `tracker` dial set) |
| `torrents-empty` | nothing active anywhere — « Rien en cours sur aucun tracker. » (`screens.torrents.empty`), a real answer (§ 8) |
| `torrents-empty-filtered` | nothing active on the FILTERED tracker — a different sentence, « Rien en cours sur ce tracker. » (`screens.torrents.emptyFiltered`), never the same copy as the unfiltered empty (a filter that reads like a bug is a defect on its own) |
| `torrent-obligation-breached` | a row « en infraction » — S5's third reader, drawn here too |

### 4.4 S4 — « Retirer de qBittorrent » (replaces the release verb — RULING 18)

**Its place.** On every Torrents-tab row.

**What happens.** « Retirer de qBittorrent » (`screens.torrents.removeFromQbittorrent`,
`data-torrent-remove`) opens a confirmation with **« Supprimer les fichiers »** checked by default,
decheckable. Confirmed, the entry (and, per round 9 Q7, EVERY qBittorrent entry sharing its files —
the grouped removal) is gone from the Torrents tab in the SAME render the operation answers, and its
obligation, if any was running, closes **« libérée »** — never left reading as still in breach, even
if it had crossed its threshold a moment before (round 10 M4: an app-confirmed removal is always a
release, not an infraction). The obligation's trace is left for Système's history (ruling 12), never
a second list on THIS page — the tracker's own « N obligations rompues » (§ 4.2, Q4) is a DIFFERENT
fact, covered below, never populated by a gesture this interface itself confirmed.

**The confirmation is owed whenever the torrent carries a RUNNING obligation, corrected against round
10 M4 — not only when files are deleted.** Ruling 18's own words name a confirmation « en cas de
suppression de fichier »; M4 reads that as a MINIMUM, not the whole rule: ending a seed commitment
early is itself the act NE-DOIT-PAS-6 guards, with or without a file ever touched. So:

- **A running obligation, whatever the file-deletion checkbox reads**: the confirmation NAMES the
  tracker (or every tracker, when files are shared and several obligations run) and says the
  obligation ends. Unchecking « Supprimer les fichiers » never skips this.
- **No running obligation, files shared**: the confirmation names the consequence — every share of
  those files ends (round 9 Q7) — with no obligation to name.
- **No running obligation, no shared file**: the confirmation is the same one a physical file
  deletion already carries elsewhere in this codebase (NE-DOIT-PAS-6) — no second, lighter wording
  invented for this case, and no confirmation at all when « Supprimer les fichiers » is unchecked and
  nothing else is at stake (an inert removal, DOIT-4 — a legitimate act is never dressed up as
  destructive when it destroys nothing).

**The external-removal HANDLED case — simplified by ruling 18, not reinvented — but not the same
fact as a « rompue » obligation (round 10 Q4).** A torrent the operator removed BY HAND in
qBittorrent, its obligation released cleanly (`released_at` set, no in-app call), is read the SAME
WAY as one this lot's own gesture closed: **the row is gone**, its trace « Libérée — retrait
externe » living in Système's history (ruling 12, L20's own surface, not drawn here). **A torrent
whose obligation the ENGINE broke (`breached_at` set) and which THEN left qBittorrent with no release
ever recorded reads differently**: the row is gone from the Torrents tab exactly the same (a live
read of qBittorrent's own state, round 9 Q3 — never a second list DOUBLING the active torrents), but
the broken obligation itself is NOT silently lost — it surfaces on its tracker's own entry as one row
of « N obligations rompues » (§ 4.2), until the operator marks it seen. This is not a second
obligations-and-torrents list (round 9 Q3's own ban): it is a per-tracker record of what the engine
itself already failed at, kept ONLY because ruling 18's own row would otherwise take it down with the
torrent, and NE-DOIT-PAS-5 forbids that silence.

**Named states.** `torrent-remove-confirm` (the confirmation, transient, no URL — D1); files shared,
the confirmation names the consequence — `torrent-remove-confirm-shared`; a running obligation named
regardless of the checkbox — `torrent-remove-confirm-obligation`.

### 4.5 S5 — The ratio alert

**Its place.** Where the ratio lives, and nowhere else (ruling 12: every thing speaks where it
lives, and the bar tab that carries it takes a badge). **Four readers, ONE derivation**: a badge on
the Trackers tab of the bottom bar (the frame draws it from the row's `badge` function), a chip on
S2's collapsed entry, a chip on S3's row when it names a breach, and S2's own « N obligations
rompues » count (§ 4.2, Q4) — the same shape R-L20-g held for the lock and its levers. **There is no
notifications box** that collects it, **no alert line on Système**, and no second place: Système's
history (L20) stays the only trace of the past, and the maintenance and the machine's faults are
Système's own badge on the menu button (L22's OPEN 8), a different thing.

**What the derivation counts (FOUR components, round 9 Q1 added the third, round 10 Q4 the fourth).**
A tracker's ratio under its own alert threshold; an obligation `breached_at` set, neither satisfied
nor released, on a torrent STILL active (§ 4.3); a tracker whose identifier is refused (round 9 Q1);
and an UNSEEN broken obligation — `breached_at` set, `released_at` never set, its torrent already gone
from qBittorrent (round 10 Q4, § 4.2). **Counting rule, round 10 M5**: a refused identifier is ONE
unit for its tracker, never one per torrent it affects — the cause lives on the tracker (« chaque
chose parle là où elle vit »), not on each of its torrents; a broken obligation is likewise one unit
PER OBLIGATION, marked seen individually, never folded into the tracker's own refused-identifier
count. **A cross-seed failure joins this same badge at L17** (round 9 Q8), and M5's own rule for it —
a failure is a STATE, so it leaves the count the moment its row stops reading as failed, by a retry or
a cut, with no fresh gesture needed — is L17's to build, not this lot's. All four of THIS lot's
components read from the SAME tracker-summary and obligations reads, refreshed through this lot's
`live.ts` — so the tab's badge moves without a refetch, like the row. Today the stream's
`RatioMeasured` and `SeedObligation*` events are EXEMPTED from every live rule, by name:
`acquisitionLiveExemptions` (`features/acquisition/live.ts`) lists them as belonging to « a ratio
surface that has no page yet (B-144) » — this lot gives them that page, claims them in
`features/trackers/live.ts`, and removes those four names from the exemption (the cross-seed events
and `TrackerAuthFailed` stay named there: L17's, and the system feature's). **No push notification is
drawn** — FCM / iOS / Android is a platform demand (`backend-demands-architecture.md` § 4), filed and
not built; this lot's own surface IS the in-app signal DOIT-1 already asks every state to carry.

**Named states.** `tracker-alert-active` (§ 4.2's entry, § 4.3's row); `tracker-identifier-refused`
(§ 4.2's entry); `tracker-broken-obligations` (§ 4.2's entry, an unseen count); `bar-trackers-alert` —
**the bar at four buttons, the Trackers tab carrying its badge** (not « the fourth place stays free »,
F10's correction), in `harness/states/frame.ts` beside `drawer-navigation` (the only anchor D8's own
oracle can prove — F58: L22's `bar-todo-badge` is a different lot's row and RULINGS never made this
one a copy of it).

### 4.6 S6 — A card deferred for ratio names its tracker (DOIT-2's ratio half)

**Its place.** The acquisition card in « En cours » — `features/acquisition`. What stagnates for a
reason other than a decision reads on its card with its reason (ruling 7, L22 § 3.3); the card is
where the operator already looks for a medium that waits, and this lot does not create a list.

**What changes, corrected against F14.** A card whose current rung names a deferral reads it as ONE
of three kinds — ratio, insufficient space, or missing content (DOIT-2's own words, « fichier
manquant ») — drawn the SAME way regardless of kind, each with its own named state on the card's
single ladder (extending L22's demand B, which already carries a reason token per rung). **The
reason is NOT composed from `stalled-grabs`**: that operation answers a different rollup (§ 2.5) and
this lot declares it for no surface. For the ratio kind specifically, the card gains a path to the
Trackers page — « Voir le tracker » (`screens.acquisition.ratioReasonTracker`), landing at
`/trackers?tab=trackers&tracker=$name` (§ 3) — and the ratio HOLD it names is read from the
tracker's own obligation (`ObligationItem.min_ratio`), never the legacy `ingest.min_ratio` key,
which is `0.0` on the operator's own host and which no card of this design ever reads (§ 2.5).
**Invariant 7 holds**: `features/acquisition` does not import `features/trackers`; the path is an
address (`lib/addresses.ts`), not a component, and the helper is `crossReference()` (`ui/variants`),
which Système's locks block already draws toward Maintenance (`features/system/locks.tsx:146`) — the
one `features/acquisition/now-tab.tsx` draws toward Arrivées dies with that page (L22b's phase 21).

**The seed is a derivation, said as one.** No card of the mock's seeds is deferred for any of the
three reasons, and § 13 forbids inventing data: the phase re-casts a real waiting card under the
reason its cause composes, or draws the state from its seed marked `x-unseeded` — the contract's own
word for « nothing was invented here » and « nobody looked » being different things — and the
steward chooses (a STOP D at the phase's opening, the precedent L22's phases 9 and 10 set).

**Named states.** `acq-card-deferred-ratio`, `acq-card-deferred-space`, `acq-card-deferred-missing` —
three, in `harness/states/acquisition.ts`, on Acquisition's existing region, each naming the
divergence it adds there. The first two readings' single `acq-card-ratio-reason` is SPLIT into these
three (F14's own scope: « every deferral reason, drawn the same way »).

### 4.7 S7 — The ranking editor (B-298), corrected against F16

**Its place.** `/settings/ranking`, new files `features/settings/ranking-screen.tsx` (or a
`features/ranking/` feature the settings route composes — the plan's opening measure decides, § 5's
phase). The settings rubric « Classement des releases » (`features/settings/page.tsx:305`,
`screens.settings.rankingTitle`) gains its path; the quality screen's `data-toast`
(`features/releases/quality-screen.tsx:283`, `screens.profile.rankingToast`) is REMOVED in the same
phase — B-298 closes when the promise it names is kept, not before.

**What is on the screen — READ, not assumed (F16).** `GET /api/config/files/ranking.json5`
(`readConfigurationFiles`, already declared and mocked, § 2.1) answers the saved `RankingConfig`;
the criteria list draws THAT answer, never a constant the screen invents. A live preview through
`POST /api/acquisition/ranking/preview` — `RankingPreviewResponse.ranked`, sorted, excluded rows
flagged and sunk last (the backend's own words, § 2.1) — reflects every unsaved edit as it is typed,
exactly as production's own twin already does. **Saving calls `PUT
/api/config/files/ranking.json5`** (`updateConfigurationFile`, the SAME operation the tracker policy
uses, § 4.2 — one write mechanism, not two), carrying the file's own `SHA-256` precondition; a save
answered `409`/`412` (a conflict — someone else wrote first) re-reads and reports, the settings
feature's own existing conflict copy, never invented twice. Once § 2.3 item 4 lands, a new criterion
the ratio can drive, using `known_trackers` (already answered) to populate a tracker-keyed field the
same way `provider` does today.

**Named states.** `ranking-editor` (the criteria, READ from the file, the live preview);
`ranking-editor-loading` · `ranking-editor-error` (the two the contract requires); `ranking-editor-saving`
· `ranking-editor-save-conflict` (F16's own two, the save's own hold).

### 4.8 The rules that bite

Numbers: the implementer binds `R-L16-a … R-L16-h` to the next free labels on the day, re-taking
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against the branch's
base at that moment (`R225` on `5e5ecd052`, at this re-read — L20's own phase 1 precedent).

| Rule | What it READS | The mutation that fells it |
| --- | --- | --- |
| **R-L16-a** — NE-DOIT-PAS-1, the ratio is the tracker's | every ratio drawn (S2's entry, S3's row, computed on the torrent's own size) compared against the mock's own field, never a local computation | compute an average client-side → the comparison falls |
| **R-L16-b** — DOIT-3, the tracker's policy and alert threshold | S2's save calling `updateConfigurationFile`; the SAME setting's OWN read (S2's entry, and Réglages' own row) reflecting the new value in the following render — one write, two doors (round 9 Q2) | message without calling → the network hold falls. Disagree S2's read from Réglages' own → the agreement falls too |
| **R-L16-c** — ruling 18, « Retirer de qBittorrent » and the external-removal read | the operation CALLED, every entry sharing the removed files gone from S3 in the SAME render (round 9 Q7's grouped removal); the touched obligation(s) read `released_at` set, NEVER left `breached_at`-only (round 10 M4); a running obligation named in the confirmation whatever the file-deletion checkbox reads; a seeded entry already absent with its obligation's `released_at` set and no removal call anywhere in the walk drawn as simply GONE, never as still active nor as an unexplained gap | make the confirm button message without calling → the network hold falls. Leave a sibling entry (same files) present after the removal → falls. Draw the external case as still active → falls too. Skip the confirmation's tracker name when the checkbox is unchecked but an obligation runs → falls. Draw a removed obligation as still in breach → falls |
| **R-L16-d** — §13, one derivation for the alert (four readers, four components, ruling 12 + round 9 Q1 + round 10 Q4/M5) | the threshold, the breach, the refused identifier and the unseen broken-obligation count read from ONE field each, by S2's entry, S3's row **and the Trackers tab's badge on the bar**; changing any of the four moves what every reader draws; a refused identifier counts ONE per tracker, never one per its torrents (M5) | disagree the chip from the row → the agreement falls. Disagree the tab's count from any reader → falls too. Drop one of the four components from the count → falls. Count a refused tracker's torrents individually → the unit hold falls, naming the inflation. Mark a broken obligation seen without the write answering → falls |
| **R-L16-e** — the ranking preview | the criteria POSTed, the rows drawn compared against `RankingPreviewResponse.ranked`, the `excluded` flag honoured (sunk last, still visible) | draw a constant ranking → the comparison falls. Hide excluded rows → falls too |
| **R-L16-f** — F16, the ranking's own read and save | the editor's criteria at OPEN equal the file `GET` answers, never a constant; a save calls `updateConfigurationFile` and the NEXT read (a reload) answers the saved weights | draw a fixed criteria list ignoring the read → falls. Message success without calling the write → the hold falls, naming the operation |
| **R-L16-g** — DOIT-2's deferral reason, three kinds | the acquisition card in « En cours » naming ONE of ratio / space / missing, its path to `/trackers` for the ratio kind, read on the URL after a tap, and the ratio hold it names equal to the tracker's OWN obligation, never `ingest.min_ratio` | drop the path (ratio kind) → falls. Name the global `ingest.min_ratio` instead of the obligation's own → falls too |
| **R-L16-h** — the addresses (D1) and the tab | `/trackers` resolves and records; the tab and tracker dials ADJUST and push nothing (`history.length` unchanged); the Trackers bar button REPLACES (§ 16 point 2) and the bar reads its four (or three, without the right) equal shares (L22's `R-L22-s`, re-run, not re-written) | make a dial push → the `history.length` hold falls. Make the bar button push → falls too |

**Every one is seen RED against `main` with no mutation needed** — none of these surfaces exists
there. The report records the red reading per rule, as every prior lot's has.

---

## 5. What is NOT drawn

- **Push notifications** (FCM, iOS, Android) — a platform demand (`backend-demands-architecture.md`
  § 4), filed here and built by whichever lot L11's entry points are extended for. This design
  draws the in-app alert only.
- **Cross-seed** — §19, L17's, which depends on L16 and follows it. The Trackers tab's badge gains
  its term there (ruling 12: « the ratio and the cross-seed on Trackers »); the « cross-seed » mark
  on S3's rows, the per-torrent per-tracker cut gesture (round 9 Q8), the naming (round 9 Q10) and
  the exclusion memory (round 9 Q11) are L17's, added to the row this lot draws. L16 does not
  pre-write any of it.
- **The bar's composition by rights, and the accounts** — L18's (ruling 11's « by rights », ruling
  14's « Comptes »; ruling 20's « ACL owned by roles »). L16 adds no role and no flag to
  `app/navigation.ts` (OPEN 2 below, ruled A).
- **A notifications box, or an alert line on Système** — none, by ruling 12.
- **A tracker's account settings** (API key, passkey, enable / disable) — those already live in
  `tracker.json5`'s `providers.<name>.enabled` / credentials, unrelated to the ratio, and stay
  wherever the trackers' activation surface already is or will be drawn; this lot's own reads of
  `economy.*` and the identifier's refused state are the ratio's business only.
- **A mean or global ratio figure anywhere** — § 1 clause 1 forbids it outright.
- **A dedicated page per tracker** — ruling 19 leaves the form to this design; the accordion (S2) is
  chosen for L16 (§ 3, § 4.2), a form ruling 19's own words name as the default. If a later lot's
  additions (L17's cross-seed switch, L18's per-account visibility) push one entry's own content past
  a screenful, that lot measures and reports whether the entry is promoted to its own address — not
  invented here.

### Ruled — the trackers domain's placement, and its form

**Ruled 2026-09-26 (operator, organisation ruling 11): the place Arrivées frees in the bottom bar
goes to a page « Trackers » — ratio, cross-seed, the tracker itself — and the bar is composed by
rights (§ 17 point 4); the page is shown only to the accounts that hold the right.** **Ruled
2026-09-27 (organisation ruling 20, precising ruling 11 and superseding the earlier « fourth place
stays free » reading, F10): once L22b lands, Trackers is INSERTED between Médiathèque and Découvrir,
not appended after a free slot** — the bar reads four equal shares for an account holding the right,
three for one that does not, never an empty one. **Ruled 2026-09-27 (organisation ruling 19,
superseding the first two readings' single-screen form): the page is TWO TABS**, « Torrents » (every
active torrent, once, filterable by tracker) and « Trackers » (one entry per tracker, form left to
the drawing — this design chooses the accordion, § 3, § 4.2).

### OPEN design questions

The first two readings' three OPEN questions were ruled by the operator on 2026-09-26 and are no
longer open; they are folded into § 0.1 and § 4 above rather than repeated here as still-live
choices (`OPEN 1 = A` — Trackers enters the bar at L16 with the ratio alone; `OPEN 2 = A` — no right
is declared before L18; `OPEN 3 = B` — superseded in substance by round 9 Q1, § 4.5's three
components). **One question is genuinely new**, born of ruling 19 itself, which names no default tab:

**OPEN 4 — which tab opens by default when `/trackers` is reached cold.** § 4.1 states its two
readings, and neither is chosen there as such. **Ruled C, 2026-09-27** (§ 4.1): « Trackers » on first
entry, then the last tab opened, kept in local storage (try/catch, falling back to « Trackers »),
by the same mechanism Acquisition's default-tab rule already carries — one rule for every tabbed
page, never a second one. This closes phase 2's STOP C (`plan/phase-02-the-page-and-tabs.md`).

---

## 6. Register rows and demands touched

**BUGS.md**, read, not edited by this design (no BUGS.md edit — this PR is documentation only):

- **B-143** — §17, out of this lot's scope (L18's).
- **B-144** — « §18 (ratio per tracker) needs operations the backend already answers and nothing
  calls » — this design's § 2.2 closes the READING half; § 2.3's demands close the rest.
- **B-145** — §19, out of scope (L17's).
- **B-257** — « Push notifications are declined for L11 and their consumer is §18's ratio alert,
  which is L16 » (`fixed #534`, closed already — L16 is the named consumer, § 5 above).
- **B-298** — « The ranking editor is a promise » — closes when S7 lands, reads AND saves (F16), and
  the toast (§ 4.7) is removed.

**`product-intent-map.md`**, read, amended by the OPERATOR, not by this PR (the map's own header):

- **DOIT-13** row — `to draw`, owner `L16` — this design is that drawing; the phase that lands S2 and
  S3 is what the closing phase reports against it.
- **DOIT-2** row — `partly`, « to draw: a torrent deferred for ratio or space — L16 (§18) » — this
  design's § 4.6 is the ratio half, generalised across the three deferral kinds and corrected against
  F14; drawn on the acquisition card, the surface L22 proposes for the row (its § 6.3), not on
  `features/arrivals`, which the row cites today and which dies at L22b; the missing-content third
  is also drawn here (DOIT-2's own words), and the row says so when amended.
- **DOIT-3** row — `partly`, « to draw: the tracker policy set from the ratio surface — L16 » — § 4.2.

**`docs/reference/backend-demands-architecture.md` § 4**, corrected in the same PR (F11(c)) and
extended by this redraw's own demands (§ 2.3): the write already exists (`updateConfigurationFile`
on the `economy` block) — only the alert threshold is a missing key, not a missing operation; a
per-tracker health read (the refused identifier, round 9 Q1); the per-tracker, per-size ratio on
each active entry; « Retirer de qBittorrent », REPLACING the release verb outright (round 10 Q3 = B,
**F15 REPLACED**) with its grouped, shared-files removal (round 9 Q7) and its always-released close
(round 10 M4); the removal-reconciliation stream event; a « vu » write for a broken obligation (round
10 Q4); the alert threshold's own push channel; the ranking's ratio-aware scoring field. **Nothing
here is a demand this design invents from nothing** — every item is this design's typed shape of a
sentence § 4 or the operator's own rulings already carry.

**`frontend/maquette/README.md`'s binding cut table** (« The cut is by the nature of the trouble »,
C9) is not edited by this design — it is a code-adjacent file outside this PR's scope — but the
closing phase's own move (§ 16 of the plan) adds the row it is missing: « A tracker in trouble
(ratio, obligation) → **Trackers** », naming ruling 12, the same move C9 asks for, made when the lot
that draws the surface lands rather than left for L17's close to invent a row of its own.

**`docs/reference/frontend-backend-demands.md`**, computed, not edited by this PR — the phase that
opens the contract (§ 2) regenerates it with `scripts/compare-contracts.py --write` and reads its
counters before and after, as every prior lot's phase 1 has.
