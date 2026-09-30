# The prototype — this directory IS the product

`design/` is the next version of the TorrentMate web UI, and it REPLACES the shipped app: on
switchover day `frontend/src` is archived and this directory takes its place. Why, and what is in
scope, is not restated here: the constitution is `docs/reference/product-intent.md` (§ 15), the
mission of 2026-08-19 and the authority of this prototype are in `CLAUDE.md` § Authority, the
target architecture and the lot order are `docs/reference/frontend-architecture.md`, and where
the work stands is `IMPLEMENTATION.md`. This file is the developer reference of the prototype.

**The design reference is the TOKENS and the COMPONENT CATALOGUE**, never one file:
`design/src/styles/theme.css` (the scale and the palette), `design/src/styles/base.css` (the base
layer), and the `variants.ts` of `design/src/ui/` and of each surface, where every drawing
decision is written beside the class that applies it. `design/src/styles/harness.css` is the
phone frame: it is in the prototype's own build and in no production build, and it dies at
switchover.

## Layout

| Path | What |
| --- | --- |
| `design/` | the served root and a Vite project — `index.html`, `src/`, `assets/`, `sw.js` |
| `design/src/routes/` | one file per address: `/`, `/acquisition`, `/media`, `/discover`, `/trackers`, `/system`, `/maintenance`, `/settings`, `/settings/ranking`, `/account`, `/add`, `/media/$provider/$id`, `/quality/$name`, `/releases/$title`, `/resolution/$folder`, `/run/$runUid` |
| `design/src/app/` | the shell: frame, drawer, tab bar, layers, history bridge, page host, store, outbox, live relay |
| `design/src/features/` | one directory per surface (acquisition, library, media, releases, trackers, system, maintenance, settings, account) |
| `design/src/ui/` | the shared components and their `variants.ts` (card, chip, dialog, panel, popover, fact rows…) |
| `design/src/lib/` | shared logic without markup (addresses, clock, relay, gestures, navigation entries…) |
| `design/src/mocks/` | the mock layer that answers the contract in process (below) |
| `design/src/harness/` | the harness-only modules: named states (`states/`), `drive.ts` (`window.__go`), `publish.ts` |
| `design/src/i18n/fr.json` | every interface string (below) |
| `contract/openapi.json` | the maquette's own data contract |
| `harness/` | the rule suite, its host and `run.sh` — never served |
| `serve.py`, `host_identity.py`, `installable.py` | the design host (`tm-design.iznogoudatall.xyz`) — never served |
| `regions.json` | `$vocabulary` (the frozen CSS-name exceptions, read by the no-French guard), `$reportedDefects`, `$adversarialReview` (the rule set R1… with what each rule is for) |

`npm run build` (in `design/`) emits `dist/` (gitignored): the envelope from `index.html`, the
module bundle under `dist/vite/`, the built worker `dist/sw.js`, and `dist/assets` linked to the
real files. `npm run typecheck` and `npm test` (vitest) are the fast checks.

## The shell, in one page

- **The router is the SINGLE writer of the URL and the history.** `go()` in the shell is the only
  caller of the router's `navigate()` (R76, `navigation.py`), and it flushes after every call so
  one call writes one entry — the router batches its commits into a microtask, and two writes in
  one task would otherwise merge. Every other module speaks to history through
  `window.__bridge` (`app/history-bridge.ts`). Ownership of a history entry is decided by the
  entry's own SHAPE, never by matching the address against a list of routes.
- **`rewind(n)` settles several entries in one announced operation.** A multi-entry
  `history.go(-n)` coalesces into ONE popstate, so the announcement is raised once, never `n`
  times (raising it `n` times swallows the operator's next real Back). `ident.py` holds it.
- **Every page is drawn by the page host** (`app/page-host.tsx`) into `#view`, and a page draws the
  same whichever surface it was reached from (R77, `page_host.py`). No rule drives a page by
  mutating the store in place: an in-place write keeps the object's identity, nothing subscribed
  moves, and the measurement lands on whatever page was drawn before.
- **The panel is one component, opened through `window.__panel`.** A producer never builds markup:
  it hands `window.__panel.open(descriptor)` a typed descriptor of ordered blocks of declared kinds,
  and an undeclared block is refused (R56, `panel.py`).
- **Screens are real routes** — the media sheet, the quality profile, `/add` (its `q` and `mode`
  are router-owned search params), the resolution and releases screens, a run — reached through
  `window.__screens`, cold by their address or from inside the app (R75, `screen_addresses.py`).
  An unknown subject renders the screen's own honest empty case instead of raising.
- **Scroll position follows the HISTORY ENTRY, not the address.** The shell keeps a map keyed by
  each entry's `key` (`app/scroll-restoration.ts`), reads the outgoing screen's offset while it is
  still in the DOM, and reapplies it once the incoming port exists and its images have settled.
- **The design's sources, plural.** A rule that greps « the design » reads `common.py`'s
  `DESIGN_SOURCES` (`index.html` plus the component sources) through `design_source()`, never one
  file; reading a declared source that no longer exists raises, deliberately.
- **The live host serves the BUILD, and so does the harness.** `serve.py` compares the newest
  mtime of the build's inputs against `dist/index.html` and rebuilds under a lock before serving,
  so an edit is visible at the next reload; a failed build answers 503 with its own last words
  (R73, `switchover.py`). The harness measures a COPY of the built document, which isolates a
  rule's corruption of its copy from what the host serves.

---

## The rule, and it is binding

> **The prototype is the reference. It is changed FIRST, and the code follows.**

This applies to every future evolution of the interface, not only to the initial rebuild:

1. **A design change starts in the surface's own `variants.ts`, or in `src/styles/theme.css`
   when it is the vocabulary that moves.** Adjust it there, check it against the harness, then
   derive the code.
2. **If a region cannot be built as drawn, amend the prototype and record why.** The code
   never diverges "temporarily" — a temporary divergence is how an interface turns into a
   patchwork.
3. **A divergence found between the app and the prototype is a bug in the app**, unless the
   prototype is explicitly amended first.
4. **Nothing ships that the prototype does not show.** A new surface is drawn here before it
   is coded.

## The scale — a design constant is a STEP, and it is declared once

The scale is one block of tokens in `design/src/styles/theme.css`, and its steps are the only
design constants the application CSS spends.

| Family                                                                          | Steps     | What it answers for                                                                                                                                                                                     |
| ------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--spacing-1…9`                                                                 | 9         | padding, gap and margin — one ramp, because a gap and a pad are the same distance seen twice                                                                                                            |
| `--text-1…8` + `--text-display`                                                 | 8 + 1     | the reading ladder, plus one display size cut against the tile it fills rather than against that ladder                                                                                                 |
| `--radius-1…4` + `--radius-full`                                                | 4 + 1     | corners; the pill is written once, so nobody re-invents `999px`                                                                                                                                         |
| `--duration-1…4`, `--duration-loop-1…3`, `--ease-standard`, `--ease-emphasized` | 4 + 3 + 2 | motion. Loop periods are named APART from response durations: a spinner is a rhythm, not an answer to a touch, and folding one onto the other makes the interface feel wrong in a way nobody can locate |

`scripts/check-css-tokens.py --arm scale` holds it, and it is a **wall rather than a budget**:
the first declaration on no step is refused, named by selector, property and literal, with the
step it sits nearest to so the reader can fold it in one edit.

Motion is held in **two dimensions**, because a curve is not a number and no pattern written for
lengths will ever see one: the duration must read a step of the ramp AND the easing must be one
of the two the scale names. A keyword easing, a `cubic-bezier(…)` written out beside the named
one, and a transition naming a duration and no easing at all — which renders the browser's
initial `ease`, a curve nobody chose — are each refused.

**Two selectors are exempt, by name and with their reason**, in the arm's own `EXEMPTIONS`
table: `.dcard .cap` reserves the footprint that clears the floating add button, and `.hero`
pulls its title up over the poster's melt. Both are measurements of a composition, not distances
anyone would want on a ramp.

**The block carries TWO marker names on one line**, `scale:start` and `login:scale:start`,
because it has two readers: the scale guard, and `serve.py`, which composes the standalone
sign-in page out of `login:*` chunks and must emit this one FIRST — a chunk folded onto a step
inherits a token the composed page would otherwise never declare.

**`--tm-bottom-bar-h` is the one custom property that is a MEASUREMENT rather than a decision** —
the bottom bar's drawn height, safe area included, known only once the bar is on screen. It is
published by the SHELL (`design/src/app/bar-height.ts`); its uses keep their `, 0px` fallback, because a runtime token
resolves to nothing until the script has run and the symptom is a flash. R84 (`runtime_tokens.py`)
holds the three ends.

## Traps this stylesheet paid for

- **The composed sign-in page does not get the application CSS** — a MARKER-reading rule can stay green over
  a page missing a declaration it still serves; the login arm reads `serve.py`'s own `extract()`
  calls instead.
- **A contrast repair verified on one theme repairs one of the two** — measure a colour in BOTH
  themes, or half the palette is uncertified.
- **A `font:` shorthand declares a size without ever writing `font-size`** — an extractor that
  claims to cover a property must read shorthands too, or a hard zero can be true of what it read
  and false of the stylesheet.
- **A tone has THREE jobs and no colour does two of them well** — a signal, a label and a fill
  each need their own token (`--danger`, `--danger-text`, `--danger-fill`), decided once.
- **« Secondary » written as `opacity` is not a colour at all** — it blends into whatever sits
  behind it, so what reaches the eye is a tone the palette never declared.
- **`stopPropagation` does not stop a listener sitting BESIDE yours on the same node** — the tap
  registry answers in CAPTURE on `document`, so a swallower must call `stopImmediatePropagation`
  and be registered first, or the click it meant to swallow fires the verb under the finger.
- **After a TOUCH drag the browser suppresses the click itself** — a hold about the click that
  ends a drag drives it with a MOUSE, or it measures the browser, not the guard.
- **`offsetParent` cannot see a closed `<details>`** — Chrome hides its content with
  `content-visibility: hidden` and the boxes stay laid out, so a hold reading only `offsetParent` is
  green over a shut fold; ask `checkVisibility()` too.
- **The mock layer intercepts `fetch` INSIDE the page** — so a Playwright response listener sees
  nothing at all on the API routes, and a rule built on one measures an empty list rather than a
  silent interface. A claim about « the request that left » is read in the layer's own register
  (`GET` the address back, or `window.__mocks.answered()`), never in a network trace.

## Every state has a name, and knows how to reach itself

`window.__go("<id>")` drives the prototype into a state **without clicking**.
`window.__states()` returns every declared id — count them there, never in a document.

This is what makes a rule deterministic. Without it, measuring "the blocked card" requires
knowing how to make one appear — and that knowledge is exactly what evaporates over time. With
it, a rule says `__go(state)` and measures.

Three orthogonal dials of the prototype's store:

| Dial          | Values                        | What it changes                      |
| ------------- | ----------------------------- | ------------------------------------ |
| Data scenario | `real` · `loaded`             | the real system state vs a dense one |
| Surface phase | `ready` · `loading` · `error` | every surface goes through all three |
| TMDB account  | connected · not               | Découvrir's full vs degraded mode    |

The states cover, among others: the startup screen, the entry screen and its refusal, the five urgency
sections in both scenarios, Suivis in its three modes plus its two empty cases, Découvrir full /
degraded / exhausted / loading, the add screen idle and with real results, the follow sheet on a
22-season complete catalogue and on a holed one, the journey sheet, the "⋮" sheet, the library in
grid and list, its empty search, its three lenses, selection mode, single and bulk delete
dialogs, loading and error on every surface, the resolution screen, the media sheet in its
variants, the navigation drawer, the two install proposals, the arbitration screen in both of its shapes, and Système.

`harness/states.py` drives every one of them and asserts each one renders content, has no horizontal
overflow and raises no JS error. **A state that renders nothing fails the pass.**

## What is real in here, and what is not

Read from the live system:

| Data                                                                                | Source                          |
| ----------------------------------------------------------------------------------- | ------------------------------- |
| Library titles, categories, counts (1,861 items)                                    | `library.db`                    |
| 12 follows with their true states                                                   | `acquire.db`                    |
| Incomplete series and their fractions                                               | `library.db`                    |
| Owned episode numbers, season by season (247 series, 9,218 episodes)                | `library.db`                    |
| Episode titles and air dates (9,779 episodes)                                       | TMDB                            |
| Staging contents                                                                    | the staging directory           |
| TMDB suggestions                                                                    | the engine, actually executed   |
| 319 wide visuals, 172 posters (64 of them at gallery definition), 55 cast portraits | TMDB / TVDB, re-encoded as WebP |
| 288 YouTube trailer ids                                                             | TMDB `/videos`                  |
| The grab cadence                                                                    | the live scheduler              |

Not real: the release candidates on the "choose another release" screen — no tracker is
queried — and the timings and counts of the `loaded` scenario, which exist so density can be
judged. Both are labelled as such in the design notes.

**The copy ages by design.** The system keeps running: the scheduler searches twice a day and
increments each follow's attempt counter in `acquire.db`, so the embedded counters drift and
`content.py` (which compares the cards against the LIVE database) goes red with no code change.
`resync.py`, the tool that rewrote those counters, is broken since the engine's removal (B-563);
until it is repaired, correct a counter by hand, as data, in a commit of its own.

**Two scenarios**, switched from the harness (the **≡** button):

- **`real`** (default) — the exact state of the system. Calm: nothing to grab, nothing in
  flight, two stuck folders. This is what makes the **rest states** judgeable; a prototype
  that is always busy never shows them.
- **`loaded`** — a dense state, for judging density and scrolling.

---

## The mock layer — what it is, and how to drive it

**The prototype is NOT connected to a backend.** A mock layer is not a connection: it answers the
maquette's own contract, in process. The wiring belongs to the switchover.

**What it is.** `design/src/mocks/` — one module replaces `fetch` with a table of routes, one per
operation `frontend/maquette/contract/openapi.json` declares, counted by
`window.__mocks.routes().length`. No service worker: a worker's registration is asynchronous and
the first paint must already be answered. It is installed synchronously in the boot, behind the
build-time constant `__MOCKS_BUILT_IN__`.

**Where its data comes from.** `design/src/mocks/seeds/*.json`, first projected from the old
engine's data (a rename of keys and a regroup of arrays, nothing invented). Their builder is gone
(B-563): after `scripts/refresh-maquette-fixture.py` rewrites a fixture, edit the affected seeds
by hand in the same commit.

**How to drive it**, from the console or from a rule — `window.__mocks`:

| | |
| --- | --- |
| `.routes()` | every route it answers, `METHOD template` |
| `.scenario()` | the scenario in force: the frozen clock, the default latency, the per-operation overrides |
| `.scenario().operations.<operationId> = { status: 503 }` | make one operation fail |
| `.scenario().operations.<operationId> = { latencyMilliseconds: 250 }` | hold one answer back |
| `.inFlight()` | how many requests are in flight |
| `.quiet()` | a promise that settles when none is |
| `.reset()` | the seeded state and the empty scenario, both back |

**A request no route claims FAILS and names itself** — 404 with the method and the path. Never a
pass-through, never a silent empty object: a mock that answers something to everything is a mock
that hides a missing handler.

**What holds it**: `harness/mocks.py` (R85) and `scripts/compare-contracts.py --check`.

---

## Two rules the prototype itself re-taught, the hard way

- **A named state RESETS the mock scenario.** `window.__go` puts the layer back, latency included,
  so a scenario asked for BEFORE a state is a scenario asked for nobody: set it after.
- **A pinned COUNT in a unit test moves with a seed row.** Adding one row to a seed moves the
  figures `design/src/**/*.test.ts` pins; `npm test` says so.
- **The library's listing is PAGED, and `total` is not what the layer holds.** `total` answers the
  library's own 1 861; `loaded` is what the seeds carry. A reading that judges the seeds by one
  page, or by `total`, invents holes that are not there.
- **R7 — `minmax(0, 1fr)`, never `1fr`.** An `auto` grid track's floor is the item's intrinsic
  size, which can blow a fixed-width frame out past its bound.
- **R8 — an author `display` rule beats `[hidden]`.** Any class declaring a `display` must
  declare its own hidden case, or `el.hidden = true` does nothing.

## One card, one behaviour — and one panel per medium

This is the contract every list in the interface obeys. It is written here because
it is the kind of thing that gets re-decided per screen, and then the screens
disagree.

- The **poster** opens the media sheet. One tap, the most frequent path.
- The **card body** opens the bottom panel.
- A **gallery tile** is all poster, so the tap is already spoken for: there the
  panel answers a **long press**.
- The **panel carries every action** available for that medium — including any
  action also drawn inline on a card.
- An **inline action** exists only where a section exists _for_ that action
  (« À récupérer », « Ça coince »). It is a shortcut, never the only way in.

**The last two clauses are the ones that matter**: an action reachable from a single surface
disappears the moment that surface is displayed differently, which is what R43 holds.

**The panel is derived, not passed in.** One builder reads what is true about the
medium — followed, incomplete, in the library, to grab, blocked, has a sheet —
and every action follows from that, which is what makes the panel reached from a
gallery identical to the panel reached from a card, by construction rather than
by vigilance.

An element states **which** panel it addresses (`data-panel="media:<title>"`) and
never how to build it. Addressing it by list index is forbidden: an index belongs
to the list on screen rather than to the medium, so it means something different
in each lens, and a numeric title (« 1917 ») read as an index opens the panel of
whatever film sits at that rank.

### Two builders, and a descriptor between them

The contract above is enforced by there being **one builder per shape**, not one per
screen:

| Shape         | Builder                        | Who uses it                                                  |
| ------------- | ------------------------------ | ------------------------------------------------------------ |
| Card          | `cardMarkup` (`ui/card-markup.ts`), `ui/card.tsx`'s parts | every list — urgency sections, follows, library, « À traiter », « En cours » |
| Tile          | `tileMarkup` (`ui/tile.ts`)    | every gallery — the library's three lenses, the follows grid, the suggestions |
| Release card  | `ReleaseCard`/`DecisionCard`   | the resolution and release screens — **not a medium**        |
| Selection row | `selectionRowMarkup` (`ui/rows.ts`) | a mode of the LIST, not a variant of the card |
| Commit row    | `commitRowMarkup` (`ui/rows.ts`), its gesture `lib/commit-swipe.ts` | a row a swipe DECIDES on release — Découvrir's list: left passes, right rejects. The swipe row (`swipeRowMarkup`) OPENS drawers and waits for a tap; the two differ on purpose |

**The card takes a descriptor of FACTS**, listed in the source next to the function:
title, kind, sub-line, reason, fraction, chip, caption, fresh, strip — and, added for
the torrent card (L16-bis), the figures on the state line (`details`), the figures on
the annotation line (`notes`), a line of marks (`marks`: a toned chip, a coloured dot
whose word is its label, or a plain figure) and a byte progress (`progress`, the
native `<progress>`, which is not the strip: the strip says which STEP, this says how
much of one). A view that
wants to show something not in that list is describing a fact the card does not yet
know about — the fix is to add the fact, never to pass ready-made markup. _An envelope
guarantees nothing about what it carries._ This is what keeps « one component with
variable display » from turning into a component with a dozen appearance flags.

**A tile is not a card with a flag.** It is a different layout — all poster, name
below — so it stays a separate builder. What the two share is the descriptor and the
behaviour contract, which is where the guarantees actually live.

**The panel is built the same way, and was the last envelope.** `openSheet` used to take
ready-made markup, so every surface assembled its own: three head shapes had grown that way —
one with a poster, one with an avatar, one with neither — two of them out of inline styles,
which belong to no stylesheet and are therefore exported nowhere. It now takes a descriptor
(title, meta, an optional poster or avatar, a chip) plus ORDERED blocks of declared kinds —
`note`, `faits`, `actions`, `saisons` — because the order is the caller's: a follow panel puts
its primary action above the season matrix and its secondary group below. A block type nobody
declared raises rather than drawing nothing.

There is one panel builder and no fallback: « nothing is known about this medium » is one of
the truths it derives from (R56, `harness/panel.py`).

**Not everything that looks like a card is one.** A release candidate shares the markup
and is a different object: it has no sheet and no panel, because it is one candidate
among several for a medium already named on the screen. It says so with
`data-nonmedia`, so the check tells them apart by construction rather than by knowing
which screen draws which (R46).

**Every list uses the same metrics** — poster 49 × 73.5, padding 9, radius 8, title 13.5, gap 10
(R47). The 49 is derived from the card's anatomy: the poster fills the shape whose purpose is
RECOGNISING a medium (title, sub-line and synopsis, 72.9 px of content, two thirds of which is
49). Card HEIGHTS differ, and that is content. A list is a list: no surface keeps its own card.

**A reason never truncates** (§12, R48). It wraps and the card grows; half a sentence is not
a reason.

### Galleries answer their container, not the window

Every gallery — the library's three lenses, the follows grid, Découvrir's posters — draws
the same tile at the same metrics (R50).

The **column count follows the scrollport's width**, through a container query, and never
the window's:

| Scrollport | Columns |
| ---------- | ------- |
| < 460px    | 3       |
| ≥ 460px    | 4       |
| ≥ 620px    | 5       |
| ≥ 820px    | 6       |

A media query would read the viewport, so a 390px frame sitting on a 1280px desktop would be
told it has room for six columns it does not have. The container query asks the width actually
available, and the app gets the same answer because there the scrollport IS the window.

`harness/cards.py` proves all of it; R41–R50 in `regions.json` state it.

## It installs, and the invitation depends on the platform

`serve.py` serves a manifest, the brand icons and a service worker, so the prototype installs
to a home screen like the app does. **The worker precaches the SHELL** — the document,
the bundles and the icons — and nothing under `/api/` or the stream: a navigation goes to the
NETWORK first and falls back to the cache, so a design judged live is never served yesterday's
build; the update discipline reloads once when the served build stops matching the running one,
signalled by `/build.json` (never the commit, since the design host's tree stays dirty across a
whole editing session).

**The worker is BUILT, not written in `serve.py`** — its source is `design/sw.js`, the build
writes the actual bundle names with their content hashes into `design/dist/sw.js`, and `run.sh`
copies it into the served copy. **The precache happens in TWO MOMENTS**, forced by the host: a
worker installs from whichever document is in front of it, which here is the SIGN-IN GATE (`/`
answers 401 there), so the install attempts everything and requires nothing — the running
application then asks for the shell to be completed (`cache-shell`), and **R105 reads the cache
after boot and refuses a shell with no bundle in it**, so a completion that failed once repairs
itself the next time.

**The invitation is actually offered, and it has two forms, not cosmetic variants (R51):**

- **Android and desktop** capture `beforeinstallprompt` and prevent its default, replaying it on
  a gesture — the banner offers a button.
- **iOS Safari** fires nothing and offers no API — the banner _is_ the guide: it walks
  Partager → « Sur l'écran d'accueil » → Ajouter.

It sits above the tab bar, since a bottom-anchored close button lands unreachable under the fixed
bar. iOS also needs `apple-mobile-web-app-capable` and `apple-mobile-web-app-title` — it reads
neither the manifest's `display` nor its `short_name`.

**It installs as a DIFFERENT application** — « TorrentMate Design », in the manifest's `name`,
`short_name` and `id`, and in the iOS meta — so it never shares a home-screen entry with the
shipped app. **It serves its own icons**, one family of three sets (app plain, staging cyan ring,
design host yellow ring) generated by `frontend/scripts/make-design-icons.py` so the ring cannot
drift between them; the MASKABLE variants take a circular ring inside the safe zone instead, since
a launcher crops to its own shape and Android prefers the maskable one for the home screen. R52
compares every served icon against the application's, byte for byte.

## A decision is a FOLDER, and the screen never forgets it

The scrape could not name what is inside it — that is the whole reason the question exists — so
what the operator is asked about is the thing on disk, set in the mono face and never cleaned
up. Its card promises neither a media sheet nor a panel, for the same reason a release candidate
promises neither: there is no medium here yet. It says so with `data-nonmedia`, the marker R46
already defines.

**The score is printed only when it separates.** « Lucky » is the case that settles it, and it is
real: four of its five candidates came back at exactly 1.00. Printing « 100 % » four times
suggests a ranking that does not exist and invites the operator to trust it. When the leaders
tie, the screen says so instead — and that sentence is the reason a human is being asked at all.

**A candidate wears only its own poster.** The lookup falls back to a year-stripped title
elsewhere, which is right for a medium with one identity and wrong here: it handed « Lucky
(2006) » the picture of « Lucky (2026) », on the one screen whose job is to tell four
nearly-identically-named series apart — while the row underneath said the provider had none.
Where a title is a proposition rather than an identity, only its own picture will do.

**Three ways out, and the third was missing.** Pick a candidate, search by hand, or LEAVE IT AS
IT IS. The last exists in the engine (`dismissed`) and existed nowhere in the interface, so a
folder whose automatic result was right had no way of being agreed with — one could only ever
contradict the machine. A pick takes the folder out of the queue.
« Laisser tel quel » means LATER: the folder stays queued, set
aside, in « Mis de côté », a folded section at the end of « À traiter » that counts neither in
the tab's number nor in the bar's badge (`harness/set_aside_is_later.py`).

Every exit returns to « À traiter », the tab open, whichever way the screen was reached — a pop
from the list, the page laid beneath on « À traiter » from a cold link. There is no « Suivant »
and no « n sur m en attente »: the tab's count carries the number (`harness/return_to_todo.py`).

`harness/decision.py` states all of it; the data is the ten real rows of `scrape_decision`, with
one ambiguity replayed as pending so the screen can be judged.

## Signing in is followed by a wait, and the wait is drawn

Two waits follow a sign-in, and both used to be blank: the browser fetching a document of
several megabytes, then the interface rendering out of it. The first belongs to the gate — it
still shows while the POST and the download run, so a tap on « Se connecter » answered with
nothing at all. The second belongs to the document.

One screen covers both. It is **declared first inside the frame**, and that is a correctness
property rather than tidiness: a browser paints what it has parsed, so a screen sitting after
the embedded artwork would appear only once the wait it exists to cover is over. It carries the
brand, an indeterminate bar — nothing here knows how far along the load is, and a bar that
pretended to would lie at every frame — and no control at all, because there is nothing to do
yet. The first render drops it, synchronously: a timer either uncovers a frame that is not
drawn or holds a ready interface, and both are visible.

The gate gets the same screen by **extraction**, the rule it already obeys for the login card
(R49), and reveals it on submit. R53 (`harness/startup.py`) checks all of it, gate included —
it starts `serve.py` on a scratch port and drives a real submit.

**Leaving is the same story told backwards.** A message is not a destination. The session IS the cookie, and the cookie belongs to the
server, so the server is asked to drop it **first** and the entry screen only reflects what has
already happened — an entry form shown over a live cookie is contradicted by the next reload.
R54 (`harness/logout.py`) checks both halves, and the invisible one is the one that
matters: it asks the server, afterwards, whether the session is still accepted.

## The cut is by the nature of the trouble

Five surfaces, and what decides which one a panel belongs to is not the page it came from:

| A medium in trouble                      | **Acquisition › « À traiter »** |
| ---------------------------------------- | ------------------------------- |
| A tracker in trouble (ratio, obligation) | **Trackers**                    |
| A machine in trouble                     | **Système**                     |
| A setting                                | **Configuration**               |
| A command run against the library        | **Maintenance**                 |

A tracker's trouble speaks where the tracker lives — its ratio under its own threshold, a refused
identifier, a broken obligation — and the badge on the bar's « Trackers » tab says it (organisation
ruling 12: each thing speaks where it lives, one badge per tab, no notification box).

`Contrôle` does not survive this cut **as it is**. Production stacks blocked media on top of disk
and provider health with nothing saying why they share a page; each of its **eight** panels
(`ToHandleList`, `ScrapeActivityPanel`, `LastRunDigest`, `StalledPanel`, `AcquisitionSummaryCard`,
`SchedulersPanel`, `CompactHealth`, `PipelineControls`) has a home under the rule. The full
placement of what remains, and the `/control` and `/pipeline` pages still owed, are L24's
(`docs/features/maquette-l24/DESIGN.md`).

**A state wears a BADGE, and it has four tones.** `success` — it works. `alert` — it does not, and
something must be done now. `warning` — important but not critical, a disk nearly full. `info` — a
fact that is neither a success nor a fault, which is what a QUANTITY is: « 1 863 titres » is neither
good nor bad, it is how big the library is. Badging a number green is how a green stops meaning
« it works ».

`alert` is the operator's word and `danger` is the stylesheet's; the mapping lives in ONE place.
**A tone has two jobs that one colour cannot do**: `--danger` is a FILL behind white text; a
label takes the tone's text variant, and all four clear AA in **both** themes.

**PM2 reports a scheduled job as `stopped` between two runs.** That is the literal truth about the
process and a lie about the system — repeated on screen it paints six red rows on a machine in
perfect health. A service is judged on whether it is UP, a scheduler on whether it RAN, and the two
lists never share a vocabulary.

**A command that DELETES cannot be run for real before it has been run blank.** Not a confirmation
dialog renamed: a dialog asks « are you sure », which is answered without reading, while a blank run
produces a list, which has to be looked at. A real deletion cannot be rehearsed here — staging writes
to the real disks — so what the interface owes is the look BEFORE, not a net after.

`harness/machine.py` states it, counting both PM2 lists and checking the 26 commands against the
engine's own registry in both directions.

## A layer is not a route, and closing one leaves the page alone

The drawer, the media screen and the bottom panel each push a history entry so a back closes
them without eating a page. Closing one then pops that entry — and **that pop must not be read
as a navigation**. The entry underneath describes where one ALREADY is, so applying it undoes
whatever the close was accompanied by, and re-renders the page one is standing on.

Both halves of that were on screen at once. Tapping a drawer entry changed the page for a frame
and the drawer's own pop put it back, so every entry in the menu led nowhere. And closing a
bottom panel opened halfway down a list rebuilt the list and sent it home — nobody had reported
that one; the mutation proving the rule bites is what found it.

So an unwind **announces itself** and the popstate handler consumes the announcement, and a
drawer navigation settles history itself — its writes wait for the traversal to land
(`walk.afterUnwind`), never issued in the same task, where the asynchronous pop would land after
them and overwrite them.

**Where Retour goes is § 16 as amended, and every entry carries the trail that says it.** Each
history entry holds the pages under it from the floor up, with their indexes (`trail`,
`lib/navigation-entry.ts`; written by `app/trail.ts`), and the verb that switches the page says how
the tap lands (`app/frame-verbs.ts`, `landingOf`):

- **a bar page** (Acquisition, Médiathèque, Trackers, Découvrir) chosen from the bar or the menu
  UNWINDS the trail onto the floor, from any depth: Retour from it reaches the entry page, and
  the entry page's own Retour arms the exit guard;
- **a menu page** (Système, Maintenance, Réglages, Profil) chosen from the menu or the account
  menu STACKS on the page left, the drawer and any rubric open under it given back first: a back
  from the destination reaches where one was before opening the drawer;
- **a link inside a page**, a screen or a panel STACKS on what it was tapped on — the entry page
  included, so the guard arms only with the entry page at the bottom; a panel's entry is kept,
  and Retour gives the page and the panel back;
- **a page already on the trail** moves to its top and is never on it twice (the operator's
  ruling of 2026-09-30): Acquisition → Système → Acquisition → Réglages → Système gives back
  Réglages, then Acquisition.

`harness/journey.py` walks every edge by finger (R-navigation-a, its table in
`harness/navigation_edges.py`) and holds B-577 (R-navigation-b).

`window.__pages()` exposes the page table, so a control can be checked against what the
interface can actually render rather than against a list written beside it — one drawer entry
named an id no page carried and answered a tap with a message.

**A fallback onto a phantom token is a landmine.** `background: var(--sidebar-accent, var(--primary))`
with `--sidebar-accent` defined nowhere paints the background in `--primary` — which is what the
label is coloured with. Contrast 1.00, a label in invisible ink. R61 forbids only BARE `var()`,
so the fallback made it look like a considered choice and the rule looked away. Contrast is
measured as PAINTED, colours converted through a canvas and never parsed: `getComputedStyle`
returns the space the author wrote — `oklch()` here — and three numbers pulled out of it with a
regex built for `rgb()` mean nothing.

`harness/drawer.py` holds all of it; R65 states it.

## A trap that cost real time: **screenshots are not proof**

**Every capture a rule takes (`common.shot`, gitignored under `harness/__screenshots__/`) is a
reading aid for a failed rule, never a proof** — two captures of the same unmodified file can
disagree on several states from animation and async-decode timing alone. A rule reads bounding
rectangles and computed style instead. For « is this CSS rule dead? », a selector count of zero
over every state, combined with « the source never writes this class name », is a proof rather
than a sample.

## And one trap that no synthetic test can catch

**Swipe gestures must claim the horizontal axis with `touch-action: pan-y` on the row itself**
(never on an ancestor) — a passive listener that claims nothing lets the browser take the gesture,
and the swipe then works only under synthetic events, which are never cancelled; a real thumb
finds nothing. `harness/touch.py` drives every gesture through real browser input
(`Input.dispatchTouchEvent`) rather than a synthetic event object, which is the only instrument
that can tell the two apart.

**Every gesture answers a pointer, not only a finger** — the interface is used from a desktop
browser too, at a phone width — held by `harness/mouse.py` (every gesture with a real mouse) and
`harness/deck.py` (the deck with touch-type pointer events). Two consequences that follow: the end
of a drag is listened for on the window (a mouse release outside the frame never reaches a
listener bound to the scrollport), and images inside a draggable surface disable the browser's
native picture drag.

**A pointer stream is not a touch stream on the scrollport**, where `pan-y` is not available to
claim (it intersects down onto siblings that need both axes) — so the scrollport reads the finger
from touch events and everything else from pointer events, one implementation, two sources, never

---

## `harness/` — the rule suite

**Run it with `harness/run.sh`, never by hand.** The script builds the prototype, refreshes the
copy the rules read and starts the harness host before measuring anything — that copy is manual,
and a stale one measures the previous build without saying so. Every script fails through its
exit code, not through its output: a script that only prints cannot fail.

```bash
frontend/maquette/harness/run.sh                             # every rule (CI runs it on a lot's pull request)
frontend/maquette/harness/run.sh --rules settings.py back.py # only the named rules, over one build
frontend/maquette/harness/run.sh --ci --shard 2/4            # a CI runner's share
```

The full suite runs in CI (`.github/workflows/harness-full.yml`), not on IznoServer. The fan-out
defaults to half the processors (`TM_HARNESS_JOBS` overrides it). One headless Chrome per rule; the rules below are
committed because they encode recipes that cost time to get right, and because a rule with no
script is a sentence in a file.

| Script                | What it proves                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `sweep.py`            | all views render content, no horizontal overflow, device at 390px, no JS error. **A view that renders nothing fails.**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `scen.py`             | the same sweep across both data scenarios, with explicit sub-view reset between runs                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `states.py`           | every named state renders, without overflow or JS error                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `common.py`           | not a rule: the plumbing every script borrows — how a verdict prints, how a run ends, how the document is opened past the startup screen. Twelve copies of the same `check()` meant a fix to the reporting had to be made twelve times, and one change to the opening cost twenty-eight hand edits                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `deck.py`             | the deck answers a swipe either way — left skips and comes back, right dismisses with an undo                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `factories.py`        | not a rule: the `cva()` factory reader — every typed variant's anchor, base and branches read as text; no rule borrows it since B-500 retired the check mark `resolution_card.py` held to `iconButton`'s size |
| `gallery.py`          | one tile pattern in every gallery                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `mouse.py`            | every gesture answers a MOUSE too: the interface is used from a desktop browser                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `surfaces.py`         | every surface the interface draws is reachable and renders                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `audit.py`            | rules R1–R10 and R20–R23 across every state, and it announces how many rules it EXECUTED                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `cards.py`            | rules R41–R50: the card and gallery contract — poster to the sheet, body to the panel, no action reachable from a single surface, the same panel from a card and from a gallery                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `bugs.py`             | one test per defect found by hand                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `inter.py`            | swipe, infinite scroll, load error + retry, delete dialog                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `follows.py`          | Suivis conformity across its three modes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `selection.py`        | the two delete paths from the grid: long-press and selection mode                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `scroll.py`           | no form interaction moves the scroll position                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `scroll_keeps_place.py`| R175 (40 holds): the in-flight list keeps the reader's place — walked by finger and by wheel at the phone width, on a desktop in the frame (fresh arrival and the return from a resolution, where lazy posters are still loading) and out of it, the port never goes back up under a downward gesture (B-490), and a gesture moves at most one container, the port (B-491) |
| `cold_follow_panel.py` | R176: a follow panel typed cold onto a page that does not load the medium's identity (`/acquisition?panel=follow:<a library title with no follow>`) offers « Voir la fiche » once the identity read lands, draws the served owned cells — compared with the same panel opened on the Médiathèque, which must carry an internal hole — and heads with an `<img>`, not the initials |
| `follows_list_posters.py` | R177: in Acquisition › Suivis list mode, every row whose seed carries a poster draws an `<img>` in its `card/poster` — read on the element, because the initials fallback fills the same box |
| `release_candidates.py` | R194: every title offered « Chercher une autre release » has a release to choose — the titles are enumerated from the surfaces (every card of Acquisition › Suivis and › En cours tapped, the verb read off its panel), each picker opened through its own verb and its drawn rows counted, so an empty list names its title |
| `filters.py`          | filters filter, and their parts sum to the whole                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `actions.py`          | the simulated behaviours really mutate the state                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `dest.py`             | every button has a destination                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `ident.py`            | identify ≠ follow: the context picks the verb — and the journey settles the history it stacked (the panel's entry and `/add`) in ONE announced operation, landing where the walk stood before `/add`, the next back still worth exactly one step                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `pop.py`              | the episode date popover, in all its states                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `chrome.py`           | R51: the harness bar covers none of the app's fixed controls, in every named state, at both sides of the 520px breakpoint                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `back.py`             | R59: the back gesture walks the path in reverse — tabs and lenses included — closes a layer first, and at the root warns instead of leaving, closing only on a second back within five seconds                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `settings.py`         | R60: the settings are navigated by what one wants to change, never by file; every real setting belongs to one rubric and is identified by its label alone — subject then action, in French; nothing is written until the save bar names the files it will write; a secret says only whether it is set                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `palette.py`          | R61: no bare `var(--x)` names a property the document never defines, and the brand colour is actually painted on the wordmark, the sign-in button and the startup bar                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `entry.py`            | R62: the sign-in screen renders identically on the host and inside the prototype, and the host redeclares nothing the reference owns                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `content.py`          | R63: a follow's card carries what `acquire.db` really holds and phrases it as « En cours » does; a library row carries the synopsis, clamped to the largest number of lines that fits, and shows nothing when the NFO has no plot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `drag.py`             | R64: a row opens a drawer either way, one at a time, without firing the tap — measured on Chromium AND WebKit, where the drawer used to spill past the card; and a REVERSAL settles the row back rather than leaping, sampled during the drag because a jump is a discontinuity                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `url_state.py`        | R69: the URL carries the state (DOIT-10) — walking writes the address, a reload lands on the same screen, only what differs from the opening state is written, a wrong address is left exactly as typed, and back walks the addresses in reverse                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `journey.py`          | R82: Back retraces the path taken (§ 16) — a page opened cold has a floor under it, the not-found surface's own way out RECORDS rather than spends the guard and the floor that switch lays is reused by every later one, switching a top-level page stacks nothing (the drawer's and the account menu's switches included), the exit guard arms at the TOP and nowhere else, a setting leaves no entry, and a Back returns to the real origin with the setting it was made under. What each group reads beyond the address differs: the cold floor and the guard's arming read `armedExit`, the not-found walks and the page switches read `history.length` AND `armedExit`, a setting reads `history.length`, and the return to a real origin reads both off the sheet and neither off the search. None of them reads the address alone: the destination's address is right whichever stack was built under it                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `address.py`          | R68: an unknown address renders instead of raising, names what was asked for and offers a way out; the account surface draws the one real account, compared against `web.json5`, and marks the place of the others EMPTY                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `machine.py`          | R67: Système is the machine, Maintenance is what one does to the library — no blocked medium on Système, no scheduler called « stopped » between two runs, both lists counted against `pm2 jlist`, every command checked against the engine's registry in both directions, and a command that DELETES inert until it has been run blank — each of the five lists held to being FOUND, with rows to judge, before anything judges its contents, because they are located by their French heading and « no row is wrong » is true of no rows at all                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `drawer.py`           | R65: the drawer is a place one passes through, not a route — every entry names a page that exists and arrives there, the destination takes the drawer's own history entry, closing a layer neither rebuilds the page underneath nor loses where it was scrolled, and every entry is legible measured as PAINTED                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `install.py`          | R51: the install offer is actually OFFERED — `beforeinstallprompt` captured, its default prevented and replayed on a gesture; the iOS guide raised by an iPhone user agent; nothing offered to an installed app, over the entry screen, or after a refusal                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `pwa.py`              | R52: the LIVE host is installable from the first document a phone reaches — manifest, icons that load, worker registered and controlling, offline fallback cached. Runs against `tm-design.iznogoudatall.xyz`, not the local server                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `startup.py`          | R53: the startup screen is declared first, covers the frame, offers no control, is gone after the first render, and the gate the server builds shows the same screen — extracted — from the submit onwards. Starts `serve.py` on a scratch port                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `logout.py`           | R54: signing out lands on the entry screen AND the server stops accepting the session. Starts `serve.py` on a scratch port                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `panel.py`            | R56: one panel builder, no caller passing markup, no inline style inside a panel, one heading, no action without a destination, and an undeclared block refused                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `decision.py`         | R57: the arbitration screen — the folder as subject, no sheet or panel promised, no engine token on screen, a score printed only when it separates, each candidate wearing only its own poster, three ways out, and answering emptying the queue on both lists                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `touch.py`            | R55: every gesture under REAL touch input (`Input.dispatchTouchEvent`), which the compositor can cancel — the pull to refresh on seven surfaces, the swipe between views, ordinary scrolling, the swipeable row and the deck                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `images.py`           | R70: the design's SOURCES embed no image and every `assets/` reference resolves to a file |
| `screens.py`          | R71: a screen above another one — back redraws the screen it covered (query and scroll included) through both exits, one more back leaves the layer, and a result card carries no inline action in its foot: the panel is the single path to the act                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `shell.py`            | R72: the Vite shell emits a real envelope — the module entry is present with the correct format and the named bundle file exists under `dist/vite/` |
| `bridge.py`           | R74: history goes through the bridge — zero raw history calls across the design's sources, the journey works through both exits, a deep URL lands on its promised state, `__go()` preserves history depth |
| `switchover.py`       | R73: the host serves the build to the byte, rebuilds stale sources before serving, and a broken build answers 503 that says so — proven against a scratch design root, never the real source                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `server.py`           | the prototype's HOST, and a rule about itself. `--serve 8899 <root>` is what `run.sh` starts and every rule reads: it serves the built copy at `/` and folds every address with no file behind it onto the document, so a page at a real path (`/media`) and a deep screen address (`/add`) can be requested cold rather than only reached from inside an already-loaded document. Two sets keep their 404 — `ASSET_PREFIXES` (`/vite/`, `/assets/`, `/src/`) and `ASSET_PATHS` (`/sw.js`, `/manifest.webmanifest`, the two icons) — because they are resources, never addresses. Run bare it is a RULE: nine holds over its own behaviour, including that the live host on 8899 is this server and not a plain `http.server`, and that neither entry point will bind a port belonging to the reverse proxy. `start_server` is the scratch variant a rule raises on an EPHEMERAL port — it is handed 0 and yields the port the kernel gave it, here and in `screen_addresses.py` alike, because a fixed port is a list that drifts and rules picking from the same list collide on one socket                                                                                                                                                                                                                                                                                                                                                                                                    |
| `screen_addresses.py` | R75: a screen route answers a real address, cold, and only while it is open — `/profile/$title` opens the promised screen with no journey and no click, every image the document loads at that depth resolves through `<base href="/">`, one back from a walked-to screen lands exactly where the walk started with the address returning to what it was, a wrong deep address renders honestly instead of raising, and `/add?q=…` opens with its field and results already drawn                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `library_sort.py`     | R78: every sort goes BOTH ways, and each way says its own name — the panel offers the six explicitly (« Ajout récent » / « Ajout ancien », « A → Z » / « Z → A », « Les plus incomplets » / « Les plus complets »), exactly one is marked, the control on the count line reads the direction in force, the reversal is measured on the ROWS DRAWN over a library narrowed until the whole set fits on one page, and the sort stays out of the address — a preference, not a place                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `library_load.py`     | R79: the library loads more, says when it cannot, and lets one try again — the end of the sample says it IS the end of the sample and how many titles the prototype really carries, a failed page says what remains valid, and « Réessayer » really loads, measured with the scroll sentinel NEUTRALISED because it produces the same outcome for a different reason                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `focus.py`            | R81: what an assistive technology is told, and an audit cannot see — a layer takes focus when it opens and gives it back when it closes; opening the drawer or the sheet moves focus INSIDE it and marks the background `inert` (never `aria-hidden`, which hides a subtree from a screen reader and leaves every control in it tabbable, the worst of both); `Escape` closes the layer on top through the verb the engine already publishes; closing gives the background back and returns focus to the control that OPENED it; and the skip link is the first stop of the tab order and lands FOCUS on the main region, not merely the scroll position. None of this is visible to an automated audit, which reads the markup of one moment where this reads a SEQUENCE — the two instruments do not overlap. Measured on a fresh page for the tab-order holds, because the browser's sequential focus starting point is set by the last CLICK and `blur()` does not move it. It also holds what the interface SAYS while it works: the main region carries `aria-busy` while a page loads and stops carrying it once loaded — set in the page host, the one place that knows every page's phase, because marked page by page the eighth call site is the one that gets forgotten — and every error surface announces, summed over EVERY state whose id says error rather than sampled on one, after a first version drove a single state, found a single surface and printed that as a census |
| `page_host.py`        | R77: one owner per PAGE, and the container never holds two — a page draws the same whichever surface it was reached from; the document-level delegation still reads the `data-*` attributes the pages emit, each driven by a REAL tap; leaving a page with an unsaved change and coming back leaves the shell alive |
| `navigation.py`       | R76: the shell owns navigation through one door — `navigate(` appears exactly once under `design/src/`, inside `go()`'s own body; a round trip through the door writes one history entry per call and back walks them in reverse, judged by the screen's own observed state, never by `history.length`; two navigations issued in the same task, no `await` between them, still produce two separate entries                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `type_scale.py`       | R83 (9 holds): the browser holds the type scale — every form field renders at least 16px, so a focused field no longer zooms iOS, and every rendered size inside the measured regions sits on a step of the scale, over every named state. The step set is READ FROM THE DOCUMENT, never carried as a pixel list that measures the scale as it was on the day the list was typed; an element whose size is INHERITED is not judged on its own, because naming it would name the wrong element. This is what a static count of literals cannot see, and it found its first defect the day it was written — a half-pixel size in an inline style, on a paragraph six states draw. Both readings are held before anything is judged against them: a scale read as empty puts every size off-step, and a field no state draws is a field nothing measured                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `hiding.py`           | R86 (26 holds): what the interface declares invisible IS invisible, read from the served document and never from the stylesheet. The design notes, hidden by default and shown by their button — BOTH directions, because a hold on the pressed state alone passed on a tree where the notes were visible in both. The `hidden` attribute made to bite on the five elements the register named, plus a probe element the markup has never met wearing an INLINE display, because five prove the elements and only the probe proves the rule; `hidden="until-found"` is spared and held. The action button, which shares the bottom-right corner with the message by construction: the collision itself is a hold, then the button is absent while a message is up, still absent while it leaves, back once it has gone, and a page with NO action does not acquire one when a message closes. Every dismissal path, including the capture-phase one that does not go through the seam and is the one that broke. And the application's own guidance, which must NOT be hidden with the annotations. WHAT IT DOES NOT READ: the stylesheet, a real finger, and every element that could ever carry the attribute |
| `identity.py`         | R87 (26 holds): the drawer names what the host is serving, or says it cannot — and the two are held apart, because the defect was never silence. A published identity is shown, branch and commit, with a dirty mark that is absent when the tree is clean and a DETACHED head named as one rather than shown as a branch called « HEAD ». With nothing published, the block says so and states no version and no build sha of its own. On the server side: the document really carries it; a scratch repository the rule builds proves it is computed PER CALL and not at boot, that a clean tree is not called dirty, and that outside a repository it names nothing rather than guessing; and a branch name that ends a script element is escaped rather than emitted — held on the SCRIPT BODY, because the corrupted payload parses as valid JSON and `json.loads` would pass. With its resource emptied the block shows its keys, never « undefined ». WHAT IT DOES NOT READ: `git` (it never re-derives what it checks), the host's real password, and production's own version endpoint |
| `runtime_tokens.py`   | R84 (8 holds): `--tm-bottom-bar-h` is published, it FOLLOWS the bar, and it has ONE publisher — exactly one file under `design/src/` writes a `--tm-` property, and it lives under `app/`. That is counted over the whole tree rather than grepped in the engine, because a rule checking « the engine does not publish » stays green over a second publisher added anywhere else, and two writers of one property agree until they do not. The value is read against the bar's own rendered height in the SAME evaluation, then the bar is forced to a height no state draws — through the cascade, never an inline style, which is what a wrong publisher would be writing. The probe is held first: a forcing that did not force would let « the value follows » pass over a publisher that had stopped observing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

### Serving the prototype — two hosts, and the harness measures only one

|                  | Port     | What                                                                                                                              | Started by                 |
| ---------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| **Harness host** | **8899** | `harness/server.py --serve`, rooted in `/private/tmp/tm-refonte`, serving a COPY of the build at `/` and folding every router-owned address onto it | `run.sh`, or by hand       |
| **Design host**  | **8712** | `serve.py`, scrypt password-protected (`tm-design.iznogoudatall.xyz`)                                                             | PM2 (`torrentmate-design`) |

`harness/common.py` pins the first one: `PROTOTYPE = "http://127.0.0.1:8899/"`. Never
8710/8711/8712/8899 for a server of your own — `harness/server.py`'s `RESERVED_PORTS` names all
four, and the reverse proxy routes the first three to production, staging and the design host.

- **`python3 serve.py 8899` is wrong**: `serve.py` is the DESIGN host, it answers 401 without a
  session, and the harness would then measure the sign-in screen — every rule green, nothing
  measured.
- **A plain `python3 -m http.server` is wrong too**: a page sits on a real path, a plain server
  answers 404 to every one of them, and the router renders its not-found page instead of the
  surface under test. `harness/server.py --serve` folds any address with no file behind it onto the
  document and keeps a 404 for the resources that really are files (`/vite/…`, `/assets/…`,
  `/sw.js`, `/manifest.webmanifest`). It is rooted on the copy of the BUILD, never on `design/`,
  which would serve unbuilt TypeScript.

What `run.sh` does, for a by-hand reading of one rule:

```bash
# 1. Rebuild, and refresh the copy the harness reads — BEFORE EVERY RUN.
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets

# 2. The harness host — check before starting, it is usually already running.
lsof -nP -iTCP:8899 -sTCP:LISTEN || (python3 frontend/maquette/harness/server.py --serve 8899 /tmp/tm-refonte &)
```

**The copy is the document AND the bundle, and half a copy is worse than none.** Refreshing
`wrapped.html` while leaving the previous `vite/` behind serves today's markup against yesterday's
shell; `vite/` is removed before it is re-copied, never merged into. Without the `assets` symlink
every image reference resolves to a 404. A stale copy of the rule scripts can also end up in
`/tmp/tm-refonte`: running those measures the previous version. The envelope carries the viewport
meta; without it Chrome falls back to the 980 px layout viewport and every measurement is wrong.

**Two rules measure the LIVE host instead** — `pwa.py` (R52) and `entry.py`, because
installability and the sign-in gate are things only a real server hands out. `serve.py` is read
once, at boot, so **after any edit to `serve.py`, `pm2 restart torrentmate-design` before reading
the suite** — until then the host answers its own build-failure page and those two go red naming
symptoms unrelated to the change.

## Language of the source

Every comment in this directory — HTML, CSS, JavaScript, Python — is written **in English**,
and carries no reference to a work session, a phase, or a dated decision. It must read years
from now, out of context. Interface copy quoted inside a comment stays in French, because that
is what the screen says.

**So is everything else the source NAMES.** Identifiers, function and type names, **class
names — code and CSS alike** — **file and directory names**, and every message a tool prints:
English, on the day the thing is written.

Two things are NOT covered by that rule, and confusing them is how a rule goes quiet:

- **The French the app RENDERS.** A hold asserting « En cours » keeps asserting « En cours »
  — the interface speaks French. Translating a word inside a rendered vocabulary does not go
  red, it goes SILENT: `"des erreurs"` became `"des errors"` once and no rule noticed, because
  a rule that measures nothing passes.
- **Data and addresses.** `data-*` names and values, route paths, `__go` state ids, the
  follow/episode state tokens, the config keys the settings dictionaries are keyed by: those
  are contracts, and renaming one moves the contract rather than a name. The frozen ones are
  listed, each with the reason it was kept, in `regions.json`'s `$vocabulary`.

## The data-* vocabulary

**One attribute, `data-part`, its value namespaced by `/`**: `card`, `card/title`,
`card/poster`. The namespace names the owning DOM concept; the leaf names the role.
Rules anchor on `data-*`, never on a style class (`docs/reference/frontend-architecture.md`, D4).

**Boolean state attributes carry no value, and the list is DERIVED, not
enumerated.** An attribute is one when the harness asks whether it is THERE —
`[data-open]`, `hasAttribute('data-open')` — and never what it says (`data-open`,
`data-empty`, `data-blocked`, `data-skeleton`, …). Derive the list from the rules; never keep
one by hand.

**In a component, a state attribute is `data-open={isOpen || undefined}` — never
`data-open={isOpen}`.** React renders `data-*` as strings, so `false` becomes the
string `"false"` and `[data-open]` then matches ALWAYS: a rule goes green while it
measures nothing. `harness/attrs.py` demonstrates it in the live document.

A NAMING attribute's VALUE is a name someone chose, so `scripts/check-no-french.py`
reads it (`markup_text.NAMING_ATTRIBUTES`: `data-part`, `data-region`, `data-tone`,
`data-action`, `data-side`). An ADDRESS is not a name: `data-go="profil"` names a page,
and the guard leaves it alone.

**An emission may be imperative.** An element built with `createElement` carries its anchor
beside the assignment, `element.dataset.part = "episode/popover"`, with a literal value: a
computed value is read by nothing.


## Where the interface's French lives

**No interface string lives in the code.** The shell's copy is in
`design/src/i18n/fr.json`, read through `react-i18next`:

```tsx
const { t } = useTranslation();
<h2 className="h2">{t("screens.profile.minResolution")}</h2>
```

- **Key convention**: `screens.<screen>.<slug>` for a screen's prose, `settings.labels.*` /
  `settings.subjects.*` / `settings.units.*` for the panel's three dictionaries, `common.*`
  for what several surfaces share, and `server.*` for the pages `serve.py` serves. The screen
  segment is the screen's ENGLISH name (`media`, `profile`, `add`), like its component and its
  file.
- **`serve.py` reads the SAME file.** The sign-in gate's title, the two 503 pages, the offline
  page and the manifest's description come from `fr.json`'s `server` namespace, read per
  request — the same discipline as the login screen's markup, which is EXTRACTED from the
  prototype rather than restated. One source, nothing to keep in step.
- **Extract, never retype.** Cut the string out of the JSX and paste it into `fr.json`. A
  retyped string is a defect even when it looks right: it renders correctly while the
  reference is broken, and the copy is the only place anyone ever looks.
- **A few literals stay French, and say why.** A data value, a `data-*` value, a route
  parameter: each carries a `// french-ok: <reason>` (or `# french-ok:`) pragma on its own
  line, the line above, or the line below. A pragma citing no reason is itself a violation.

**All of this is enforced in CI**: `python3 scripts/check-no-french.py` (strings, identifiers,
file names, class names; its arms are listed in its own docstring).
