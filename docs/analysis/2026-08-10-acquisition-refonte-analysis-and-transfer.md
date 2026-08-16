# What the Acquisition mobile-first rebuild actually did — and what transfers

**Date:** 2026-08-10 · **Author:** analysis pass before the Médias / Pipeline / Contrôle / shell redesign
**Scope read:** `origin/main` @ `720d2536` (PR #422 `acq-mobile` + PR #423 `suivi-termine`)
**Sources:** `docs/archive/superpowers/specs/2026-08-06-acquisition-mobile-refonte-design.md`,
`docs/archive/analysis/2026-08-08-maquette-parity-ledger.md`, `docs/reference/product-intent.md`,
`frontend/src/{pages,components,styles,lib}`

---

## 1. Inventory — what shipped on `/acquisition`

### 1.1 Information architecture

Seven data-named tabs (`Suivis · File · Parcours · Téléchargements · Vue d'ensemble · Veille ·
Réglages`) were replaced by **two question-named views** plus two entry points:

| Surface | Answers | Implementation |
|---|---|---|
| **Suivis** (default, clean URL) | *« qu'est-ce que je suis ? »* | `SuivisPanel.tsx` (748 LOC), 3 display modes |
| **Maintenant** (`?tab=maintenant`) | *« est-ce que quelque chose m'attend ? »* | `MaintenantPanel.tsx` (940 LOC), 5 urgency sections |
| **`+`** (FAB) | *« ajouter »* | `AddMediaScreen.tsx` (822 LOC), full screen |
| **`⋮`** (detached) | second-rank: Veille, Obligations | `PlusSheet.tsx` (199 LOC), bottom sheet |

Dissolved: `Vue d'ensemble` → section headers carry their own counts (a number that opens
nothing is a dead end, NE-DOIT-PAS-9). `Parcours` → per-item journey strip + `JourneyDetailSheet`.
Moved out: `Réglages` → `/config?tab=classement`, with the legacy deep link redirected.

**The load-bearing move is the naming axis**: tabs named after *questions the operator asks*,
not after *tables the backend owns*. The design doc states it explicitly (§1.2) and it is the
one decision that made everything else possible — a density pass at constant structure was
explicitly rejected (arbitration A1).

### 1.2 The shell became an app frame

`AppShell.tsx:156` — `flex h-svh overflow-clip`, with `main[data-scroll-root]` as **the single
scrollport**. The document itself no longer scrolls.

This was not cosmetic. It is the fourth and final fix for the iOS sticky-header shimmer: while
the document scrolls, iOS collapses/expands the URL bar throughout the gesture, resizing the
visual viewport and `env(safe-area-inset-*)` on every frame, so a `position: sticky` header is
re-placed on the main thread one frame behind compositor-scrolled content. Three earlier
attempts (layer promotion, passive listeners, quantised heights) damped the symptom. The frame
removes the cause.

**This change is already global** — every route renders inside it. It is the single biggest
already-paid-for asset for the other pages.

### 1.3 Measured geometry contracts

`components/layout/bottom-bar-metrics.ts` — three bars publish their **real measured height**
to `:root` CSS vars (`--tm-bottom-bar-h`, `--tm-topbar-h`, `--tm-viewtabs-h`), and
`aboveBottomBar(gap)` is the single expression for "sit above the bar".

The rule it encodes (design doc R4): **nothing is positioned by a distance from the screen
edge; anchor it to what it belongs to.** The original defect was `bottom: 84px` calibrated on
desktop — on iPhone the bar grows by `env(safe-area-inset-bottom)` (~34 px) and the toast slid
underneath it.

`publishMeasuredHeight(var, h, exact)` additionally writes **only on change**, because the iOS
URL bar resizes observed elements continuously mid-scroll and every write invalidates document
style.

### 1.4 Gesture layer

| Gesture | Where | Non-obvious constraint |
|---|---|---|
| Horizontal view swipe | `AcquisitionPage` pager, `gestures.ts` | 30 px left dead zone (iOS back); a drag starting on `[data-swipe]` or `[data-noswipe]` is not ours |
| Pull-to-refresh | `AcquisitionPage`, raw `touch*` listeners | **every listener passive** — one non-passive `touchmove` on the scrolling subtree takes iOS off the compositor; the native pull is refused in CSS (`overscroll-behavior-y: none`) |
| Card swipe actions | `SwipeActions.tsx` (292 LOC) | actions revealed under a translating card; the card can never be dragged further open than its actions are wide |
| Back closes a layer | `lib/use-back-closes.ts` | same-URL marker entry, `preventScrollReset`; two instances need **distinct identities**, and the close must be gated on a POP |
| Sheet drag-to-close | `SheetGrabHandle.tsx` (105 LOC) | 36 px handle strip is the drag origin |

`touch-action` **intersects down the whole chain** — the single most expensive lesson: a
`pan-x` pill scroller under a `pan-y` ancestor pans on neither axis. The restriction was moved
off the pager and onto the regions that want it.

### 1.5 Visual language — a transplanted maquette, measured to zero divergence

`styles/ps/maquette-acquisition.css` (997 LOC, scoped under `.mq`) is a value-for-value
transplant of the operator-approved prototype; `tokens/maquette.css` holds the raw colours C19
forbids outside `tokens/`.

Parity was **measured, not eyeballed**: a headless Playwright harness at exactly 390 px / DPR 2
DOM-probed 15 region maps against the prototype and drove the differ to **0 divergences on an
explicit allowlist**, plus a 12/12 gesture pass. Two findings that only a measurement could
produce: the app runs Geist while the prototype ran the system stack (`line-height: normal` at
13 px → 17.55 vs 18 px, structural divergence), and three pinned `height`/`line-height` values
were stale artefacts of the previous font.

The concrete vocabulary now available:

```
.viewtabs   flex bar: .seg (equal-width segment, elevated selected pill) + detached .more (40×40)
.seg .n     amber count badge inside a segment button
.filters    pinned zone: .search (muted rounded field) + .pillbar
.pillbar    .pillscroll (touch-action: pan-x, hidden scrollbar) + .vswwrap (1px divider) + .vsw
.pill       12/600, radius 99, aria-pressed → primary fill
.vsw        display-mode switcher, 32×28 buttons, elevated pressed state
.tile       poster tile for grid mode, .p initials placeholder, .fr fraction, .off dimmed
.ptr        pull-to-refresh chrome, .armed / .loading
.actions    swipe action rail: .act.grab / .act.pause / .act.remove
.sheetgrab  36 px drag handle · .sheettitle · .sheetmeta · .sheetacts(.secondary) · .sact
.fichebar   « ‹ Retour » bar — screens get the bar, bottom sheets keep the handle
.mqtoast    in-page toast, close cross, anchored to the zero-height dock above the bottom bar
.fab        floating «+», anchored by aboveBottomBar()
.res        search-result row: poster + title + meta + 2-line overview + action button
.crossref   discreet "N autres … → Contrôle" line
.kv         key/value row (Veille & obligations)
.empty      empty state that names what was searched and offers the fallback
.dlg        confirmation dialog + .dlgscrim
```

### 1.6 Card grammar

`AcquisitionCard.tsx` is the **single** card component for all seven lists on the page. It
enforces §12's engraved composition rule structurally rather than by convention:

- line 1 = title, alone, `truncate` (R3);
- line 2 = subtitle; then `reason` at `line-clamp-2` (a blocking reason **never** truncates);
- line 3 = meta (fraction first, then status chip);
- `strip` and `footer` are **full-width own lines**, never siblings of the title row (R2);
- the poster is a button **only** when a media sheet exists — an unidentified media gets no
  button at all, not a disabled one (§11: a greyed control is the same broken promise);
- controls that belong to a card live **inside** the card, in flow (R1) — the `⋮` used to be
  absolutely positioned on the swipe wrapper while the card translated.

### 1.7 Truth discipline carried into the UI

- **One derivation per question (§13):** card fraction ≡ sheet header ≡ Σ season headers read
  the same computation; the prototype disagreed with itself (`24/25` vs `23/25` summed) and
  that had to become impossible by construction.
- **The nav badge and the tab badge read the same hook** (`useWaitingForOperator`), and it
  counts *what awaits the operator* (`à récupérer + à traiter`). The old `pendingWanted` said
  3 and landed on a view showing `0/0/0/59`.
- **An unknown count renders `?`, never `0`** — both in the badge and in the tab pip.
- **A refresh that could not run says so** (toast), because silence reads as "up to date".

### 1.8 Performance, discovered by measurement

- `fetch` has **no default timeout** → a stalled mobile socket hangs every waiter forever
  (the pull-to-refresh spinner). The web client now carries a finite budget, and the PTR
  spinner is additionally **capped** so it collapses while refetches finish in background.
- The SPA shipped **1.05 MB of raw JS**, no `content-encoding`, no `Cache-Control`.
  `GZipMiddleware` + immutable hashed `/assets` → 311 KB cold, zero on repeat. `index.html`
  must stay revalidated or no deploy reaches the device.
- List posters go through `posterThumb()` (TVDB `_t` variants, TMDB `w342`) — a full-size
  TVDB poster weighs ~370 KB.

---

## 2. The transferable rule set

These are the parts that are **not** about acquisition. They are the redesign's real output.

### 2.1 Design rules (from the spec's §11 + the review lessons)

| # | Rule |
|---|---|
| R1 | A control that belongs to a card lives **inside** the card, in flow. |
| R2 | A full-width element gets **its own line**, never a sibling of the title row in a `row` flex. |
| R3 | The title line accepts nothing but the title; qualifiers go to the meta line — the only one that wraps. |
| R4 | Nothing is positioned by a distance from the screen edge; anchor to what it belongs to (measured heights). |
| R5 | A class on a `<span>` declares its `display`; no class name is reused across two roles. |
| R6 | No dangling reference: removing an entity cuts its row everywhere, and renderers skip an orphan rather than throw. |
| R7 | Grid tracks use `minmax(0, 1fr)`, never `1fr` (whose `auto` floor is intrinsic content size). |
| R8 | An author `display` rule beats `[hidden]` — add `&[hidden] { display: none }`. |

### 2.2 Mobile-platform rules

| # | Rule |
|---|---|
| M1 | The shell is a **frame**, not a document: one viewport tall, `overflow-clip`, one named scrollport. |
| M2 | **Every** touch listener on a scrolling subtree is passive; refuse the native pull in CSS (`overscroll-behavior-y: none`, not `contain`). |
| M3 | `touch-action` intersects down the chain — declare it on the region that wants it, never on an ancestor. |
| M4 | No `backdrop-filter` on sticky chrome; never promote sticky elements with `translateZ(0)`. |
| M5 | Never write a `:root` var from a `ResizeObserver` without a change-guard; quantise with `ceil` when two published heights are summed. |
| M6 | `min-h-screen` = `100vh` = the **large** viewport → use `svh`. |
| M7 | Zoom is disabled app-wide (`maximum-scale=1`), which also kills iOS input-focus auto-zoom. |
| M8 | Back closes the topmost layer — via a same-URL history marker, with distinct identities per layer and a POP gate. |

### 2.3 Method rules

| # | Rule |
|---|---|
| P1 | Design at 390 px in an interactive prototype driven by real events; a static mockup cannot arbitrate a gesture conflict. |
| P2 | Parity is **DOM-probed and measured**, with an explicit justified allowlist — never eyeballed. |
| P3 | Validate on staging against real data before merge. |
| P4 | Every operator-visible decision is recorded as a numbered arbitration (A1…A18) that is an *input*, not a proposal. |
| P5 | An adversarial multi-agent review after the gates are green still found 15 real defects — green gates are not a review. |

---

## 3. Where the other four surfaces stand today

Read at `origin/main` @ `720d2536`. None of them has received any of the above.

### 3.1 `/medias` — `Medias.tsx` (548 LOC)

- **Three tabs live in `PageHeader`'s `actions` slot** (`Bibliothèque · À résoudre (n) ·
  Décisions`) — a `flex` row of three `Button`s that at 390 px competes with the `h1` for the
  same line from `sm` up, and is a horizontally-laid group below it. No `.seg` segment, no
  equal widths, no measured pinning.
- **A second control group immediately under it** (`Tous · À traiter · En cours · Prêts`),
  same shape, `w-fit`. Two tab levels — the exact D2/D4 defect the acquisition rebuild removed.
- **Tabs are `useState`, not URL** — `?media=` / `?decision=` are addressable, the tab itself
  is not (DOIT-10 partially unmet; the tab is only *derived* from those params at mount).
- The decisions view is a **desktop two-pane grid** (`lg:grid-cols-[2fr_3fr]`) whose mobile
  fallback is "detail replaces list with a ← Retour button" — a hand-rolled version of what
  `useBackCloses` + a sheet now do properly.
- Status filter chips are `Badge`s wrapped in 44 px hit-area buttons — the `.pill` train
  already solves this, with counts and horizontal scroll.
- `PageHeader title="Médias"` duplicates the highlighted bottom-bar entry — defect D3.

### 3.2 `/pipeline` — `Pipeline.tsx` (154 LOC)

- A **linear stack of 7 heavy panels** in `max-w-5xl`: PageHeader → ActionBanner → FlowBoard →
  Controls → InterpretedRunFeed → RecentResolutions → raw-log Accordion → RunHistoryTable →
  RunDetail. On a phone this is a very long scroll with no urgency ordering and no way to get
  to the history without passing everything.
- `FlowBoard` is an **8-stage board** — the surface most likely to fight 390 px.
- `RunDetail` renders **inline in the flow** when `?run=` is set, rather than as a screen or a
  sheet: on a phone the detail appears *below* everything you were reading.
- No section pips/counts, no pinned sub-nav, no pull-to-refresh, no gestures.
- Same D3 title duplication.

### 3.3 `/controle` — `Dashboard.tsx` (79 LOC)

- **Seven stacked panels in priority order** — the intent is right (attention-first) and it is
  the closest in spirit to « Maintenant ». But it is a *document*: `ATraiterList`,
  `ScrapeActivityPanel`, `LastRunDigest`, `StalledPanel`, `AcquisitionSummaryCard`,
  `SchedulersPanel`, `CompactHealth`, `PipelineControls`, one under the other, no folding, no
  counts in headers, no drill-down grammar, no card component shared with `/acquisition`.
- Overlaps `/acquisition` (« À traiter » exists on both, by design and by cross-reference) and
  `/pipeline` (`PipelineControls` and last-run digest are rendered on both). **The boundary
  between Contrôle and Pipeline is the open question of this redesign**, not a styling matter.
- `max-w-[1280px]` — a desktop-origin width on a mobile-first page.

### 3.4 The template — `AppShell` + `TopBar` + `BottomTabBar` + `Sidebar` + `PageHeader`

Already good:

- app frame + single scrollport (§1.2), measured bar heights (§1.3), 4-entry bottom bar
  matching the nav order, badges with `?` for unknown, mobile nav Sheet carrying `VersionCard`.

Open on the template:

- **`PageHeader` is dead weight on mobile** — every page's `h1` repeats the highlighted bottom
  tab (D3). `/acquisition` already dropped it; the other three still pay for it.
- **`PageHeader.actions` is being used as a tab bar** on `/medias` — a slot with no layout
  contract at 390 px.
- **No shared "page sub-nav" primitive.** `/acquisition` has `.viewtabs` (`.seg` + `.more`,
  pinned by measured height); the other pages each hand-roll a `Button` group. This is the
  single highest-leverage template extraction.
- **No shared card.** `AcquisitionCard` enforces §12's engraved composition; every other list
  re-derives its own row shape, so §12 is enforced on exactly one page.
- **`.mq` is scoped to acquisition by design** — extending the language to other pages means
  deciding whether it graduates to the design system or stays a per-surface transplant. That
  is an explicit decision to make, not a mechanical move.
- **No transverse gesture affordances** — PTR, back-closes-layer and sheet handles exist as
  reusable modules (`lib/use-back-closes.ts`, `lib/scroll-root.ts`, `gestures.ts`,
  `SheetGrabHandle`) but are only wired on `/acquisition`.

---

## 4. Open questions the brainstorm must arbitrate

1. **Contrôle vs Pipeline** — two surfaces, overlapping content, one of which (« ce qui
   m'attend ») is already the job of `/acquisition`'s « Maintenant ». Do the four bottom-bar
   entries survive as four? This is an IA question, and §1.1 says IA is where the value is.
2. **Does `.mq` graduate?** Promote the maquette vocabulary to the design system (one language,
   four pages) or keep per-surface transplants (independent evolution, guaranteed drift).
3. **Which primitives get extracted first** — `ViewTabs`, `FilterBar`, `MediaRow`, `Sheet`
   grammar, `PullToRefresh` — and does extraction happen before or during the page work.
4. **Is a measured-parity harness re-run per page**, or is the prototype the contract and the
   probe reserved for the pages that carry dense chrome?
5. **What is each page's question?** The acquisition rebuild worked because « Maintenant » and
   « Suivis » are questions. Médias, Pipeline and Contrôle are currently named after *things*.

---

## 5. Non-negotiables carried forward

- `docs/reference/product-intent.md` is binding; each PR cites the § it serves.
- §12 proofs are at **390 px on real data**; a large-screen-only validation is worth nothing.
- §13: one derivation per question; `scripts/check-acquisition-coherence.py` at zero anomalies
  for any acquisition-touching claim.
- `make check` runs a **stricter** frontend gate than `eslint src` (C19 raw-colour ban, `<img>`
  forbidden → `MediaPoster`).
- Any route change ⇒ `make openapi` + commit the regenerated files.
- Version bump on every PR (operator standing rule).
