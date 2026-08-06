# TorrentMate — Acquisition, mobile-first rebuild (2 views, 3 display modes, touch gestures)

**Date:** 2026-08-06 · **Status:** DRAFT — awaiting operator review
**Surface:** `/acquisition` (`frontend/src/pages/AcquisitionPage.tsx` + `frontend/src/components/acquisition/*`)
**Constitution:** serves §1, §2, §3, §5, §8, §11, §12, §13, §14 + DOIT-1, DOIT-9, DOIT-10, NE-DOIT-PAS-2,
NE-DOIT-PAS-4, NE-DOIT-PAS-9 — cited inline. Brand unchanged (amber / dark / Geist / DS tokens).

---

## 1. Grounding — executed evidence

Everything below was verified against the running system, not inferred.

- **Live prod review, 2026-08-06** — `tm.iznogoudatall.xyz/acquisition`, authenticated, narrow viewport,
  tabs `?tab=followed`, `?tab=file`, `?tab=apercu` inspected.
- **Interactive prototype** built at real 390 px and driven with synthetic pointer events; every claim in
  §4–§10 below was measured in the DOM (geometry, overlap, truncation), not eyeballed.
  Prototype source: `scratchpad/acquisition-prototype.html` (not part of the deliverable).
- **Code read:** `AcquisitionPage.tsx` (7 tabs), `acquisition/meta.ts` (vocabulary maps),
  `FollowedPanel.tsx`, `FileDAcquisitionPanel.tsx`, `OverviewPanel.tsx`, `MediaSearchAdd.tsx`,
  `layout/nav.ts`, `layout/AppShell.tsx` (badge sources), `controle/ATraiterList.tsx`,
  `media/MediaSheet.tsx`, `media/__tests__/constitution.test.tsx` (§11 + its exception),
  `StagingBanner.tsx`.

### 1.1 Measured defects on the current page

| # | Defect | Evidence |
|---|---|---|
| D1 | On `?tab=followed`, the first card starts at **57 % of usable height**. Stack before any content: TopBar → title « Acquisition » → 7-tab strip → « Rechercher un média à suivre » field → Tout/Séries/Films + Chercher → « ou ajouter par ID » → Séries/Films sub-tabs → cadence caption → « Filtrer par nom » field. | live prod |
| D2 | **Two tab levels and two search fields** on one view; nothing distinguishes the field that *adds* from the field that *filters*. | live prod |
| D3 | The `PageHeader` title duplicates the highlighted bottom-bar entry. §12 forbids redundancy that costs width. | `AcquisitionPage.tsx:156` |
| D4 | **7 tabs in one scrolling strip**, 3 visible; `Réglages` is two swipes away. They are not peers: rollup / daily work / surveillance / audit / config. | `meta.ts:85-93` |
| D5 | Density is inverted: `apercu` fills ~35 % of one screen; a followed card costs ~136 px for one line of information (an always-rendered « Détail par épisode » accordion bar) → 3 cards per screen. | live prod |
| D6 | **The nav badge leads nowhere**: it reads `pendingWanted` (`AppShell.tsx:127`) and lands on `apercu`, whose vocabulary is `in_flight` / `stuck` / `awaiting_resolution` / `dispatched`. Badge said 3, page said 0/0/0/59. | `AppShell.tsx` + live prod |
| D7 | No app-grade affordance: no swipe between tabs, non-sticky filters, no pull-to-refresh, primary action out of thumb reach. | live prod |

### 1.2 Root cause

The tabs are named after **data tables** (Suivis, File, Parcours), not after **questions**. The operator's three
real questions each cut across several tabs, which is why no tab is ever sufficient:

| Question | Currently answered in |
|---|---|
| « Est-ce que quelque chose m'attend ? » | Suivis + File + Vue d'ensemble |
| « Où en est ce qui est parti ? » | Parcours + Téléchargements + Vue d'ensemble |
| « Ajouter un truc à suivre » | top of Suivis |

D4 is a symptom of this, not the disease. Fixing tab *count* without fixing the axis would not help.

---

## 2. Operator arbitrations (binding)

Decided during the 2026-08-06 session. These are inputs, not proposals.

| # | Decision |
|---|---|
| A1 | **Rebuild the information architecture**, not a density pass at constant structure. |
| A2 | Primary jobs: *ça m'attend* / *où en est ce qui est parti* / *ajouter*. Surveillance & audit are second rank. |
| A3 | **Two views: « Maintenant » and « Suivis ».** In-flight and takeable merge into one urgency-ordered flow. |
| A4 | `Réglages` → `/config`. `Watcher` + `Obligations` stay on the page behind a single « Plus » entry point. |
| A5 | Card language: poster everywhere; journey strip **only** where it carries information (`en vol`, `à traiter`). |
| A6 | « Suivis » offers **three display modes** (liste / groupé / grille) behind a switcher. |
| A7 | Mode is **persisted locally** (browser / PWA), **never in the URL** — it is a preference, not a location. `?tab=` stays the only shareable state (DOIT-10). |
| A8 | Default mode: **liste**. |
| A9 | Switcher placement: **B** — pinned at the end of the filter-pill train. *(Operator choice against the recommendation; mitigated by a hard divider + solid ground so it never reads as the last pill.)* |
| A10 | Gestures: swipe between views, pull-to-refresh, swipe actions on a card — all three. |
| A11 | **No « ··· » on touch.** It exists **only on desktop**, where there is no swipe. |
| A12 | The « ··· » must offer « Voir la fiche ». |
| A13 | Tapping the **poster** goes straight to the media sheet — the most-used path, it must not go through the detail sheet. |
| A14 | For a film the verb is **« Ajouter »**, not « Suivre » — aligned across every action label. |
| A15 | Notifications sit **above** the bottom bar and carry a **close cross**. |
| A16 | Everything is validated **on staging before merge**. |
| A17 | The staging banner is **removed entirely** — frame *and* badge. The PWA already identifies staging by its icon. |

**A17 — the justification is verified, not assumed.** Deleting the in-app "you are on staging" signal is only safe
if another one survives. It does, and it is stronger:

- `frontend/index.html:40-41` swaps, at runtime on a staging host, **both** `link[rel="manifest"]` →
  `/manifest-staging.webmanifest` **and** `link[rel="apple-touch-icon"]` → `/apple-touch-icon-staging.png`.
- The staging asset set exists and is complete: `pwa-192-staging.png`, `pwa-512-staging.png`,
  `maskable-192-staging.png`, `maskable-512-staging.png`, `apple-touch-icon-staging.png`, `icon-staging.svg`.
- `lib/env.ts` already switches `BRAND_ICON` to the staging mark, and its own docstring states the intent:
  *"prod and staging are told apart by the logo alone"*.

So an **installed** staging PWA carries a different home-screen icon, and the in-app logo differs on every screen.
The banner was a third, redundant signal — and the most expensive one, since the 3 px frame costs width on all four
edges at 390 px (§12).

| # | Decision (added 2026-08-06, after A17, during execution) |
|---|---|
| A18 | **Staging may WRITE to production data — for acquisition and decisions only.** The pipeline runner and the config editor stay guarded by `require_not_staging`. |

**A18 — why, and what it costs.** `require_not_staging`'s own docstring states that prod and staging share the
same `config/`, hence the same `data_dir`, `library.db`, `acquire.db` and storage disks. Every acquisition write
therefore 403s on staging — which makes the rebuild's mutating journeys (§5 replacement confirmation, « Récupérer »,
« Retirer », the swipe actions) **impossible to validate before merge**, defeating A16.

Scope was deliberately narrowed by the operator to the two families whose worst case is a repairable row:

- **opened** — `acquisition.py` (follow create / update / delete), `acquisition_triggers.py` (5 POSTs),
  `acquisition_seasons.py` (season grab), `decisions.py` (resolve / dismiss). Worst case: a wrong follow row or an
  extra torrent in the client. Both undoable by hand.
- **still guarded** — the **pipeline runner**, because it MOVES REAL FILES on the storage disks and no database
  backup rolls that back; and the **config editor**, because the config is the one piece of state shared by both
  instances, so corrupting it breaks prod and staging in the same stroke.

**Known tension with A17, flagged to the operator and left to them.** A17 removed the staging banner on the grounds
that staging was read-only. It no longer is. The data risk did not grow — the two instances write to the *same*
rows, so confusing them changes nothing about the outcome — but a NEW hazard appeared: pressing a control « just to
see the animation », believing one is on a mock. The differing PWA icon remains the only signal, and it became quiet
exactly as the stakes rose. Re-adding the top badge (without the 3 px frame) is a one-line change if wanted.

---

## 3. Target information architecture

```
/acquisition
├── « Maintenant »                        ← default, urgency-ordered
│   ├── À récupérer            (warning)  server says something is takeable
│   ├── À traiter              (danger)   blocked, needs a decision   ← ex-"en attente de résolution"
│   │   └── crossref → Contrôle           blocked items with NO acquisition provenance
│   ├── En vol                 (info)     grabbed → … → dispatched, with journey strip
│   ├── Cherché, rien trouvé   (waiting)  §14.1 legitimate rest state
│   └── Rangé aujourd'hui      (success)
├── « Suivis »                            catalogue; 3 display modes
│   └── media sheet (§11)                 poster tap / « Voir la fiche »
├── « + »                                 add screen (search + by-ID)
└── « ⋮ »                                 Veille + Obligations (second rank)

moved out: Réglages → /config
dissolved: Vue d'ensemble → section headers carry the counts
dissolved: Parcours (tab) → journey strip on the card + « Voir le parcours » per item
```

### 3.1 Where « en attente de résolution » lands

§14.3 decides it: *« un parcours n'a pas de trou »*. An item the operator grabbed, that was ingested and then
stalled at identification, is **mid-journey**. Removing it from view would hide something they started.

- Blocked items **with an acquisition provenance row** → section **« À traiter »** in « Maintenant », between
  « À récupérer » and « En vol » (what is stopped and waiting on me comes before what advances alone).
- Blocked items **without** one (manual staging drop) → **no card here**, they are not acquisitions. But they are
  not silenced either (§méthode: never under-count what needs attention): a discreet crossref line
  « N autres médias à traiter ne viennent pas d'une acquisition → Contrôle ».
- **Vocabulary is reused, not invented**: `/controle` already owns the panel « À traiter » with a « Résoudre → »
  link (`ATraiterList.tsx`). Same words here.

### 3.2 Badge semantics (fixes D6)

The nav badge and the « Maintenant » tab badge both count **what awaits the operator**:
`à récupérer + à traiter`. An in-flight item awaits nothing from them. This replaces `pendingWanted`.

---

## 4. View « Maintenant »

Sections, each with a coloured pip and a count in its header (this is what dissolves `OverviewPanel`: a number
that opens nothing is a dead end — NE-DOIT-PAS-9; a section header *is* its own drill-down).

**Card anatomy** — one `<div class="card">` hosting **two distinct targets** (a button inside a button is invalid
HTML, and A13 requires two destinations):

```
┌────────────────────────────────────────────┐
│ [poster] Titre                       [···] │  poster → media sheet (§11)
│          S02E05 · 1080p · 42 sources       │  rest   → detail sheet     ··· desktop only (A11)
│          ● À récupérer                     │
├────────────────────────────────────────────┤  ← separator, full width
│  ●───────●───────○───────○───────○         │  journey strip: OWN LINE
│ pris  téléch. ingéré  scrapé  rangé        │
└────────────────────────────────────────────┘
│ « Résoudre → »  (full width, « à traiter » only)
```

- The **journey strip renders only** for `en vol` and `à traiter`; on a takeable item it would say nothing.
- **Blocked is its own station state** — neither `now` (it is not moving) nor pending (it was reached and stayed).
  §14.3: an unreached step is never painted as if nothing happened.
- On an « à traiter » card the **blocking reason must not truncate** — it is what the operator decides on. It
  wraps to two lines and the action drops to a full-width row below the strip (§12: essential information does not
  share its line).

---

## 5. View « Suivis »

### 5.1 What disappears

- **Séries / Films sub-tabs** → filter pills carrying their counts. One tab level removed.
- **The second search field** → only the *filter* remains, and it is sticky. Adding lives on the `+`.
- **The always-rendered « Détail par épisode » accordion** → replaced by the detail sheet (tap the card).
  A followed row goes from **~136 px to ~66 px**.

### 5.2 The three modes (A6)

| Mode | For | Composition |
|---|---|---|
| **Liste** (default) | scanning | one card per follow, urgency first, `à jour` last; status chip on each row |
| **Groupé** | sorting | same card, status moves to the section header and leaves the row (§12: no repetition) |
| **Grille** | recognising | 3-up poster grid |

**Grid badge rule** — a colour alone is mute, which would contradict « une couleur par statut » (that rule presumes
the status is *readable*). The badge therefore carries a **number**: `Silo ①` amber = 1 episode takeable,
`Batman ㉒` = 22 waiting, `?` for `non_verifie`. **A follow with nothing to do carries no badge at all** — absence
is the signal. A paused follow renders with a dimmed poster.

**Switcher (A9)** — pinned at the end of the pill train, preceded by a **1 px divider on solid ground**, never a
gradient fade: the pills filter *data*, the switcher changes *presentation*, and the two natures must not read as
one train. Persisted in `localStorage`, absent from the URL (A7).

### 5.3 Detail sheet (tap a card)

- Title, meta, **the one offered action** if any (« Récupérer maintenant »), legend, season matrix, then the
  **six secondary actions at the bottom**. Reason: the card was tapped to *see state*; opening on seven buttons
  buries it — and it keeps « Retirer » away from the arriving thumb.
- **Season matrix** as episode pills, not stacked rows: a 15-episode season occupies 3 lines instead of 15.
- **Large catalogues** (measured on a 21-season, 390-episode follow): most recent season **first**; a complete
  season is **collapsed** (`<details>`, its header suffices to say "nothing here"); an incomplete one is **open**
  and carries a « N manquant(s) » chip. The **legend sits above the matrix**, not below — under 390 episodes it
  would be invisible exactly when needed.

### 5.4 One derivation per question (§13)

The card fraction, the sheet header and every season header answer *the same* question and therefore **read the
same computation**: `owned = count(en_mediatheque)`, `aired = count(state !== 'annonce')`. An announced episode is
not aired and can never be missing from the denominator. The prototype initially disagreed with itself
(`24/25` on the card vs `23/25` summed) — that must be impossible by construction, not by care.

---

## 6. Media sheet (§11)

Reached by **poster tap** (A13) and by **« Voir la fiche »** in the « ··· » menu and the detail sheet (A12).
It is a **screen with its own back**, not a sheet: it is a destination, it is URL-shareable, and it is the end of
the most-used path.

Sections mirror the existing `MediaSheet.tsx`: hero (poster + title + year + kind + status + rating), genres,
**Synopsis**, **Médiathèque** (Saison / Épisodes / Possédés / Complétude, with a completion bar; the table scrolls
in its own container so the page never scrolls sideways), **Informations** (Créateur/Réalisateur, follow state,
next search, provider ids), and a link back to the follow's actions.

**§11 exception is enforced** — `constitution.test.tsx` forbids a dead link for an unidentified media. When no
provider id resolved: the poster is **not a button at all** (not a disabled one), « Voir la fiche » is **absent**
from the menu, and a line says why. A greyed button would be the same broken promise.

Missing provider data renders « inconnu », never a mute dash (§14.3: an unknown step is « inconnue », never
« pas faite »).

---

## 7. Add flow (`+`)

A **full screen**, not a low sheet: the keyboard eats half the phone.

- **Submit on validation only**, never per keystroke (this is the current, deliberate behaviour —
  `MediaSearchAdd.tsx:174-177`). Skeletons during the call.
- **Vertical result list, not the current horizontal rail.** A rail shows three posters and hides year, kind and
  overview — which is precisely what separates two homonyms. §12: width is the scarce resource; a rail spends it
  on emptiness. Each row: poster, title, `2024 · Film · TMDB`, two lines of overview, action.
- **The provider total is shown** — « 6 résultats affichés sur 13 trouvés ». Ships today and the reason is
  recorded in-code: five results out of eighty-one otherwise reads as "that's all there is" (§8).
- **Already-known state is on the button, not beside it**: `✓ Suivi` / `✓ Ajouté`, disabled. The former
  « déjà dans vos suivis » tag is **removed** — pure redundancy (§12). **« déjà en médiathèque » stays**: it speaks
  about the disks, not the list, and it is what explains why the button asks instead of acting.
- **§5 replacement confirmation** — a film already owned: button reads « Ajouter… », and confirming states that the
  acquisition will **replace** the version in place.
- **Empty result never blanks the screen** (§3): it names what was searched and offers the by-ID fallback.
- **Add-by-ID** validates *before* sending, and the disabled button **says why**: `12e34` is rejected
  (`Number()` coerces scientific notation — the ticket-250 trap), IMDB expects `tt1234567`. An unresolved TVDB id
  is **admitted out loud**: episode detection stays unavailable — never a silently inert follow.
- **After adding:** the button flips, a footer bar reports « N média(s) ajouté(s) · Voir mes suivis → » (so several
  can be added in a row), the created follow is **sorted to the top** of « Suivis » with a « Nouveau » chip, and a
  toast names what happens next. Initial state is **`non_verifie`, not `en_attente`** — §14.1 separates
  "searched, found nothing" (a legitimate rest) from "not looked at yet" (not one). The fraction reads « — », never
  `0/0`, which would read as an empty series.

---

## 8. Gestures (A10) and their arbitration

| Gesture | Behaviour | Conflict handled |
|---|---|---|
| Horizontal swipe | switches Maintenant ⇄ Suivis | **30 px dead zone on the left edge** — iOS reserves it for "back" |
| Pull-to-refresh | refetches the view | `overscroll-behavior-y: contain` on the scroller, or the browser's own pull-to-refresh reloads the whole page |
| Card swipe | right → Récupérer · left → Pause / Retirer | see below |

**Two horizontal gestures compete for the same surface.** Arbitration: **a gesture that starts on a card belongs
to the card**; anywhere else it changes view. Consequence to accept: in card-dense areas, view switching happens
mostly through the tabs. This was surfaced by the prototype and cannot be judged from a mockup — **it is the first
thing to validate on staging (A16).**

**Discoverability without the « ··· » (A11):** every action also lives in the **detail sheet**, reachable by tap.
The swipe is a shortcut to what the sheet already contains, never the only path. On desktop the « ··· » returns and
opens **the same action block** — one list in the code, so there can never be two truths about what a follow allows.

---

## 9. Vocabulary — film vs série (A14)

One does not *follow* a film: nothing accrues, and §5 removes it from the list once acquired.

| | Film | Série |
|---|---|---|
| add | **Ajouter** / **✓ Ajouté** | Suivre / ✓ Suivi |
| suspend | **Ne plus chercher** / **Chercher à nouveau** | Mettre en pause / Réactiver |
| remove | **Retirer de la liste** | Retirer le suivi |
| suspended state | **Recherche arrêtée** | En pause |
| swipe (84 px) | **Ne plus chercher** · Retirer | Pause · Retirer |

Extends the existing `FOLLOW_STATUS_LABEL_MOVIE` pattern in `meta.ts` — same mechanism, more entries. The tag
« déjà dans vos suivis » named a *place*, not the action; it is removed for redundancy (§7), not for wording.

**§5 is finally stated**: a non-acquired film's sheet says « Une fois acquis, ce film quittera automatiquement
votre liste. » No label said it — the operator saw films vanish, which reads as loss rather than rule.

**Removal is confirmed**, and the text differs by nature: a series is *deactivated and reactivable*, a film
*leaves the list* and returns via a search.

---

## 10. Notifications (A15)

Anchored to a **zero-height dock placed just above the bottom bar**, in flow — not positioned at a fixed distance
from the screen bottom. The old `bottom: 84px` was a magic number calibrated on desktop; on iPhone the bar grows by
`env(safe-area-inset-bottom)` (~34 px) and the toast slid underneath it. The dock makes it correct by construction
at any bar height. It also fixed a second, pre-existing overlap: toast and FAB boxes crossed by ~47 px.

The dock is `position: relative` **without** `z-index`, so it creates no stacking context: the toast (40) stays
above the full screens (35) while the FAB (20) correctly passes under them.

Close **cross**, and auto-dismiss lengthened 2.2 s → 5 s (two-line messages were unreadable in 2.2 s). The cross is
the real control; nobody is forced to wait.

---

## 11. Transverse layout rules

Five defects of the same family showed up during prototyping. They become rules, not five patches.

| R | Rule | The defect it prevents |
|---|---|---|
| R1 | **A control that belongs to a card lives inside the card, in flow.** | The « ··· » was `position: absolute` on the swipe wrapper while the *card* translates: it stayed put and landed on top of « Retirer ». |
| R2 | **A full-width element gets its own line**, never a sibling of the title row in a `row` flex. | The journey strip was squeezed into a narrow column; its labels overlapped. |
| R3 | **The title line accepts nothing but the title** (§12). Everything qualifying a media goes on the meta line — the only one that wraps. | The « Nouveau » chip was clipped on a long title. |
| R4 | **Nothing is positioned by a distance from the screen edge**; anchor to what it belongs to. | The toast under the bottom bar on iOS. |
| R5 | **A class used on a `<span>` declares its `display`**, and no class name is reused across two roles. | `.bar` inline → the progress bar rendered as a huge blob; `.act.grab` collided with the sheet handle `.grab` (36×4 px) → the swipe action was painted invisible. |

**R6 — no dangling reference.** `takeable` / `blocked` / `inflight` reference a follow **by id**. Removing a follow
must cut its row **everywhere it is carried**, and renderers must skip an orphan row rather than throw. In the
prototype this crashed `renderNow()` mid-render, so the follows list was never re-rendered and every « ··· »
pointed at nothing — a single removal silently broke the whole page. This is exactly the hole §14.3 forbids.

**R7 — grid tracks use `minmax(0, 1fr)`, not `1fr`.** `1fr` means `minmax(auto, 1fr)`, whose `auto` floor is the
content's intrinsic size: one long title pushed its column past its share and collapsed the grid.

**R8 — an author `display` rule beats `[hidden]`.** Any class with a `display` must add `&[hidden] { display: none }`.

---

## 12. Delivery constraints

- **A16 — staging validation before merge.** Every phase is deployed to `tm-staging.iznogoudatall.xyz` and
  validated there against real data before the PR is merged. Proofs at 390 px (§12's opposable clause: *« une
  maquette validée uniquement sur grand écran ne vaut rien »*).
- **A17 — delete the staging banner.** Scope, verified by grep:
  - remove `frontend/src/components/StagingBanner.tsx` and `StagingBanner.test.tsx`;
  - remove its **two** render sites — `App.tsx:62` (host-based global overlay) and `Config.tsx:83`;
  - **keep `lib/env.ts:isStaging()`** — still used by `BRAND_ICON`, and its docstring must drop the
    `{@link StagingBanner}` reference in the same commit.

  **`/config` nuance, checked:** that render site is *not* host-based — it is gated on
  `useConfigEditor`'s `role === "staging"` returned by the API. Removing the banner there loses nothing, because
  the page renders a « Mode lecture seule — les modifications sont désactivées » alert immediately below
  (`Config.tsx:84-89`) which carries the operative message. **To confirm during staging validation:** that this
  alert does render on staging (i.e. `readOnly` is true there) — if it does not, the read-only state must be
  surfaced before the banner is dropped from that page.
- **Version bump on the PR** (operator standing rule), `pyproject.toml` + `/api/version` verified.
- **`make openapi`** if any FastAPI route/signature/docstring moves — CI fails on drift.
- Frontend gates: `eslint` **and** `tsc -b --noEmit` **and** `vitest`, all three before commit.

---

## 13. Test plan

Beyond unit coverage, these are the assertions that encode the decisions above:

1. §12 — at 390 px, no route scrolls horizontally; the title line never shares with a chip (R3).
2. §13 — card fraction ≡ sheet header ≡ Σ season headers, property-checked over generated catalogues (§5.4).
3. §11 — an unidentified media renders **no** poster button and **no** « Voir la fiche » (extends
   `constitution.test.tsx`; the existing WIRED_SURFACES array gains the new surfaces).
4. §14.3 — removing a follow leaves **zero** row referencing it in takeable / blocked / inflight (R6).
5. §5 — an already-owned film cannot be followed without passing the replacement confirmation.
6. Badge — nav badge ≡ `à récupérer + à traiter`, and the landing view shows exactly those items (fixes D6).
7. A7 — the display mode is absent from the URL and survives a reload.
8. Vocabulary — every action label on a `movie` follow comes from the film column of §9 (exhaustive map test,
   `Record<FollowStatus, …>` style, so a new state breaks `tsc` rather than printing a slug).
9. A17 — no module imports `StagingBanner` any more, and `isStaging()` still resolves `BRAND_ICON` to the staging
   mark (the surviving signal must be proven alive by the same commit that removes the redundant one).

---

## 14. Out of scope / open items

- **Renaming the « Suivis » tab.** The film verb is now « Ajouter » while the destination is still called
  « Suivis ». Defensible (it names a place), but the operator may want to revisit — **their call**.
- **Watcher / Obligations content** is moved behind « Plus » unchanged; redesigning those two panels is not in
  this scope.
- **`/config` reception of the ranking editor** — this spec removes the tab; the receiving surface's layout is a
  `/config` concern.
- **A global « Parcours » list.** Journeys become per-item. The operator did not object when this was flagged,
  but no global list is specified. If one is wanted, it is a separate item.
- **Desktop layout beyond "stays functional"** — §12 makes the phone the design origin; wide-screen refinements
  (multi-column grid, denser tables) are deliberately not specified here.
