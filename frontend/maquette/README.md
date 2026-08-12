# The prototype — this directory is the visual reference

**`refonte.html` is the design reference for the TorrentMate web UI. Any change to the
design starts here, not in `frontend/src`.**

It is the operator-approved interactive prototype of the mobile-first interface:
`/acquisition` (three views), `/mediatheque`, `/arrivees`, `/systeme`, plus the media
sheet and the shared shell. It is **not an illustration**. It is the source the shipped UI
is derived from, and the reference every measurement compares against.

Design spec: `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md` — §7
is the parity methodology and is the part that matters most.

---

## The rule, and it is binding

> **The prototype is the reference. It is changed FIRST, and the code follows.**

This applies to every future evolution of the interface, not only to the initial rebuild:

1. **A design change starts in `refonte.html`.** Adjust it there, check it against the
   harness, then derive the code.
2. **If a region cannot be built as drawn, amend the prototype and record why.** The code
   never diverges "temporarily" — a temporary divergence is how an interface turns into a
   patchwork.
3. **A divergence found between the app and the prototype is a bug in the app**, unless the
   prototype is explicitly amended first.
4. **Nothing ships that the prototype does not show.** A new surface is drawn here before it
   is coded.

This rule is also recorded in `docs/reference/product-intent.md` and in the project's root
`CLAUDE.md`, so it survives outside this directory.

---

## Why this file exists at all

A previous rebuild of one page cost days it should not have. Its post-mortem names two
causes:

1. **Translating instead of transplanting.** Prototype fragments were grafted onto existing
   component skeletons. Every detail *resembled*; the whole diverged.
2. **Eyeball validation.** "Present in the DOM" was treated as "conformant". Several
   "it's ready" claims collapsed on contact with the operator's thumb.

Underneath both: the parity harness was built **after** the code, as a repair, and it
measured a **deployed** build — so every loop cost minutes and measuring became something to
skip.

This directory inverts that. The prototype comes first, the CSS is generated from it, and the
measurement runs locally on every change.

---

## The four working rules

### 1. The prototype is the source. Change it FIRST.

See the binding rule above.

### 2. The CSS is generated, never retyped.

`scripts/extract-maquette-css.py` lifts this file's app CSS block, scopes it under `.tm`, and
writes `frontend/src/styles/ps/app-surface.css`.

- **Editing the generated file by hand is the defect**, not a shortcut.
- `make check` re-runs the extraction and fails on drift — the same guard that protects
  `openapi.json` / `schema.d.ts`.
- To change a pixel, you change the prototype.

The `<style>` element is physically split into two commented blocks:

- **BLOCK 1 — PROTOTYPE HARNESS**: the phone frame (`.stage`, `.device`), the demo top and
  bottom bars, the design-note callouts (`.note`), the scenario switch. **Never exported.**
- **BLOCK 2 — APPLICATION CSS**: everything that ships.

Extraction works from an **allowlist** of selectors declared in `regions.json`, never a
blocklist — so a prototype-only helper can never silently reach production.
`harness/export.py` fails on any BLOCK 2 class that is neither covered by the allowlist nor
classified as harness, and on any dead rule.

### 3. The DOM is a contract, checked offline.

Per region, a vitest test renders the component with the shared fixture and asserts that the
emitted **tag chain + class chain** equals the prototype's. jsdom, milliseconds, no browser.
This catches "translating" at the moment it happens.

### 4. Zero divergence is a build condition, not a ticket.

`scripts/parity-probe.py` walks `regions.json` in two headless contexts — the prototype and a
production build it serves itself from `frontend/dist` — at 390 × 844 / DPR 2 / mobile / touch,
and diffs
`getBoundingClientRect` plus a fixed `getComputedStyle` subset. The allowlist is explicit and
**every entry carries an inline justification**. Wired into `make check` and CI.

The probe is **append-only over regions**: each pass re-runs everything already at zero. This
work has already produced the defect that rule exists for — after a change to one view, only
that view was checked, and another page shipped blank.

---

## Every state has a name, and knows how to reach itself

`window.__go("<id>")` drives the prototype into a state **without clicking**.
`window.__states()` returns the 51 ids. The **≡** button in the harness opens a panel listing
them all.

This is what makes the parity probe deterministic. Without it, measuring "the blocked card"
requires knowing how to make one appear — and that knowledge is exactly what evaporates over
time. With it, the probe iterates `regions.json` → for each region, the states it is visible
in → `__go(state)` → measure.

Three orthogonal dials the panel exposes:

| Dial | Values | What it changes |
|---|---|---|
| Data scenario | `reel` · `charge` | the real system state vs a dense one |
| Surface phase | `prete` · `chargement` · `erreur` | every surface goes through all three |
| TMDB account | connected · not | Découvrir's full vs degraded mode |

The 47 states cover: the five urgency sections in both scenarios, Suivis in its three modes
plus its two empty cases, Découvrir full / degraded / exhausted / loading, the add screen idle
and with real results, the follow sheet on a 22-season complete catalogue and on a holed one,
the journey sheet, the "⋮" sheet, the library in grid and list, its empty search, its three
lenses, selection mode, single and bulk delete dialogs, loading and error on every surface,
the resolution screen, the media sheet in its variants, the navigation drawer, and Système.

`harness/states.py` drives all 47 and asserts each one renders content, has no horizontal
overflow and raises no JS error. **A state that renders nothing fails the pass.**

## `regions.json` — the extraction contract and the measurement map

One file, four jobs:

- **`exportedSelectors`** — the allowlist `extract-maquette-css.py` exports. Anything not
  listed is not exported.
- **`harnessSelectors`** — the prototype's own chrome, listed so its exclusion is explicit
  rather than implied.
- **`regions`** — what `parity-probe.py` measures, each naming the states it is visible in,
  so the probe never has to guess how to reach a card state.
- **`$adversarialReview`** — the rule set (R1…R52) plus `$methodLessons`: what each rule
  exists for, and what a rule that failed to bite taught. `$reportedDefects` lists the
  defects found by hand, each with its test in `harness/bugs.py`.

It also carries the probe's emulation settings, the `computedStyle` subset to diff, the
allowlist of accepted divergences — **every entry carries an inline justification** — and
`outOfScope`, the surfaces deliberately not covered.

## What is real in here, and what is not

Read from the live system:

| Data | Source |
|---|---|
| Library titles, categories, counts (1,861 items) | `library.db` |
| 12 follows with their true states | `acquire.db` |
| Incomplete series and their fractions | `library.db` |
| Owned episode numbers, season by season (247 series, 9,218 episodes) | `library.db` |
| Episode titles and air dates (9,779 episodes) | TMDB |
| Staging contents | the staging directory |
| TMDB suggestions | the engine, actually executed |
| 319 wide visuals, 172 posters (64 of them at gallery definition), 55 cast portraits | TMDB / TVDB, re-encoded as WebP |
| 288 YouTube trailer ids | TMDB `/videos` |
| The grab cadence | the live scheduler |

Not real: the release candidates on the "choose another release" screen — no tracker is
queried — and the timings and counts of the `charge` scenario, which exist so density can be
judged. Both are labelled as such in the design notes.

**Two scenarios**, switched from the harness (the **≡** button):

- **`reel`** (default) — the exact state of the system. Calm: nothing to grab, nothing in
  flight, two stuck folders. This is what makes the **rest states** judgeable; a prototype
  that is always busy never shows them.
- **`charge`** — a dense state, for judging density and scrolling.

---

## Two rules the prototype itself re-taught, the hard way

- **R7 — `minmax(0, 1fr)`, never `1fr`.** An `auto` grid track's floor is the item's
  *intrinsic* size, so a horizontally-scrolling pill train sized its track to max-content and
  blew a 390px frame out to 910px.
- **R8 — an author `display` rule beats `[hidden]`.** A class declaring `display: grid` made
  `el.hidden = true` do nothing. Any class declaring a `display` must declare its own hidden
  case.

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
- An **inline action** exists only where a section exists *for* that action
  (« À récupérer », « Ça coince »). It is a shortcut, never the only way in.

The last two clauses are the ones that matter. An action reachable from a single
surface disappears the moment that surface is displayed differently: the poster
view of « Incomplets » offered no way to complete a series, because the only
« Compléter » was a button drawn on a card, and a gallery draws no cards. When
the rule that forbids this (R43) was first run, it found the same hole in
« Récupérer » and in « Résoudre » — neither of which anyone had reported.

**The panel is derived, not passed in.** One builder reads what is true about the
medium — followed, incomplete, in the library, to grab, blocked, has a sheet —
and every action follows from that. This is what makes the panel reached from a
gallery identical to the panel reached from a card, by construction rather than
by vigilance. Two builders existed before, and neither offered everything.

An element states **which** panel it addresses (`data-panel="media:<title>"`) and
never how to build it. Addressing it by list index is forbidden: an index belongs
to the list on screen rather than to the medium, so it means something different
in each lens, and a numeric title (« 1917 ») read as an index opens the panel of
whatever film sits at that rank.

### Two builders, and a descriptor between them

The contract above is enforced by there being **one builder per shape**, not one per
screen:

| Shape | Builder | Who uses it |
|---|---|---|
| Card | `cardHTML(descripteur, opts)` | every list — urgency sections, follows, library, arrivals |
| Tile | `tileHTML(o, sousLigne, opts)` | every gallery — the library's three lenses, the follows grid |
| Release card | `releaseCardHTML(...)` | the resolution and release screens — **not a medium** |
| Selection row | `libRowHTML` | a mode of the LIST, not a variant of the card |

Three views used to rebuild a card by hand. One of them had already drifted, and it
took a separate edit to bring it back in line — the kind of edit that is silently
forgotten. Breaking the shared builder on purpose now produces **332 failures across
every list**; the same edit once reached only the lists that happened to use it.

**The card takes a descriptor of FACTS**, listed in the source next to the function:
title, kind, sub-line, reason, fraction, chip, caption, fresh, strip. A view that
wants to show something not in that list is describing a fact the card does not yet
know about — the fix is to add the fact, never to pass ready-made markup. *An envelope
guarantees nothing about what it carries.* This is what keeps « one component with
variable display » from turning into a component with a dozen appearance flags.

**A tile is not a card with a flag.** It is a different layout — all poster, name
below — so it stays a separate builder. What the two share is the descriptor and the
behaviour contract, which is where the guarantees actually live.

**Not everything that looks like a card is one.** A release candidate shares the markup
and is a different object: it has no sheet and no panel, because it is one candidate
among several for a medium already named on the screen. It says so with
`data-nonmedia`, so the check tells them apart by construction rather than by knowing
which screen draws which (R46).

**Every list uses the same metrics** — poster 38 × 57, padding 9, radius 8, title 13.5,
gap 10 (R47). Card HEIGHTS differ, and that is content: a card carrying a reason is taller
than one that does not. Découvrir was the last holdout, with its own builder and a poster
63 % larger, on a page that already offers a gallery and a deck for visual browsing. A list
is a list.

**A reason never truncates** (§12, R48). It wraps and the card grows; half a sentence is not
a reason.

### Galleries answer their container, not the window

Every gallery — the library's three lenses, the follows grid, Découvrir's posters — draws
the same tile at the same metrics (R50). Découvrir was the last holdout here too, with its
own builder, its own class vocabulary and a tile 53 % wider on a page that already offers a
deck for visual browsing.

The **column count follows the scrollport's width**, through a container query, and never
the window's:

| Scrollport | Columns |
|---|---|
| < 460px | 3 |
| ≥ 460px | 4 |
| ≥ 620px | 5 |
| ≥ 820px | 6 |

A media query would read the viewport, so a 390px frame sitting on a 1280px desktop would be
told it has room for six columns it does not have — which is exactly why a harness deviation
used to pin three columns by hand. That deviation is gone: the container query asks the width
actually available, and the app gets the same answer because there the scrollport IS the
window.

`harness/cartes.py` proves all of it; R41–R50 in `regions.json` state it.

## It installs, and the invitation depends on the platform

`serve.py` serves a manifest, the brand icons and a service worker, so the prototype installs
to a home screen like the app does. **The worker caches nothing.** Its only job is to satisfy
the installability criterion; a caching worker would serve yesterday's prototype to someone
judging today's design, which is the single failure a design reference cannot afford.

The invitation has two forms, and they are not cosmetic variants (R51):

- **Android and desktop** fire `beforeinstallprompt`, which a page may capture and replay on a
  gesture — so the banner offers a button.
- **iOS Safari** fires nothing. There is no event to await and no API to call, so the banner
  *is* the guide: it walks Partager → « Sur l'écran d'accueil » → Ajouter. A single banner
  saying « installez-moi » on both would be a dead end on one of them.

It sits **above** the tab bar. Anchored to the bottom edge its close button lands under the
fixed bar and cannot be reached — reported from a real phone, on both platforms.

iOS also reads neither the manifest's `display` nor its `short_name`: standalone mode and the
home-screen label need `apple-mobile-web-app-capable` and `apple-mobile-web-app-title`, or the
icon opens a Safari tab instead of an app.

## A trap that cost real time: **screenshots are not an oracle**

Two captures of the **same, unmodified file** disagreed on 8 to 15 of the 47 states. Skeleton
shimmer, the media-sheet header entrance, async decode of the embedded WebP visuals: none of
it settles on a schedule you can wait out reliably. Freezing animations and awaiting
`img.decode()` narrowed it and did not close it.

A run of that oracle "proved" 20 states changed after a deletion. They had not. The deletion
was correct all along.

**Use the deterministic oracle instead** — the one `parity-probe.py` uses:
`getBoundingClientRect` plus a fixed `getComputedStyle` subset. And for the specific question
"is this rule dead?", there is an exact answer that needs no oracle:

```js
document.querySelectorAll('.act.grab').length   // over all 47 states → 0 means it can never apply
```

combined with "the source never writes this class name" (so no interaction can produce it).
That is a proof, not a sample. `harness/export.py` runs exactly that.

## And one trap that no synthetic test can catch

Swipe gestures **must claim the horizontal axis** with `touch-action: pan-y` on the row itself
(never on an ancestor — `touch-action` intersects down the whole chain). A passive listener
that claims nothing lets the browser take the gesture and fire `touchcancel`: the swipe then
works **only under synthetic events**, which are never cancelled. This exact divergence has
happened here — the code was present, the test was green, and a real thumb found nothing.

**Every gesture answers a pointer, not only a finger.** The handlers listen for pointer events,
so one path serves finger, mouse and pen — the interface is used from a desktop browser too, at a
phone width. Two things a touch-only implementation never meets, both found by testing with a
real mouse on a browser with no touch at all:

- **The end of a drag is listened for on the window.** A touch is captured implicitly by the
  element that received the start; a mouse is not, so a release outside the frame never reaches a
  listener bound to the scrollport, and the gesture hangs half-done.
- **Images inside a draggable surface disable the browser's native picture drag**, which
  otherwise swallows the pointer stream outright — two moves, never an up.

The **axis claim** stays in `touch-action`: it is what makes a real touch gesture arrive at all,
and no synthetic event exercises it, so it is asserted on the declaration itself.
`harness/souris.py` proves every gesture with a real mouse; `harness/deck.py` proves the deck
with pointer events of type « touch ».

---

## `harness/` — the probe's working prototype

Scripts that already do, in headless Chromium, what `scripts/parity-probe.py` must inherit.
They are committed because they encode recipes that cost time to get right.

| Script | What it proves |
|---|---|
| `sweep.py` | all views render content, no horizontal overflow, device at 390px, no JS error. **A view that renders nothing fails.** |
| `scen.py` | the same sweep across both data scenarios, with explicit sub-view reset between runs |
| `states.py` | all 45 named states render, without overflow or JS error |
| `audit.py` | rules R1–R10 and R20–R23 across every state, and it announces how many rules it EXECUTED |
| `audit2.py` | rules R11–R17 and R26–R31: uniformity, honesty of the text, one back design, one season rendering, episode presence against the data, a panel that never offers an action the medium does not support |
| `cartes.py` | rules R41–R50: the card and gallery contract — poster to the sheet, body to the panel, no action reachable from a single surface, the same panel from a card and from a gallery |
| `export.py` | every BLOCK 2 class is classified; fails on dead CSS or on a class missing from the allowlist |
| `bugs.py` | one test per defect found by hand |
| `inter.py` | swipe, infinite scroll, load error + retry, delete dialog |
| `suivis.py` | Suivis conformity across its three modes |
| `sel.py` | the two delete paths from the grid: long-press and selection mode |
| `scroll.py` | no form interaction moves the scroll position |
| `filtres.py` | filters filter, and their parts sum to the whole |
| `actions.py` | the simulated behaviours really mutate the state |
| `dest.py` | every button has a destination |
| `ident.py` | identify ≠ follow: the context picks the verb |
| `pop.py` | the episode date popover, in all its states |

Run them with the Python that carries Playwright, against a local static server on
**127.0.0.1:8899** — **never** 8710 / 8711, which the reverse proxy routes to prod and
staging.

The prototype must be served inside a wrapper supplying `<meta name="viewport">`; without it
Chrome falls back to the legacy 980px layout viewport and every measurement is wrong. The file
also injects that meta itself if the host page has none — do not remove that guard.

## Language of the source

Every comment in this directory — HTML, CSS, JavaScript, Python — is written **in English**,
and carries no reference to a work session, a phase, or a dated decision. It must read years
from now, out of context. Interface copy quoted inside a comment stays in French, because that
is what the screen says.
