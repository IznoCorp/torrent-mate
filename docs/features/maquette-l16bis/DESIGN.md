# L16-bis — the Trackers page's correction, and Découvrir's header · DESIGN

Contract: the operator's feedback of 2026-09-29 16:4x–17:1x on the Trackers page L16 shipped (#634), recorded verbatim
in `docs/reference/operator-method.md` (entries 16:4x, 16:48, 16:52, 16:58, 17:17), and the auditor's orders 57, 69,
76, 77, 79 and 80 read against it. `docs/reference/frontend-architecture.md` § 4 carries the lot's one-line entry,
placed BEFORE L17, because L17 draws on these same torrent rows.

This document is written for a session that has none of the context it was produced in. **Nothing under
`frontend/maquette/` was touched to write it** — no code, no rule, no mock, no seed, no harness run: prose and
numbers. Every figure carries the command that produced it.

**Written 2026-09-29, on `main` at `f3d8fed01`** (L16 merged, #634). The plan's order becomes `… L22 · L16 · L16-bis ·
L17 · L18 · L23 · L24`. **Amended 2026-09-29**, PR #637's correction round: § 5's nine OPEN questions are DECIDED, the
operator's own words in `/Users/izno/dev/review-archive/l16bis/rulings-2026-09-29.md` — nothing left open in this
document.

---

## 0. What L16-bis owes, said once

| # | Subject | Its source (verbatim in `operator-method.md`) | Surface | Held for |
| --- | --- | --- | --- | --- |
| 1 | « Torrents » first; the first opening lands on it, then on the tab opened last | 16:4x (1) — amends L16 OPEN 4 = C | **S1** | § 1.1 |
| 2 | a tracker SELECTOR atop the torrents list, the list of trackers being long | 16:4x (2) | **S2** | § 1.2 |
| 3 | a LEGEND of every colour code the page uses — its absence is a defect | 16:4x (3); order 57 | **S3** | § 1.3 |
| 4 | the torrent card says: the full file name, size, state, down / up, popularity, date added | 16:4x (4) | **S4** | § 1.4 |
| 5 | the torrent card takes the media card's style and gestures: poster → the medium's sheet, the rest → a bottom panel, a swipe each way | 16:4x (5) | **S4**, **S5**, **S6** | § 1.4–1.6 |
| 6 | every case of every surface touched, each a named state reachable from the catalogue | orders 76, 77 | § 3 | § 3 |
| 7 | the whole page brought back to the design system — an element redrawn where one exists is a defect | 16:48; order 79 | the table of § 1.8 | § 1.8, § 1.9 |
| 8 | Découvrir's header message beside the view switch; its content replaced by something useful | 16:52 | **S8** | § 1.10 |
| 9 | an activation switch per tracker; a failing tracker switched off by itself, its error said on re-activation; the list grows | 16:58 | **S7** | § 1.7 |
| 10 | ONE tab component, adapted, for every tabbed page | 17:17; order 80 | **S1** | § 1.1 |

### 0.1 Measurements that correct the premises

Each read on `f3d8fed01`, from the worktree root.

1. **The strip already reads « Torrents · Trackers »; the LANDING is what reads « Trackers » first.**
   `features/trackers/page.tsx:25–28` lists `torrents` then `trackers`. But the first opening lands on « Trackers »:
   `tabMemory("trackers-tab", "trackers", TABS)` (`features/trackers/verbs.ts:18`) and `trackersTab: "trackers"` in the
   interface's opening state (`app/arrival.ts:27`). What the operator saw — « l'onglet Tracker est en premier » — is
   the tab the page opens on. Point 1 is two values, not a re-ordering.
2. **Three tab bars, two sizes, three compositions, no component.**
   `git grep -n 'role="tablist"' -- 'frontend/maquette/design/src/*.tsx'` reads three:
   `features/acquisition/acquisition-tabs.tsx:34` (`segmentTab` + the feature's `fingerTab`, 44 px, counts, a « ⋮ »),
   `features/library/library-head.tsx:41` (`segmentTab` alone — no 44 px floor, counts) and
   `features/trackers/page.tsx:32` (`segmentTab` + the feature's own `trackersTab`, 44 px). Each page composes the
   variants `viewTabs` / `segment` / `segmentTab` / `segmentCount` of `ui/variants/controls.ts` inline; the height
   floor is re-declared per feature (`fingerTab`, `trackersTab`) and forgotten once (Médiathèque).
3. **Three fold drawings.** `git grep -n "summary::before" -- 'frontend/maquette/design/src/*.ts'`:
   `ui/variants/surfaces.ts:407` (`ui/Disclosure`: the glyphs `▸` / `▾`, swapped), `features/acquisition/variants.ts:48`
   (« par identifiant »: `▸` / `▾` again, re-declared), `features/media/variants.ts:226` (a season: `›` in a 20 px
   muted chip, turned 90° when open). Three raw `<details>` bypass the component: `features/acquisition/add-screen.tsx:337`,
   `features/media/panel-seasons.tsx:143` and `features/media/season-list.tsx:256`. The Trackers tab folds through
   `ui/Disclosure` (`features/trackers/trackers-tab.tsx:9, 100, 144`) — the operator reads ITS chevron as the stranger,
   against the seasons' one he meets on every series sheet.
4. **A legend exists — in a feature.** `features/media/variants.ts:346, 358` (`legend`, `legendSwatch`: « only the
   states present, each with its swatch », over the season matrix). Invariant 7 forbids `features/trackers` to import
   it: reusing it means MOVING it to `ui/`, not redrawing it.
5. **The page's colour codes, counted.** `features/trackers/torrents-tab.tsx` and `trackers-tab.tsx` draw **seven**:
   the origin dot (`statusDot` `info` = the original grab, `waiting` = a cross-seed; L23 OPEN 5 = B adds a third,
   « publié par vous »), and the chips `info` (« obligation en cours »), `success` (« obligation terminée »), `danger`
   (« en infraction », « N obligations rompues », « identifiant refusé ») and `warning` (under the alert threshold).
   None is explained on the page; the dot has an `aria-label` only.
6. **The longest real torrent name is 132 characters; the seeds' longest is 80.**
   `sqlite3 "file:$HOME/dev/PersonalScraper/.data/acquire.db?mode=ro" "select max(length(release_name)) from staging_provenance"`
   → **132** (« Stuart.Fails.to.Save.the.Universe.S01E07.Spoiler.Dexys.Midnight.Runners.Get.a.Royalty.Payment.MULTi.1080p.WEB.SDR.EAC3.5.1.x265-BYOR »,
   79 rows with a name); `mocks/seeds/downloads.json` → 7 entries, the longest `name` **80**
   (« Star.Trek.Strange.New.Worlds.S04E10… »). The card's title today is `cardTitle` —
   `whitespace-nowrap overflow-hidden text-ellipsis` (`ui/variants/card.ts:37`) — which cuts such a name at ~30
   characters on a phone, what § 12 calls « une devinette ».
7. **What the entry answers, and what it does not.** The contract's `Download` carries `name`, `state` (eight engine
   tokens: `downloading`, `stalled`, `seeding`, `paused`, `queued`, `in_client`, `missing`, `errored`), `sizeBytes`,
   `ids`, `tracker`, `origin`, `ratio`, `deadline` — and **no rate, no volume, no popularity, no date added**. The
   engine HAS two of the four on its client item and does not route them: `swarm_seeds`
   (`personalscraper/api/torrent/_base.py:77`, from qBittorrent's `num_complete`) and `added_on` (`:48`); its
   `AcquisitionDownload` (`frontend/openapi.json`) carries neither. No rate and no per-entry volume is read anywhere
   (`git grep -n "dlspeed\|upspeed" -- 'personalscraper/*.py'` → nothing). `fr.json` holds no word for any of the
   eight states.
8. **Every real entry is linked to a medium.** The seven seed entries all carry `ids`; an unlinked torrent (a hand-added
   one, or one the engine never identified) has no real row — it is POSED (RULINGS 7's standing rule), never seeded.
9. **The real configuration holds a third tracker, switched off after it failed.** The operator's
   `~/.torrentmate/config/tracker.json5` line 11: `lacale: { enabled: false, cross_seed: false }` with the comment
   « deprecated + unreachable (la-cale.space down) — disabled to stop CircuitOpenError crashing grab »; the maquette's
   `mocks/seeds/settings.json:594` carries `tracker.providers.lacale.enabled`, and `mocks/seeds/trackers.json` carries
   only `c411` and `tr4ker`. The engine today switches NOTHING off by itself: a refused credential raises
   `TrackerAuthFailed` (`personalscraper/acquire/events.py:316`, HTTP 401/403) and abandons the item; an unreachable
   tracker opens its circuit (`CircuitOpenError`) — the operator switched `lacale` off by hand.
10. **Découvrir's header figures are copy, not data.** `features/acquisition/discover-tab.tsx:151–160` draws
    `liveBefore` « Réserve remplie il y a 2 h · », `liveSuggestions` « 503 », `liveOwned` « 1 832 », `liveAfter`
    « ids TMDB possédés exclus » — four `fr.json` strings (`i18n/fr.json:850–854`): no read feeds them, § 13's
    « aucun état affiché n'est une constante ». The pill row above it holds an EMPTY `pill/list`
    (`discover-tab.tsx:107`) beside the view switch — the place point 8 names. The engine has no suggestions route at
    all (`frontend/openapi.json`: no path holds `suggest` or `discover`): `readSuggestions` is already a demand.

### 0.2 What L16-bis builds on, and does not redraw

| Landed | L16-bis reads it as |
| --- | --- |
| L16 (#634) — the page, its two tabs, the reads, « Retirer de qBittorrent » and its three confirmations, the alert and its four readers, the broken obligations, the policy's second door, the ranking editor | the subject corrected; the removal's confirmations, the alert's derivation, the policy rows and the ranking editor are KEPT as they are |
| L22 — Acquisition's media card (`ui/card-markup.ts`, `features/acquisition/card-markup.ts`), its poster → sheet, its body → bottom panel | the card the torrent card takes its style and taps from |
| L12 — the swipe row (`ui/rows.ts`, `lib/swipe-arbitration.ts`), the follow row's two drawers (`features/acquisition/follows-tab.tsx:153–159`) | the gesture the torrent card takes |
| L15 — the bottom panel (`ui/panel/`), its generic blocks (facts, actions) | the torrent's panel |
| `lib/tab-memory.ts` — one rule for every tabbed page | the landing rule, re-valued |

---

## 1. The surfaces

Copy is given in « guillemets » as `fr.json` will carry it; a key is proposed beside new copy.

### 1.1 S1 — The tabs, and the one tab component (points 1, 10)

**The landing (point 1, as amended by the operator).** « Torrents » is the first tab AND the first landing; then the
tab opened last on this device. Two values change: `tabMemory`'s first tab (`verbs.ts:18`) and the opening state's
`trackersTab` (`arrival.ts:27`), both to `torrents`. L16 OPEN 4 = C is AMENDED, not reversed: the rule (first tab,
then the last opened, local memory, try/catch) is kept; its first tab is « Torrents ». A landing that NAMES a tab
(`trackers:c411`, the deferred card's « Voir le tracker ») is obeyed, unchanged.

**The one tab component (point 10).** No component exists (§ 0.1 item 2). The DESIGN specifies it; the CONFORMITY
TRAIN builds it, on the existing validated bars (Acquisition first) as its reference (DECIDED 7, § 5) — L16-bis's
code waits for the train, then uses the component for Trackers. No phase of this plan builds it.

- **Where**: `ui/`, one component `Tabs`, knowing no domain (invariant 10), composed from the variants that exist —
  `viewTabs`, `segment`, `segmentTab`, `segmentCount`, `moreButton` — with the 44 px floor INSIDE `segmentTab`, so no
  feature re-declares it (`fingerTab`, `trackersTab` die).
- **What it takes**: the tabs (2 to N — four today at most, Acquisition), each `{ id, label, count?, badge? }`; the
  selected id; the verb its taps write (`data-*` the caller names, as `Disclosure` leaves the parts to its caller);
  an optional trailing control (Acquisition's « ⋮ »). A count is `segmentCount`; a badge is the bar's badge drawing
  (`tabBarBadge`, `ui/variants/frame.ts:133`), never a third drawing.
- **What it owns**: `role="tablist"`, `role="tab"`, `aria-selected`, the size, the sticky row. **What it does not
  own**: the landing rule — that stays `lib/tab-memory.ts`, each page bringing its key and first tab.
- **The three bars** (Acquisition, Médiathèque, Trackers) are brought to it; the guard of § 1.9 refuses a
  `role="tablist"` outside `ui/`.

**Named states** — § 3, S1.

### 1.2 S2 — The tracker selector (point 2)

**Its place.** Atop the « Torrents » list, in the filter zone the app already draws above a list: `filterZone` →
`pillBar` (`ui/variants/controls.ts:317, 320`), the Médiathèque's own row shape.

**What it shows.** ONE pill (`filterPill`), reading « Tous les trackers » (`screens.torrents.selectorAll`) when the
list is unfiltered, and the tracker's name when it is filtered — `aria-pressed` then, the pill's existing pressed
drawing; its count (`filterPillCount`) is the number of entries shown. A tap opens the **bottom panel** with the
choices, drawn by the choice list the settings panel already draws for an enumerated setting (`optionList`, `option`,
`optionMark`, `ui/variants/controls.ts:165–236`): « Tous les trackers » first, then every tracker of the roster in its
configuration order, each with its entry count, a tracker switched off said so beside its name (S7's word). A choice
closes the panel and filters; it pushes nothing (the `trackers-filter` verb, an adjustment, RULINGS 3).

**Why a panel, not pills.** Pills scroll sideways and hide what is off-screen; the operator names the length of the
list as the reason (« la liste de tracker peut être longue ») — six trackers in the seeds of § 2.3, more to come. The
panel is the app's own long-choice surface.

**How it clears, and RULINGS 3.** The steward's RULINGS 3 (a line « Filtré sur <tracker> · Tout voir » above the rows)
answered « the filter is seen and can be lifted ». **The feedback REVERSES its form, not its intent**: the pill SAYS
the filter (the name, pressed) and « Tous les trackers » lifts it, so the line is removed — two drawings of one
fact would be § 13's two derivations. `torrents-empty-filtered` keeps its own sentence (L16 § 4.3).

### 1.3 S3 — The legend (point 3)

**The defect.** Seven colour codes (§ 0.1 item 5), none explained: filed in § 6 (order 57).

**What it draws.** Every colour the page uses, each with its word, **only the codes present** on the tab being read —
the season legend's own rule (`features/media/variants.ts:345`). The dot's three values (« téléchargé ici »,
« cross-seed », « publié par vous » — the last from L23, drawn once L23 lands, the legend reading the page's own
values) and each chip tone with the words of the chips it colours. The legend READS the same tone map the rows draw
from — one derivation (§ 13): a colour added to a row without its legend entry is what R-L16bis-c fells.

**Its component.** The season legend, MOVED to `ui/` (invariant 7), unchanged in drawing; `features/media` imports it
from there. **Where it sits**: inline, above the list (DECIDED 5, § 5) — the season legend's own place, REUSED as is.

### 1.4 S4 — The torrent card (points 4, 5)

**Its component: the media card** — `ui/card-markup.ts` (`cardMarkup`), the one Acquisition's cards are drawn with,
wrapped in the swipe row (S6). The row of `features/trackers/torrents-tab.tsx:51–120` (a `factRow` with a text
button for a title and a text « Retirer » in danger colour) is replaced.

**What the card says, in § 12's order.**

1. **Line 1 — the file name, WHOLE** (`Download.name`). It wraps; it never ellipsises (§ 12 « rien d'essentiel n'est
   tronqué »). The card's title variant gains a `wrap` value — `[overflow-wrap:anywhere]` in place of `nowrap` /
   `ellipsis` — because a release name has no spaces to break at: a new VARIANT of an existing part, justified by
   § 0.1 item 6's 132 characters, never a second title part. At 369 px (order 60's width) the 132-character name
   takes ≈ 5 lines; the card grows, the poster keeps its box at the top.
2. **Line 2 — the state first** (a chip: the engine's eight tokens in eight words, `screens.torrents.states.*`, each
   with its tone — `downloading` `info`, `seeding` `success`, `stalled` `warning`, `errored` / `missing` `danger`,
   `paused` / `queued` / `in_client` `neutral`), then the size (« 766 Mo », `sizeBytes`, the interface's unit words),
   then the ratio on this tracker (L16's, unchanged).
3. **Line 3 — the annotations** (`cardAnnotations`): down / up, per DECIDED 1 (§ 5) — THREE named states, not one
   drawing: **default** (nothing active) shows the received/sent VOLUMES (« ↓ 766 Mo · ↑ 1,2 Go »,
   `torrent-card-volumes`); **while downloading**, a PROGRESS BAR with the download RATE (« ↓ 2,4 Mo/s »,
   `torrent-card-downloading-progress`); **while uploading**, no bar, the upload RATE alone (« ↑ 310 Ko/s »,
   `torrent-card-uploading-rate`) — then the popularity (« 12 sources », `swarmSeeds`; « sources inconnues » when the
   client does not say — never « 0 », which means a dead swarm, `_base.py:57`), the date added (« ajouté le
   26 septembre », `addedAt`).
4. **The marks** (L16's, unchanged): the tracker's name, the obligation chips (`info` / `success` / `danger`), the
   deadline.

**What it does not say**: the medium's title — the poster carries it (its `aria-label`, « Fiche de President
Curtis »), and the name already holds it (§ 12 « pas de redondance »).

**The two taps — the media card's own.**

- **The poster**, when the entry is linked (`ids` present): the medium's poster, a tap opens its sheet
  (`data-mediasheet`, the media card's attribute, `features/acquisition/card-markup.ts:218–221`). NE-DOIT-PAS-9's
  path to the sheet. An entry linked but without artwork draws the poster fallback (its initials,
  `posterFallback`) — still a path to the sheet, the card's own rule.
- **Unlinked** (`ids` null): no poster. What stands in its place, per DECIDED 2 (§ 5): the media card's own
  non-medium side, the folder icon and its word (`cardFolder`) — the same card anatomy as every other row, a tap
  opening the panel. An unlinked entry's path to resolution (NE-DOIT-PAS-9's exception) is in its panel (S5), never
  on a dead poster.
- **The rest of the card** opens the torrent's bottom panel (S5): `data-panel`, the body's attribute.

### 1.5 S5 — The torrent's bottom panel (point 5)

**Its component**: `ui/panel` with its generic blocks only — a facts block (`FactLine` rows) and an actions block
(`Action`) — no block kind of the feature's own. Its subject is the entry, `torrent:<infoHash>:<tracker>`.

**The details**, one fact each, every one said when absent (« inconnu », never blank — § 8): the full name, the
medium (its title and a path to its sheet when linked), the tracker and the origin (the legend's word), the state,
the size, the progress when downloading, down / up (DECIDED 1, § 5 — the same three states as the card: volumes by
default, the download rate while downloading, the upload rate while uploading), the popularity, the date added, the
ratio on this tracker, the obligation (running until / met on / broken on) and its deadline.

**The actions**: « Voir la fiche » (linked) or « Identifier » (unlinked, an entry whose staging folder the engine
holds — `/resolution/$folder`; an entry with none says « Aucun dossier à identifier. »); « Retirer de qBittorrent »
(`tone` danger — the L16 verb and its three confirmations, unchanged); and the place of L17's « Chercher un
cross-seed » and its per-tracker mark, which L17 adds to this panel's actions and facts (L17 § 3.3 is re-homed from
the row to this panel; L17's own plan re-reads it at its opening).

### 1.6 S6 — The swipe (point 5)

**Its component**: the swipe row (`swipeRowMarkup`, `ui/rows.ts:39`; `swipeAction` tones, `ui/variants/rows.ts:30`),
the follow row's own gesture, `lib/swipe-arbitration.ts`: one row open at a time, the axis claimed, the click that
must not follow a drag.

- **Travel left → the right drawer: « Retirer »** (`tone: remove`, the trash icon — the follow row's own drawer for
  its own removal). Its tap is the SAME verb as the panel's « Retirer de qBittorrent », so it ALWAYS opens L16's
  confirmation (round 9 Q7, organisation ruling 18, round 10 M4): a swipe never removes by itself.
- **Travel right → the left drawer: the manual cross-seed**, the row's one « for » action (the arbitration's own
  wording: « the left one holds the single thing the row is FOR »). Its verb is L17's; per DECIDED 9 (§ 5), L16-bis
  draws NOTHING in the meantime — the drawer does not exist until L17 adds it; nothing is drawn that does nothing.

### 1.7 S7 — The tracker roster: the switch, the failure, the longer list (point 9)

**The row.** Name, then the activation switch at the row's end — `toggleSwitch` (`ui/variants/controls.ts:145`),
`role="switch"`, `aria-checked`, the one the settings panel draws (`features/settings/panel-field.tsx:74`). **Corrected 2026-09-30 (the conformity train, phase 6):** when this was written the settings panel drew its own `fieldToggle` + `fieldKnob`, not `toggleSwitch`; the train made `toggleSwitch` the app's one switch, the settings field included, so the sentence is true from that phase on — § 1.8's « the activation switch → `toggleSwitch` » reuses that one switch. Under the
name, L16's facts: ratio, trend, volumes, and the chips. **The form of the row**, per DECIDED 3 (§ 5): the body opens
the BOTTOM PANEL (settings, cross-seed and upload switches, broken obligations) — like the torrent card, S5; the
activation switch stays on the row, never moved into the panel.

**Which switch where.** ON THE ROW: **activation** alone — the operator's « facilement ». In the tracker's detail (its
panel, DECIDED 3): **cross-seed** (L17 § 3.2, round 8 Q2 — « activation is not cross-seed ») and **accepts
uploads** (L23, round 11 Q2 = B), each its own row, never merged into activation.

**One write, two doors (round 9 Q1).** The switch writes `tracker.providers.<name>.enabled` through
`updateConfigurationFile` — the SAME setting Réglages draws (`mocks/seeds/settings.json:594, 611, 670`), the SAME
pending-edits bar (RULINGS 2, C2) and the SAME three-choice leave confirmation (round of 2026-09-29 Q4). A tap
toggles the pending value; the save bar writes it.

**Three states of a switch.**

| State | The switch | Under the name |
| --- | --- | --- |
| active | on | L16's facts |
| off by the operator | off | « Désactivé » (`screens.trackers.disabledByOperator`) |
| off by failure | off | « Désactivé — injoignable depuis le 12 septembre » (`screens.trackers.disabledByFailure`, the reason in the engine's words, § 2.2) |

**Re-activating a failed tracker.** A tap on its switch asks the engine; while the tracker still fails, the answer is
a REFUSAL and the switch stays off, the refusal said under the row in the engine's own words — « Identifiant refusé
par le tracker (HTTP 403) », « Tracker injoignable » — never a code alone (NE-DOIT-PAS-4) and never a toast that
leaves (NE-DOIT-PAS-5). The refusal is a state (`tracker-reactivate-refused`). Per DECIDED 6 (§ 5), an off-by-failure tracker counts ONE in
the Trackers badge, exactly like the refused identifier — the same counting mechanism, adapted (§ 2.2).

**The longer list (composed rows).** `v3x.club`, `draupnirr.xyz`, `digitalcore.club` do not exist in the engine; their
rows are COMPOSED, declared so in `frontend/maquette/fixture-register.json` (« composé — tracker demandé, absent du
moteur »), never presented as lived (§ 13). The real `lacale` (§ 0.1 item 9) is the lived « off after a failure » —
its reason « injoignable » read from the operator's own configuration comment, declared as such. The seeds of § 2.3
give every case one subject.

### 1.8 The design system, element by element (point 7)

**Binding constraints, the operator's own words, this round (§ 5, DECIDED 3/5/6)**: coherence everywhere — design,
ergonomics, gesture, component, design system; a component is REUSED, never copied — one design system, one
component, and changing it changes everywhere it is used; two similar mechanisms of the app behave the same way — no
new component is created where an existing one can be ADAPTED (only when adapting is not reasonably possible is a new
one justified), and every adaptation is written into the design system, kept up to date. These bind every row below.

Every element of the Trackers page after L16-bis, and of Découvrir's header, against the component or variant it
uses. **A NEW part is written only with its justification**; everything else REUSES.

| Element | Today (L16) | After L16-bis | New? |
| --- | --- | --- | --- |
| the tab strip | `segment` + `segmentTab` + `trackersTab` inline | `ui` `Tabs`, built by the conformity train (§ 1.1, DECIDED 7) | no (this lot draws none of it) |
| the tracker selector | — (RULINGS 3's line, `torrentFilter` / `torrentFilterClear`) | `filterZone`, `pillBar`, `filterPill`, `filterPillCount`; the panel's `optionList` / `option` | no |
| the legend | — | the season legend, MOVED to `ui/` | no (moved) |
| a torrent | `factRow` + `torrentHead` + `torrentTitle` + `torrentChipLine` + `torrentRemove` | `cardMarkup` in `swipeRowMarkup` | a `wrap` value on the card title (justified: § 0.1 item 6) |
| the origin mark | `statusDot` | `statusDot`, unchanged | no |
| the state, the obligation | — / `chip` | `chip` | no |
| down / up, popularity, date | — | `cardAnnotations`, `cardCaption` | no |
| the download progress bar | — | a new fill variant | yes (justified: DECIDED 1, § 5 — no byte-progress component exists; `cardStrip` is a stage strip, a different mechanism, not redrawn) |
| the torrent's detail | — | `ui/panel` facts + actions | no |
| « Retirer » (row) | `torrentRemove`, a text button in danger colour | `swipeAction({ tone: "remove" })` + the panel's action | no |
| a tracker row | `Disclosure` + `factRowBody` | a list row → `ui/panel` (DECIDED 3, § 5) | no |
| the fold chevron | `ui/Disclosure`'s `▸` / `▾` | the seasons' chevron, the app's ONE (DECIDED 4, § 5), in `ui/Disclosure` only | no |
| the activation switch | — | `toggleSwitch` | no |
| policy rows | `FactRows` → the `setting` panel (RULINGS 2) | unchanged | no |
| « Voir les torrents » | `crossReference` + `seeTorrents` | `crossReference` (the floor moved into it) | no |
| « Vu » | `seenControl` | the panel's action drawing | no |
| alert / refusal chips | `chip` | `chip` | no |
| empty, loading, error | `emptyNote`, `Skeletons`, `SurfaceError` | unchanged | no |
| Découvrir's message | `liveStrip` in the body | `liveStrip` inside `pillBar`'s `pill/list` place | no |

**The feature's own variants that die** (`features/trackers/variants.ts`): `torrentTitle`, `torrentFilter`,
`torrentFilterClear`, `torrentHead`, `torrentChipLine`, `torrentRemove`, `trackersTab`, `seeTorrents`, `seenControl`
— nine of nine; the file is removed if nothing is left in it.

### 1.9 The guards — cost evaluated (order 79 (3), order 80)

Both are specified for the **conformity train** (order 80), NOT for L16-bis: a lot adds no guard, arm or tool
(`docs/reference/implementer-office.md`, « Fixed non-goals »), and both would be red on `main` at landing until the
train converts the other sites.

**The fold chevron — an ARM of `scripts/check-component-once.py`** (« a component is written once »: its subject
already, one arm today). **Specification**: over every `.ts` / `.tsx` under `frontend/maquette/design/src` outside
`ui/`, `engine/`, `mocks/`, refuse (1) a `<details` element and (2) a `summary::before` or `summary::after` class
token; `ui/disclosure.tsx` is the one place allowed. Hard zero, no allow-list; a floor on the corpus (the guard's own
« empty read » rule). **Measured today**: 5 hits (§ 0.1 item 3: `add-screen.tsx:337`, `panel-seasons.tsx:143`,
`season-list.tsx:256`, `features/acquisition/variants.ts:48`, `features/media/variants.ts:226`). **Cost**: ≈ 40
lines of guard and its test, plus the 5 conversions (the season fold becomes a `Disclosure` variant) — ≈ 8 points,
cheap. A chevron drawn as an SVG `path` outside `ui/` is NOT read (the icon set `app/icons.ts` has `right`, used for
navigation, not folding) — said, so nobody reads more into the arm.

**The tab bar — an ARM of the same guard** (the operator's « mandatory »): refuse `role="tablist"` (in JSX or in
markup strings) outside `ui/`. Measured today: 3 hits (§ 0.1 item 2). Cost ≈ 3 points beside the chevron arm.

### 1.10 S8 — Découvrir's header (point 8)

**(a) The place.** The message leaves the body and takes the empty `pill/list` place of the pill row
(`discover-tab.tsx:107`), beside the view switch: same row, same height saved (the `liveStrip` box, ≈ 44 px plus the
body's gap). It keeps `liveStrip`'s drawing, its border dropped inside the row (a `liveStrip` variant `inline`, the
one new value, justified by the host row). **One line**: it ellipsises at the switch — the only text on the page
allowed to, because it is secondary and its whole is on its tap (the bottom panel with the sentence whole). **It comes
down** into the body if the row's place is ever taken — the operator's own words; a note in the component, not a
rule.

**(b) The content.** The count and the TMDB ids excluded go (§ 0.1 item 10: they were not even read). Per DECIDED 8
(§ 5), what replaces them is « n séries et m films à découvrir » (`screens.discover.headerCount`) — both numbers
counted from the suggestions already read (the same list the tab already renders, split by media type), no new
field and no engine demand.

**The TMDB-disconnected warning** (`discover-tab.tsx:162–184`) stays in the body: it is a state with an action, not a
header message.

---

## 2. The contract (D7) — and it comes FIRST

**Measured on `f3d8fed01`**: `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
→ **75** operations. `Download` and `Tracker` shapes: § 0.1 item 7 and `Tracker`'s `name, ratio, downloadedBytes,
uploadedBytes, trend, alertThreshold, identifierRefusedSince, brokenObligations`.

### 2.1 `Download` — extended (a shape edit)

| Field | For | The engine |
| --- | --- | --- |
| `addedAt` (epoch s, null) | the date added | HAS it (`TorrentItem.added_on`), not routed — an extension of `AcquisitionDownload` |
| `swarmSeeds` (int, null) | the popularity | HAS it (`TorrentItem.swarm_seeds`), not routed |
| `swarmLeechers` (int, null) | the popularity's second half | qBittorrent answers `num_incomplete`; the engine's mapper does not read it — PROPOSED |
| `downloadedBytes`, `uploadedBytes` (bytes, null) | down / up, default state (DECIDED 1, § 5) | neither is read by the engine — PROPOSED |
| `downloadRate`, `uploadRate` (bytes/s, null) | down / up, while downloading / while uploading (DECIDED 1, § 5) | neither is read by the engine — PROPOSED, a stream demand on `TorrentProgress` |

### 2.2 `Tracker` — extended, and the activation's refusal

- `enabled` (bool) — read from the same setting the switch writes, so the roster and Réglages agree.
- `disabled`: `null` or `{ by: operator | failure, reason: identifierRefused | unreachable | other, message, since }` —
  `message` is the engine's own sentence. **`identifierRefusedSince` is FOLDED into it** (one field per fact, § 13):
  a refused identifier is `reason: identifierRefused`; L16's alert derivation and R-L16-d's unit hold (M5) re-read
  it there, re-aimed out loud.
- **The refusal.** `updateConfigurationFile` on `…enabled = true` for a tracker whose failure persists answers `422`
  with a `Problem` whose `detail` is the engine's words — a mock scenario over a declared operation, no new operation.

### 2.3 The seeds (every case has one subject — order 77)

| Subject | Real or composed | Carries |
| --- | --- | --- |
| `c411`, `tr4ker` | real | active; L16's cases (alert, refused identifier, broken obligations) posed as today |
| `lacale` | real (§ 0.1 item 9) | off after a failure, « injoignable », declared |
| `v3x.club` | composed, declared | active, no entry — a tracker with nothing running |
| `draupnirr.xyz` | composed, declared | off by the operator |
| `digitalcore.club` | composed, declared | off by failure, « identifiant refusé », the re-activation refused |
| the seven real entries | real | each gains `addedAt`, `swarmSeeds`, down / up — **read from the operator's qBittorrent once, read-only, at the phase's opening**, its date in the register; a figure the client does not give stays `null` |
| a 132-character name | real NAME, posed entry | `poseLongName`, on a real entry, the name of § 0.1 item 6 (RULINGS 7) |
| an unlinked entry | posed | `poseUnlinked`, a real entry's `ids` removed, declared a derivation |
| one entry, none | posed | the list reduced to one / emptied (the empty already exists) |
| each engine state | posed | `stalled`, `paused`, `queued`, `errored` (its `errorReason`), `missing` on real entries |

---

## 3. Named states — every case, per surface

Every id is PROPOSED; L16's ids that survive are marked « kept ». Each is declared in
`frontend/maquette/design/src/harness/states/trackers.ts` (or `acquisition.ts` for S8) with its French label — the
source the catalogue of order 76 lists.

**S1 — the tabs**: `trackers-page` (kept — now landing on « Torrents ») · `trackers-page-remembered` (a second
visit, « Trackers » opened last) · `trackers-landing-named` (« Voir le tracker » naming `trackers:c411`) ·
`trackers-loading` · `trackers-error` (kept).

**S2 — the selector**: `torrents-selector` (the pill, unfiltered) · `torrents-selector-open` (the panel, six
trackers, their counts, the off ones said) · `torrents-list-filtered` (kept — the pill pressed) ·
`torrents-empty-filtered` (kept).

**S3 — the legend**: `torrents-legend` (every code present) · `torrents-legend-partial` (a filtered list, only its
codes) · `trackers-legend` (the roster's codes).

**S4 — the list and the card**: `torrents-list` (kept, many) · `torrents-one` · `torrents-empty` (kept) ·
`torrents-loading` · `torrents-error` · `torrent-card-long-name` (132 characters at 369 and 390 px) ·
`torrent-card-unlinked` · `torrent-card-no-artwork` (linked, initials) · `torrent-card-no-popularity` ·
`torrent-card-downloading` · `torrent-card-stalled` · `torrent-card-paused` · `torrent-card-queued` ·
`torrent-card-errored` · `torrent-card-missing` · `torrent-card-cross-seed` · `torrents-obligation-done` (kept) ·
`torrent-obligation-breached` (kept) · `torrents-external-removal` (kept) · `torrent-card-volumes` (DECIDED 1,
default — received/sent) · `torrent-card-downloading-progress` (DECIDED 1 — the progress bar and the download rate)
· `torrent-card-uploading-rate` (DECIDED 1 — no bar, the upload rate alone).

**S5 — the panel**: `torrent-panel` (linked) · `torrent-panel-unlinked` (« Identifier ») ·
`torrent-panel-unlinked-no-folder` · `torrent-panel-partial` (every « inconnu »).

**S6 — the swipe**: `torrent-swipe-remove` (the right drawer open) · `torrent-remove-confirm` ·
`torrent-remove-confirm-obligation` · `torrent-remove-confirm-shared` (kept — reached from the swipe too). No
cross-seed state (DECIDED 9, § 5): the left drawer is not drawn until L17.

**S7 — the roster**: `trackers-roster` (kept — six trackers) · `trackers-roster-one` · `trackers-roster-empty`
(kept) · `tracker-active` · `tracker-off-by-operator` · `tracker-off-by-failure` · `tracker-reactivate-refused` ·
`tracker-switch-pending` (the save bar up) · `tracker-switch-write-failed` · `trackers-entry-open` (kept — now the
panel, DECIDED 3) · `trackers-policy-unset` (kept) · `tracker-alert-active` · `tracker-identifier-refused` ·
`tracker-broken-obligations` · `tracker-broken-obligations-open` (kept) · `tracker-composed` (a composed row, its
declaration readable in the catalogue label).

**S8 — Découvrir's header**: `discover-header` (« n séries et m films à découvrir », each view mode — list, posters,
deck) · `discover-header-narrow` (369 px, ellipsised, its tap opening the sentence) · `discover-header-loading` ·
`discover-header-unavailable` (its datum's read failed — said, never blank). No conditional content state: DECIDED 8
(§ 5) needs none of readings A or C.

**Counted** (by script over this section): **62** ids — every one of L16's 21 kept, **41 new**, none conditional: the
three ids that were conditional on an OPEN reading (`torrent-swipe-cross-seed`, `discover-header-new-none`,
`discover-header-stale`) are dropped with the readings that did not survive (DECIDED 9, DECIDED 8), replaced one for
one by DECIDED 1's three card states (`torrent-card-volumes`, `torrent-card-downloading-progress`,
`torrent-card-uploading-rate`).

---

## 4. The rules that bite

Labels, never numbers: they bind to the range the steward reserves in the lot's launch brief.

| Rule | What it READS | The mutation that fells it |
| --- | --- | --- |
| **R-L16bis-a** — the landing (point 1) | a cold `/trackers` opens « Torrents »; after « Trackers » is opened, the next cold entry opens « Trackers »; storage refused opens « Torrents »; a named landing obeys — by a finger walk | first tab back to `trackers` → falls |
| **R-L16bis-b** — the selector (point 2) | the pill names the filter and is pressed; the panel lists every roster tracker in order with its count; a choice filters and pushes nothing (`history.length`); « Tous les trackers » lifts it | drop a tracker from the choices → falls; push on choice → falls |
| **R-L16bis-c** — the legend is complete (point 3) | every tone and dot value drawn on the tab has its legend entry, and no entry names a code absent from the tab | add a tone to a row without its entry → falls |
| **R-L16bis-d** — the card says it all, whole (point 4) | the name equals `Download.name` in full (no ellipsis, no clipping, at 369 px), then state, size, down / up (DECIDED 1's three states: volumes by default, the bar and the download rate while downloading, the upload rate alone while uploading), popularity, date — each from its field, each absence said | ellipsise the title → falls; draw `0` for a null popularity → falls; draw a rate outside its state → falls |
| **R-L16bis-e** — the card's taps (point 5) | poster → the medium's sheet (linked); no poster (unlinked); the body → the torrent's panel; the panel's facts equal the entry's fields | open the panel from the poster → falls |
| **R-L16bis-f** — the swipe removes only through its confirmation | the right drawer's action opens L16's confirmation; nothing is removed before « Confirmer » (the network read) | call the removal from the drawer → falls |
| **R-L16bis-g** — the switch, one write two doors (point 9) | the row's switch and Réglages' row write the same key through `updateConfigurationFile`, and each reads the other's value in the next render | write a second key → the agreement falls |
| **R-L16bis-h** — a failing tracker says why (point 9) | off by failure reads its reason; re-activating it answers the refusal, the switch stays off, the engine's words drawn under the row and staying | turn the switch on before the answer → falls; toast the refusal → falls |
| **R-L16bis-i** — the design system is reused (point 7) | the page's parts come from `ui/`: the card parts, the swipe row, the tab component, the switch, the legend; no `features/trackers` variant draws a title, a filter or a removal | re-add `torrentRemove` → falls |
| **R-L16bis-k** — Découvrir's header (point 8) | the message is in the view row, not the body; every figure it draws comes from a read (never a `fr.json` literal) | draw the literal back → falls |

**R-L16bis-j WITHDRAWN** (DECIDED 7, § 5): « one tab component, the three bars at the same height » is the conformity
train's rule, over Acquisition, Médiathèque and Trackers together — L16-bis builds none of the component and cannot
hold a rule over pages it does not touch. R-L16bis-i still reads that Trackers' own strip is the `ui` `Tabs`, once
the train has landed it.

L16's R-L16-d re-aim (the refused identifier read from `disabled`, § 2.2) is said out loud in its docstring.

---

## 5. What L16-bis does NOT draw, and the questions

**Owned elsewhere, one line each**: the cross-seed mark and « Chercher un cross-seed » — **L17** (this lot leaves
their place: the panel's actions and facts, the swipe's left side); the upload switch — **L23**; the rights on the
page — **L18**; the conformity of Système, Acquisition, Médiathèque, Réglages beyond the tab bars — **the conformity
train** (order 80), which also builds the two guard arms of § 1.9; Système's index — its own design, queued after this
one; the harness at 369 px — order 60. **Not drawn**: a push notification (L16 § 5); a mean ratio anywhere.

### DECIDED — the operator's nine rulings, 2026-09-29 (round of PR #637)

Every OPEN question of this section is now closed. Each item below quotes the operator verbatim (in « guillemets »,
`/Users/izno/dev/review-archive/l16bis/rulings-2026-09-29.md`), gives its English meaning, and states what changes
against the reading that was costed above. Nothing here is re-argued.

**DECIDED 1 (was OPEN 1) — « Réception / Envoi ».** Verbatim: « Les 2, B par défaut. Mais lors du téléchargement la
carte affiche une barre de progression du téléchargement avec le débit de download. Lors d'un upload en cours pas de
barre, mais l'affichage du débit d'upload. » Meaning: the card is neither reading A (rates) nor reading B (volumes)
alone — it is THREE named states. Default (nothing active): the received/sent VOLUMES (reading B). While
downloading: a PROGRESS BAR with the download RATE (reading A's datum, on the state reading A described). While
uploading: no bar, the upload RATE alone. **Cost**: both demands are needed, not one or the other — `downloadedBytes`
/ `uploadedBytes` (volumes) AND `downloadRate` / `uploadRate` (the stream demand on `TorrentProgress`), ≈ 1 point more
than either reading alone (phase 1); three named states join § 3, S4 (`torrent-card-volumes`,
`torrent-card-downloading-progress`, `torrent-card-uploading-rate`).

**DECIDED 2 (was OPEN 2) — an UNLINKED torrent's left.** Verbatim: « A ». Meaning: reading A — the media card's own
non-medium side, the folder icon and its word (`cardFolder`), the same card anatomy for every row; a tap opens the
panel. Reading B (no side, `CardSide` made optional) is refused. **Cost**: unchanged from reading A — none; phase 10
drops reading B's variant.

**DECIDED 3 (was OPEN 3) — the tracker row.** Verbatim: « B effectivement, design, ergonomie, geste, composant,
design system, je veux de la cohérence partout ! » Meaning: reading B — a row that opens the BOTTOM PANEL (settings,
cross-seed and upload switches, broken obligations), like the torrent card; the activation switch stays on the row.
Reading A (the fold) is refused. **Cost**: reading B's ≈ 13 points (phase 15) — a panel subject, the policy rows
re-homed in it (RULINGS 2's door unchanged), two states and two rules re-aimed.

**DECIDED 4 (was OPEN 4) — the fold chevron.** Verbatim: « A ». Meaning: reading A — the seasons' chevron (`›`, in a
pill, turning a quarter) becomes `ui/Disclosure`'s ONLY drawing; every fold takes it, including « par identifiant ».
Reading B (keep `▸` / `▾`) is refused. Held by order 79 (3)'s chevron guard (§ 1.9). **Cost**: unchanged — 1 point in
`ui/Disclosure` (phase 15); the other four sites are the conformity train's, under the guard arm.

**DECIDED 5 (was OPEN 5) — where the legend sits.** Verbatim: « Rappel, les composants sont réutiliser, si un jour je
change un composant ça change partout, c'est le design système ! A, encore une fois, 1 design système, 1 composant,
de la cohérence ! » Meaning: reading A — inline, above the list, only the codes present; the season legend's own
place, IMPORTED, never copied. Reading B (behind a « Légende » control) is refused. **Cost**: unchanged — ≈ 9 points
(phase 7), equal either way.

**DECIDED 6 (was OPEN 6) — a tracker off by FAILURE in the Trackers badge.** Verbatim: « 2 mécanismes similaires de
l'application devrait avoir le même comportement, on crée pas de nouveau composant on adapte (autant que faire ce
peux bien-sûr, si c'est trop compliqué on fait pas), mais on adapte le composant pour qu'il puisse prendre en compte
les particularités de son nouvelle usage, on ne recrée pas de composant et on tiens à jour le design système. A »
Meaning: reading A — yes, one unit per tracker, generalising the refused identifier's unit (round 9 Q1, M5) to every
failure; the existing badge mechanism is ADAPTED to the new case, never rebuilt. **Cost**: reading A's ≈ 3 points
(phase 14) — one badge term and its hold. The adaptation itself: the badge already counts one unit per
`disabled.reason: identifierRefused` tracker (§ 2.2); it is extended to count one unit per any `disabled` tracker
(`by: operator` excluded — an operator's own choice is not a fault — `by: failure` counted, whatever the `reason`),
same counting mechanism, same drawing, one more predicate.

**DECIDED 7 (was OPEN 7) — who builds the one tab component.** Verbatim: « B, là où on en as besoin c'est d'abord
l'existant ! » and, on the reference: « C'est pas les autres systèmes d'onglet qui doivent resemblé à tracker mais
tracker qui doit ressembler aux autres systèmes d'onglet, l'existant est ce qui est validé. » Meaning: reading B —
the CONFORMITY TRAIN builds the single tabs component first, on the EXISTING validated tab bars (Acquisition first,
then Médiathèque, then any other tabbed page) as its reference; it arms the guard. L16-bis's CODE WAITS for that
train, then USES the component for Trackers; Trackers conforms to the existing bars, never the reverse. Reading A
(L16-bis builds it) is refused. **Harness queue** (operator, verbatim): « #636 keychain → #635 → conformity train
(tabs first, then the 369 px width red rule) → catalogue 76 → L16-bis code → L17 »; the conformity reading and
inventory (orders 80, 77.3, 81) come BEFORE the train. **Cost**: phase 5 (which built the component) is REMOVED from
this plan — see `plan/INDEX.md`'s header and `docs/reference/frontend-architecture.md`'s entry for the dependency.

**DECIDED 8 (was OPEN 8) — Découvrir's header content.** Verbatim: « D: "n Séries et m Fims à découvrir" ». Meaning:
none of the three costed proposals (A, B, C — all three explicitly refused) — a fourth reading, the operator's own:
the message reads « n séries et m films à découvrir », beside the view-switch buttons, both numbers drawn from the
suggestions already read (no new field, no new route — the same list Découvrir already renders is counted by media
type). **No engine demand**: T4 is REMOVED from § 6's demand table and from phase 18's register — `readSuggestions`
remains an existing demand (§ 0.1 item 10), unrelated to this count. **Cost**: the move alone (phase 17, ≈ 9 points,
reading B's figure — no field declared, no seed column, no new demand); the three conditional states tied to
readings A and C (`discover-header-new-none`, `discover-header-stale`) are dropped from § 3.

**DECIDED 9 (was OPEN 9) — the swipe's cross-seed side before L17.** Verbatim: « A ». Meaning: reading A — absent;
the row travels one way until L17 adds the left drawer with its verb; nothing is drawn that does nothing. Reading B
(drawn now, disabled) is refused. **Cost**: unchanged — none; phase 11 drops reading B's drawer and its state
(`torrent-swipe-cross-seed`), dropped from § 3.

**The operator's binding principles, this round** (verbatim, DECIDED 3/5/6 above): coherence everywhere, across
design, ergonomics, gesture, component and design system; a component is REUSED, never copied — one design system,
one component, changing it changes everywhere it is used; two similar mechanisms of the app behave the same way — no
new component is created where one can be adapted (only when adapting is not reasonably possible is a new one
justified), and the design system is kept up to date with the adaptation. Written once here; applied at § 1.8 as the
lot's binding constraint, and by DECIDED 6 above as its own worked example.

---

## 6. The register rows and the demands

**Defects filed (order 57), each with where it escaped from, why, and the family repaired.** The register rows
themselves come with the lot (`BUGS.md` is not edited here).

| Defect | Escaped from | Why | Family repaired by |
| --- | --- | --- | --- |
| The Trackers page draws seven colour codes and explains none | L16's reader round and its states | no layer reads that a colour carries a word; the dot's `aria-label` satisfied the a11y pass | R-L16bis-c (every code has its legend entry) and the legend read by the rule, not by eye |
| The Trackers page redrew a title, a filter line, a removal and a tab floor that `ui/` already had; its fold chevron is not the app's | L16's phases and reader round | no layer reads design-system reuse; family: a component redrawn | the reader's design-system lens (order 79 (2)), R-L16bis-i, and the guard arms of § 1.9 in the conformity train |
| Three tab bars at two heights | L20, L22, L16 each composing the variants inline | no component, so no single place for the floor | the `ui` `Tabs`, built by the conformity train (§ 1.1, DECIDED 7) and its guard arm |
| Découvrir's header draws four `fr.json` literals as figures | L08-bis / L22's move of the surface | a figure in copy passes every guard: `check-no-french` exempts `fr.json`, no rule reads the strip | R-L16bis-k (a figure comes from a read) |

**RULINGS of L16 touched**: **3** — reversed in form (§ 1.2); **2** (the second door) kept and extended to
`enabled`; **7** (poses in place of composed rows) applied to the unlinked, the long name and the states; the others
untouched.

**PROPOSED demands, in `docs/reference/backend-demands-architecture.md`'s shape** (written here, not in that file):

| Demand | What the engine must do | Why (verbatim source) | Surface |
| --- | --- | --- | --- |
| **T1 — three more trackers** | support `v3x.club`, `draupnirr.xyz` and `digitalcore.club` as tracker providers (search, grab, ratio, cross-seed), each with the `enabled` / `cross_seed` / `economy` block `c411` has | operator, 2026-09-29 16:58: « le but est d'en ajouter … notamment v3x.club et draupnirr.xyz, mais aussi digitalcore.club » | S7's composed rows become real |
| **T2 — a failing tracker switches itself off, with its reason** | on a persistent failure (a refused credential, 401/403; an unreachable host — the circuit open past a threshold), set `enabled: false` with `disabled: { by: failure, reason, message, since }`; refuse `enabled: true` while the failure persists, answering the reason; emit an event so the roster moves live | operator, 2026-09-29 16:58: « Si un tracker fonctionne plus le toggle passe en désactivé et affiche un message avec l'erreur si j'essaye de le réactiver » — and `lacale`, switched off by hand for exactly this (§ 0.1 item 9) | S7's three states and the refusal |
| **T3 — the entry says more** | route `added_on`, `swarm_seeds`, `num_incomplete` and, per DECIDED 1 (§ 5), BOTH the rates and the volumes on `AcquisitionDownload` (a stream demand for the rates) | operator, 2026-09-29 16:4x (4) and 2026-09-29 (Q1) | S4, S5 |

T4 (Découvrir's header datum) is WITHDRAWN: DECIDED 8 (§ 5) draws the header from the suggestions already read — no
engine demand.

**`docs/reference/product-intent-map.md`**, read, not edited: DOIT-13 (`served` by L16) and DOIT-2 are unchanged in
verdict; the lot adds proofs under DOIT-9 (§ 12's card and « rien d'essentiel n'est tronqué », R-L16bis-d) and
NE-DOIT-PAS-4 / -5 (the refusal, R-L16bis-h) — proposed to the operator at the close, never written.

**L17**: its § 3.3 (the per-pair mark « on the ORIGIN row ») is re-homed by this lot to the torrent's PANEL and the
swipe's left side; L17's plan re-reads its phases 6, 9, 10 and 15 at its opening (a STOP D there, not here).
