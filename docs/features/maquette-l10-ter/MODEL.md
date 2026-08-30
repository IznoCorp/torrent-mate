# L10-ter — the model: the application's frame, part by part

**What this file is.** Invariant 10 of `docs/reference/frontend-architecture.md` has been binding
since L09 — « the frame does not name the domain » — and its subject, the frame, was never
defined. This is the definition. It is documentary and structural: **no rendering is drawn
here**, because the rendering of every part below is already validated by the operator (mission of
2026-08-19) and unchanged. What was missing was not an image but a model — which part exists,
where it lives under invariant 10, what it owns, what it must never know, and **who draws it
today**, which `SURVEY.md` measured.

**How to read a part.** Each carries five lines: *what it is* · *where it lives* (the directory
invariant 10 assigns, and the file) · *what it owns* · *what it never knows* · *today → target*,
naming the lot that moves it. « Today » is the survey's finding; « target » is the plan's.

---

## 1. Three words, fixed here so the rest can use them

- **The frame** is everything on screen that is not a surface's content: the document skeleton,
  the chrome (top bar, tab bar, action button, the bottom slot), the layers (drawer, screen, sheet,
  dialog, popover, toast, scrim), the entry (splash, login, install proposal, theme), and the
  machinery beneath them (boot, address, history and ladder, page host, focus, scroll, geometry,
  liveness, offline). Invariant 10 is about this list and nothing else.
- **A surface** is what a feature draws inside a slot the frame offers. Four kinds, and the kind
  decides the address (D1) and the ladder step (D1b): a **page** (`#view`, its own path, replaces
  on switch), a **screen** (a route over the page, its own path, pushes), a **panel** (the sheet,
  a descriptor of facts, addressed in the query when its subject is stable), and a **transient**
  (dialog, popover, toast — no address; Back closes a dialog, a timer or a tap closes the others).
  A fifth kind does not exist: a feature that needs one has found a hole in this model and says so
  in its wave's design rather than inventing a layer.
- **The template** is the contract between the two: the frame offers a slot, a table entry and a
  set of verbs; a feature supplies a component, a descriptor and its own query slice. **A new
  surface never edits the frame's code** — it adds a row to a table the frame reads (`routes/`,
  the navigation table, `PAGES` in the page host) and a folder under `features/`. That is the
  whole test of whether the template is finished: the day §18's ratio page lands with zero lines
  in `app/`, `ui/` or `lib/`, it is.

---

## 2. The frame, part by part

### Part 1 — The document

*What it is.* `frontend/maquette/design/index.html`: the skeleton every module finds when it
evaluates, in an order that is itself a decision (the splash first so it paints first; the skip
link first in the frame; the layers last so they paint over the page; `#toast`'s live region
present before any text reaches it).
*Where it lives.* The document itself — outside every directory, which is right: it names no
module and no domain.
*What it owns.* The **ids that are contracts**: `#port`, `#view`, `#nav`, `#drawer`, `#dlg`,
`#toast`, `#scrim`/`#sheet` (rendered by React at these very ids), `#screen`, `#installbar`,
`#login`, `#splash`, `#fab`. The `pwa:start…end` block the login gate borrows. The viewport meta.
*What it never knows.* A page name, a title, a count. Its only words are the shell's own
(« Aller au contenu », the login labels) — and those are the `server` namespace's, served by
`serve.py` from `fr.json`.
*Today → target.* Correct as a skeleton. Two containers are declared EMPTY for the engine to fill
(`#nav`, `#drawer`) and one is dead (`#screen`). Target: the empty containers become React mount
points or disappear (a React tab bar renders `<nav id="nav">` itself, as `ui/sheet.tsx` renders
`#sheet`), `#screen` is removed with its three readers, and `theme-color` follows the theme
(B-233). **L15** for the containers and the meta; **L13** for `#screen`.

### Part 2 — The boot

*What it is.* `app/shell.tsx`: the order in which seams, store, cache, relay and root are
installed. It decides WHEN; the modules it calls decide WHAT.
*Where it lives.* `app/` — the application's shape, by definition.
*What it owns.* The order, and the single instant each owner is created (store, query client,
history).
*What it never knows.* An event name, a query key, a media title. It names FEATURES — seven
`install*` imports from `features/*` (`grep -o "install[A-Za-z]*" app/shell.tsx | sort -u`) — which
is the frame naming its parts once, the
same species as `router-tree.tsx`'s one import per page, blessed under invariant 10 by L10's
reading (`frontend-architecture.md` § 3, invariant 10, « re-measured at L10's close »).
*Today → target.* Already the frame's. It also re-parents `#shell` relative to `#screen`
(`shell.tsx:288–291`) — the one line that reads a dead node, gone with **L13**. The i18n bootstrap
(`src/i18n`, imported first for its side effect) is this part's too: the boot decides that the
words exist before the first component asks for them.

### Part 3 — The address model and the router

*What it is.* `lib/addresses.ts` (which page sits at which path, which screen belongs to which
parent, the tiers of D1), `app/router-tree.tsx` (which addresses exist), `routes/*` (one file per
address, thin).
*Where it lives.* `lib/` for the model, `app/` for the tree, `routes/` for the leaves — two of
invariant 10's three named exceptions, because an address IS a page's identity.
*What it owns.* Identity in the path, state in the query (D1); the parent floor under a cold
screen (D1b, rule 3); the sign-in address as a layer over a built frame.
*What it never knows.* How a page is drawn, or what its data is.
*Today → target.* Already the frame's, and complete. **Unchanged by any lot** — but see Part 5:
the page TABLE exists four times, and `PAGE_PATHS` here is one of the four.

### Part 4 — History and the ladder

*What it is.* Two halves today. `app/history-bridge.ts` owns the PRIMITIVES — `record`, `replace`,
`pushLayer`, `back`, `rewind`, `onBack` — on the one history instance the router also uses. The
engine owns the LOGIC: `onEngineBack` walks the ladder (drawer → `#screen` → sheet → page → exit
guard), `unwindLayer`/`__derouler` announce a layer's own pop so it is not read as a navigation,
`hideLayers` resets every layer for `__go`, `__closeLayers` says what a scrim tap closes.
*Where it lives.* `app/` — a ladder is the application's shape: it knows the NAMES of layers and
their rank, never what any layer shows.
*What it owns.* The ranking of layers; that opening pushes and adjusting replaces (D1b, rule 1);
that a top-level switch replaces (rule 2); the exit guard; the announcement of an unwind.
*What it never knows.* The content of any layer. A layer registers itself — a name, an `isOpen`,
a `close(pop)` — and the ladder walks registrations. The sheet already does exactly this through
`window.__panel`; the drawer and the dialog should register the same way.
*Today → target.* The ladder is missing a rung (**B-229**: the dialog pushes no entry and Back
does not close it, against D1's own third tier) and walks a dead one (`#screen`). Target: one
`app/layers.ts` holding the ranked registrations, the back handler, `closeLayers` and
`hideLayers`, with the engine calling it through the seam it already has. **The ranking is
frame; the move is behaviour** — so the drawer and dialog REGISTER in **L15** (a rung added,
held by a rule), and the handler itself moves out of the engine in **L13**, where the rest of the
navigation logic goes.

### Part 5 — The page host and the page table

*What it is.* `app/page-host.tsx` portals a page into `#view`, names it for a screen reader,
marks `#port` busy, and announces the handover both ways. Beside it, **the table**: which pages
exist, at which path, with which label, icon, badge derivation, and whether they sit in the bar.
*Where it lives.* `app/` — and the table is invariant 10's third exception, « whatever table the
shell reads to compose navigation ».
*What it owns.* One owner for `#view` at a time (R77); the page heading; `aria-busy`.
*What it never knows.* What a page draws or fetches. It knows a page's NAME and its `Body`.
`app/not-found.tsx` is the one page the FRAME draws — the answer to an address nobody serves — and
it belongs here, not to a feature: it names no domain.
*Today → target.* **The table exists four times**, and a fact that exists four times is stale in
three of them: `PAGES_OF()` in the engine (id, label, icon, badge, `offBar`, `fab`), `NAVIGATION`
in the engine (the drawer's grouping — Supervision / Système / Configuration), `PAGES` in the page
host (id → component), `PAGE_PATHS` in `lib/addresses.ts` (id → path). Target: **one table,
`app/navigation.ts`** — id · path · component · label key (`fr.json`) · icon · group · in the bar
· has the action button · `badge()` — that the page host, the tab bar, the drawer and the address
model all read, and that a new page joins with one row. The badge derivation is a FUNCTION the row
points at, exported by the feature (`features/acquisition/queries.ts` already computes « to grab
+ to resolve »), so the frame names the feature once and never its counters. **L15.** After it,
the engine holds no copy: `PAGES_OF` and `NAVIGATION` are subtracted, and the engine's `render()`
asks the seam for `fab` and the 404 fallback, the way it asks `__address` for a path.

### Part 6 — The chrome

*What it is.* The top bar (brand, connection mark, burger, avatar), the tab bar, the floating
action button, and the **bottom slot** — the place above the tab bar where a feature may put a
bar of its own (today: the library's selection bar) and where the install proposal and the toast
also sit, all clearing the bar through `--tm-bottom-bar-h`.
*Where it lives.* `app/` for the bars (`app/top-bar.tsx`, `app/tab-bar.tsx`,
`app/action-button.tsx`, `app/bottom-slot.tsx`); `ui/` for what they are built from.
*What it owns.* Geometry — safe areas, the published bar height (R84, one publisher), **the
z-order**, which today is not a decision but an accumulation: the tab bar is `z-50`; above it the
drawer and the install card (`z-[55]`), the selection bar (51), the popover, the harness panel
and the login (60), the splash (70); **and below it the dialog (48) — a confirmation opens with
the tab bar over its lower edge (B-237)**. One ranked list, in one place, is what this part owns;
`md:hidden` on the bar; the current-page mark (`aria-current`); the slot's stacking.
*What it never knows.* What a badge counts, what a slot contains, what the action button does
on a given page (the table says whether there is one; the page says what it does).
*Today → target.* The top bar is static markup with one React child; the tab bar is **rebuilt
by the engine on every `render()`** (B-231) from the engine's table; the FAB is toggled by the
engine; the selection bar is created by the engine and appended to `#device`. Target: the four
are React, reading the one table of Part 5 and the store; the selection bar becomes the
library's component rendered into the frame's slot (a portal into `app/bottom-slot.tsx`'s node,
which is how `#view` already works). **L15.** Node identity across a page switch becomes a
property (§ 3, P2) and a rule holds it.

### Part 7 — The layers

*What it is.* The drawer, the screens, the sheet, the dialog, the popover, the toast, and the
scrim under three of them.
*Where it lives.* `ui/` for the primitives — `ui/sheet.tsx` exists; `ui/drawer.tsx`,
`ui/dialog.tsx`, `ui/popover.tsx`, `ui/toast.tsx` join it; `app/` for the HOSTS that hold the
verbs and the state: `app/panel-host.ts` exists, and it is the precedent — a descriptor of facts
crosses, the markup is the component's.
*What it owns.* Open and close, the history entry each kind takes (Part 4), the drawer's own
dismiss gesture (`app/drawer-gesture.ts`, E-002 — it stays a frame gesture and moves with the
drawer in L15), focus in and out
(`app/focus.ts`, which already watches `data-open` on all of them and needs nothing from the
engine), `inert` on the background, the accessible name (a dialog reads its own heading; a drawer
is « Menu »), **and the scrim — with ONE owner.** Today the scrim is raised by the engine for the
drawer and the dialog and by React for the sheet, on one shared element; `hideLayers` and
`closeDlg` each clear it as a side effect. Target: the layer host raises the scrim when any
scrim-backed layer is open and no one else writes it.
*What it never knows.* What a dialog asks. The two engine producers hand `openDlg` an HTML
string today; they hand it a descriptor — `{ heading, body, actions: [{ text, tone, target }] }`
— exactly as `panel.open` receives one. A toast is `{ message, undo? }`. A popover is
`{ anchor, content }` where content is the feature's component. A drawer is the navigation table
plus the appearance control plus the served identity — three things the frame owns anyway.
*Today → target.* Sheet and screens are React; drawer, dialog, popover, toast are the engine's.
**L15** converts the four, each behind a descriptor on the seam the engine already speaks
(`window.__panel`'s sibling verbs), each with its rule, oracle green — the sheet's own conversion
is the proof this is « one kind of change ». The ten panel PRODUCERS (the descriptors' authors)
are not layers and not chrome: they are Part 12's subject.

**A BOTTOM LAYER COVERS THE TAB BAR — dictated by the operator on 2026-08-30, from a screenshot
of the acquisition sheet, and corrected by the operator the same evening after the steward first
wrote the opposite.** Today the sheet is anchored at the screen's bottom edge (`bottomSheet`:
`bottom-0 z-[47]`) and rises BEHIND the tab bar (z-50), so the bar stays painted over the sheet's
foot and the sheet's body reserves the bar's height by a padding to keep its last action reachable.
The operator wants the sheet to rise from the screen's bottom edge **over** the bar: **while a
bottom layer is open the tab bar is not seen** — the layer ranks above it, the padding that
reserved the bar's height goes with the overlap it compensated, and the scrim and the bar are both
under the layer. Inherent to the template, not a property of one sheet: every bottom layer (the
sheet, the dialog already at 56) paints over the chrome. It changes nothing of interaction —
`app/focus.ts` already marks `#nav` `inert` under a modal, and B-237 measured that the bar's
buttons were never hit-testable over one. P31 is the property; B-248 is the entry; L15 carries it
as a behaviour change in its own commit. The words are the operator's; the reading was the
steward's, wrong once, and this is the corrected one.

### Part 8 — Focus, scroll and geometry

*What it is.* `app/focus.ts` (focus enters a layer and returns), `app/scroll-restoration.ts`
(position per history entry), `app/bar-height.ts` (the runtime token).
*Where it lives.* `app/` — all three already.
*What it owns.* The focus stack; the scroll memory keyed by entry; one publisher of
`--tm-bottom-bar-h`.
*What it never knows.* A route, a panel, a domain. All three read the document and the history.
*Today → target.* Already the frame's. One debt stays written where it is: « programmatic
scrolling has one path » (plan § 1, the semantic index's door) is NOT paid — `focus.ts` writes
`#port.scrollTop` from the skip link and the engine writes `scrollTop` at **eleven** sites
(`grep -c "\.scrollTop = " legacy.js`), `applyState` on every page switch among them
(`legacy.js:9656`). Target: `scroll-restoration.ts` exports the one verb and every caller uses
it; the sheet resetting ITS OWN port is not a second path (a layer's port is not `#port`) and is
written down as such. The engine's writes go with **L13** (or with the producer that owns each, in
**L19**); the skip link's goes when the index is scheduled, and not before — churn with no defect
is churn. **Pull-to-refresh** (`#ptr`, engine-driven, `index.html:241`) is this part's: a gesture on
`#port` that knows nothing of what refreshes — it moves with the gesture vocabulary in **L12**.

### Part 9 — The entry

*What it is.* The splash (paints first, stays until the interface has rendered), the login gate
(a layer over a built frame, at `/login`), the install proposal (two platforms, two forms — R51),
the appearance (read from `localStorage` before first paint by the inline script the login gate
borrows).
*Where it lives.* `app/` — `app/splash.ts`, `app/sign-in.tsx`, `app/install.ts`,
`app/appearance.ts`; the inline script stays in the document because it must run before any
module does.
*What it owns.* When the splash lifts (`__loadingDone`); the gate's show/hide and its address;
who is asked to install and when (never over the gate, never when standalone, not twice a
session); **standalone-mode detection** (`display-mode: standalone`, read today only by the install
offer at `legacy.js:9878`) as the one place that knows whether browser chrome exists around the
application; the theme's three values and the meta that follows them (B-233).
*What it never knows.* What is behind the gate. The gate posts to `/api/auth/login` and reads a
yes or a no; rights (§17) are a feature's to read from `/api/auth/me`, never the gate's.
*Today → target.* All four are engine logic over static markup (`legacy.js:9678–9915`, `10116`).
L13 currently names « `/login` and the splash as components » among the engine's residue. **They
move to L15 with the rest of the frame** — they are the frame, and §17 (L18) redraws the gate for
Plex SSO and cannot do so while the gate is engine code (D5 allows no addition there).

### Part 10 — Liveness and data

*What it is.* `lib/relay.ts` and its siblings, `app/live-updates.ts`, `app/connection-notice.tsx`,
`lib/query-client.ts`, `app/store.ts`, `mocks/`.
*Where it lives.* As it is — L08 to L10 placed each under invariant 10 and measured it.
*What it owns.* Server state in the cache and nowhere else (invariant 4); the address in the
router; **only ephemeral interface state in the store** — which page, which tab, which lens, a
panel's descriptor, selection mode, phase. The relay's condition drawn once, outside the router.
*What it never knows.* An event name or a key (`features/*/live.ts` own those).
*Today → target.* Done. **Unchanged.** One consequence for the parts above: a layer's open state
(`panelOpen`) is already store state, so the drawer's and the dialog's become the same —
`drawerOpen`, `dialogDescriptor` — and the engine reads them through the seam rather than the
DOM, as `panel.isOpen()` already does.

### Part 11 — The measuring seams

*What it is.* The `window.__*` names (43 distinct across `design/src`), `states.js` (the
harness's table, registered with the engine), `styles/harness.css` (the phone frame), the harness
bar and panel.
*Where it lives.* Wherever it is; it ships nowhere — `harness.css` is imported once and by
nothing that ships; the seams die with the engine.
*What it owns.* Deterministic driving: `__go(id)` reaches a named state without a click.
*What it never knows.* Nothing the product depends on may depend on it: a seam is read by a rule,
never by a component.
*Today → target.* The seams that exist because the ENGINE needs them (`__address`, `__bridge`,
`__panel`, `__screens`, `__store`) die with it at **L13**; the ones the HARNESS needs (`__go`,
`__states`, `__queries`, `__relay`, `__mocks`) die at switchover with `harness.css`, and L13's
« nothing reads a `window.__` seam » is re-read accordingly in the plan — a harness driving seam
is not the engine's residue.

### Part 12 — What is NOT the frame and the engine still owns: the producers and the verbs

*What it is.* Ten `panel.open(…)` producers (every sheet's content: the follow sheet, the journey,
the « ⋮ », the account menu, a setting, the seasons, the acquisition status), the Découvrir feed
(list, poster, deck, footer), the episode popover's content, **and the 71 `data-*` verbs the
document-level delegation handles** (`legacy.js:10136–10894`; four more `dataset.*` keys are read
outside that span, by the gestures) — the actions those surfaces offer. `app/engine-data.ts` (34
domain words: what the engine reads with no component to ask for it) is this part's seam and dies
with the last producer.
*Where it lives.* `features/<domain>/` — a producer is a function from the cache to a descriptor,
and it belongs with what makes it change.
*What it owns.* What a surface says and offers.
*What it never knows.* How the frame draws it.
*Today → target.* All in the engine, all reading the sixty fixture families L13 was told belong
« to surfaces the engine still draws ». They belong to surfaces the engine still PRODUCES, and
D5's « surface by surface » applies to them exactly as it did to the pages: each producer moves to
its feature with its share of the fixture dying, oracle green. **No lot owes this today** (B-236);
**L19** does from here. The delegation's verbs move with their producers where a producer owns
them (`data-cancelsetting` is the settings feature's) and to `app/` where they are the frame's
(`data-drawer`, `data-navgo`, `data-sheet`).

### Not assigned to a part, and said so — `lib/queue.ts`

Invariant 10's own text deferred one arbitration « to the next wave »: whether a shared domain
module (`lib/queue.ts`, 169 domain words by the invariant's count, 6 by the arm's) belongs in a
`domain/` bucket rather than in `lib/`. **Decided here, and it is the phase's to decide under
§ 7.1**: no bucket yet. A bucket with one member is a folder for a KIND of file, which the tree
rule forbids; the ratchet (`check-frame-domain.py`) holds the count from rising; and L16 adds the
second shared domain module (a tracker is read by the acquisition and by the media sheet), which is
the day a `domain/` bucket has two members and a reason. L16's design takes it up.

### Part 13 — Offline and the worker (not built; modelled so L11 builds the right thing)

*What it is.* The service worker, the offline shell, the queue of mutations issued offline, the
platform entry points (share target, link handling).
*Where it lives.* `app/` for registration, update discipline and the queue; the worker source
beside `index.html`; the manifest and the worker route in `serve.py` until switchover.
*What it owns.* The cached SHELL — the document, the bundles, the icons, the fonts — and nothing
under `/api/` or the stream (`NetworkOnly`, as `web-ui.md` § PWA has it); the update discipline
(`registerType: 'prompt'`, check on load / visibility / 15 min, `/api/version` compared to the
baked commit, one reload); the queue's exactly-once departure.
*What it never knows.* What a mutation IS. The queue holds `{ key, request }` opaque envelopes a
feature's `queries.ts` enqueues; replay calls the same mutation function.
*Today → target.* The design host's worker caches nothing, deliberately (README). **L11**, after
L15 — an offline shell caches the chrome, and the chrome must be the product's before it is
cached.

---

## 3. « As close to a mobile application as possible », as properties a rule can read

The dictated objective is a mood until it is a list. Each row: the property, **the instrument that
reads it** (exists · to build · device-only), whether it holds today, and the lot that owns it.
**A property with no conceivable instrument is not on the list** — it was restated until one was,
or dropped and named in § 3.1.

**Seven rows were refreshed by L15, in the wave that made them move** — § 7.1's duty, not an
amendment: what the phase DECIDED is untouched and only the measurement under it changed. P1, P2,
P3, P14, P21, P28 and P31 read `true` with the rule that says so; P10 says it survived the two bars
becoming components. **And P1's instrument is not the one this table specified**: the column read
« `performance.getEntriesByType("navigation").length` stays 1 », which holds ONE ENTRY PER DOCUMENT
— so a full navigation makes a new document where the count is one again, and the reading cannot
come out the other way. A sentinel on `window` and the `load` event are what separate the two.

| # | Property | Instrument | Today | Lot |
| --- | --- | --- | --- | --- |
| P1 | **One document.** No full navigation between any two named states: a sentinel planted on `window` survives the walk, and no `load` event fires | R100 — and NOT `performance.getEntriesByType("navigation").length`, which holds one entry PER DOCUMENT and reads 1 either way | **true, and measured** (L15) | — |
| P2 | **A persistent chrome.** The tab bar's button nodes keep identity across a page switch and a store bump (`isSameNode`) | R100 | **true** since L15 — the bar is a component (B-231's cause removed) | — |
| P3 | **Back walks the ladder**, every rung: drawer, sheet, dialog, page, exit guard — each layer closes on Back and nothing else pops | R59 (four holds for the dialog since L15), R65, R69, R82, R94 | **true** — B-229 closed by L15 | — |
| P4 | **Opening pushes, adjusting replaces** (D1b) | R69 | true | — |
| P5 | **A declared transition between sibling surfaces**: a page switch runs inside `document.startViewTransition`, the rules are `::view-transition-*` in `base.css`, none is a script (D9) | to build — a rule reads `document.getAnimations()` mid-switch under `no-preference`, and reads NONE under `reduce` (invariant 14) | false — `grep -rn "view-transition" design/src` → 0 | L12 |
| P6 | **A shared element survives navigation**: the poster carries a `view-transition-name` on the card and on the sheet | to build | false | L12 |
| P7 | **The shell opens offline**: `context.set_offline(True)`, reload `/`, a named state renders | to build — `harness/pwa.py` is where it goes | false by design (the design host's worker caches nothing) | L11 |
| P8 | **A mutation issued offline departs exactly once** on reconnection | to build on L10's fake transport | false | L11 |
| P9 | **Installable, and the handler of its own links**: manifest `display`, `id`, icons (R52), and the entry points L11 names | R51, R52 exist for the first half; the second half is a decision (`QUESTIONS.md` Q4) | half | L11 |
| P10 | **Safe areas**: the two bars pad by `env(safe-area-inset-*)` and nothing else positions by a distance to an edge | static read of the bars' classes (the compositor guard's shape); the rendered check is device-only | true in the markup, and still true after L15 moved both bars into components | — |
| P11 | **Dynamic viewport**: the frame is `100dvh`, no `100vh` anywhere | `check-css-tokens.py`-shaped static read | **false** — no `dvh` in the tree; `base.css:54` is `height: 100%`; the only `100svh` is `harness.css`, which ships nowhere | L12 |
| P12 | **Contained overscroll** on `#port` | the compositor-CSS guard | true | — |
| P13 | **No zoom on focus**: every field ≥ 16 px | R83 | true | — |
| P14 | **Pinch-zoom allowed**: neither directive, on any host | axe 1.4.4 on every named state (`window.__states()`, 87 on 2026-08-30) **and `scripts/check-viewport-directives.py`**, which reads markup, script AND stylesheet — axe can only see a directive PRESENT on the document it audits, and B-230's was written into a branch that never fired here | **true, and no longer a landmine** — B-230 closed by L15 | — |
| P15 | **Touch targets at the floor** (WCAG 2.5.8) | axe `target-size` | true, 0 violations | — |
| P16 | **Gestures survive the compositor**: every gesture proved under a real touch stream AND a real mouse | R55, R98, `deck.py`, `drag.py`, `mouse.py` | true for the gestures measured | L12 extends |
| P17 | **The keyboard resizes the content, not the viewport**: `interactive-widget=resizes-content` | static read of the meta | **false** — B-234 | L12 |
| P18 | **Scroll restored per history entry**, pages included | R94 | true | — |
| P19 | **An action answers the finger before the network**: every mutation optimistic with a rollback | L09's rules | true where wired | — |
| P20 | **Reduced motion is a designed state** for every transition and gesture | R80 under both preferences; extended per transition | true for what exists | L12 |
| P21 | **The status bar follows the theme**: `theme-color` differs under `data-theme="light"` | R102, which compares the meta against the PAINTED ground through a canvas | **true** — B-233 closed by L15 | — |
| P22 | **Never « connected » over a dead link** | R95 | true | — |
| P23 | **No chrome flash at boot**: splash first, bar height published before first paint | R53, R84 | true | — |
| P24 | **No unvirtualised long list** (1 861 titles) | to build — a rule counts rendered rows against the data length | **false** — `features/library/page.tsx:371` is infinite scroll by `IntersectionObserver`, not virtualisation | L12 |
| P25 | **No tap flash**: `-webkit-tap-highlight-color: transparent` on every interactive element | the compositor-CSS guard | **false** — `grep -rn "tap-highlight" design/src design/index.html` → 0 | L12 (base layer) |
| P26 | **A long press selects no text** on a tile or a card (`user-select: none`) | the compositor-CSS guard, and the real-touch long press `selection.py` already drives | partly — `legacy.css` and one `select-none` on the drawer | L12 |
| P27 | **Standalone hides browser-only chrome**: what exists only because a browser is around it is absent under `display-mode: standalone` | a rule under an emulated `display-mode` media | unmeasured — nothing reads it but the install offer | L11 |
| P28 | **Focus survives a redraw**: `document.activeElement` is the same node across a page switch and a store bump | R100, with P2's | **true** since L15 | — |
| P29 | **No layout shift when a poster loads**: every poster box declares its size (`aspect-ratio` or width/height) | static read of the gallery variants, and a CLS probe on a named state | to measure | L12 |
| P31 | **A bottom layer covers the tab bar**: while the sheet is open the bar is not seen — the sheet's rank is above the bar's, its box starts at the screen's bottom edge, and `elementFromPoint` at the bar's centre answers the sheet | R101, with the bar's `inert` LIFTED for the length of one reading: `inert` takes an element out of hit-testing as well as out of the focus order, so a plain reading answers the sheet at 47 exactly as at 52 — the overlap needs no producing here, because the sheet is anchored on the screen's bottom edge | **true** — the sheet is z-52 and reserves nothing (B-248 closed by L15) | — |
| P30 | **Back-forward cache is not evicted**: `pageshow.persisted` is true after a walk out and back | a rule on a real navigation | to measure — the exit guard's handler is the kind of thing that evicts | L11 |

### 3.1 Discarded, and why

- **« Feels native », « fluid », « snappy ».** No instrument; restated into P2, P5, P19.
- **« 60 fps ».** A headless browser's frame timing says nothing about a phone's; L12's « interaction
  budget measured on a real device » is a device-only PROTOCOL — a written run with a date, like
  the oracle's certification — and it is not a gate. Kept in L12's Done-when as written.
- **« The app remembers where I was across a restart »** (per-page stacks). Considered and rejected
  in D1b; not a property.
- **Orientation** and **font scaling**. The harness measures 390 × 844 only, and R83 holds the
  16 px floor, not the layout under a 200 % text scale (WCAG 1.4.4's other half). Both are
  measurable and neither is a property of « a mobile application » specifically; they are the
  accessibility tier's to extend, recorded here so the omission is a choice.

---

## 4. B-142 — the instrument nothing has, and the mapping it needs

Three instruments compare the interface to what exists; none reads `product-intent.md`. The arm
that would needs one thing no grep can produce: **a declared mapping from each clause to the
surface serving it**. That mapping is `docs/reference/product-intent-map.md`, written by this
phase, one row per DOIT and NE-DOIT-PAS clause, each carrying a verdict and — where the verdict
is « to draw » — the lot that owes it. It is a directive file: the operator amends it, an agent
proposes.

**The arm's shape, so the lot that builds it builds the right one.** It reads the constitution's
numbered clauses **inside the two sections « Ce que l'interface DOIT faire » and « Ce que
l'interface NE DOIT PAS faire » only** — `^\d+\. \*\*(DOIT|NE-DOIT-PAS)-\d+` over the whole file
matches 24 lines for 23 clauses, because §19's fourth point begins « 4. **NE-DOIT-PAS-8 est la
limite dure.** » — reads the map, and refuses: a clause with no row; a `served`, `served,
unproved` or `partly` row naming a surface that does not exist in the tree (a route path absent
from `routes/`, a feature absent from `features/`) — `to draw` and `outside the interface` rows
name none and are exempt from that check; a `to draw` row, or the « to draw » half of a `partly`
row, naming no lot, or a lot absent from the plan; a `served` row naming no proof. **And one thing
it cannot do, said so nobody expects it**: it cannot tell whether a named proof READS the clause —
two rows of the first map named a print statement and a rule about PM2 processes as proof, and
only a reader found them. That check is a review's, at every amendment of the map. It prints one line per clause and never a
count alone. **Two traps it must not fall into, both paid for**: it must not be seeded « served »
from what exists (the map was written clause by clause against the tree, and five of its rows
say « to draw »); and a refusal carries its reason, or it gets worked around. It is placed in
**L15** — the first lot after this phase — because a specification nobody is allowed to build is
a sentence, and this phase is not allowed to build it (brief, « You implement nothing »).

---

## 5. The tension, settled the way the steward proposed

The method says the maquette is modified first; this phase implements nothing. **Documentary, with
structure mock-ups** — the tables above are the structure: parts, boundaries, ownership, the four
kinds of surface, the one table. No rendering mock-up was drawn, because the rendering of every
part is validated and does not change; a frame lot that moved a pixel would be a lot the oracle
refuses. If the operator wants a drawn structure diagram, it is one artifact away and changes no
decision here.
