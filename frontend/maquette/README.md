# The prototype — this directory IS the product

> **This prototype is the product, not a reference.** Operator directive of 2026-08-13: the
> mission is no longer a mobile restyling of the shipped app but a REDESIGN — a finished v1. Every
> page production serves is owed here, including the ones production has and this does not. The
> app is bound to it afterwards, in a separate mission, and only once the operator judges the
> design and the front-end architecture solid enough. The inventory of what is still owed is in
> `IMPLEMENTATION.md`.

**`design/refonte.html` is the design reference for the TorrentMate web UI. Any change to the
design starts here, not in `frontend/src`.**

`design/` is the served root — everything a browser reaches lives there (the prototype, images,
PWA assets). The `harness/`, `serve.py`, and `regions.json` siblings are never served.

`design/` is also a Vite project — the chassis the conversion will move into, sub-project by
sub-project. `npm run build` emits `dist/` (gitignored): the real envelope from `index.html`
with the prototype injected **verbatim** — a local plugin inserts the fragment after Vite's
own HTML processing, so no minifier ever touches it — and `dist/assets` linked to the real
files. R72 (`coquille.py`) is the contract: the built output must render identically to the
source, DOM and geometry, or the shell is lying.

**The live host serves the BUILD.** `serve.py` compares the newest mtime of the build's
inputs (`refonte.html`, `index.html`, `vite.config.mjs`) against `dist/index.html` and
rebuilds under a lock before serving (0.4 s measured), so an edit is still visible at the
next reload. A failed build answers 503 with its own last words — serving the previous
output would date what is being judged falsely. R73 (`bascule.py`) holds all of it against
a scratch design root. The harness, meanwhile, keeps measuring the SOURCE through
`wrapped.html`: that copy is what isolates rule mutations from what the host serves, and
R72 is the bridge that keeps source and build interchangeable.

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

1. **A design change starts in `design/refonte.html`.** Adjust it there, check it against the
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
   component skeletons. Every detail _resembled_; the whole diverged.
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
writes `frontend/src/styles/ps/app-surface.css`. It exists — it did not, for a while, while three
binding documents described it, which is the kind of promise that gets cited as done.

**The app has not adopted it.** Nothing imports the generated stylesheet, and that is deliberate:
adopting it is deriving app code, which §15 forbids until the operator has judged the design. It is
generated and GUARDED now so that the guard is in place before there is anything to protect —
measured, not argued: `frontend/dist` is byte-identical with the file present and absent.

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
`window.__states()` returns the 54 ids. The **≡** button in the harness opens a panel listing
them all.

This is what makes the parity probe deterministic. Without it, measuring "the blocked card"
requires knowing how to make one appear — and that knowledge is exactly what evaporates over
time. With it, the probe iterates `regions.json` → for each region, the states it is visible
in → `__go(state)` → measure.

Three orthogonal dials the panel exposes:

| Dial          | Values                            | What it changes                      |
| ------------- | --------------------------------- | ------------------------------------ |
| Data scenario | `reel` · `charge`                 | the real system state vs a dense one |
| Surface phase | `prete` · `chargement` · `erreur` | every surface goes through all three |
| TMDB account  | connected · not                   | Découvrir's full vs degraded mode    |

The 54 states cover: the startup screen, the entry screen and its refusal, the five urgency
sections in both scenarios, Suivis in its three modes plus its two empty cases, Découvrir full /
degraded / exhausted / loading, the add screen idle and with real results, the follow sheet on a
22-season complete catalogue and on a holed one, the journey sheet, the "⋮" sheet, the library in
grid and list, its empty search, its three lenses, selection mode, single and bulk delete
dialogs, loading and error on every surface, the resolution screen, the media sheet in its
variants, the navigation drawer, the two install proposals, the arbitration screen in both of its shapes, and Système.

`harness/states.py` drives all 54 and asserts each one renders content, has no horizontal
overflow and raises no JS error. **A state that renders nothing fails the pass.**

## `regions.json` — the extraction contract and the measurement map

One file, four jobs:

- **`exportedSelectors`** — the allowlist `extract-maquette-css.py` exports. Anything not
  listed is not exported.
- **`harnessSelectors`** — the prototype's own chrome, listed so its exclusion is explicit
  rather than implied. **Eight class names sit on BOTH lists** — `topbar`, `bottombar`, `brand`,
  `mk`, `lb`, `port`, `sp`, `row` — because the demo bars and the app's own bars share their
  names, one set in BLOCK 1 and the other in BLOCK 2. Extraction only ever reads BLOCK 2, so it
  reads them as exported, and it PRINTS that it did: a contradiction nobody is told about is how
  the wrong reading survives for a year.
- **`regions`** — what `parity-probe.py` measures, each naming the states it is visible in,
  so the probe never has to guess how to reach a card state.
- **`$adversarialReview`** — the rule set (R1…R64) plus `$methodLessons`: what each rule
  exists for, and what a rule that failed to bite taught. `$reportedDefects` lists the
  defects found by hand, each with its test in `harness/bugs.py`.

It also carries the probe's emulation settings, the `computedStyle` subset to diff, the
allowlist of accepted divergences — **every entry carries an inline justification** — and
`outOfScope`, the surfaces deliberately not covered.

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
  _intrinsic_ size, so a horizontally-scrolling pill train sized its track to max-content and
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
- An **inline action** exists only where a section exists _for_ that action
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

| Shape         | Builder                        | Who uses it                                                  |
| ------------- | ------------------------------ | ------------------------------------------------------------ |
| Card          | `cardHTML(descripteur, opts)`  | every list — urgency sections, follows, library, arrivals    |
| Tile          | `tileHTML(o, sousLigne, opts)` | every gallery — the library's three lenses, the follows grid |
| Release card  | `releaseCardHTML(...)`         | the resolution and release screens — **not a medium**        |
| Selection row | `libRowHTML`                   | a mode of the LIST, not a variant of the card                |

Three views used to rebuild a card by hand. One of them had already drifted, and it
took a separate edit to bring it back in line — the kind of edit that is silently
forgotten. Breaking the shared builder on purpose now produces **332 failures across
every list**; the same edit once reached only the lists that happened to use it.

**The card takes a descriptor of FACTS**, listed in the source next to the function:
title, kind, sub-line, reason, fraction, chip, caption, fresh, strip. A view that
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

A **fallback** builder had also appeared, answering for whatever the first did not recognise,
and it shipped six buttons of which three led nowhere at all. That is what a fallback becomes:
never the one being looked at, so never the one being fixed. There is one builder now, and
« nothing is known about this medium » is one of the truths it derives from. R56
(`harness/panneau.py`) states it.

**Not everything that looks like a card is one.** A release candidate shares the markup
and is a different object: it has no sheet and no panel, because it is one candidate
among several for a medium already named on the screen. It says so with
`data-nonmedia`, so the check tells them apart by construction rather than by knowing
which screen draws which (R46).

**Every list uses the same metrics** — poster 49 × 73.5, padding 9, radius 8, title 13.5,
gap 10 (R47). That 49 is derived from the card's own ANATOMY, not from a percentile: the 135
cards the interface draws fall into eight shapes by which blocks they carry, and the poster
fills the one whose purpose is RECOGNISING a medium — title, sub-line and synopsis, 72.9px of
content, two thirds of which is 49. It used to fill the median card (60.7 → 42) and that
reference had run out: the poster had become what set the median, so re-running the computation
returned its own answer. The two neighbouring shapes, for another notch: a card carrying a
reason gives 58, the fullest card gives 63. Card HEIGHTS differ, and that is content: a card carrying a reason is taller
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
| ---------- | ------- |
| < 460px    | 3       |
| ≥ 460px    | 4       |
| ≥ 620px    | 5       |
| ≥ 820px    | 6       |

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

**And it is actually offered**, which is the half that was missing: the banner existed and nothing
ever showed it — it was reachable only by driving to its named state, so on a real phone it never
appeared. Android and desktop capture `beforeinstallprompt` **and prevent its default**, or the
browser posts its own proposal in its own place and ours never gets a turn; the event is then
replayed on a gesture, the only moment a browser accepts a prompt. iOS Safari fires nothing and
offers no API, so nothing waits for an event there: the page knows it is Safari on iOS and not
already standalone, and that is enough. Nobody is asked while already installed, nobody is asked
over the entry screen, and a refusal is not repeated in the same session.

The invitation has two forms, and they are not cosmetic variants (R51):

- **Android and desktop** fire `beforeinstallprompt`, which a page may capture and replay on a
  gesture — so the banner offers a button.
- **iOS Safari** fires nothing. There is no event to await and no API to call, so the banner
  _is_ the guide: it walks Partager → « Sur l'écran d'accueil » → Ajouter. A single banner
  saying « installez-moi » on both would be a dead end on one of them.

It sits **above** the tab bar. Anchored to the bottom edge its close button lands under the
fixed bar and cannot be reached — reported from a real phone, on both platforms.

iOS also reads neither the manifest's `display` nor its `short_name`: standalone mode and the
home-screen label need `apple-mobile-web-app-capable` and `apple-mobile-web-app-title`, or the
icon opens a Safari tab instead of an app.

**And it installs as a DIFFERENT application.** The shipped app installs as « TorrentMate »;
this one installs as « TorrentMate Design », in the manifest's `name`, in its `short_name` —
the home-screen label on Android — and in the iOS meta, because Safari reads neither manifest
field. An abbreviation is not a distinction: two entries on one home screen that differ only
by one teaches nobody which is which, and the one that gets opened is whichever was tapped
last. The manifest also declares an explicit `id`; left out, the identity falls back to
`start_url`, which is « / » on both, so nothing but the origin separates them — and an origin
is not something a home screen shows.

**And it serves its own icons.** A name distinguishes two entries in a list; on a home screen
what is seen first is the picture, and two identical pictures under different labels are still
two identical pictures. Three sets now form one family — the app's plain, staging's with a cyan
ring, the design host's with a yellow one — generated by `frontend/scripts/make-design-icons.py`
rather than drawn, so the ring cannot drift between them: the shape is read off the staging set
pixel by pixel, antialiasing included, and repainted.

The MASKABLE variants take a **circular** ring instead, inside the safe zone. A launcher crops a
maskable icon to its own shape and a ring at the edge is simply cut; staging can afford to drop
the ring there because it also recolours the mark, but this set recolours nothing, so a ringless
maskable icon would be byte-identical to the app's — and Android prefers the maskable one for the
home screen. The very icon the operator would see would be the one saying nothing.

R52 compares every served icon against the application's, byte for byte.

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
contradict the machine. Answering, whichever way, takes the folder out of the queue, on BOTH
lists it appears on: « À traiter » on the acquisition side used to keep it forever, because the
answer only ever looked in the Arrivées list.

The desktop deck's keyboard shortcuts (← → ⏎) have no phone. What they were for — going through
several in a row — survives as a plain progression: « 1 sur 2 », and « Passer à la suivante ».

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
(R49), and reveals it on submit. R53 (`harness/demarrage.py`) checks all of it, gate included —
it starts `serve.py` on a scratch port and drives a real submit.

**Leaving is the same story told backwards.** « Se déconnecter » used to answer with a message
saying the session had been closed, over an interface that had not moved and was still signed
in. A message is not a destination. The session IS the cookie, and the cookie belongs to the
server, so the server is asked to drop it **first** and the entry screen only reflects what has
already happened — an entry form shown over a live cookie is contradicted by the next reload.
R54 (`harness/deconnexion.py`) checks both halves, and the invisible one is the one that
matters: it asks the server, afterwards, whether the session is still accepted.

## The cut is by the nature of the trouble

Four surfaces, and what decides which one a panel belongs to is not the page it came from:

| A medium in trouble               | **Arrivées**      |
| --------------------------------- | ----------------- |
| A machine in trouble              | **Système**       |
| A setting                         | **Configuration** |
| A command run against the library | **Maintenance**   |

`Contrôle` does not survive this cut. Production stacks blocked media on top of disk and provider
health with nothing saying why they share a page; each of its seven panels has a home under the
rule, and none of those homes is a new page. The full mapping, panel by panel, is in
`IMPLEMENTATION.md`.

**A state wears a BADGE, and it has four tones.** `success` — it works. `alert` — it does not, and
something must be done now. `warning` — important but not critical, a disk nearly full. `info` — a
fact that is neither a success nor a fault, which is what a QUANTITY is: « 1 863 titres » is neither
good nor bad, it is how big the library is. Badging a number green is how a green stops meaning
« it works ».

`alert` is the operator's word and `danger` is the stylesheet's; the mapping lives in ONE place.
And **a tone has two jobs that one colour cannot do**: `--danger` is a FILL, painted behind white
text on a button, and reusing it as a label colour on a 20 % tint of itself put every red badge at
3.69, under AA, while every green sat at 5.5. The light theme was worse and had been for as long as
the chips existed — success at 2.91, warning at 2.02, on every chip in the interface. Each tone now
carries a text variant, and all four clear AA in **both** themes.

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
drawer navigation settles history itself: the destination TAKES the drawer's entry through
`replaceState` rather than unwinding and pushing within one task, where the asynchronous pop
lands after the push and overwrites it. A back from the destination then reaches where one was
before opening the drawer, which is the only thing a drawer can honestly promise.

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

`harness/tiroir.py` holds all of it; R65 states it.

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
document.querySelectorAll(".act.grab").length; // over all 47 states → 0 means it can never apply
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

**And a pointer stream is not a touch stream.** Two gestures on the scrollport — the pull to
refresh and the swipe between views — were lost the day the gesture layer moved to pointer
events, and no script noticed, because every script drove them synthetically. The cause is that
the compositor owns vertical panning inside a scroller: the moment it claims the gesture it
fires `pointercancel` and stops delivering `pointermove`, while the touch stream for the same
finger keeps arriving. Measured: one pointer move, then cancel, against ten `touchmove`.

The usual answer — claim the axis in `touch-action` — is **not available on the scrollport**:
`pan-y` there intersects down onto `.pillscroll` and `.cast`, which declare `pan-x pan-y` and
would then pan on neither axis. So the surfaces that CAN claim their axis (a swipeable row, a
deck card) keep the pointer path, and the scrollport reads the finger from touch events and
everything else from pointer events — one implementation, two sources, never both for the same
finger. `pointercancel` is deliberately ignored for a finger; ending on it would undo the fix.

`harness/doigt.py` drives all of it through `Input.dispatchTouchEvent`, which is real browser
input rather than an event object handed to a listener. That is the only oracle that can tell
the two apart.

---

## `harness/` — the probe's working prototype

Scripts that already do, in headless Chromium, what `scripts/parity-probe.py` must inherit.
They are committed because they encode recipes that cost time to get right.

| Script            | What it proves                                                                                                                                                                                                                                                                                                                          |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sweep.py`        | all views render content, no horizontal overflow, device at 390px, no JS error. **A view that renders nothing fails.**                                                                                                                                                                                                                  |
| `scen.py`         | the same sweep across both data scenarios, with explicit sub-view reset between runs                                                                                                                                                                                                                                                    |
| `states.py`       | every named state renders, without overflow or JS error                                                                                                                                                                                                                                                                                 |
| `commun.py`       | not a rule: the plumbing every script borrows — how a verdict prints, how a run ends, how the document is opened past the startup screen. Twelve copies of the same `verifier()` meant a fix to the reporting had to be made twelve times, and one change to the opening cost twenty-eight hand edits                                   |
| `deck.py`         | the deck answers a swipe either way — left skips and comes back, right dismisses with an undo                                                                                                                                                                                                                                           |
| `galerie.py`      | one tile pattern in every gallery                                                                                                                                                                                                                                                                                                       |
| `souris.py`       | every gesture answers a MOUSE too: the interface is used from a desktop browser                                                                                                                                                                                                                                                         |
| `surfaces.py`     | every surface the interface draws is reachable and renders                                                                                                                                                                                                                                                                              |
| `audit.py`        | rules R1–R10 and R20–R23 across every state, and it announces how many rules it EXECUTED                                                                                                                                                                                                                                                |
| `audit2.py`       | rules R11–R17 and R26–R31: uniformity, honesty of the text, one back design, one season rendering, episode presence against the data, a panel that never offers an action the medium does not support                                                                                                                                   |
| `cartes.py`       | rules R41–R50: the card and gallery contract — poster to the sheet, body to the panel, no action reachable from a single surface, the same panel from a card and from a gallery                                                                                                                                                         |
| `export.py`       | every BLOCK 2 class is classified; fails on dead CSS or on a class missing from the allowlist                                                                                                                                                                                                                                           |
| `bugs.py`         | one test per defect found by hand                                                                                                                                                                                                                                                                                                       |
| `inter.py`        | swipe, infinite scroll, load error + retry, delete dialog                                                                                                                                                                                                                                                                               |
| `suivis.py`       | Suivis conformity across its three modes                                                                                                                                                                                                                                                                                                |
| `sel.py`          | the two delete paths from the grid: long-press and selection mode                                                                                                                                                                                                                                                                       |
| `scroll.py`       | no form interaction moves the scroll position                                                                                                                                                                                                                                                                                           |
| `filtres.py`      | filters filter, and their parts sum to the whole                                                                                                                                                                                                                                                                                        |
| `actions.py`      | the simulated behaviours really mutate the state                                                                                                                                                                                                                                                                                        |
| `dest.py`         | every button has a destination                                                                                                                                                                                                                                                                                                          |
| `ident.py`        | identify ≠ follow: the context picks the verb                                                                                                                                                                                                                                                                                           |
| `pop.py`          | the episode date popover, in all its states                                                                                                                                                                                                                                                                                             |
| `chrome.py`       | R51: the harness bar covers none of the app's fixed controls, in every named state, at both sides of the 520px breakpoint                                                                                                                                                                                                               |
| `retour.py`       | R59: the back gesture walks the path in reverse — tabs and lenses included — closes a layer first, and at the root warns instead of leaving, closing only on a second back within five seconds                                                                                                                                          |
| `reglages.py`     | R60: the settings are navigated by what one wants to change, never by file; every real setting belongs to one rubric and is identified by its label alone — subject then action, in French; nothing is written until the save bar names the files it will write; a secret says only whether it is set                                   |
| `palette.py`      | R61: no bare `var(--x)` names a property the document never defines, and the brand colour is actually painted on the wordmark, the sign-in button and the startup bar                                                                                                                                                                   |
| `entree.py`       | R62: the sign-in screen renders identically on the host and inside the prototype, and the host redeclares nothing the reference owns                                                                                                                                                                                                    |
| `contenu.py`      | R63: a follow's card carries what `acquire.db` really holds and phrases it as « En cours » does; a library row carries the synopsis, clamped to the largest number of lines that fits, and shows nothing when the NFO has no plot                                                                                                       |
| `glisse.py`       | R64: a row opens a drawer either way, one at a time, without firing the tap — measured on Chromium AND WebKit, where the drawer used to spill past the card; and a REVERSAL settles the row back rather than leaping, sampled during the drag because a jump is a discontinuity                                                         |
| `adresse_url.py`  | R69: the URL carries the state (DOIT-10) — walking writes the address, a reload lands on the same screen, only what differs from the opening state is written, a wrong address is left exactly as typed, and back walks the addresses in reverse                                                                                        |
| `adresse.py`      | R68: an unknown address renders instead of raising, names what was asked for and offers a way out; the account surface draws the one real account, compared against `web.json5`, and marks the place of the others EMPTY                                                                                                                |
| `machine.py`      | R67: Système is the machine, Maintenance is what one does to the library — no blocked medium on Système, no scheduler called « stopped » between two runs, both lists counted against `pm2 jlist`, every command checked against the engine's registry in both directions, and a command that DELETES inert until it has been run blank |
| `arrivees.py`     | R66: Arrivées carries the pipeline's health — one control that fits the state, a run asked during a run QUEUED rather than refused, the engine's nine steps in its order, nothing-to-do said with an em dash, and every figure checked against the run `library.db` really recorded                                                     |
| `tiroir.py`       | R65: the drawer is a place one passes through, not a route — every entry names a page that exists and arrives there, the destination takes the drawer's own history entry, closing a layer neither rebuilds the page underneath nor loses where it was scrolled, and every entry is legible measured as PAINTED                         |
| `installation.py` | R51: the install offer is actually OFFERED — `beforeinstallprompt` captured, its default prevented and replayed on a gesture; the iOS guide raised by an iPhone user agent; nothing offered to an installed app, over the entry screen, or after a refusal                                                                              |
| `pwa.py`          | R52: the LIVE host is installable from the first document a phone reaches — manifest, icons that load, worker registered and controlling, offline fallback cached. Runs against `tm-design.iznogoudatall.xyz`, not the local server                                                                                                     |
| `demarrage.py`    | R53: the startup screen is declared first, covers the frame, offers no control, is gone after the first render, and the gate the server builds shows the same screen — extracted — from the submit onwards. Starts `serve.py` on a scratch port                                                                                         |
| `deconnexion.py`  | R54: signing out lands on the entry screen AND the server stops accepting the session. Starts `serve.py` on a scratch port                                                                                                                                                                                                              |
| `panneau.py`      | R56: one panel builder, no caller passing markup, no inline style inside a panel, one heading, no action without a destination, and an undeclared block refused                                                                                                                                                                         |
| `decision.py`     | R57: the arbitration screen — the folder as subject, no sheet or panel promised, no engine token on screen, a score printed only when it separates, each candidate wearing only its own poster, three ways out, and answering emptying the queue on both lists                                                                          |
| `doigt.py`        | R55: every gesture under REAL touch input (`Input.dispatchTouchEvent`), which the compositor can cancel — the pull to refresh on seven surfaces, the swipe between views, ordinary scrolling, the swipeable row and the deck                                                                                                            |
| `images.py`       | R70: the source embeds no image and every `assets/` reference resolves to a file                                                                                                                                                                                                                                                        |
| `ecrans.py`       | R71: a screen above another one — back redraws the screen it covered (query and scroll included) through both exits, one more back leaves the layer, and a result card carries no inline action in its foot: the panel is the single path to the act                                                                                    |
| `coquille.py`     | R72: the Vite shell's build renders identically to the source — DOM serialization and region geometry compared per driven state on both pages, and no failed response (4xx/5xx) on either side (the uninvited /favicon.ico miss excepted)                                                                                               |
| `bascule.py`      | R73: the host serves the build to the byte, rebuilds stale sources before serving, and a broken build answers 503 that says so — proven against a scratch design root, never the real source                                                                                                                                            |

Run them with the Python that carries Playwright, against a local static server on
**127.0.0.1:8899** — **never** 8710 / 8711, which the reverse proxy routes to prod and
staging.

The wrapper directory `/tmp/tm-refonte/` must carry an `assets` symlink to the repo's
`design/assets/`:

```bash
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets
```

Without it, every image reference (`src=` and `url()` values) resolves to a 404. The harness
runs measure against this local server, so the symlink must be in place before any test.

The prototype must be served inside a wrapper supplying `<meta name="viewport">`; without it
Chrome falls back to the legacy 980px layout viewport and every measurement is wrong. The file
also injects that meta itself if the host page has none — do not remove that guard.

## Language of the source

Every comment in this directory — HTML, CSS, JavaScript, Python — is written **in English**,
and carries no reference to a work session, a phase, or a dated decision. It must read years
from now, out of context. Interface copy quoted inside a comment stays in French, because that
is what the screen says.
