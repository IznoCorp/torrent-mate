# The desktop adaptation of the screens — a milestone, not a lot · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### Desktop adaptation of the screens — a milestone,
not a lot`, whose whole body is the operator's sentence of 2026-09-29 (L24's OPEN 6), verbatim: « A dans un premier
temps, mais prévoir une phase final d'adaptation des écrans pour une utilisation plus agréable sur desktop. On en
décidera des contours en temps et en heure quand la maquette sera prête ». The maquette is ready (every drawn lot
merged, `main` at `27b304157`). **This document prepares his decision; it decides nothing.** It measures what the
maquette does on a desktop today (§ 1), lists what an adaptation can mean in his own principles' terms with the
cost of each (§ 2), asks the open questions in the shape `/orchestrator:decide` presents (§ 3), and cuts a first
order of phases for after his rulings (§ 4).

**Nothing under `frontend/maquette/` was touched to write it** — no code, no rule, no seed. Written 2026-10-01, on
`main` at `27b304157`.

---

## 0. The authority, said once

| Source | What it says about the desktop | Consequence here |
| --- | --- | --- |
| `product-intent.md` § 12 | « Toute surface se conçoit à la largeur d'un téléphone, puis se laisse respirer sur grand écran — jamais l'inverse. Le desktop doit rester pleinement fonctionnel, mais il n'est pas le point de départ du dessin. » | Every proposal below STARTS from the phone surface and lets it breathe; none draws a desktop screen the phone does not have. |
| DOIT-9 | « le desktop reste pleinement fonctionnel » | Already proved by R413 (`harness/desktop_holds.py`, L24): every named state at 1280 × 800, pointer, no touch, content, no overflow, no JS error, the drawer reaches every page. This milestone is about « plus agréable », not « fonctionnel ». |
| § 16 | Opening a surface stacks, adjusting replaces; the bar's pages replace; the drawer's pages stack | A desktop layout changes WHERE a surface is drawn, never what it does to the history. Every proposal keeps § 16 untouched. |
| `operator-method.md` § 1, 09-29 | « design et ergonomie d'application mobile natif » · « Responsive partout » · « cohérence partout » · « les composants sont réutilisés […] si un jour je change un composant ça change partout » · « on crée pas de nouveau composant on adapte » | No parallel desktop app, no second set of components: each proposal is ONE existing component given another arrangement at a width, in its own `variants.ts`. |
| `operator-method.md` § 3, 09-29 | « le grand écran reste mobile d'abord, avec une phase finale bureau » | This is that phase. |
| Q1, 2026-08-30 (B-235) | « the drawer alone, at every width — and not frozen […] a rail is drawn only if real use asks for it » | The rail is asked (OPEN 2), flagged as REOPENING a ruling, because the ruling itself says it is not frozen and this milestone is the moment he named for it. |
| `frontend-architecture.md` § 3, invariant 12 | A component asks the width it HAS (container queries); the shell keeps its media queries | Every width threshold below is either the SHELL's (a media query: the rail, the column, the layer anchoring) or a component's container query. A capped column therefore re-answers every component's container query for free. |

---

## 1. The inventory as it is

### 1.1 How it was walked

Every named state the maquette declares (`window.__states()`, **319 states**) was opened on
`tm-design.iznogoudatall.xyz` at **1280 × 800**, pointer and no touch, the harness's phone frame taken off through
its own switch (« Sortir du cadre », `#desktop-switch`, R140), through `window.__go(id)`. A representative subset of
**44 states** (one or two per page, sheet, screen and dialog) was walked again at **1024 × 800** and **1440 × 800**.
Each state was measured (the open layer, its rectangle, the number of full-width rows, the longest prose line in
characters, the gallery's columns, the tab bar, the FAB) and photographed. Screenshots:
`/private/tmp/desktop-shots/<width>/<state>.jpg` (never committed); measures: `/private/tmp/desktop-shots/walk-<width>.json`.

**What holds, at every width walked**: zero JS error, zero horizontal overflow, every state draws content — R413's
reading, confirmed on the live host. Nothing below is a functional defect.

### 1.2 What the measures say, in five lines

1. **Everything fills.** Every page, screen and panel stretches to the window: cards, fact rows, buttons and inputs
   run 1 250 px wide at 1280 (1 410 at 1440). On average a state draws **13 rows wider than 85 % of the window**.
   **Nothing stays a phone column** — except the sign-in gate, whose card is bounded and centred (`signin.jpg`): the
   only surface that already reads well on a desktop, and the precedent for the rest.
2. **Prose lines are too long to read.** **144 of the 319 states** carry a prose line longer than 90 characters; the
   longest reach **246 characters** at 1280 (Système, a run's detail) and **278 at 1440**. A comfortable measure is
   60–80.
3. **The bottom layers are phone layers.** The bottom sheet (66 states) rises over the full 1 280 px with its grab
   handle in the middle; the confirmation dialog (13 states) is **1 248 px wide** with buttons as wide as itself.
4. **The tab bar is gone, the FAB is not.** `#nav` is `md:hidden` (`ui/variants/frame.ts`, `tabBar`): from 768 px the
   four bar pages (Acquisition, Médiathèque, Trackers, Découvrir) are reached through the drawer only, and their bar
   badges with them. The « + » FAB stays pinned bottom-right of the WINDOW (98 Acquisition states).
5. **Galleries stop at six columns.** The tile grid's container query (`ui/variants/tile.ts`) caps at 6 columns from
   820 px, so tiles grow with the window: **≈ 200 px at 1280, ≈ 227 px at 1440** — one and a half rows per screen at
   1440 (`1440/lib-grid.jpg`).

### 1.3 Page by page (1280 unless said)

| Surface | What fills | What stays a phone column | What is awkward | Shot |
| --- | --- | --- | --- | --- |
| Acquisition — Suivis (list) | the cards, 1 250 px | — | a poster and four short lines on the left, 1 000 px of empty card on the right | `1280/acq-follows-list.jpg`, `1024/acq-follows-list.jpg` |
| Acquisition — Suivis (grid) | 6 tiles | — | tiles ≈ 200 px, two rows visible | `1280/acq-follows-grid.jpg` |
| Acquisition — En cours | the cards | — | the eight-rung ladder stretched over 1 150 px: the dots no longer read as one sequence | `1280/acq-now-loaded.jpg` |
| Acquisition — À traiter | the cards | — | same ladder; « Relancer » and « Abandonner » each 580 px wide | `1280/acq-todo-loaded.jpg` |
| Acquisition — « + » (`/add`) | the search field, the results | — | the synopsis cut to one line though 900 px stay empty beside it | `1280/acq-add-results.jpg` |
| Resolution screen | the candidates | — | « Choisir » floats after each synopsis, at a different x on every row | `1280/acq-resolution-tie.jpg` |
| Releases screen | the candidates | — | « Prendre celle-ci à la place » is a 1 230 px button | `1280/screen-releases.jpg` |
| Journey sheet, follow sheet, « ⋮ » sheet | the bottom sheet, full width | — | a ladder of 14 steps with the label at x 40 and the date at x 1 250; the season chips wrap nowhere, the « Récupérer la saison » buttons 1 250 px | `1280/sheet-journey.jpg`, `1280/followsheet-gaps.jpg`, `1280/sheet-more.jpg` |
| Médiathèque — grid | 6 tiles | — | tiles ≈ 200–227 px; 24 shown of 1 861, two rows | `1280/lib-grid.jpg`, `1440/lib-grid.jpg` |
| Médiathèque — list | the rows | — | the synopsis runs 200 characters on one line | `1280/lib-list.jpg` |
| Médiathèque — panel | the bottom sheet, full width | — | covers the grid's lower half; four 1 250 px actions | `1280/lib-film-panel.jpg` |
| Médiathèque — selection | the grid; the selection bar spans the window | — | « Annuler » at x 110 and « Supprimer » at x 1 180 | `1280/lib-selection.jpg` |
| Delete confirmation (dialog) | 1 248 px | — | a confirmation as wide as the page, its three buttons too | `1280/lib-delete.jpg` |
| Media sheet (`/media/…`) | the hero, 1 280 × 400 | — | the backdrop is upscaled and soft; the cast row holds six people at the left; the facts run label-left value-right 1 250 px apart | `1280/mediasheet-series.jpg` |
| Découvrir — list | the rows | — | as Suivis | `1280/discover-full.jpg` |
| Découvrir — posters | 6 tiles | — | as the library grid | `1280/discover-posters.jpg` |
| Découvrir — deck | ONE card 1 250 × 640 | — | a portrait poster cropped into a landscape backdrop; the swipe is a 1 250 px drag | `1280/discover-deck.jpg` |
| Trackers — Torrents | the cards | — | release names fit, but each card is 80 % empty | `1280/trackers-page.jpg` |
| Trackers — Trackers (roster) | the rows | — | the ratio at x 1 140 and the switch at x 1 230, the facts at x 25 | `1280/trackers-roster.jpg` |
| Torrent panel | the bottom sheet | — | fact rows 1 230 px wide, the label and its value an eye-sweep apart | `1280/torrent-panel.jpg` |
| Système | the sections | — | the longest prose lines of the app (225 characters) | `1280/system.jpg` |
| A run (`/run/…`) | the steps | — | **the one surface the width serves**: log lines that wrap at 390 px fit whole | `1280/run-detail-log.jpg` |
| Maintenance | the topic cards | — | a title and a line on the left, a count at the far right | `1280/maintenance.jpg` |
| Réglages — a topic | the fields | — | the key's label at x 27, its value at x 1 250 | `1280/settings-topic.jpg` |
| Classement des releases | the criteria | — | the number field sits under its label at the left of a 1 250 px row | `1280/ranking-editor.jpg` |
| Comptes, Profil | the rows | — | the role at the far right of each account | `1280/accounts-roster.jpg` |
| The drawer | 288 px over a scrim | — | a desktop opens it, picks a page, and it closes: every page change is two clicks | `1280/drawer-navigation.jpg` |
| Sign-in, 404, no-access | the gate is a bounded card | **the gate** | — | `1280/signin.jpg` |

**At 1024** the same, narrower: nothing breaks, the empty right half is smaller. **At 1440** the same, wider: the
longest line reaches 278 characters and the tiles 227 px.

**Not counted — the harness's own chrome**: the ⓘ and data buttons the harness pins top-right sit over « Connecté »
and over a screen's title (`1280/screen-releases.jpg`, « Silo » half hidden). They are `harness.css`, which ships
nowhere and dies at switchover; nothing to adapt.

### 1.4 What already exists and is reused

- **Keyboard**: Escape closes the top layer (`app/focus.ts`, one handler, the interface's own two verbs), Tab walks
  the focus order, a skip link reaches `#port`. Nothing else.
- **Hover**: one generic rule — `button, a, [role=button], summary` dim to 0.85 under `@media (hover: hover)`
  (`styles/base.css`). No row, card or tile answers the pointer.
- **Pointer gestures**: every gesture answers a mouse as well as a finger (`harness/mouse.py`, README « Every gesture
  answers a pointer »): swipes, the deck, the sheet's drag.
- **Container queries**: the port is a container (`ui/variants/layout.ts`, `@container/port`); the galleries already
  read it. A column cap re-answers them without a line changed.

---

## 2. The contours proposed

Each is ONE existing component given a desktop arrangement, written in its own `variants.ts`, never a second
component. Each threshold is the shell's (a media query) or the component's (a container query), per invariant 12.
A cost is counted in surfaces (pages and screens the change shows on), components (the `ui/` or feature module that
changes) and rules (the harness rules to write or re-aim).

| # | Contour | What it serves | What it costs |
| --- | --- | --- | --- |
| C1 | **A content column.** Pages, screens and their headers are drawn in a centred column capped at a reading width (≈ 760 px for lists and forms); galleries keep the full width. The column is the port's `max-width`, so every component below re-reads its container. | § 12 « se laisse respirer »: the 144 states over 90 characters fall under it; the label/value sweep of every fact row shortens to the column. The phone surface is literally kept and given air. | 1 shell variant (`layout.ts`: the port and the screen); 0 feature code; 1 rule (the measure ≤ 90 characters and the column ≤ its cap, every named state at 1024/1280/1440). Every surface shows it. |
| C2 | **The drawer pinned as a rail.** From a desktop width the same drawer (`ui/drawer.tsx`) stays open beside the column instead of over a scrim: the same entries, groups, badges and order, the burger hidden. | Native desktop ergonomics (Material 3's « expanded » navigation drawer, iPadOS's sidebar): one click to change page instead of two, the badges always in sight, which the hidden tab bar took away. | 1 component's variant (`frame.ts`: `drawer` gets a `pinned` arrangement) + the shell's layout (the port beside it); § 16 unchanged (the entries already carry their landing); R-drawer rules re-aimed at the pinned state; REOPENS Q1. |
| C3 | **Panels as side sheets.** The bottom sheet (`ui/sheet.tsx`, `bottomSheet`) rises from the right edge instead of the bottom on a desktop, ≈ 420–480 px wide, full height, the list left visible beside it; the confirmation dialog takes the sign-in card's bounded width (≈ 480 px), centred. | The list stays readable while a panel is open (the panel covers half the library today); a confirmation reads as one, not as a page. Material 3 « side sheet », macOS inspector. | 2 variants (`layout.ts`: `bottomSheet` anchoring and its `translateX` closed state; `dialog`'s max-width); the drag-to-close follows the anchoring axis (the gesture module reads one more axis); 66 sheet states and 13 dialog states re-photographed; R56/R-panel rules re-aimed. |
| C4 | **Two panes: list + sheet.** On the list pages (Acquisition, Médiathèque, Trackers), opening a medium's screen draws it in a second pane beside the list instead of over it; Back closes the pane. | One screen holds the list and the detail, the desktop « mail » layout. | High: the page host draws two routes at once (`app/page-host.tsx`), the screen routes get a pane arrangement, § 16's « ouvrir empile » holds but « the parent is rendered » becomes literal; every screen's states re-walked; new rules for the pane's stack. |
| C5 | **Galleries wider.** The tile grid's columns follow a minimum tile width rather than stopping at 6 (e.g. 7 at 1280, 8 at 1440, 9 at 1680); the deck's card keeps a portrait poster's proportion, centred. | More of the library at a glance (24 shown of 1 861 today); the deck shows a poster, not a crop. | 1 variant (`tile.ts`: two or three more container steps); 1 variant (the deck card's max-width/aspect); R41–R50 re-aimed (they pin 3/4/5/6). |
| C6 | **Keyboard and hover.** A small, declared set: `/` focuses the page's search, ↑/↓ move through a list's rows, Enter opens, Escape closes (exists); a row, card or tile answers the pointer with a hover ground (`@media (hover: hover)`, the existing idiom). No action exists only on hover. | A desktop user's hands stay on the keyboard; the pointer sees what it would open. | 1 shell module (one keymap, beside `app/focus.ts`'s Escape), 1 base rule (hover ground); i18n strings for a shortcut legend if one is drawn; 1 rule. |
| C7 | **The FAB and the selection bar.** On a desktop the « + » joins the header (or the rail's top, with C2) and the selection bar is drawn under the column's width. | No floating button at the bottom-right corner of a 1 440 px window; « Annuler » and « Supprimer » within one glance. | 2 variants (`frame.ts`: the add action; `selection/bar`); 2 rules re-aimed. |
| C8 | **Inside the cards: the empty right half.** With C1 the card is ≤ 760 px and most of this vanishes. Without it, a card would have to re-lay its own parts at a wide container (the ladder, the actions, the synopsis) — per-card desktop drawings. | Only needed if C1 is refused. | Per feature: Acquisition cards, follows, torrents, roster, fact rows — the most expensive way to the same result. |

**What no contour does**: draw a page the phone does not have; move an action the phone has into a desktop-only
place; add hover-only or keyboard-only actions; change § 16; touch the backend. The backdrop's softness on the media
sheet's hero (an image upscaled to 1 280) is a backend image-size limitation — **recorded, not a reason to draw less**
(mission point 4); C1 bounds the hero to the column and makes it moot.

---

## 3. The open questions — OPEN 1…7, written for `/orchestrator:decide`

Each: the thing on the screen, the choices with their cost and gain, ONE recommendation and its reason. None is
answered here.

**OPEN 1 — How wide is a page on a desktop?** On the screen: every list, form, fact row and button runs the whole
window (1 250 px at 1280); 144 states carry a line over 90 characters; the confirmation dialog is 1 248 px wide.
- *A — as today*: everything fills. Cost: none. Gain: none; every awkward line of § 1.3 stays.
- *B — one column for everything*: pages, screens and galleries capped at ≈ 760 px, centred. Cost: one shell
  variant, one rule. Gain: reading width everywhere; but a gallery of 760 px on a 1 440 window shows FEWER posters
  than today.
- *C — a column for reading, the full width for galleries*: lists, forms, screens, fact rows and dialogs capped
  (≈ 760 px; the dialog ≈ 480 px, the sign-in card's width), the tile grids and the deck keep the window. Cost: one
  shell variant + the gallery's own opt-out, one rule. Gain: every awkward reading line goes, the galleries keep
  their room.

**Recommendation: C.** It is the phone surface given air, which is § 12's own phrase; it removes most of § 1.3 with a
single component change (the components re-read their container, invariant 12); and it is the arrangement the
operator's only already-bounded surface — the sign-in card — already uses.

**OPEN 2 — How does one change page on a desktop?** On the screen: the tab bar is hidden from 768 px, so the four bar
pages and their badges are behind the burger; every page change is two clicks and a scrim. **This reopens Q1
(2026-08-30, « the drawer alone, at every width — and not frozen »)**, which said a rail is drawn « only if real use
asks for it »; this milestone is the moment he named for that call.
- *A — the drawer alone* (Q1 as ruled). Cost: none. Gain: nothing changes; two clicks per page change.
- *B — the same drawer pinned open* from ≈ 1 024 px, beside the column: the same component, entries, groups, badges,
  order; the burger hidden. Cost: one variant of `drawer`, the shell's layout, the drawer rules re-aimed. Gain: one
  click, the badges always seen — the native desktop navigation drawer.
- *C — a compact icon rail* (icons and badges, 72 px), the full drawer still behind the burger. Cost: a second
  arrangement of the entries (icons only), tooltips for the names, its own rules. Gain: less width taken; but a
  second way to draw the same menu, which the « cohérence » principle resists.

**Recommendation: B.** It adapts the existing component rather than creating one (« on crée pas de nouveau composant
on adapte »), restores the badges the hidden bar took away, and with C1 the column leaves the room for it at 1 024
and above.

**OPEN 3 — Where does a panel open on a desktop?** On the screen: a medium's panel, the journey, the follow sheet, the
« ⋮ » sheet, a torrent's panel (66 states) rise from the bottom over the full 1 280 px, covering half the list.
- *A — the bottom sheet as today*. Cost: none. Gain: nothing.
- *B — the bottom sheet, bounded*: the same rise, capped to the column and centred. Cost: one variant. Gain: the
  panel reads as one; it still covers the list.
- *C — a side sheet*: the same panel slides in from the right edge, ≈ 440 px, full height, the list readable beside
  it; drag-to-close follows the horizontal axis; Escape and the scrim unchanged. Cost: one variant (anchoring and
  closed transform), the drag reads one more axis, 66 states re-photographed, the panel rules re-aimed. Gain: the
  native desktop arrangement (Material 3 side sheet), the list and its panel at once.

**Recommendation: C.** The panel is the app's most-used layer; the side sheet is the expanded-width form of the very
same component in the native design languages he cites, and it gives most of « two panes » (OPEN 4) at the cost of
one variant.

**OPEN 4 — Does a desktop show a list and a screen side by side?** On the screen: a medium's screen (`/media/…`), a
resolution, the releases, a run open over the whole window, their list gone until Back.
- *A — no*: screens stay full-window routes (with OPEN 1 = C, in the column). Cost: none. Gain: § 16 stays exactly
  as delivered.
- *B — two panes on the list pages*: the screen opens beside its list on Acquisition, Médiathèque, Trackers from
  ≈ 1 280 px. Cost: high — the page host draws two routes at once, every screen gets a pane arrangement, § 16's
  « parent rendered » and the stack get new rules, every screen state re-walked. Gain: the desktop « mail » layout.

**Recommendation: A.** With OPEN 3 = C the frequent case (glance at a medium from its list) already keeps the list in
sight; B is the costliest contour of all and the one most likely to bend § 16, for a gain the side sheet mostly
gives.

**OPEN 5 — How many posters in a gallery?** On the screen: the library, the follows grid and Découvrir's posters stop
at 6 columns; tiles grow to ≈ 200 px at 1280 and 227 px at 1440, two rows per screen; the deck's single card is a
portrait poster cropped into a 1 250 × 640 landscape.
- *A — as today* (6 at most). Cost: none.
- *B — columns by tile width*: one or two more container steps (7 at ≈ 1 100 px of gallery, 8 at ≈ 1 300) so a tile
  stays ≈ 160–180 px; the deck's card keeps a poster's proportion, centred. Cost: `tile.ts` steps, the deck card's
  variant, R41–R50 re-aimed. Gain: a third more of the library per screen; the deck shows the poster.

**Recommendation: B.** It is the existing container query given one more step, the tile itself unchanged (R50 « the
same tile at the same metrics »), and the deck stops showing a crop.

**OPEN 6 — Does the desktop get keys and hover?** On the screen: only Escape and Tab work; nothing but buttons answers
the pointer.
- *A — as today*. Cost: none.
- *B — a small declared set*: `/` to the page's search, ↑/↓ through a list, Enter opens, Escape closes; rows, cards
  and tiles answer the pointer with a hover ground. No action exists only on hover or only on a key. Cost: one
  keymap module beside Escape's, one base rule, one harness rule. Gain: a desktop used from the keyboard and the
  pointer like a native app.
- *C — B plus per-action shortcuts* (e.g. a key to follow, to delete) and a shortcut legend. Cost: every action
  given a key, a legend surface, i18n, rules per action. Gain: power use; but a second way to every action, to keep
  consistent forever.

**Recommendation: B.** It is what a native desktop app gives by default, it adds no action anywhere, and it is one
module.

**OPEN 7 — Where do « + » and the selection bar go on a desktop?** On the screen: the « + » floats at the bottom-right
corner of the window (98 Acquisition states); in selection, « Annuler » sits at x 110 and « Supprimer » at x 1 180.
- *A — as today*. Cost: none.
- *B — bounded to the column*: the « + » sits at the column's bottom-right, the selection bar spans the column only.
  Cost: two variants. Gain: within one glance; the phone arrangement unchanged.
- *C — into the chrome*: the « + » joins the rail's top (OPEN 2 = B) or the header; the selection bar becomes the
  header's selection mode. Cost: two variants and a header arrangement; R-FAB rules re-aimed. Gain: Material 3's
  expanded layout (the FAB in the rail).

**Recommendation: B.** It follows mechanically from OPEN 1 = C, moves no action to a new place (the phone's « + »
stays the same button at the same corner of the content), and stays valid whatever OPEN 2 decides.

---

## 4. A first cut of phases — after his rulings

Cut by surface, as `method.md` asks (« A phase is one surface »), for the recommended answers (1 C · 2 B · 3 C · 4 A ·
5 B · 6 B · 7 B). A refused contour removes its phase or its line. Each phase changes the maquette FIRST, lands with a
rule that bites (invariant 11) and photographs its states at 1024, 1280 and 1440, and at 390 to prove the phone is
untouched.

| Phase | Surface | What lands | Its rule |
| --- | --- | --- | --- |
| 1 | **The shell** | the desktop threshold (one token, the shell's media query); the content column (C1) with the gallery opt-out; the drawer pinned (C2); the dialog bounded | every named state at 1024/1280/1440: the column ≤ its cap, no prose line > 90 characters, the drawer pinned and every page one click away; 390 unchanged |
| 2 | **The layers** | the side sheet (C3): anchoring, closed transform, drag axis, focus and scrim unchanged | every sheet state: the sheet at the right edge, ≤ its width, the list's first row visible beside it; drag-to-close by mouse |
| 3 | **Acquisition** | its three tabs, the cards and the ladder read in the column; `/add`, the resolution and the releases screens; the « + » bounded (C7) | the ladder's eight rungs within the card at every width; « Choisir » aligned on every candidate |
| 4 | **Médiathèque + the media sheet** | the grid's columns (C5), the list, the panel as a side sheet, the selection bar bounded (C7), the hero bounded | columns by width (7 at 1280, 8 at 1440); the selection's two buttons within the column |
| 5 | **Découvrir** | posters (C5), the deck's portrait card, the list | the deck's card keeps a 2:3 poster; the swipe by mouse |
| 6 | **Trackers** | torrents, roster, the torrent panel, the cross-seed sheets and confirmations | the roster's ratio and switch within the column |
| 7 | **Système, a run, Maintenance** | the sections and the run in the column (the log keeps its wrap) | the measure rule over Système's 38 states |
| 8 | **Réglages, Classement, Comptes, Profil, the gates** | the fields and the ranking editor in the column; sign-in, 404 and no-access unchanged | the ranking's number field beside its label |
| 9 | **Keys and hover** (C6) | the keymap and the hover ground, across every surface | `/`, ↑/↓, Enter, Escape walked on Acquisition, Médiathèque, Trackers; hover reads a ground; no hover-only action |
| 10 | **The close** | R413 extended to the three widths and the new arrangements; one independent reader looks at the screens at 1280 on tm-design, as `method.md`'s 390 reading | — |

**The order's reason**: phases 1 and 2 change the two shared components every surface sits in; once landed, phases
3–8 are mostly verification and the few per-surface lines § 1.3 names, and they can run two at a time without
touching the same file. Phase 9 is independent of all but phase 1.

**Points**: not estimated here — a plan is cut after the rulings, from this table.
