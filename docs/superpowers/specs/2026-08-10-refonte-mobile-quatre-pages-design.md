# TorrentMate — mobile-first rebuild of the whole shell (design)

**Date:** 2026-08-10 · **Status:** approved — the maquette is the engraved design reference (§15
of the constitution)
**Base:** `origin/main` @ `720d2536`, version `0.89.0`
**Surfaces:** the entire authenticated app except `/config` — `/acquisition` (third view added),
a NEW `/mediatheque`, a NEW `/arrivees` replacing `/medias` + `/pipeline`, and `/systeme` in
reception only. Plus a new TMDB suggestion engine and a destructive delete path.
**Constitution:** `docs/reference/product-intent.md` — §3, §5, §8, §9, §11, §12, §13, §14 +
DOIT-1, DOIT-2, DOIT-7, DOIT-9, DOIT-10, DOIT-11, NE-DOIT-PAS-1, NE-DOIT-PAS-4, NE-DOIT-PAS-6,
NE-DOIT-PAS-8, NE-DOIT-PAS-9. Cited inline.
**Interactive maquette (the contract):** `frontend/maquette/refonte.html`, committed, with its
harness under `frontend/maquette/harness/` and its rule set in `frontend/maquette/regions.json`
— see §7.1. It is the **binding visual reference** for this rebuild and for every later
evolution of the interface.

---

## 1. Why this exists

`/acquisition` was rebuilt mobile-first and shipped (PR #422, #423). The other three surfaces
were not, and the audit that opened this mission
(`docs/analysis/2026-08-10-acquisition-refonte-analysis-and-transfer.md`) found that the problem
is not styling:

| Job the operator actually comes to do  | Where it lives today                                 | Verdict                  |
| -------------------------------------- | ---------------------------------------------------- | ------------------------ |
| Something awaits me / my follows / add | `/acquisition`                                       | already rebuilt          |
| Did what I added by hand get through?  | `/pipeline` **and** `/medias`                        | 2 surfaces, no narrative |
| Unblock what is stuck                  | `/controle` **and** `/medias` **and** `/acquisition` | 3 surfaces               |
| Browse / search my library             | —                                                    | **does not exist**       |
| Check everything is healthy            | `/controle` **and** `/systeme`                       | 2 surfaces               |
| Be offered something to watch          | —                                                    | **does not exist**       |

Two of the six jobs have no surface at all, and `/medias` lies about its name: it serves
`GET /api/staging/media`, i.e. the staging area, not the library.

**Measured, not assumed:** `personalscraper/web/routes/media.py` serves only the media sheet
(`/media/{provider}/{provider_id}`); `/search` and `/lookup` query providers, not the disks.
No route lists what the operator owns.

---

## 2. Operator arbitrations (binding inputs, not proposals)

Decided during the 2026-08-10 brainstorm. These override the maquette where they conflict.

| #   | Decision                                                                                                                                                                                                                                                                                                                                                              |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1  | **Re-cut the information architecture first**, not a density pass at constant structure.                                                                                                                                                                                                                                                                              |
| B2  | Page map **C**: `Acquisition` · `Médiathèque` · `Arrivées` · `Système` — four bottom-bar entries.                                                                                                                                                                                                                                                                     |
| B3  | The suggestion engine is the **third view of Acquisition**, not its own page. Cost accepted: Acquisition stops being only « what awaits me ».                                                                                                                                                                                                                         |
| B4  | **One single mission** — IA rebuild _and_ suggestion engine in the same spec and PR series.                                                                                                                                                                                                                                                                           |
| B5  | **`Système` enters in reception only**: it receives health, runs and pipeline controls, and takes the 4th bar slot, but its own mobile redesign is deferred.                                                                                                                                                                                                          |
| B6  | Suggestions are built on **TMDB only** — for films _and_ series. TVDB has no recommendation API and no account API. TMDB proposes, **TVDB still identifies**: a series suggestion is resolved TMDB → TVDB before the follow is created.                                                                                                                               |
| B7  | Suggestion basis: **library + TMDB account**. Personalised recommendations from the operator's ratings, crossed with similars of what they own. Exclusions, in order: owned, rated (= seen), already followed, manually dismissed.                                                                                                                                    |
| B8  | **Deleting a media asks at confirmation time** what it means for the follow — stop the follow, or keep it (the operator may be deleting to re-acquire a better version). No permanent exclusion list.                                                                                                                                                                 |
| B9  | Delete is **dry-run-first**; the dry-run stays mandatory until the operator validates it tells the truth. Removing it later is an explicit act.                                                                                                                                                                                                                       |
| B10 | Delete is also reachable **from the poster grid**, presented without degrading the grid.                                                                                                                                                                                                                                                                              |
| B11 | **Method A** — one global interactive maquette at 390 px is arbitrated first; the shared language is then extracted from what the maquette proved necessary; pages are delivered against it with measured parity.                                                                                                                                                     |
| B12 | **Nothing reaches production until everything is validated together.** The six PRs target an integration branch; `staging` tracks it; `main` (and therefore prod) is touched once, at the end. **Non-negotiable.**                                                                                                                                                    |
| B13 | Labels: Acquisition's first view is **« En cours »** (was « Maintenant »); the Médiathèque's first lens is **« Médias »** (was « Catégories »); the middle section of Arrivées is **« Ça avance »** — renamed because « En cours » would otherwise have named three different populations (the Acquisition tab, that section, and a Suivis group), which §13 forbids. |
| B14 | The third page is named **« Arrivées »**, and it absorbs both `/medias` and `/pipeline`.                                                                                                                                                                                                                                                                              |
| B15 | **Pixel-perfect is the bar.** Not « close ». The maquette may be reworked as much as needed to make it implementable, but what ships must be provably identical to it.                                                                                                                                                                                                |

---

## 3. Target information architecture

```
Acquisition   [ En cours | Suivis | Découvrir ]                 (+) (⋮)
  En cours    what awaits me — 5 urgency sections               unchanged
  Suivis      my catalogue — liste / groupé / grille            unchanged
  Découvrir   what I am offered — TMDB pool                     NEW
  nav badge   counts « En cours » ONLY (§13, one derivation)

Médiathèque   [ Médias | Incomplets | Récents ]                 NEW PAGE
  Médias      browse by category, grid or list, server-paged
  Incomplets  series with holes, sorted by what is missing most
  Récents     first seen by the index (labelled truthfully)
  search      one field, all three lenses
  delete      swipe (list) · long-press (grid) · selection mode (bulk)

Arrivées      ● Ça coince (n) · ● Ça avance (n) · ● Rangé aujourd'hui (n)
  everything entering, followed or dropped by hand into qBittorrent
  live scrape strip · crossref to Acquisition
  resolution opens as a SCREEN                                  replaces /medias + /pipeline

Système       health · disks · index · providers · schedulers
              pipeline controls · runs · run detail (?run=<uid>)
              RECEPTION ONLY — no mobile redesign in this mission

Config        untouched, drawer only
```

**Dissolved:** `/controle` as a page — « À traiter » and the scrape feed go to Arrivées, health
and pipeline controls go to Système. **Demoted:** `/pipeline` as a bar entry — its real job
(« did my manual qBittorrent adds get through? ») is served by Arrivées; run detail becomes a
destination in Système.

**Legacy routes** keep working: `/medias`, `/pipeline`, `/controle` and `/` redirect with
`{ replace: true }` (existing `LegacyRedirect`), preserving query params. `?run=<uid>` on
`/pipeline` redirects to `/systeme?run=<uid>`.

---

## 4. The shared language

### 4.1 The scope rename

`styles/ps/maquette-acquisition.css` → `styles/ps/app-surface.css`; the scope class `.mq`
becomes `.tm`. **No declaration changes.** `.tm .seg` has the same specificity as `.mq .seg`,
so Acquisition renders byte-identical. The scope stays a per-page class so an unconverted page
cannot be contaminated mid-flight.

**Gate:** the parity harness is re-run on Acquisition after the rename and must still report
zero divergence. A moved pixel means the rename is refused, not "explained".

### 4.2 Primitives extracted to `components/ds/`

Only what at least two surfaces need. Everything else stays where it is — speculative
abstraction is how the previous rebuild produced a monster.

| Primitive       | Contents                                                                                                        | Consumers                                                      |
| --------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `ViewTabs`      | pinned `.viewtabs` = equal-width `.seg` + optional detached `.more` + `.n` badge; publishes its measured height | Acquisition (3), Médiathèque (3), Arrivées (0 — sections only) |
| `FilterBar`     | `.filters` = `.search` + `.pillbar` (`.pillscroll` `touch-action: pan-x` + `.vswwrap` divider + `.vsw`)         | Médiathèque, Suivis                                            |
| `MediaCard`     | `AcquisitionCard` moved to `ds/`, unchanged                                                                     | all four pages                                                 |
| `PosterTile`    | `.tile` + `.p` + numeric badge + `.nm`/`.fr`, dimmed variant                                                    | Médiathèque, Découvrir, Suivis                                 |
| `SectionHeader` | pip + label + count, itself the drill-down                                                                      | Arrivées, En cours                                             |
| `SheetShell`    | `.sheetgrab`, `.sheettitle`, `.sheetmeta`, `.sheetacts(.secondary)`, `.sact`, `.fichebar`                       | everywhere                                                     |
| `PullToRefresh` | the touch logic currently inline in `AcquisitionPage` + `.ptr` chrome                                           | all four pages                                                 |
| `SwipeActions`  | moved to `ds/`, unchanged                                                                                       | Médiathèque, Arrivées, Suivis                                  |

**Not extracted:** the urgency logic of « En cours », the journey strip, the season matrix.
One surface each.

### 4.3 §12 becomes structural

`MediaCard` enforces the engraved rule by construction: title alone on line 1, qualifiers on
the wrapping meta line, a blocking reason that never truncates (`line-clamp-2`), full-width
elements on their own line, and a poster that is a button **only** when a sheet exists — an
unidentified media gets no button at all, never a disabled one (§11).

**Regression already caught by the maquette:** replacing a flex body with a block `<button>`
made `<span class="t">` and `<span class="m">` inline again, and the title went back to sharing
its line. This is rule R5 (_a class on a `<span>` declares its `display`_). The primitive must
pin it with a test that asserts `title.bottom <= meta.top`.

### 4.4 `PageHeader` leaves mobile

An `h1` repeating the highlighted bottom tab costs a full line for zero information (defect D3
of the Acquisition audit). The title stays in the DOM as `sr-only` — accessibility is not paid
for in pixels — and becomes visible again from `md`.

---

## 5. New surfaces

### 5.1 Médiathèque — a read-model, never a scan

`GET /api/library/items`, reading `library.db` only. Same discipline as `insights/`: no
filesystem walk, no write, ever.

**Schema reality, verified against the live DB — this is not the initial migration:**

- `media_item` no longer has `tmdb_id` / `imdb_id` / `tvdb_id`. The provider-ids migration
  replaced them with **`external_ids_json`**, shaped
  `{"tmdb": {"series_id": "...", "episode_id": null}, "tvdb": {...}, "imdb": {...}}`.
- `series_id` is a **string, sometimes slug-suffixed** (`"91989-au-bout-c-est-la-mer"`).
  Every join must normalise to the leading integer.
- Coverage on the live library: **1 842 / 1 861 carry a TMDB id, 716 carry a TVDB id.**
  The 19 without a TMDB id cannot be excluded by identity — see §5.2.

**Query surface:** filter by category / kind / completeness, sort by title or `date_created`,
server-side pagination (page of 24). Each row carries its provider ids so the tile links to the
existing `/media/:provider/:id` sheet — the sheet is not rebuilt.

**Honesty clauses:**

- « Récents » is derived from `media_item.date_created`, which is _when the index first saw the
  media_, not when it landed on disk. **The label says exactly that** (§13: no displayed state
  is a silent approximation).
- Completeness reads `season.episode_count`, which is known to drift (hence the
  `fix-season-counts` maintenance action). A season whose count is unknown renders **`?`**,
  never an invented `12/12`.
- The count line always shows _displayed / total_ — §8, never hide what is missing.

**Load:** this is the largest list in the app — 1 861 items, not 24 staging rows. Three
non-negotiables: server-side pagination (never « fetch all then filter in JS », which is what
`/medias` does today), `posterThumb()` on every tile (a full-size TVDB poster weighs ~370 KB),
and server-resolved filtering. Infinite scroll is legitimate here **because the source is
local**: one more page costs no provider quota. A failed page load says so and offers retry
(§8, DOIT-2) — a list that stops silently reads as « there is nothing more », which is a lie.

### 5.2 Découvrir — TMDB proposes, TVDB identifies

**Measured against the live API and the live library, 2026-08-10** (not extrapolated):

- `/recommendations`, `/similar`, `/discover` return **20 results per page, invariably**. The
  page size is not configurable. Fight Club: 333 recommendations over 17 pages; Friends: 1 052
  over 53 pages.
- Running the engine for real: **16 seeds → 32 API calls → 640 raw titles → 503 survivors**
  after excluding the 1 832 owned TMDB ids. 21 % rejection.

**Consequence, and it is the design:** 32 calls yield 500 suggestions, so the constraint was
never the batch size — it is _when_ the calls happen. A background pass (same shape as the
watcher) pages TMDB at a civil pace, filters, and writes survivors to a local pool. The screen
reads the pool. Scrolling therefore costs nothing, and batches of 30 are free — without ever
bursting a dependency (**NE-DOIT-PAS-8**).

**Seed selection matters and must not be naive.** The 16 seeds used in the measurement were the
16 most recently added items — all recent super-hero films — and the output leaned heavily that
way. Seeds must be diverse and rating-weighted, not « the last N added ».

**Exclusions:** owned (join on normalised `external_ids_json.$.tmdb.series_id`), rated on TMDB
(= seen), already followed, manually dismissed. The **19 items with no TMDB id** get a
title+year fallback, and the fallback is _stated_, not silent.

**Card interaction (B10-adjacent, operator-specified):**

- poster → the media sheet (§11);
- rest of the card → bottom sheet, same grammar as Suivis: **« Suivre »** (series) /
  **« Ajouter »** (film) per §9, plus « Voir la fiche », plus « Pas intéressé »;
- swipe **either direction** → dismissed, with **« Annuler »** in the toast. A gesture-triggered
  action must be reversible: a sliding thumb errs more than a tapping finger.

**Three formats, one grammar (R32).** A switcher — the same control Suivis already uses — offers
list, posters and **slide cards**. The formats change how much of the poster you see, never what
the gestures mean and never which actions exist:

| Format | Layout | Poster taps | Body taps | Swipe |
|---|---|---|---|---|
| list | full-width rows | media sheet | bottom sheet | either direction dismisses |
| posters | two-column grid | media sheet | bottom sheet | — |
| slide cards | one card filling the surface, the next ones stacked behind | the whole card opens the media sheet | — | **left « Passer »** decides nothing and the card comes round again; **right « Pas intéressé »** removes it, with an undo |

No format carries actions of its own: « Suivre » / « Ajouter » / « Pas intéressé » live in the
bottom sheet, reached the same way everywhere. A drag born on a card belongs to the card — without
that claim the page-swipe handler fires too and navigates away mid-gesture.

**The pile is animated, never rebuilt (R33).** Advancing moves the existing nodes: the outgoing
card flies out, the ones behind change depth and their transition carries them forward, and a new
card is inserted at the back, rising from under the deck. Rebuilding the markup replaces every
node, and a replaced node cannot transition — the pile then cuts instead of moving. This must be
checked **mid-flight**, not at rest: a check at the destination cannot tell a pile that moved from
a pile that was rebuilt.

**Slide cards carry their own poster source (R34).** The thumbnail poster is right at thumbnail
size and mush once blown up to fill a phone screen. The format uses posters sized for the surface
they fill, for the suggestions actually served — the weight follows what is reachable, not the
whole catalogue.

**Degraded mode:** with no TMDB account connected, the view does not blank. It serves similars
of the library and **says what is missing and why** (§8, DOIT-7). The account token is stored
with the other secrets — never in a document, never in a log.

### 5.3 Delete — the most dangerous gesture in the app

Joins the existing destructive action catalogue (`web/maintenance/registry.py`), with its
pipeline lock and its append-only journal (`indexer/destructive_journal`).

**Protocol:**

1. **Mandatory dry-run** — enumerates video files + size, metadata (NFO, artwork), library rows,
   Plex entry. Nothing is touched.
2. **Confirmation states the real consequence** — when the media is followed: « this series is
   followed: without action, these episodes will be re-downloaded at the next search » — and
   makes the operator choose on the spot: _delete and stop the follow_ / _delete and keep it_
   (B8).
3. **Identity by provider-ID**, never by title (NE-DOIT-PAS-6).
4. The dry-run stays mandatory until the operator validates it tells the truth (B9).

**Three reachable paths, none of which degrades the poster grid (B10):**

| Path                                   | Where     | Cost at rest                                  |
| -------------------------------------- | --------- | --------------------------------------------- |
| swipe left on a row                    | list mode | none                                          |
| **long-press on a poster**             | grid mode | **none** — no chrome at all                   |
| **« Sélectionner »** in the count line | grid mode | one text button in a line that already exists |

Selection mode turns delete into a **bulk** action, which is the real need in a 1 861-item
library, and it is what makes the long-press discoverable. **A simple tap still opens the
sheet** — the most frequent path is never sacrificed to a rare action (NE-DOIT-PAS-9).

**Open and honest:** Plex deletion is **not promised** by this spec. `api/plex.py` only knows
how to refresh. Which of the two routes works on this server — targeted refresh that drops the
item, or direct `DELETE /library/metadata/{ratingKey}` — is a **verification step of the plan**,
not an assertion. See §11.

---

### 5.4 Two verbs must never share a screen

The search surface is reached from two places that mean opposite things, and the maquette
originally sent both to the same screen — a fault of intent found by the operator:

| Reached from             | Intent                        | Verb                          | Effect                                                                                                                                    |
| ------------------------ | ----------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| the `+` on Acquisition   | **surveiller** a media        | « Suivre » / « Ajouter » (§9) | creates a follow; an owned film passes the replacement confirmation (DOIT-8)                                                              |
| a resolution in Arrivées | **identifier** a stuck folder | « Associer »                  | binds the media so the pipeline resumes its scrape. **No follow is created** — an already-owned media is the expected case, not a warning |

The verb follows the **context that opened the screen**, and the screen states its intent in a
banner. Proposing « add to follows » where the operator wanted to unblock a folder is not a
labelling detail: it performs the wrong action.

### 5.5 The per-series quality profile — what the backend actually holds

Verified in `acquire/desired.py`. `QualityProfile` has **four fields, and no others**:

| Field                      | Meaning                                                         | Default                                                          |
| -------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------- |
| `min_resolution`           | a **floor**, not a multi-select — everything below is dropped   | `None` (no floor)                                                |
| `required_audio`           | tiers `{VF, VOSTFR, VO}`; a release must carry **at least one** | empty (no language filter)                                       |
| `require_known_resolution` | fail closed on an unparseable resolution                        | `False` (fail open — usually a REMUX naming gap)                 |
| `exclude_3d`               | drop SBS / Over-Under encodes                                   | **`True`** — the one non-permissive default, a correctness floor |

**What is NOT per-series**: the ranking weights (resolution, codec, format, audio, language,
source, seeders, size, provider) live in `config/ranking.json5` and already have an editor at
`/config?tab=classement`. **The profile FILTERS (it eliminates); the ranking ORDERS (it breaks
ties among survivors).** Losing that distinction is how an editor ends up promising settings the
engine never reads.

**Backend gap to close, and it is bounded.** The profile is _read_ at grab time
(`_pass_gates.resolve_effective_profile` → `_filters`), but `UpdateFollowRequest` deliberately
excludes `quality_profile` with the comment « do NOT expose an editor until the backend consumes
it ». Shipping this screen therefore requires **opening the write path**: add the field to the
PATCH body, validate the four keys, persist to `quality_profile_json`, `make openapi`. Nothing
else — the read path, the overlay precedence and the hard filter already exist and are tested.

**Out of scope**: `SourceCriteria` (the per-item override) is decode-only with no live producer
(« no live producer until Follow D4 »). The maquette does not draw it.

### 5.6 The media sheet — one template, and it is reached from everywhere

The media sheet is the surface most often reached and the one that most easily grows two faces.
Four rules make it single, each with a rule in `regions.json` → `$adversarialReview`.

**The visual is the top of the sheet (R26).** A wide TMDB backdrop occupies the top band at
full width, sharp, in the flow, and melts into the body colour through a closing gradient; the
title sits under it, overlapping the melt's lower edge. There is no thumbnail beside the title —
the visual already is the anchor. Three precautions carry it: the gradient closes on a solid
colour _before_ the text, opacity and saturation are capped, and no information lives in the
image. A medium with no backdrop degrades to a short muted field — a declared difference, and
the only one. Verified in **both themes**: a light-theme-only regression already happened here
when a deletion left an orphan selector.

**One back control, in the flow (R28).** Exactly one design, on every screen that has one. It
lives in the flow so it _pushes_ content instead of covering it — a floating variant over the
image created a second design that overlapped the title on screens without an image. No text
sits closer than 8px to it.

**The trailer always opens YouTube (R27).** A trailer is a real `<a>` to
`https://www.youtube.com/watch?v=…`, `target="_blank"`, `rel="noopener"`, offered wherever one
arrives from — library, acquisitions or Découvrir. **Playback never happens in the app**, even
when a local trailer file exists next to the media. The backend already exposes
`trailer_url` on the media model; file presence is a separate fact and must not change this
control.

**Sections are identical everywhere (R13).** Fixed order: hero → trailer → synopsis → cast →
library state → seasons (series) → identifiers → actions. The only variations are the ones
nature imposes. Sections that are optional by nature (no trailer, unknown catalogue) do not
count as divergence. The conformity sample is **drawn from the data** — complete, incomplete,
without visual, film, series — never from a fixed handful of states: sampling five frozen
states is exactly how a divergence stayed invisible.

**A library card opens the media sheet, never the acquisition sheet (R31).** A card's
destination follows the page it lives on. Opening « Récupérer maintenant / Mettre en pause »
from the library created a second sheet design whose content also varied with the follow state.
« Compléter → Acquisition » remains the path to acquisition.

### 5.7 Seasons and missing episodes — the answer is _which_, not _how many_

For an incomplete series the operator's question is **which episodes are missing**. Two rules.

**Presence is read, never inferred (R29).** Episode presence comes from the **list of owned
episode numbers**, per season, derived from `library.db` (an episode counts if it carries at
least one file). A `number <= owned count` threshold assumes the hole sits at the end of the
season and is **false for 35 series in this library** — one shipped example owns episodes
1, 3, 5, 7, 9, 11, 13 and was displayed as owning 1 to 7. The same threshold existed in the
follow sheet and must go there too.

**One season rendering (R30).** Seasons are derived from the provider catalogue crossed with
the owned numbers, and every season renders the same way: expandable, complete seasons
collapsed, incomplete ones open and carrying « N manquant(s) », the missing numbers named in
readable ranges (« Manquants : 2, 4, 6, 8, 10, 12 ») above the list, then the episodes with
their air date and a subtle state dot. The numbered matrix is the **declared fallback** when a
provider gives no episode titles — never a second design chosen by accident.

Three cases stay honest rather than invented: an unknown aired total shows `?` and reasons only
up to the highest owned episode; an announced season shows « à venir »; nothing known says so.

## 6. Gestures and platform invariants

The app frame is already paid for: `AppShell` is one viewport tall (`h-svh overflow-clip`) with
a single named scrollport. New pages inherit it.

| Gesture             | Where                            | Non-negotiable constraint                                                                                       |
| ------------------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Pull-to-refresh     | all four pages                   | every touch listener **passive**; the native pull refused in CSS (`overscroll-behavior-y: none`, not `contain`) |
| View swipe          | Acquisition (3), Médiathèque (3) | 30 px left dead zone (iOS back); a drag born on `[data-swipe]` / `[data-noswipe]` is not ours                   |
| Card swipe actions  | Médiathèque, Arrivées, Suivis    | the row **claims** the axis with `touch-action: pan-y`                                                          |
| Suggestion swipe    | Découvrir                        | both directions = dismiss, with undo                                                                            |
| Long-press          | Médiathèque grid                 | 480 ms, cancelled by any move                                                                                   |
| Back closes a layer | everywhere                       | same-URL history marker, distinct identity per layer, close gated on a POP                                      |
| Sheet drag-to-close | everywhere                       | from the 36 px handle strip                                                                                     |

**`touch-action` claiming is not optional, and it is the trap that will be re-fallen into.**
Passive listeners that claim nothing let the browser take the gesture and fire `touchcancel`; the
swipe then works **only under synthetic events**, which are never cancelled. This exact
divergence was reproduced in the maquette during this brainstorm: the code was present, the
test passed, and the operator's thumb found nothing. A synthetic-event test is not proof that a
gesture works.

Eight platform rules become gates, not reminders: passive listeners; `touch-action` on the
region that wants it and never on an ancestor; no `backdrop-filter` on sticky chrome; no
`translateZ(0)` on a sticky element; no `:root` var written from a `ResizeObserver` without a
change guard; `svh` never `vh`; zoom disabled; Back closes the top layer.

**Screens, not panels.** Blocking resolution and run detail stop appearing _below_ the list
being read. They are destinations with their own URL and « ‹ Retour » bar — the costliest
defect of `/medias` and `/pipeline` on a phone.

**URL vs preference.** Active view and every detail are addressable (`?tab=`, `?run=`,
`?media=`) — DOIT-10. Display mode and filters stay in `localStorage`: they are preferences,
not locations. Arbitration A7 of the Acquisition rebuild, applied without exception.

---

## 7. Parity methodology — the heart of this spec

> The Acquisition rebuild's own post-mortem names the two errors that cost it days:
> **« translating instead of transplanting »** (maquette fragments grafted onto existing
> component skeletons — every detail resembled, the whole diverged) and **eyeball validation**
> (« present in the DOM » treated as « conform »). The parity harness that eventually fixed it
> was built _after_ the code, as a repair.
>
> This mission does not repeat that. The method below makes translation **structurally
> impossible** and moves the measurement **before the commit** instead of after the deploy.

### 7.1 The maquette is a repository artifact, not a scratchpad file

Committed at **`frontend/maquette/refonte.html`** — outside `src/` and `public/`, so Vite never
bundles it, but versioned, reviewable and diffable. The previous mission's maquette lived in a
session scratchpad that a purge could destroy; its parity harness had to be rebuildable from a
plan. That is not a source of truth, that is a liability.

The maquette is **allowed and expected to change** (B15). When implementation reveals that a
region cannot be built as drawn, the maquette is amended **first**, the change is recorded, and
the code follows. The code never diverges "temporarily".

**This outlives the rebuild.** The maquette is now the engraved design reference for the web UI
— recorded as **§15 of `docs/reference/product-intent.md`**, in the root `CLAUDE.md`, and in
`frontend/maquette/README.md`. Every future evolution of the interface starts there: a
divergence between the app and the maquette is **a defect in the app**, unless the maquette was
amended first with the reason written down; and nothing ships that the maquette does not show.
The implementer inherits a reference, not a snapshot.

### 7.1 bis The rule set is the deliverable, not the anecdotes

`regions.json` → `$adversarialReview` carries **31 rules (R1…R31)**, each generalised from a
defect rather than patched on the case where it was seen, plus `$methodLessons` — what a rule
that _failed to bite_ taught. `$reportedDefects` lists the defects found by hand, each with its
test in `harness/bugs.py`.

Three of those lessons bind the implementer directly:

- **A screenshot fingerprint is not an oracle.** Two captures of the same unmodified file
  diverge on 8 to 15 of the 45 states. Use `getBoundingClientRect` plus a fixed
  `getComputedStyle` subset — which is what §7.4's probe already does — and, for "is this rule
  dead?", the exact proof: `querySelectorAll` over every state plus the fact that the code never
  writes the class.
- **An audit must announce how many rules it EXECUTED.** "0 violations across 0 rules" reads
  identically when all is well and when nothing runs.
- **A rule that never bit proves nothing.** Every rule added must be mutation-tested: break the
  behaviour on purpose, confirm the rule falls, restore.

### 7.1 ter Source language

Every comment in `frontend/maquette/` — HTML, CSS, JavaScript, Python — is written **in
English** and carries no reference to a work session, a phase, or a dated decision: it must read
years from now, out of context. Interface copy quoted inside a comment stays in French, because
that is what the screen says. The same rule applies to any code derived from the maquette.

### 7.2 CSS is extracted, never retyped

`scripts/extract-maquette-css.py` reads `frontend/maquette/refonte.html`, lifts its `<style>`
block, prefixes every selector with the `.tm` scope, and writes
`frontend/src/styles/ps/app-surface.css` with a generated-file header.

**The maquette's own harness must not leak into the app.** The prototype carries chrome that
exists only to make it demonstrable — the phone frame (`.stage`, `.device`), its stand-in top
and bottom bars, and the design-note callouts (`.note`). The extractor therefore works from an
**explicit allowlist of exported selectors** declared in `frontend/maquette/regions.json`, never
from a blocklist: a selector that is not declared is not exported, so a new prototype-only
helper can never silently reach production. That same allowlist is what the probe walks (§7.4),
so the set of exported rules and the set of measured regions cannot drift apart.

- **The file is generated. Editing it by hand is the defect.**
- `make check` re-runs the extraction and **fails on drift** — exactly the guard that already
  protects `openapi.json` / `schema.d.ts`.
- Consequence: a value can no longer be « improvised in the app » (post-mortem error #1). To
  change a pixel, you change the maquette.

### 7.2 bis The chrome's truth flows the OTHER way

**For the pages, the maquette is the source. For the shell chrome, the app is.**

`AppShell`, `TopBar` and `BottomTabBar` were rebuilt, measured and proven during `acq-mobile`:
the app frame, the published measured heights, the end of the iOS sticky shimmer. Redrawing them
would re-open solved problems. The maquette therefore **mirrors** them — value for value,
converted from their Tailwind classes — and they are promoted from harness to **measured
regions**, so they cannot drift afterwards.

This matters more than it sounds. Every page is composed _inside_ the chrome: the scrollport
height, the bottom reservation, and therefore the density judgement, all depend on it. A region
measured at zero divergence inside an invented frame can be wrong inside the real one. The first
version of this maquette had a top bar on `--sidebar` instead of `--background`, no hamburger, a
19 px mark instead of 28, and a **red** nav badge where `NavCountBadge` is amber.

Any deliberate change to the chrome is an **exception, named in this spec** — never a side
effect of page work.

**One declared divergence.** The real bottom bar is `position: fixed` against the viewport,
correct in the app where the viewport _is_ the phone. Inside a phone frame inset in a wide
window, `fixed` would pin it to the window. The maquette overrides it to `absolute` (same for
the FAB and the selection bar). This lives in `regions.json`'s probe allowlist **with its
justification** — a declared deviation, not a discovered one.

### 7.2 ter Out-of-scope surfaces — quarantined, not forgotten

`/config` and the interior of `/systeme` stay out of scope (B5). They render in the same shell as
converted pages, so three rules keep that honest:

1. **Never a half-conversion.** A surface speaks the maquette's language or the old one, never
   both. The `.tm` scope class is applied per page, which makes it structural rather than
   disciplinary.
2. **Not-measured is _declared_.** `regions.json` carries a `horsPerimetre` map naming every
   uncovered surface **and why**. « Not tested » stops being a possible oversight.
3. **Opposable non-regression.** Their existing component tests plus a screenshot baseline are
   frozen before phase 1 and replayed at every phase. A pixel that moves there fails the build
   unless declared. **Corollary:** the `PageHeader` removal applies only to converted pages,
   never globally — an out-of-scope surface must not be touched by a rule it never asked for.

The residual cost is a visible seam: two languages coexist until Système and Config are
converted. That is the price of B5, and it is **listed here** so it is never discovered.

### 7.3 The DOM is a contract, checked offline

`frontend/maquette/regions.json` maps each region to a CSS selector present in **both** the
maquette and the app (`viewtabs`, `filters`, `card`, `tile`, `sug`, `sheet`, `dlg`, `selbar`, …).

For every region, a vitest test renders the corresponding component with the **shared fixture**
and asserts that the emitted **structure** — tag chain + class chain, in order — equals the
maquette's for that region. This runs in jsdom, in milliseconds, with no browser. It catches
« translating » at the exact moment it happens, not three days later.

### 7.4 The probe gate runs on a local build, on every PR

The previous mission's loop was: fix → commit → push → merge to staging → poll `/api/version` →
measure. Minutes per loop, and it made measuring expensive enough to skip. **This mission
measures against a local `vite preview` build**, headless Chromium at 390 × 844 / DPR 2 / mobile
/ touch, with API responses served by the shared fixtures.

`scripts/parity-probe.py`:

1. asserts `document.documentElement.clientWidth === 390` before trusting any number
   (emulation stickiness trap);
2. walks `regions.json` in two contexts — maquette and app;
3. emits per node: `getBoundingClientRect` plus a fixed `getComputedStyle` subset (font-size,
   font-weight, line-height, padding, margin, border, radius, gap, color, background-color,
   box-shadow, animation), colours resolved to rgb;
4. diffs, with an **explicit allowlist whose every entry carries an inline justification**.

**Pass = zero divergence.** The probe is wired into `make check` and into CI. A divergence is a
build failure, not a ticket.

**Font trap, already paid for once:** the app runs Geist; a maquette on the system stack
diverges structurally (`line-height: normal` at 13 px resolved 17.55 vs 18 px). The committed
maquette therefore embeds Geist as a data URI, so both sides measure under the same font by
construction.

### 7.5 One fixture set, one truth

`frontend/maquette/fixtures.js` (maquette) and `frontend/src/test/fixtures/` (app) are generated
from **one** JSON source. Identical content on both sides is what makes a whole-card overlay
meaningful rather than a comparison of chrome.

The maquette already runs on the operator's **real data** — 260 library titles, 12 real follows,
150 real TMDB suggestions produced by executing the engine. Fixtures keep that property: the
comparison is done on data that actually exists.

### 7.5 bis Behaviour is part of the contract, not just pixels

The maquette's actions **mutate state**. Grabbing moves the card out of « À récupérer » into
« En vol » at the _pris_ station and decrements the nav badge. Resolving empties « Ça coince ».
Pause, removal and deletion act, each with an undo where a gesture triggered them.

This exists because a screenshot cannot say « grabbing moves the card ». `harness/actions.py`
asserts the six behaviours by reading state before and after, so the developer inherits an
opposable behavioural contract rather than an impression.

`window.__reset()` restores the seed, and `__go()` calls it by default: a measurement must never
inherit a previous measurement's mutations.

### 7.6 Gestures are proven under real touch, or not at all

Every gesture claim requires a run in a real browser with **`TouchEvent`s dispatched on the app
surface** — never `PointerEvent`s, never a synthetic shortcut around the listener under test —
plus a recording. §6 explains why: passive listeners that claim no axis pass synthetic tests and
fail a thumb.

The operator's phone validation stays the closing gate. It is not a substitute for the above; it
is what the above earns the right to ask for.

### 7.7 Loop protocol — no exceptions

1. Amend the **maquette** if the region needs it; regenerate the CSS.
2. Build **one** region. Never two before a measurement — divergence attribution dies otherwise.
3. Local gates: `npx tsc -b --noEmit`, `npx eslint src`, `npx vitest run`, `parity-probe` on the
   regions touched **plus** every region already at zero (append-only regression guard).
4. Commit (Conventional Commits, French body, no AI attribution; write « ticket 411 », never
   « #411 », inside `frontend/` — eslint reads it as a hex colour).
5. Ledger entry: region, probe output, gate output. **No « conforme » without the measurement.**

### 7.8 What the whole sweep must cover

Every screen **and every state**: the five sections of « En cours » with all card states
(takeable, blocked with a wrapping reason, in-flight strip, resting verdict, settled), Suivis in
its three modes with an empty group and a heterogeneous group, Découvrir (list, sheet, swipe,
undo, exhausted pool, no-account degraded mode), Médiathèque (three lenses, grid + list, loading
skeletons, load error + retry, end of list, selection mode, delete dialog single and bulk),
Arrivées (three sections, resolution screen, crossref), Système in reception, plus every sheet,
dialog, toast and empty state.

---

## 8. Delivery

### 8.1 Integration branch — B12, non-negotiable

`main` is autodeployed to production. Therefore **the six PRs do not target `main`.**

```
6 PR ─────────►  feat/<codename>          epic branch — codename derived at
                                          create-branch; never merged mid-flight
                        │
                        ├──► `staging` branch pointed at it
                        │      └─► tm-staging.iznogoudatall.xyz  ← the operator validates
                        │                                          the accumulating whole
   main ──merges────────┤   (main is re-integrated regularly so the epic does not rot)
                        │
                        └──► ONE final PR to main  ← after the operator's global sign-off
                                     └─► prod
```

A second backend instance was considered and rejected: prod and staging already share
`library.db`, `acquire.db` and the storage disks, so a third instance protects nothing while
costing infrastructure. What protects production is that **nothing reaches `main`**.

### 8.2 Phases — one per PR

| Phase | Delivers                                                                                            | Visible to the operator                                                                                    |
| ----- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **0** | Maquette committed, extraction script, `regions.json`, fixtures, probe wired into `make check` + CI | Nothing in the app — and that is the gate: the probe must report zero on Acquisition **as it ships today** |
| **1** | Scope rename `.mq`→`.tm`, eight primitives extracted to `ds/`, `PageHeader` off mobile              | Nothing — same gate: parity on Acquisition still zero                                                      |
| **2** | **Arrivées** + reception into Système; `/medias`, `/pipeline`, `/controle` demoted to redirects     | The largest step: three pages become one                                                                   |
| **3** | **Médiathèque** read-only (three lenses, pagination, thumbnails)                                    | Browsing the library becomes possible for the first time                                                   |
| **4** | **Media sheet** (§5.6, §5.7): visual header, single back control, YouTube trailer, seasons naming their missing episodes | Every poster in the library leads somewhere worth arriving at |
| **5** | **Delete**, dry-run enforced, three paths, bulk                                                     | Deleting becomes possible, showing first what would go                                                     |
| **6** | **Découvrir**: TMDB client extension, account auth, background pool, third view                     | The suggestion view lights up                                                                              |

Order is not arbitrary: phase 2 must carry the Système reception **in the same PR**, or removing
`/pipeline` from the bar orphans its runs. Phases 0–1 come first because they are the only ones
whose failure is visible on a page that already works. Phase 4 follows phase 3 because the
library is what makes the media sheet reachable at scale — rebuilding the sheet first would leave
it without traffic to prove it. Phases 0–4 have **no TMDB account dependency**, so a blocked
account in phase 6 cannot hold the rebuild hostage.

**Two backend openings, both bounded, both named here so they are not discovered late:**

- **Phase 4** needs owned episode numbers per season exposed to the web layer. `library.db`
  already holds them (`media_item` → `season` → `episode` → `media_release` → `media_file`); no
  schema change, a read model and a typed route.
- **Phase 4** also opens the quality-profile write path described in §5.5: add
  `quality_profile` to `UpdateFollowRequest`, validate its four keys, persist to
  `quality_profile_json`, `make openapi`. The read path and the hard filter already exist.

### 8.3 Gates on every commit

`npx tsc -b --noEmit` (never `tsc --noEmit`, which checks nothing in `frontend/`), `npx eslint
src`, `npx vitest run`, `make check` (stricter than `eslint src`: raw-colour ban, `<img>`
forbidden → `MediaPoster`, module-size budget), `make openapi` on any route change with the
regenerated files committed, and a **version bump on every PR** (operator standing rule).

---

## 9. Test plan

Beyond unit coverage, these encode the decisions above:

1. **Parity** — `parity-probe` reports zero divergence on every region of `regions.json`, at
   390 px, with a justified allowlist. Wired into `make check`.
2. **Extraction** — re-running `extract-maquette-css.py` produces a file identical to the
   committed one. Drift fails the build.
3. **DOM contract** — per region, the component's tag+class chain equals the maquette's.
4. **§12** — no route scrolls horizontally at 390 px; on every card, `title.bottom <= meta.top`
   (the R5 regression, pinned).
5. **§13** — the Médiathèque completeness fraction is cross-checked against the disks by an
   executable control at zero anomalies; an unknown `episode_count` renders `?`, never a number.
6. **§11** — `constitution.test.tsx` and its `WIRED_SURFACES` array gain Médiathèque, Découvrir
   and Arrivées: an identified media with no path to its sheet fails the suite.
7. **§9** — every action label on a `movie` suggestion or follow comes from the film column
   (exhaustive `Record<>` map, so a new state breaks `tsc` rather than printing a slug).
8. **NE-DOIT-PAS-8** — the suggestion pool is filled by the background pass; a test asserts that
   rendering and scrolling Découvrir issues **zero** provider call.
9. **Delete** — identity is by provider-ID; a followed media cannot be deleted without passing
   the follow arbitration; the dry-run manifest is produced before any destructive call.
10. **Gestures** — each gesture exercised with `TouchEvent`s on the real surface, with its
    recording; `touch-action` asserted on the rows that must claim the axis.
11. **Load** — the Médiathèque issues one request per page and never fetches the full library;
    a failed page renders the retry path, not a silent stop.
12. **Regression per bug** — every defect found gets a test that reproduces it, written with the
    fix (standing operator rule).

Every `ACCEPTANCE.md` criterion is an **executable shell command with its documented expected
output**. Prose criteria are invalid.

---

## 10. Risks and mitigations

| Risk                                                  | Mitigation                                                                                                                                                                                                                                                                      |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Translating instead of transplanting (post-mortem #1) | CSS generated from the maquette; DOM contract tested per region; hand-editing the generated file fails `make check`                                                                                                                                                             |
| Eyeball validation (post-mortem #2)                   | Probe is the gate and runs locally on every commit; no « conforme » without its output                                                                                                                                                                                          |
| Measuring only what was just touched                  | The probe is append-only over regions; the sweep re-runs everything already at zero. **This mission already produced this defect**: after a Découvrir change, only Découvrir was checked, and the Médiathèque shipped blank because a slice edit had removed a constant it used |
| A gesture that passes synthetically and fails a thumb | `TouchEvent`s only; `touch-action` asserted; operator phone gate                                                                                                                                                                                                                |
| PWA stale bundle                                      | `/api/version` checked in the measuring tab itself; assets immutable and hashed, `index.html` revalidated                                                                                                                                                                       |
| Epic branch rotting behind `main`                     | `main` merged into the epic at every phase boundary (merge, never rebase — the PRs are squashed)                                                                                                                                                                                |
| Shared databases                                      | Fixtures via response interception only. **Never** test rows in `library.db` / `acquire.db`                                                                                                                                                                                     |
| TMDB account unavailable                              | Phases 0–3 carry no TMDB dependency; degraded mode is specified and tested                                                                                                                                                                                                      |
| `rg` over the 14 GB fixture tree                      | Type filters always; `curl` always with `--connect-timeout` and `--max-time`                                                                                                                                                                                                    |

---

## 11. Open items — carried, not hidden

1. **Plex deletion.** `api/plex.py` only refreshes. Which route actually removes the entry on
   this server is a **verification step of phase 5** (Delete), not a claim of this spec.
2. **Real deletion cannot be validated before production.** Staging writes to the real disks and
   the real databases, and fabricating a media for the proof is forbidden by a standing operator
   rule. Protocol: on staging, dry-run only; the first real deletion happens **after** the
   production merge, on a media the operator names, after a genuine `sqlite3 .backup` of
   `library.db` (a file copy of a WAL database is not a backup), with the destructive journal as
   evidence. This is the single item of the mission that B12 cannot cover, and it was flagged
   before the phase was planned.
3. ~~**Cron shown raw.**~~ **Closed.** The cadence is translated — « Recherche automatique :
   2 fois par jour, à 3 h 20 et 15 h 20 » — with an explicit fallback to the raw form when the
   pattern is not recognised, rather than an invented sentence. Covered by
   `harness/bugs.py` (« cadence in words »). The app must carry the same translation.
4. **`?tab=maintenant`.** The label became « En cours » (B13); whether the URL param migrates
   (with a legacy redirect) or stays is an implementation detail of phase 6's sibling work — the
   deep link must keep working either way.
5. **The 19 media with no TMDB id** fall back to title+year for suggestion exclusion. The
   fallback must be visible, never silent.
6. **Système's own mobile redesign** is deferred by B5. Until then one bar entry will not speak
   the same language as the other three — the accepted cost.
7. **`IMPLEMENTATION.md` at the repo root is stale** (it still describes `file-absorbee`). It is
   rewritten at `create-branch`; noted so it is not mistaken for the current tracker.

---

## 12. Out of scope

- `/config` — untouched, as the operator asked at mission start.
- ~~The media sheet~~ — **now IN scope.** It was listed here when the mission opened; §5.6 and
  §5.7 supersede that. The sheet is rebuilt: melting visual header, single back control, trailer
  as an outbound YouTube link, and seasons naming their missing episodes. It keeps its URL
  `/media/:provider/:id` and its status as a destination, not a sheet.
- Desktop beyond « fully functional »: the 672 px centred column, a denser tile grid, and the
  « ⋮ » where there is no swipe. §12 makes the phone the origin of the drawing; wide-screen
  refinement is deliberately unspecified.
- Watcher and Obligations panel contents, moved behind « ⋮ » unchanged.
