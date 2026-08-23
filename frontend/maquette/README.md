# The prototype — this directory IS the product

> **This prototype is the product, not a reference.** Operator directive of 2026-08-13: the
> mission is no longer a mobile restyling of the shipped app but a REDESIGN — a finished v1. Every
> page production serves is owed here, including the ones production has and this does not. The
> app is bound to it afterwards, in a separate mission, and only once the operator judges the
> design and the front-end architecture solid enough. The inventory of what is still owed is in
> `IMPLEMENTATION.md`.
>
> **Restated and widened, 2026-08-19 — EVERY screen is to be redrawn. All of them.** This is a
> new version of the app, not a reskin: its purpose is a new, COHERENT user experience, and the
> first objective is to FREEZE that interface. Four things follow.
>
> 1. **No surface is out of scope.** A production screen with no page here is owed, never an
>    arbitration to leave it out. `/control` and `/pipeline` had been ruled deliberately
>    page-less; the operator overturned that on 2026-08-19. Where their panels BELONG remains a
>    live UX argument (`IMPLEMENTATION.md`); being drawn is no longer in question.
> 2. **What this prototype already holds is VALIDATED** by the operator. Do not relitigate it.
> 3. **What remains is not only pages** — the UX, the interaction language and this prototype's
>    own ARCHITECTURE have to be finished and consolidated before the freeze.
> 4. **The backend follows the interface.** The engine will be adapted to what the new interface
>    needs, and that comes AFTER the freeze — so a backend limitation is never a reason to draw
>    less. Record it, and draw what the experience requires.
>
> **It REPLACES the app; it is not transposed into it (2026-08-20).** On switchover day
> `frontend/src` is ARCHIVED and this directory takes its place. Every page and every MECHANISM
> the shipped app has must therefore end up here — afterwards there is nothing left to take from
> it. And the corollary that cost the most: the CSS extraction, the `.tm` scope, the selector
> allowlist and the rendering-parity probe were built for the OPPOSITE model — migrating the app
> surface by surface, planned in the 2026-08-10 spec §4.1/§7.2 and reversed on 2026-08-13. They
> have no subject and are being retired. The measured inventory of what is done and what remains
> lives in `IMPLEMENTATION.md` § THE OBJECTIVE.

**`design/refonte.html` is the design reference for the TorrentMate web UI. Any change to the
design starts here, not in `frontend/src`.**

`design/` is the served root — everything a browser reaches lives there (the prototype, images,
PWA assets). The `harness/`, `serve.py`, and `regions.json` siblings are never served.

`design/` is also a Vite project — the chassis the conversion is moving into, sub-project
by sub-project. `npm run build` emits `dist/` (gitignored): the real envelope from
`index.html` with the prototype injected **verbatim** — a local plugin inserts the fragment
after Vite's own HTML processing, so no minifier ever touches it — plus the shell's module
bundle under `dist/vite/`, and `dist/assets` linked to the real files. R72 (`shell.py`)
holds what remains true of that emission: the fragment appears verbatim exactly once, the
document names exactly one module entry, and the bundle it names exists.

**The fragment is a title and a stylesheet, and nothing else.** Two things left it. The
engine — the 35 052-line script it used to carry — lives at `design/src/engine/legacy.js`, a
module the shell imports before it starts it; it was moved byte for byte, not rewritten, and
it stays JavaScript on purpose, because typing it would mean editing it and an edit hidden
inside a move that size is an edit nobody can review. The application shell's markup — the
phone frame, the splash, the sign-in card, the topbar, the drawer, the layer hosts — lives in
`index.html`, the document Vite owns.

**The markup went to `index.html` rather than into React**, and the reason is the engine's
boot: it captures its containers at module evaluation (`view = F('#view')` and its siblings),
and a module evaluates before React has rendered anything. Markup drawn by a component would
not exist when the engine looks for it. `index.html`'s body is parsed before any module runs —
the order the markup already had — and it sits after the injection marker so the order inside
`<body>` is unchanged too: mount node, stylesheet, shell.

What remains in the fragment is BLOCK 1 and BLOCK 2, unchanged: the CSS contract is SP5's
subject, not SP4's.

Two consequences worth knowing before writing a rule:

- **The design has SOURCES, plural** — the fragment, `index.html`, and the engine module.
  `common.py` names them (`DESIGN_SOURCES`) and `design_source()` reads them together. A rule
  that greps « the design » greps that, never one file: four rules once grepped
  `refonte.html` alone and stayed green after their subject moved out of it — 930 image
  references, five colour references, and the body of code one of them counts history
  primitives in. Reading a declared source that no longer exists raises, deliberately.
- **The login gate reads each block where it lives.** `serve.py` clones the sign-in MARKUP
  from `index.html` and inherits its STYLE from the fragment; `extract` raises on a missing
  marker, so pointing one at the wrong file fails the gate rather than serving a screen
  stripped of its design.
- **Names are English, and the guard asks « is this word one we use? »** The other question —
  « is this word French? » — is only as good as its list of French words, and that list had
  holes: a hundred and forty French names sat under a green guard. `scripts/code-vocabulary.txt`
  holds the 522 words this codebase's names are built from, and a name built from a word nobody
  wrote down is refused whatever language it comes from. Adding a word is one line, deliberately.
- **A `data-*` name is code; its VALUE is not.** `data-go="profil"` names a page, and a page id
  is an address. A contract has three ends — the markup that emits it, the `dataset.X` that
  reads it, the rules that tap it — and they move in ONE step. Beware the ones the engine
  GENERATES: it writes `data-${nom}` from a data key, so no search for the literal `data-x`
  will ever list them.
- **The engine republishes its own surface.** A classic script's top-level declarations are
  global; a module's are not, and the harness drives the engine by bare name in some forty
  `page.evaluate` call sites. The block at the bottom of `legacy.js` republishes exactly
  what already existed — by value, or by getter for the bindings the engine reassigns, and
  the split is measured rather than chosen. `state` is neither: there is no cached binding
  left to publish, so its getter reads the store.
- **The engine imports what it calls.** `src/seams.ts` holds `pont`, `ecrans` and `panneau`
  as live `export let` bindings the shell fills at boot — the implementations need the
  store, which the shell creates in its body, after its imports. The globals stay published
  because this harness drives through them; they are the same objects, so the two ways
  cannot disagree.
- **The scenario table is not the engine's.** `src/states.js` holds the 656 lines every
  `window.__go(id)` reaches, and registers them with the engine. The DRIVING stayed engine-
  side: `__go` holds `pilotage`, a latch the engine reassigns, and an imported binding
  cannot be assigned.

**React and TanStack Router are the outer shell.** The router is the SINGLE writer of the
URL and the history: the legacy engine keeps its navigation logic but speaks to
`window.__bridge` (six verbs) instead of the History API. The shell creates the store and
the real bridge FIRST and only then starts the engine (`window.__demarrerMoteur` — the boot
inversion described below), so every bridge call the engine makes at boot lands straight on
the single writer; nothing before it needs queueing or replaying. R74 (`bridge.py`) holds the
bridge: no direct history writer left in the source, the back journey redraws through it,
a deep URL lands on its promised state, `__go` drives without touching history depth, and
the boot handshake is real — the startup screen comes off on its own, before the harness
ever touches it. One faithfully-kept legacy trait: forward is not a return — going back
from a sheet and then forward closes it rather than restoring it, exactly as before the
router.

**Two screens are routed for real, not merely driven by `__go()`.** `/profile/$title`
(the quality-profile screen, `ProfileScreen`) and `/add` (the add screen, `AddScreen`,
whose `q` and `mode` search params are router-owned for as long as the address reads
`/add`) render as final components inside the React root, reached by a real address
rather than by the legacy fragment's own state machine. `go()` in `shell.tsx` is
the ONLY function allowed to call `routeur.navigate()` — R76 (`navigation.py`) holds it
to exactly one call site, source-level counted, sitting inside `go()`'s own body:
the router library batches its commits into a microtask, so two writes issued in the
same task would merge into one entry unless something flushes between them, and the
legacy unwinding logic counts entries. `go()` flushes immediately after every
`navigate()` to keep native `pushState` semantics — one call, one entry. Ownership of a
history entry is decided by the entry's own SHAPE, never by matching the address
against a list of routes: a `layer` entry and a `tm: "nav"` entry keep the legacy
engine's exact existing handling, and an entry the router wrote carries neither key, so
the popstate callback's own checks fall through it harmlessly.

**The engine's boot order inverted once the bridge was real.** `window.__demarrerMoteur`
is the handshake: the shell creates the store and the real `__bridge` FIRST, then calls it
once, and the engine's own boot writes — the arrival state, the guard entry, the back
listener — land straight on the single writer, in the engine's own order, before the
first render. The queue-and-replay pre-bridge (recording writes issued before the shell
existed, then replaying them on mount) is retired: nothing writes before the handshake
runs, so nothing needs recording or replaying. A module that fails to evaluate simply
never calls `__demarrerMoteur`, and the startup screen — already first in the frame —
stays up: a visible, truthful failure instead of an app with mute verbs.

**EVERY PAGE is the shell's: `sys`, `maint`, `cfg`, `arr`, `lib`, `acq`, `profil`, `404`.** A page is not a screen — it has no
address of its own, `/` stays the pages' route with its legacy query, the legacy parser keeps
owning it, and a page's markup must land inside `#view`, where the stylesheet, the harness
selectors and the document-level click delegation all expect it. So the shell PORTALS into
`#view`: a `PAGES_OF()` entry carries `shellOwned`, `render()` skips its `innerHTML` write for
such a page and does everything else it always did, and `src/pages/host.tsx` holds the ONE table
a later wave adds a page to. THE HANDOVER IS ANNOUNCED, in `render()`, the one place that already
knows which world owns the page: taking, the fragment removes the nodes IT wrote and lets React
draw into the container; releasing, it calls `window.__releasePage()` — a `flushSync`, so React
has let go of every node before the next statement writes there. Removing its own nodes rather
than emptying the container is deliberate: a store write and a `render()` are not always the same
task, so the shell may already have drawn, and emptying then deletes nodes React believes it
holds. An earlier arrangement gave each page a HOST ELEMENT of its own; it could not describe a
page that emits several roots (the Médiathèque draws four siblings), and wrapping those would be
a markup change.
A migrated page's entry loses its `render`, so clearing `shellOwned` without restoring a
renderer crashes rather than quietly drawing a page nobody maintains. What the page host owes
the fragment in return: the legacy must never touch a node React holds — the settings page's
save bar is a second portal, into `#device`, and the legacy's own removal of that node tore the
React root down until the mounter was deleted. The fragment's `PAGES_OF()` carries no `render` at all any more; what it still draws is the SUGGESTION machinery — `#sugitems`, `#sugload` and the deck's `.deckbody`, containers the Acquisition component draws and fills only with what the FRAGMENT emits — the rows from `fillSug`, the deck's pile from `deckHTML`, written once when the container has none rather than on every commit, because `avancerDeck` mutates the deck's own DOM in place and a replaced node cannot animate. R77 (`page_host.py`) holds all of it — including one law about the RULES rather than the pages: no rule drives a page by mutating the engine's `state` alias. That alias points at the store's CURRENT object, so an in-place write leaves its identity unchanged, nothing React subscribes to moves, and the measurement lands on whatever page was drawn before.

**The panel is one component, opened through `window.__panel`.** `<PanelContent>`
(`components/panel.tsx`) is the single React constructor every panel draws through — a
`PanelDescriptor` of typed `PanelBlock`s, refused outright if a block's `type` is not one of the five
declared kinds. A producer never builds markup: it calls `window.__panel.open(descriptor)`,
and `.fermer(pop?)` / `.ouverte()` complete the surface, backed by the shell's own store
(`panneauOuvert`/`panneauDescripteur`). The legacy `openSheet()` is retired to a tripwire —
it throws, so a producer nobody converted fails where it is written instead of quietly doing
nothing; `closeSheet(pop)` stays as a one-line verb pointing at `window.__panel.close`,
kept because the harness driver still says it. R56 (`panel.py`) holds the shape: no caller
hands the panel markup, exactly one constructor, every declared block draws, an undeclared
one is refused.

**The fiche is a real route, `/fiche/$titre`.** `MediaScreen` renders it inside the React root
like `/profile/$title` and `/add` before it, reached through `window.__screens.mediaSheet(title)`
(NFC-normalised on write, same door as `.profil()`). An unknown title still renders, honestly
— the legacy `openFiche()` it was transplanted from never had a not-found branch either — and
a real fiche without a trailer shows its own "no trailer" line rather than hiding the section.
R75 (`screen_addresses.py`) holds the address at this depth: cold entry, the hero image the
screen paints itself actually loads, one Back returns to where the walk started, a wrong
address still renders instead of raising.

**Two more real routes: `/resolution/$dossier` and `/releases/$titre`.** `ResolutionScreen`
and `ReleasesScreen` are transplanted from `openResolve()` and `openReleases()` — the arbitration
screen and the release-choice screen — reached through `window.__screens.resolution(folder?,
replace?)` and `.releases(titre)`. `resolution`'s argument is optional: the legacy function
picked the first stuck folder itself when called with none, and the shell reproduces that default
rather than pushing the choice onto each caller; its `replace` flag turns a legacy
close-then-reopen (a pop plus a push, net one history entry) into a single `go(..., replace:
true)`, worth exactly as much. `releases` writes `state.relatedTitle` — the legacy function's own
first line — BEFORE navigating, since the `data-take` delegation branch still reads it after
the route has rendered. `releaseCardHTML`/`decisionCardHTML`, the legacy builders both screens
drew their cards with, are gone once their last caller moved: `ReleaseCard` and `DecisionCard`
(`design/src/screens/resolution.tsx`) are what replaced them. R75 extends with six holds for the
two screens: cold deep entry (including a dossier name carrying its own dots, the shape a real
staging folder actually has — `server.py`'s and `serve.py`'s SPA fallbacks both fold it to the
document rather than 404ing), one Back landing on `/`, and an unknown subject rendering the
screen's own honest empty case instead of raising.

**`window.__bridge` gained a sixth verb: `rewind(n)`**, the door for settling SEVERAL history
entries in one announced operation instead of calling `retour()` twice in the same task. It
flushes pending writes, announces the traversal to the engine (`window.__annoncerPops`, next to
`window.__derouler`), THEN issues a single `historique.go(-n)` — measured, not assumed: a
multi-entry `history.go(-n)` coalesces into ONE popstate at the browser level, so the engine's
own latch is raised once per announcement, never by `n` (raising it by `n` was tried and falls a
mutation: it swallows the operator's next real Back in silence). This closed M11 — the Associer
flow (`data-act="add:N"` from an `/add` result, with `state.addMode === "identifier"`) used to
fire two raw `history.back()` calls in the same task, which the engine's own coalescing latch
could absorb only one of; the second read as an unannounced operator gesture and happened to
land correctly only by the accident of which
entry sat underneath. `ident.py` holds the settlement: one entry back, no layer left open, the
next Back still worth exactly one step.

**Scroll position follows the HISTORY ENTRY, not the address.** A screen opened over another
used to be the same legacy layer restoring its own scroll on unwind; a router-owned screen
unmounts instead, taking its DOM — and its offset — with it. The shell keeps a small map keyed
by each history entry's own `key` (`shell.tsx`, "SCROLL FOLLOWS THE HISTORY ENTRY"),
reads the outgoing screen's position in the history subscription — the only instant it is
still in the DOM — and reapplies it once the incoming screen's port exists and its images have
settled. Components never see it: no prop, no hook, no context.

**The live host serves the BUILD, and so does the harness.** `serve.py` compares the
newest mtime of the build's inputs (the three roots and every file under `src/`) against
`dist/index.html` and rebuilds under a lock before serving (0.4 s measured), so an edit is
still visible at the next reload. A failed build answers 503 with its own last words —
serving the previous output would date what is being judged falsely. R73 (`switchover.py`)
holds all of it against a scratch design root. The harness measures the same truth:
`wrapped.html` is a COPY of the built document — the copy is what isolates rule mutations
from what the host serves.

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

### 2. The CSS is the maquette's own — there is nothing to translate.

BLOCK 2 of `design/refonte.html` IS the application's stylesheet. When the maquette replaces the
app, that block ships as-is; nothing lifts it, rescopes it or copies it anywhere.

**This section used to describe the opposite, and that is the lesson worth keeping.**
`scripts/extract-maquette-css.py` lifted BLOCK 2, scoped every selector under `.tm`, and wrote
`frontend/src/styles/ps/app-surface.css`; an allowlist of 461 selectors in `regions.json` said
what could ship; `harness/export.py` guarded the allowlist from the other side; and
`scripts/parity-probe.py` proved the rescoping had not changed the rendering — 1 614 measurements
and **7 minutes of CI on every PR**. All of it was built for the 2026-08-10 spec's model, in which
the SHIPPED app was migrated towards the maquette surface by surface, so the two stylesheets had
to coexist. The operator reversed that on 2026-08-13 and the tooling stayed until 2026-08-20.

**You do not translate a CSS that becomes the CSS.** What survives is the one distinction that
was never about translation:

- **BLOCK 1 is the harness** — the phone frame, the demo bars, the design notes. It must NOT
  ship on switchover day, and the maquette's own build carries it today. That is an open item,
  recorded in `IMPLEMENTATION.md`, not a solved one.
- **BLOCK 2 is the product**, and `scripts/check-css-tokens.py` holds it: every `var()` in
  BLOCK 2 resolves to a declaration in BLOCK 2, or is a `--tm-*` runtime token carrying a
  fallback. A token that only BLOCK 1 declares works in the prototype and dies at switchover —
  which is exactly the state that rule was written for: 35 tokens used, ONE declared.

### 3. The DOM is a contract, checked offline.

Per region, a vitest test renders the component with the shared fixture and asserts that the
emitted **tag chain + class chain** equals the prototype's. jsdom, milliseconds, no browser.
This catches "translating" at the moment it happens.

### 4. What replaced « zero divergence »

`scripts/parity-probe.py` used to render the same DOM twice — once dressed by BLOCK 2, once by
the extracted stylesheet — and diff `getBoundingClientRect` plus a fixed `getComputedStyle`
subset over 51 regions × 49 states × 2 themes. It was the only thing that could catch the
rescoping changing a cascade while the emitted text stayed exactly right, and it earned its keep:
it caught two such defects on 2026-08-20 alone, one of them 7 300 divergences wide.

**It was deleted with the extraction it measured.** There is no second stylesheet to be in parity
WITH: BLOCK 2 is the app's CSS, full stop. Keeping the probe would have meant paying 7 minutes of
CI per PR to compare a file with itself.

What holds BLOCK 2 now is narrower and honest about it: `scripts/check-css-tokens.py` (every
`var()` resolves), the 50 rule scripts in `harness/`, and the fact that a rendering change in the
prototype IS the product changing — there is no copy of it left to diverge.

## Every state has a name, and knows how to reach itself

`window.__go("<id>")` drives the prototype into a state **without clicking**.
`window.__states()` returns the 54 ids. The **≡** button in the harness opens a panel listing
them all.

This is what makes a rule deterministic. Without it, measuring "the blocked card" requires
knowing how to make one appear — and that knowledge is exactly what evaporates over time. With
it, a rule says `__go(state)` and measures. The parity probe used to walk `regions.json` this
way; both it and that map went on 2026-08-20 with the extraction they served.

Three orthogonal dials the panel exposes:

| Dial          | Values                            | What it changes                      |
| ------------- | --------------------------------- | ------------------------------------ |
| Data scenario | `real` · `loaded`                 | the real system state vs a dense one |
| Surface phase | `ready` · `loading` · `error`     | every surface goes through all three |
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

## `regions.json` — the project's memory

It used to carry the extraction contract too: `exportedSelectors` (the 461-entry allowlist),
`harnessSelectors`, `probe`, `regions`, `states`, `scope` and `outOfScope`. All seven served the
CSS extraction and its parity probe, and went with them on 2026-08-20 — there is nothing to
export to. What is left is the part that was never machinery:

- **`$vocabulary`** — the frozen CSS-name exceptions, each with the reason it was kept. Read by
  the no-French guard's class-name and custom-property arms.
- **`target`** — read by `harness/address.py`.
- **`$adversarialReview`** — the rule set (R1…R64) plus `$methodLessons`: what each rule
  exists for, and what a rule that failed to bite taught. `$reportedDefects` lists the
  defects found by hand, each with its test in `harness/bugs.py`.

It used to carry the probe's emulation settings, the `computedStyle` subset to diff, the
allowlist of accepted divergences and `outOfScope`. All four went with the parity probe on
2026-08-20 — see the section above. What is left is the project's memory, and `$vocabulary`,
which the no-French guard reads.

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

**The copy ages by design.** The system keeps running: the scheduler searches twice a day
and increments each follow's attempt counter in `acquire.db`, so the embedded counters
drift and `content.py` (which compares the cards against the LIVE database) goes red with
no code change. `resync.py` closes the gap the only honest way — it reads the live
counters and rewrites the embedded ones, nothing else. Run it when the suite names a
drift, review the diff, commit it as data.

`frontend/maquette/resync.py` is that tool, run standalone
(`python3 frontend/maquette/resync.py`) before the suite, not as part of it: it opens
`acquire.db` read-only, computes each followed title's real attempt count, and rewrites
only the matching counters already embedded in `design/src/engine/legacy.js`'s data blocks —
never a layout, a class, or anything the harness itself measures. It reports how many
objects it corrected and touches the file only when a count actually changed, so a clean
run leaves no diff to review. A correction is committed on its own, as data, never folded
into a code change it happens to precede.

**Two scenarios**, switched from the harness (the **≡** button):

- **`real`** (default) — the exact state of the system. Calm: nothing to grab, nothing in
  flight, two stuck folders. This is what makes the **rest states** judgeable; a prototype
  that is always busy never shows them.
- **`loaded`** — a dense state, for judging density and scrolling.

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
| Release card  | `ReleaseCard`/`DecisionCard` | the resolution and release screens — **not a medium**        |
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
(`harness/panel.py`) states it.

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

`harness/cards.py` proves all of it; R41–R50 in `regions.json` state it.

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
(R49), and reveals it on submit. R53 (`harness/startup.py`) checks all of it, gate included —
it starts `serve.py` on a scratch port and drives a real submit.

**Leaving is the same story told backwards.** « Se déconnecter » used to answer with a message
saying the session had been closed, over an interface that had not moved and was still signed
in. A message is not a destination. The session IS the cookie, and the cookie belongs to the
server, so the server is asked to drop it **first** and the entry screen only reflects what has
already happened — an entry form shown over a live cookie is contradicted by the next reload.
R54 (`harness/logout.py`) checks both halves, and the invisible one is the one that
matters: it asks the server, afterwards, whether the session is still accepted.

## The cut is by the nature of the trouble

Four surfaces, and what decides which one a panel belongs to is not the page it came from:

| A medium in trouble               | **Arrivées**      |
| --------------------------------- | ----------------- |
| A machine in trouble              | **Système**       |
| A setting                         | **Configuration** |
| A command run against the library | **Maintenance**   |

`Contrôle` does not survive this cut **as it is**. Production stacks blocked media on top of disk
and provider health with nothing saying why they share a page; each of its **eight** panels
(`ToHandleList`, `ScrapeActivityPanel`, `LastRunDigest`, `StalledPanel`, `AcquisitionSummaryCard`,
`SchedulersPanel`, `CompactHealth`, `PipelineControls`) has a home under the rule. The full
mapping, panel by panel, is in `IMPLEMENTATION.md`.

> ⚠ **Amended 2026-08-19.** This paragraph used to end « and none of those homes is a new page »,
> and that sentence was read as « `/control` and `/pipeline` are deliberately page-less ». The
> operator has overturned it — see the banner at the top of this file: EVERY screen is redrawn.
> What survives here is the PLACEMENT argument, never an exemption from being drawn. The
> identical sentence was amended in `IMPLEMENTATION.md` first and this copy was missed, which is
> the third time one wording has outlived its correction in a second file.

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

`harness/drawer.py` holds all of it; R65 states it.

## A trap that cost real time: **screenshots are not an oracle**

Every capture a rule takes goes through `common.shot` and lands in
`harness/__screenshots__/`, gitignored: a reading aid you open when a rule fails, never a
proof — a path relative to the caller once scattered 127 of them across the repository
root, where a blanket `*.png` rule hid every one.

Two captures of the **same, unmodified file** disagreed on 8 to 15 of the 47 states. Skeleton
shimmer, the media-sheet header entrance, async decode of the embedded WebP visuals: none of
it settles on a schedule you can wait out reliably. Freezing animations and awaiting
`img.decode()` narrowed it and did not close it.

A run of that oracle "proved" 20 states changed after a deletion. They had not. The deletion
was correct all along.

**Use the deterministic oracle instead** — bounding rectangles plus a fixed `getComputedStyle`
subset. That is what the parity probe used before it was deleted with the extraction it
measured, and the recipe outlives it. And for the specific question
"is this rule dead?", there is an exact answer that needs no oracle:

```js
document.querySelectorAll(".act.grab").length; // over all 47 states → 0 means it can never apply
```

combined with "the source never writes this class name" (so no interaction can produce it).
That is a proof, not a sample. `harness/export.py` ran exactly that, and went with the
allowlist it guarded — the question and its answer are recorded here because the NEXT dead-rule
hunt will need them.

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
`harness/mouse.py` proves every gesture with a real mouse; `harness/deck.py` proves the deck
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

`harness/touch.py` drives all of it through `Input.dispatchTouchEvent`, which is real browser
input rather than an event object handed to a listener. That is the only oracle that can tell
the two apart.

---

## `harness/` — the rule suite

**Run it with `harness/run.sh`, never by hand.** The script builds the prototype and refreshes
the copy the rules read before measuring anything — that copy is manual, and a stale one measures
the previous build without saying so. Two tiers: `--contracts` (5 rules, minutes, wired into CI
on every maquette PR) and no flag (all of them, the gate before a wave merges — one headless
Chrome per rule, as many at a time as the machine has processors).

Until 2026-08-20 the suite ran NOWHERE automatically — not in CI, not in `make check`, which only
printed a reminder. That day a rename broke six contracts and four were visible to nothing else.

The 51 scripts that measure the prototype in headless Chromium. They are committed because they
encode recipes that cost time to get right, and because a rule with no script is a sentence in a
file.

| Script               | What it proves                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sweep.py`           | all views render content, no horizontal overflow, device at 390px, no JS error. **A view that renders nothing fails.**                                                                                                                                                                                                                                                                                                                                                             |
| `scen.py`            | the same sweep across both data scenarios, with explicit sub-view reset between runs                                                                                                                                                                                                                                                                                                                                                                                               |
| `states.py`          | every named state renders, without overflow or JS error                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `common.py`          | not a rule: the plumbing every script borrows — how a verdict prints, how a run ends, how the document is opened past the startup screen. Twelve copies of the same `check()` meant a fix to the reporting had to be made twelve times, and one change to the opening cost twenty-eight hand edits                                                                                                                                                                              |
| `deck.py`            | the deck answers a swipe either way — left skips and comes back, right dismisses with an undo                                                                                                                                                                                                                                                                                                                                                                                      |
| `gallery.py`         | one tile pattern in every gallery                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `mouse.py`          | every gesture answers a MOUSE too: the interface is used from a desktop browser                                                                                                                                                                                                                                                                                                                                                                                                    |
| `surfaces.py`        | every surface the interface draws is reachable and renders                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `audit.py`           | rules R1–R10 and R20–R23 across every state, and it announces how many rules it EXECUTED                                                                                                                                                                                                                                                                                                                                                                                           |
| `audit2.py`          | rules R11–R17 and R26–R31: uniformity, honesty of the text, one back design, one season rendering, episode presence against the data, a panel that never offers an action the medium does not support                                                                                                                                                                                                                                                                              |
| `cards.py`          | rules R41–R50: the card and gallery contract — poster to the sheet, body to the panel, no action reachable from a single surface, the same panel from a card and from a gallery                                                                                                                                                                                                                                                                                                    |
| `bugs.py`            | one test per defect found by hand                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `inter.py`           | swipe, infinite scroll, load error + retry, delete dialog                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `follows.py`          | Suivis conformity across its three modes                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `selection.py`             | the two delete paths from the grid: long-press and selection mode                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `scroll.py`          | no form interaction moves the scroll position                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `filters.py`         | filters filter, and their parts sum to the whole                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `actions.py`         | the simulated behaviours really mutate the state                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `dest.py`            | every button has a destination                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `ident.py`           | identify ≠ follow: the context picks the verb — and the journey settles the history it stacked (the panel's entry and `/add`) in ONE announced operation, landing where the walk stood before `/add`, the next back still worth exactly one step                                                                                                                                                                                                                               |
| `pop.py`             | the episode date popover, in all its states                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `chrome.py`          | R51: the harness bar covers none of the app's fixed controls, in every named state, at both sides of the 520px breakpoint                                                                                                                                                                                                                                                                                                                                                          |
| `back.py`          | R59: the back gesture walks the path in reverse — tabs and lenses included — closes a layer first, and at the root warns instead of leaving, closing only on a second back within five seconds                                                                                                                                                                                                                                                                                     |
| `settings.py`        | R60: the settings are navigated by what one wants to change, never by file; every real setting belongs to one rubric and is identified by its label alone — subject then action, in French; nothing is written until the save bar names the files it will write; a secret says only whether it is set                                                                                                                                                                              |
| `palette.py`         | R61: no bare `var(--x)` names a property the document never defines, and the brand colour is actually painted on the wordmark, the sign-in button and the startup bar                                                                                                                                                                                                                                                                                                              |
| `entry.py`          | R62: the sign-in screen renders identically on the host and inside the prototype, and the host redeclares nothing the reference owns                                                                                                                                                                                                                                                                                                                                               |
| `content.py`         | R63: a follow's card carries what `acquire.db` really holds and phrases it as « En cours » does; a library row carries the synopsis, clamped to the largest number of lines that fits, and shows nothing when the NFO has no plot                                                                                                                                                                                                                                                  |
| `drag.py`          | R64: a row opens a drawer either way, one at a time, without firing the tap — measured on Chromium AND WebKit, where the drawer used to spill past the card; and a REVERSAL settles the row back rather than leaping, sampled during the drag because a jump is a discontinuity                                                                                                                                                                                                    |
| `url_state.py`     | R69: the URL carries the state (DOIT-10) — walking writes the address, a reload lands on the same screen, only what differs from the opening state is written, a wrong address is left exactly as typed, and back walks the addresses in reverse                                                                                                                                                                                                                                   |
| `address.py`         | R68: an unknown address renders instead of raising, names what was asked for and offers a way out; the account surface draws the one real account, compared against `web.json5`, and marks the place of the others EMPTY                                                                                                                                                                                                                                                           |
| `machine.py`         | R67: Système is the machine, Maintenance is what one does to the library — no blocked medium on Système, no scheduler called « stopped » between two runs, both lists counted against `pm2 jlist`, every command checked against the engine's registry in both directions, and a command that DELETES inert until it has been run blank — each of the five lists held to being FOUND, with rows to judge, before anything judges its contents, because they are located by their French heading and « no row is wrong » is true of no rows at all                                                                                                                                            |
| `arrivals.py`        | R66: Arrivées carries the pipeline's health — one control that fits the state, a run asked during a run QUEUED rather than refused, the engine's nine steps in its order, nothing-to-do said with an em dash, and every figure checked against the run `library.db` really recorded                                                                                                                                                                                                |
| `drawer.py`          | R65: the drawer is a place one passes through, not a route — every entry names a page that exists and arrives there, the destination takes the drawer's own history entry, closing a layer neither rebuilds the page underneath nor loses where it was scrolled, and every entry is legible measured as PAINTED                                                                                                                                                                    |
| `install.py`    | R51: the install offer is actually OFFERED — `beforeinstallprompt` captured, its default prevented and replayed on a gesture; the iOS guide raised by an iPhone user agent; nothing offered to an installed app, over the entry screen, or after a refusal                                                                                                                                                                                                                         |
| `pwa.py`             | R52: the LIVE host is installable from the first document a phone reaches — manifest, icons that load, worker registered and controlling, offline fallback cached. Runs against `tm-design.iznogoudatall.xyz`, not the local server                                                                                                                                                                                                                                                |
| `startup.py`       | R53: the startup screen is declared first, covers the frame, offers no control, is gone after the first render, and the gate the server builds shows the same screen — extracted — from the submit onwards. Starts `serve.py` on a scratch port                                                                                                                                                                                                                                    |
| `logout.py`     | R54: signing out lands on the entry screen AND the server stops accepting the session. Starts `serve.py` on a scratch port                                                                                                                                                                                                                                                                                                                                                         |
| `panel.py`         | R56: one panel builder, no caller passing markup, no inline style inside a panel, one heading, no action without a destination, and an undeclared block refused                                                                                                                                                                                                                                                                                                                    |
| `decision.py`        | R57: the arbitration screen — the folder as subject, no sheet or panel promised, no engine token on screen, a score printed only when it separates, each candidate wearing only its own poster, three ways out, and answering emptying the queue on both lists                                                                                                                                                                                                                     |
| `touch.py`           | R55: every gesture under REAL touch input (`Input.dispatchTouchEvent`), which the compositor can cancel — the pull to refresh on seven surfaces, the swipe between views, ordinary scrolling, the swipeable row and the deck                                                                                                                                                                                                                                                       |
| `images.py`          | R70: the design's SOURCES embed no image and every `assets/` reference resolves to a file — read across the fragment AND the engine module, because the 930 references live in the latter                                                                                                                                                                                                                                                                                                                                                                                                   |
| `screens.py`          | R71: a screen above another one — back redraws the screen it covered (query and scroll included) through both exits, one more back leaves the layer, and a result card carries no inline action in its foot: the panel is the single path to the act                                                                                                                                                                                                                               |
| `shell.py`        | R72: the Vite shell emits the prototype verbatim inside a real envelope — the fragment refonte.html appears byte-for-byte exactly once, the module entry is present with the correct format, and the named bundle file exists under dist/vite/                                                                                                                                                                                                                                     |
| `bridge.py`            | R74: the bridge wires the legacy nav cluster to the router — zero raw history calls across the design's sources, the journey works through both exits, deep URL entry lands on promised state, __go() preserves history depth, and the boot handshake is real: `window.__demarrerMoteur` exists and the startup screen comes off on its own, before the harness ever touches it                                                                                                                      |
| `switchover.py`         | R73: the host serves the build to the byte, rebuilds stale sources before serving, and a broken build answers 503 that says so — proven against a scratch design root, never the real source                                                                                                                                                                                                                                                                                       |
| `server.py`         | the prototype's HOST, and a rule about itself. `--serve 8899 <root>` is what `run.sh` starts and every rule reads: it serves the built copy at `/` and folds every address with no file behind it onto the document, so a page at a real path (`/media`) and a deep screen address (`/add`) can be requested cold rather than only reached from inside an already-loaded document. Two sets keep their 404 — `ASSET_PREFIXES` (`/vite/`, `/assets/`, `/src/`) and `ASSET_PATHS` (`/sw.js`, `/manifest.webmanifest`, the two icons) — because they are resources, never addresses. Run bare it is a RULE: seven holds over its own behaviour, including that the live host on 8899 is this server and not a plain `http.server`. `start_server` is the scratch variant a rule raises on its own port (8918 here, 8917 in `screen_addresses.py`) |
| `screen_addresses.py` | R75: a screen route answers a real address, cold, and only while it is open — `/profile/$title` opens the promised screen with no journey and no click, every image the document loads at that depth resolves through `<base href="/">`, one back from a walked-to screen lands exactly where the walk started with the address returning to what it was, a wrong deep address renders honestly instead of raising, and `/add?q=…` opens with its field and results already drawn |
| `library_sort.py`    | R78: every sort goes BOTH ways, and each way says its own name — the panel offers the six explicitly (« Ajout récent » / « Ajout ancien », « A → Z » / « Z → A », « Les plus incomplets » / « Les plus complets »), exactly one is marked, the control on the count line reads the direction in force, the reversal is measured on the ROWS DRAWN over a library narrowed until the whole set fits on one page, and the sort stays out of the address — a preference, not a place |
| `library_load.py`    | R79: the library loads more, says when it cannot, and lets one try again — the end of the sample says it IS the end of the sample and how many titles the prototype really carries, a failed page says what remains valid, and « Réessayer » really loads, measured with the scroll sentinel NEUTRALISED because it produces the same outcome for a different reason |
| `focus.py`           | R81: what an assistive technology is told, and an audit cannot see — a layer takes focus when it opens and gives it back when it closes; opening the drawer or the sheet moves focus INSIDE it and marks the background `inert` (never `aria-hidden`, which hides a subtree from a screen reader and leaves every control in it tabbable, the worst of both); `Escape` closes the layer on top through the verb the engine already publishes; closing gives the background back and returns focus to the control that OPENED it; and the skip link is the first stop of the tab order and lands FOCUS on the main region, not merely the scroll position. None of this is visible to an automated audit, which reads the markup of one moment where this reads a SEQUENCE — the two instruments do not overlap. Measured on a fresh page for the tab-order holds, because the browser's sequential focus starting point is set by the last CLICK and `blur()` does not move it. It also holds what the interface SAYS while it works: the main region carries `aria-busy` while a page loads and stops carrying it once loaded — set in the page host, the one place that knows every page's phase, because marked page by page the eighth call site is the one that gets forgotten — and every error surface announces, summed over EVERY state whose id says error rather than sampled on one, after a first version drove a single state, found a single surface and printed that as a census |
| `page_host.py`       | R77: one owner per PAGE, and the container never holds two — the fragment writes `#view` only for a page without `shellOwned`, the shell empties it when it takes ownership, and a page draws the same whichever world it was reached from (the residue hold, which measures constancy across predecessors rather than a root count, because pages emit different numbers of roots); the delegation still reads what React emits — the nine `data-*` attributes the document-level handler acts on, each driven by a REAL tap that compares the row's own value against what opened, and looked up before it is tapped so an absent or inert control is a verdict rather than a dead script; and leaving a migrated page with an unsaved change and coming back leaves the shell ALIVE — the hole that let the legacy remove a node React owned, tearing the root down; and the handover law is held TWICE — structurally, read from the engine's source because the branch it guards is dead while every page is shell-owned, and behaviourally, by spying on `#view`'s own setter through one real redraw, a hold that carries its own positive control because a count of zero passes just as happily when the detector is dead |
| `navigation.py`      | R76: the shell owns navigation through one door — `navigate(` appears exactly once under `design/src/`, inside `go()`'s own body; a round trip through the door writes one history entry per call and back walks them in reverse, judged by the screen's own observed state, never by `history.length`; two navigations issued in the same task, no `await` between them, still produce two separate entries                                                                    |

Run them with the Python that carries Playwright, against a local static server on
**127.0.0.1:8899** — **never** 8710 / 8711, which the reverse proxy routes to prod and
staging.

**Two rules measure the LIVE host instead** — `pwa.py` (R52) and `entry.py`, because
installability and the sign-in gate are things only a real server hands out. That makes them
the only rules whose verdict depends on a PROCESS rather than on a file: `serve.py` is read
once, at boot, so a change to it is not live until `pm2 restart torrentmate-design`. Until
then the host answers its own build-failure page, and those two go red naming symptoms that
have nothing to do with the change under test — « the login gate declares no manifest »,
`Cannot read properties of null`. Both were seen, and both were the stale process.

**So: after any edit to `serve.py`, restart the design host before reading the suite.**

**The harness measures the BUILD.** `wrapped.html` is a copy of `dist/index.html` — the
same document the host serves — rebuilt and re-copied before every run, or the suite
measures the previous version. The copy is what isolates rule mutations from the host:
a rule may corrupt its copy freely, the real build stays untouched.

```bash
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
```

The wrapper directory `/tmp/tm-refonte/` must also carry an `assets` symlink to the repo's
`design/assets/`:

```bash
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets
```

Without it, every image reference (`src=` and `url()` values) resolves to a 404. The
envelope carries the viewport meta; the prototype also injects one itself if the host page
has none — do not remove that guard.

## Language of the source

Every comment in this directory — HTML, CSS, JavaScript, Python — is written **in English**,
and carries no reference to a work session, a phase, or a dated decision. It must read years
from now, out of context. Interface copy quoted inside a comment stays in French, because that
is what the screen says.

**So is everything else the source NAMES.** Identifiers, function and type names, **class
names — code and CSS alike** — **file and directory names**, and every message a tool prints:
English, on the day the thing is written. This is not a cleanup someone does later; a French
name arriving today is a French name a whole wave has to remove tomorrow, and it will be
holding four worlds together by then (the fragment's markup, the shell's components, the
harness's selectors, the extracted stylesheet).

Two things are NOT covered by that rule, and confusing them is how a rule goes quiet:

- **The French the app RENDERS.** A hold asserting « En cours » keeps asserting « En cours »
  — the interface speaks French. Translating a word inside a rendered vocabulary does not go
  red, it goes SILENT: `"des erreurs"` became `"des errors"` once and no rule noticed, because
  a rule that measures nothing passes.
- **Data and addresses.** `data-*` names and values, route paths, `__go` state ids, the
  follow/episode state tokens, the config keys the settings dictionaries are keyed by: those
  are contracts, and renaming one moves the contract rather than a name. The frozen ones are
  listed, each with the reason it was kept, in `regions.json`'s `$vocabulary`.

## The data-* vocabulary (L02)

**One attribute, `data-part`, its value namespaced by `/`**: `card`, `card/title`,
`card/poster`. The namespace names the owning DOM concept; the leaf names the role.
The style class STAYS beside it — `className="ctitle" data-part="card/title"` — the
class still styles, and L07 removes it. Keeping both is not duplication: it is the
separation L02 exists to create.

**Boolean state attributes carry no value, and the list is DERIVED, not
enumerated.** An attribute is one when the harness asks whether it is THERE —
`[data-open]`, `hasAttribute('data-open')` — and never what it says. Twenty-four
qualify today: `data-announced`, `data-blocked`, `data-clearq`, `data-confirmadd`,
`data-delsel`, `data-drawer`, `data-edited`, `data-empty`, `data-in-library`,
`data-leave`, `data-manual`, `data-mono`, `data-no-poster`, `data-open`,
`data-qsettings`, `data-read-only`, `data-resolve`, `data-restart`, `data-save`,
`data-scroll-root`, `data-shown`, `data-skeleton`, `data-solid`, `data-sort`. Do not
maintain that list by hand — `check-markup-contracts.py` prints what it derived on
every run. It was a hand-written tuple of SEVEN for one wave, and twelve shipped.

**In a component, a state attribute is `data-open={isOpen || undefined}` — never
`data-open={isOpen}`.** React renders `data-*` as strings, so `false` becomes the
string `"false"` and `[data-open]` then matches ALWAYS: a rule goes green while it
measures nothing. The trap is not a remembered convention — `harness/attrs.py`
demonstrates it in the live document, rule 51 of the suite, and ARM 4 of
`check-markup-contracts.py` refuses the spelling that falls into it.

A NAMING attribute's VALUE is a name someone chose, so `scripts/check-no-french.py`
reads it — 484 values today, through `nofrench_values.py`. Five attributes qualify
(`markup_text.NAMING_ATTRIBUTES`: `data-part`, `data-region`, `data-tone`,
`data-action`, `data-side`), and the markup guard reads the SAME list to hold a
different question — every value a rule selects is emitted somewhere. An ADDRESS is
not a name: `data-go="profil"` names a page, and the guards leave it alone.

**An emission may be imperative.** Most parts are anchored in markup — `class="ep"
data-part="episode"` — but an element the engine BUILDS carries no markup literal:
`createElement.className = "eppop"` is such an element, and its anchor sits beside the
assignment, `createElement.dataset.part = "episode/popover"`. The guard's emission reader
knows that form and `setAttribute("data-part", "…")`, with a literal value only; a computed
value is unread in every form, so a computed class is anchored with a literal `data-part` at
the same site.

**The floor is a HARD ZERO, not a burn-down.** `scripts/check-markup-contracts.py`
refuses the FIRST class token in any rule selector — passed to `querySelector`, held
in a variable, a table, a concatenation, or READ from the class attribute without a
selector at all (`className.includes('x')`, a regex of class names, a table matched
against a spread `classList`, an injected CSS rule) — and the first
`classList.contains` at a site `GENRE_SITES` does not exempt, by `file:line`. There is no baseline file, no budget and no
`--allow-additions`: the guard takes no argument at all. The shipped debt was carried by
a burn-down list while it was being migrated, and list, ratchet and escape hatch were
deleted in the same move as the last entry — an empty tolerance is a tolerance someone
raises.

**And the zero is only worth what the readers SEE.** A selector the harness BUILDS
spells itself in neither shape a naive reader expects: an f-string carries `{…}`
interpolations, and a selector concatenated onto a variable starts with a space. Both
were live and read by NOTHING — not the guard, not the independent
`classify-rule-anchors.py`. The shape test now treats an interpolation as an opaque
token that does not end the selector, and accepts the leading space; it still refuses a
brace that never balances (`.splashbar {` is stylesheet text) and an `=` outside an
attribute block (`#splash.hidden = {…}` is a journal label about an element, not a
selection of it). Both readers must report zero — `classify-rule-anchors.py --baseline`
prints `[]` — because one reader's zero is a claim.

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
  reference is broken, and the copy is the only place anyone ever looks. The proof that an
  extraction changed nothing is byte-identity of the rendered text across every driven state,
  plus the full suite at unchanged hold counts.
- **A few literals stay French, and say why.** A data value, a `data-*` value, a route
  parameter: each carries a `// french-ok: <reason>` (or `# french-ok:`) pragma on its own
  line, the line above, or the line below. A pragma citing no reason is itself a violation.

**All of this is enforced, not remembered**: `python3 scripts/check-no-french.py` — fourteen
arms, listed in that script's own docstring and held against it by arm 13, which also reads
the count out of `CLAUDE.md` and out of THIS file
(strings, identifiers, file names, class names), wired into `make check` and into its own CI
job. Each arm also reports what it READ, and an arm that read nothing fails: a scope that
silently empties would otherwise announce « no violation » while measuring nothing.
