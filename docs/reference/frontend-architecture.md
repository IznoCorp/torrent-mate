# Frontend architecture — the target the maquette is built towards

**This file says what the maquette must BECOME, and in what order. It never says where the work
stands** — that is `IMPLEMENTATION.md` § « Where the frontend work stands », and it is the only
file that says it.

The maquette is the next version of the frontend and it REPLACES the shipped one: on switchover
day `frontend/src` is archived and `frontend/maquette/` takes its place (`product-intent.md`
§15). So every page and every MECHANISM the shipped app has must eventually exist here. The pages
are the part that is finished. What remains is most of what makes an application, and this file
is the plan for it.

---

## 0. Picking up work — read this first

1. Read `IMPLEMENTATION.md` § « Where the frontend work stands » — which lot landed, which is
   next. Its § THE OBJECTIVE carries the measured inventory, not the state; the two are different
   sections and this file used to name only the second.
2. Come back here and find **the first lot whose status is not `LANDED` and whose dependencies
   are all `LANDED`**. That is the work. There is no other selection rule, and lots are not
   reordered for convenience.
   **If that lot carries a blocking note**, take the next one that satisfies the same rule, and
   say in the wave's plan which lot you skipped and why. A blocked lot is not a reason to stop
   or to go asking where to start — this file is where to start.
3. Read that lot's **Done when**. It is the contract. A lot is not finished because its code
   exists; it is finished when every line of that list is true.
4. Write the wave's plan under `docs/superpowers/plans/`, on its own branch, as every wave here
   has been done.

**Three rules bind everything below.**

- **No figure in this file without the command that produces it.** Numbers rot. A number nobody
  can re-measure is a number nobody can contest, and this repository has already read a stale
  table as current for three days.
- **One kind of change per wave.** A conversion proves the rendering did not change; a
  behaviour change proves the behaviour did. Never both in one wave — an edit hidden inside a
  move is an edit nobody can review.
- **If a lot has lost its subject, stop and say so.** Do not execute it faithfully because it is
  written here. See § 7.

---

## 1. What this file covers, and what it does not

| Document | Owns |
| --- | --- |
| `docs/reference/product-intent.md` | what the product must BE (constitution, binding, dictated by the operator) |
| **this file** | what the frontend must BECOME technically, and in what order |
| `IMPLEMENTATION.md` | where the work stands — the only state, with its commands |
| `docs/superpowers/specs/` · `plans/` | the scope and the steps of ONE wave |
| `frontend/maquette/README.md` | how the prototype runs, its named states, the traps already paid for |

This file covers items 2, 3 and 4 of `IMPLEMENTATION.md` § THE OBJECTIVE → REMAINS — the visual
language, the application itself, and the legacy engine — plus the safety net they all need and
the method they all follow.

**Item 1 is deliberately outside this file**: `/control` (8 panels) and `/pipeline` (10 panels)
are surfaces still to be drawn. They follow the existing method — drawn in the maquette first,
named states, a rule that bites — and they are named here only so nobody reads their absence as
an arbitration. They are not blocked by any lot below, and no lot below is blocked by them.

---

## 2. Decisions on the record

Each entry states what it replaces and what it makes void. **This section exists because of the
most expensive failure in this project's history**: a decision changed on 2026-08-13, the
implementation directives did not, and a whole layer of tooling stayed in place with no subject
for seven months of work. When a decision changes, what loses its subject is removed in the same
move — not kept "just in case".

### D1 — The address carries identity; the query carries state

**Decision.** Every page and every screen has a real path. The **path carries the IDENTITY** —
which thing is being looked at. The **query carries the STATE** — how it is being looked at.
`/library/breaking-bad?sort=recent&season=3`. Never `?page=lib`, never `/library/sort/recent`.

**Replaces.** The model where a page lived in the query and only screens had paths.

**Why.** Every detail owes its URL (`product-intent.md` DOIT-10). A path makes a surface
shareable, reloadable, and gives the phone's Back button a coherent meaning.

**What it costs, and it is PAID.** The maquette stops opening from `file://` — the single use
lost, and it is gone rather than pending. Path routing needs a host that rewrites unknown
addresses onto the document: `serve.py` already did, the reverse proxy will, and the harness host
moved from a plain `http.server` to `server.py --serve` in L05, which is what makes every rule,
the oracle and the accessibility audit read a page at a real path instead of a not-found page.

**What becomes void.** R69 holds the opposite rule today. It is renegotiated in the same wave
that lands D1, with the reason written down — never left to contradict this.

**Layers are ranked in three tiers**, and the tier decides the addressing:

| Tier | Example | Addressing |
| --- | --- | --- |
| Content | a media sheet, its releases, a resolution | its own **path** |
| Screen state | an actions panel, a filter drawer | a **query parameter** |
| Transient | a sort menu, a confirmation | **no URL**, but Back still closes it |

### D1b — Back pops a stack of deliberate arrivals; the parent is only the floor

**Decision, dictated by the operator on 2026-08-23 and completed on 2026-08-24. DELIVERED** by
the L05 repair wave's phase 11 (`docs/archive/features/maquette-l05/plan/phase-11-navigation-path.md`),
merged in PR #484. The constitution's `product-intent.md` § 16 is the authority; this entry says
what the implementation owes and records what was built. Three rules stand; a fourth was
considered and rejected — see rule 4 below.

1. **Back pops, and the stack holds only deliberate arrivals.** Opening a surface — a sheet, a
   resolution, a panel — pushes. Adjusting one — a filter, an inner tab, a sort, a lens —
   replaces. The engine did NOT work this way before phase 11: `recordPath()` had eight call
   sites and seven pushed a SETTING. Phase 11 split it into `recordPath()` (arrivals) and
   `replacePath()` (settings), and gave each page switch its own verb (rule 2).
2. **Switching a top-level page REPLACES, with the entry page kept beneath.** The stack under any
   top-level page is `[guard, /acquisition]`; under a non-home page
   `[guard, /acquisition, /page]`. Switching between two non-home pages replaces the top; going
   TO `/acquisition` from elsewhere pops back onto the floor already there (pushing or replacing
   would leave two acquisition entries, and a silent Back). Back from any page lands on
   `/acquisition`; Back from there arms the exit guard. That is Android's
   `popUpTo(startDestination)` said in this codebase's terms — taken because a system Back drives
   a PWA, where no platform stacks visited tabs.
3. **Where no stack exists, synthesise it from the hierarchy.** A cold link poses the real parent
   under the screen — the library under a media sheet, the arrivals under a resolution, read off
   the emitter of the screen's own opener rather than guessed — and that parent is **rendered**,
   not merely recorded (`SCREEN_PARENTS` in `lib/addresses.ts`). **What this does NOT simplify,
   measured before phase 11 opened**: a panel's entry composed over the parent still stops the
   router matching the screen's own path and unmounts the sheet (finding 9.3) — the panel hangs
   off the screen's own address whatever page sits beneath, so 9.3's fix stands independently.
4. **Up is a separate gesture, and it is drawn.** Back pops; Up climbs one level whatever the
   path. **NOT delivered** — no lot carries it yet; it is a surface to be drawn in the maquette
   first, like every surface.

**Replaces** the reading under which every screen resolved to the home page (D-8.1, struck by
phase 11 naming this decision). That was not only a UX default: it is the mechanism behind a
reviewed defect — a cold screen address carrying a panel composed the panel's entry over the home
page and the sheet unmounted behind it. Naming the real parent removes the cause.

**The trap this decision exists to forbid**: sending **Back** to the declared parent while a
stack entry exists. History first; the parent is a floor, never a destination.

**Deliberately not done, so it is a choice and not an omission**: per-page stacks. Leaving the
library with a sheet open and returning lands on the library's root, not back in the sheet. It is
added only if real use asks.

**What it cost in proof, and this part had already been paid once before phase 11.** The cases
are held SEPARATELY, in R69's own rule: an in-app walk whose Back returns to the real origin, a
cold link whose floor is the parent, a page switch that stacks nothing (asserted on
`history.length`, never on the address alone), and an exit guard that arms only at
`/acquisition`. A hold that exercises only the cold load is how two of L05's defects passed under
green rules.

### D2 — Tailwind v4 provides the implementation; CVA components provide the API

**Decision.** Styling goes through Tailwind utilities. The design vocabulary is expressed as
**typed component variants** (`class-variance-authority`), not as hand-written CSS class names:
`<Card variant="compact" tone="warning">`, not `class="card card--compact"`.

**Replaces.** The 4 052-line hand-written semantic stylesheet of `refonte.html`.
<sub>`awk 'NR>=188' frontend/maquette/design/refonte.html | wc -l`</sub>

**Why.** Three reasons, in order of weight. Tailwind **enforces a scale by construction**, which
is exactly the defect measured for the visual language — 21 distinct font sizes, 17 radii, 65
padding values, 18 gaps.
<sub>`cd frontend/maquette/design && grep -oE "padding:[^;]+;" refonte.html | sort -u | wc -l`</sub>
Deleting a component then deletes its style, so **no orphan rule can accumulate** invisibly in a
four-thousand-line sheet. And a **typed variant is checked by the compiler**, where a misspelt
class name is silent — which is a stronger guarantee for an agent than any naming convention.

**Why the objection to it was wrong, recorded so it is not re-argued.** Tailwind was rejected on
the grounds that the rule harness selects by CSS class. That defends a defect: a rule anchored on
a style class fails when the STYLE changes, which is the opposite of what a rule is for. The
coupling is the thing to remove (L02), and it is worth removing whether or not Tailwind lands.

**What it costs, and it is accepted.** Roughly eight times the surface of the scale work alone.
The re-anchoring this depended on is **paid**: L02 took the class-anchored selections to a hard
zero, so what Tailwind still costs from here is the conversion alone. A handful of selectors it
cannot express (`:has()`, deep descendant combinators) stay in the base layer. Visual diffs
become noisier — they move from CSS rules into JSX.

**Three conditions, and none is optional.** The oracle exists first (L01). The anchors move
first (L02). Tailwind's scan is confined to the maquette — it has already leaked 936 bytes into
production by scanning from the project root.

### D3 — CSS lives in three layers, and nowhere else

| Layer | Content | Where |
| --- | --- | --- |
| **Tokens** | the whole scale: colour, space, type, radius, duration, easing | **one file**, `@theme` |
| **Base** | reset, safe areas, `100dvh`, view transitions, `@keyframes`, the few selectors Tailwind cannot express | **one file**, short, each rule carrying its reason |
| **Everything else** | a component's own styling | **in the component**, as utilities behind typed variants |

**Why.** One direction of dependency — a component reads tokens, never the reverse. Nothing
global can break a component at a distance. And an agent modifying a component opens **one file**
instead of hunting a rule through four thousand lines.

**What becomes void.** `refonte.html` stops carrying the stylesheet. §15 of the constitution names
that file as the visual reference; when the CSS leaves it, the reference becomes **the tokens
plus the component catalogue**, and §15 is amended in the same move rather than left pointing at
a file that no longer holds its subject.

### D4 — Rules anchor on `data-*`, never on a style class

**Decision.** A harness rule selects on `data-*` attributes and on structural ids. Never on a CSS
class.

**Measured after L02**: 699 selection calls in `harness/*.py` — **0 anchored on a CSS class**,
473 on `data-*`, 188 on an id, 33 on a bare tag, 5 on a role.
<sub>method: extract the string argument of every `querySelector|querySelectorAll|locator|matches` call in `harness/*.py` and classify it</sub>

<sub>Before L02 the same command read 684 calls, 281 of them on a class — that figure is what the
lot existed to burn down, and it is kept here as the measure of what moved, never as a
description of the tree.</sub>

**Why not accessible roles** — the reason held when this was written and no longer does. The
markup could not carry them: 13 `role=`, 2 `<nav>`, **0 `<main>`, 0 `tabindex`**. L03 has landed,
so roles and landmarks ARE a legitimate anchor now. The 699 existing selections are not
re-anchored onto them — `data-*` is not worse, and churn with no defect to point at is churn — but
a NEW rule may select a role where that reads better than a `data-*` invented for it.

**A `data-*` contract has three ends** — the markup that emits it, the `dataset.x` that reads it,
and the rule that taps it. They move in ONE step, or the interface half-works in a way no single
file reveals.

### D5 — The engine dies by subtraction, surface by surface

**Decision.** The legacy engine is not a lot of its own to be executed after the application. Its
cross-cutting parts are lifted once and early; the rest dies with each surface as that surface is
converted and wired.

**Why, and this is a measurement rather than a preference.** `legacy.js` is 34 650 lines, of
which **27 678 (79 %) are fixtures** — `SHEETS_RAW` alone is 20 538 lines of episode catalogue.
The engine's actual code is about **6 949 lines**.
<sub>method: bracket-match every `const X = [` / `const X = {` declaration and sum the spans over 100 lines</sub>
Most of that fixture stops existing when real data arrives. Killing the engine before the data
layer means facing 34 650 lines; killing it as surfaces convert means facing seven thousand,
in pieces, each with the oracle green.

**What is cross-cutting and does NOT strangle surface by surface**: the document-level event
delegation, the boot handshake, and the 254 top-level declarations republished on `window` for the
harness to drive through. **Navigation was on this list and is LIFTED**: L05 took the address
model out of the engine — `URL_DEFAULTS`, `urlFromState`, `stateFromUrl` and the `baseAddress`
plumbing — leaving it the navigation LOGIC (when to record an arrival, what the entry carries, how
a back unwinds the layers). `openScreen` went with them, having lost every caller. `__go` and the
named states remain the harness's own driving seam and belong to L13. The
delegation, the boot, `/login` and the splash close the plan as L13.

### D6 — Accessibility is a lot, not a side effect

**Decision.** Accessibility is planned, proved and landed as its own wave (L03), not absorbed
into other lots.

**Why it was scheduled, and it is history now.** Accessibility was nearly absent — 0 `<main>`,
0 `tabindex`, 13 `role=`. **L03 landed and closed it**: 4 `<main>`, 7 `tabindex`, 32 `role=`, and
744 axe violations over 7 rules taken to a hard zero across the 83 named states, held by
`a11y.py` on its own `--a11y` tier.
<sub>`grep -rho 'tabindex' frontend/maquette/design/src frontend/maquette/design/*.html | wc -l`</sub>
It serves the native-feel objective directly (focus management, assistive technology, keyboard
paths), and — this is what makes it schedulable anywhere — `role`, `aria-*` and `tabindex` are
**invisible to the oracle**: they change neither a rectangle nor a computed style. Only element
substitutions and focus rings are visible, and those are handled as such.

### D7 — The data contract is the maquette's, and it touches no backend

**Decision.** The maquette declares the contract its interface REQUIRES, as its own artefact
inside `frontend/maquette/`. It starts from the contract that already exists
(`frontend/openapi.json`, generated FROM the backend) and diverges deliberately where the new
experience needs more. **Every divergence is recorded as a demand on the backend.**

**No backend work happens until the interface is frozen and validated.** The backend follows the
interface; starting it earlier means rebuilding against a specification that is still moving.
The recorded divergences ARE that future specification, delivered as a diff rather than a blank
page.

**What must not happen**: transposing production's 11 API modules. Production is archived, not
harvested. Its data layer is a reference for what the replacement must be able to do — never a
model to copy.

### D8 — The oracle measures geometry and computed style, never pixels

**Decision.** Non-regression is proved by bounding rectangles plus a fixed subset of computed
style properties, recorded and replayed. Screenshots are not an oracle here.

**Why.** Measured, twice: two captures of the same unmodified file diverge on 8 to 15 states, and
one run of that oracle "proved" twenty states had changed after a deletion that was correct all
along.

### D9 — What a library is adopted for, and where motion lives

**Two rules, and between them they settle every "should we use library X" question without
re-opening the argument.**

1. **What is declarative lives in the stylesheet** — therefore in the design reference, therefore
   under the oracle. Motion written in JavaScript leaves the field of measurement, and a design
   decision nobody can measure is a design decision nobody can defend.
2. **A library is adopted for maths nobody has written. Never for an arbitration already
   proved.**

**Applied, with the verdicts they produce.** These were argued against real alternatives; the
reasoning is kept so the alternatives are not proposed again as if new.

| Candidate | Verdict | Because |
| --- | --- | --- |
| **View Transitions API** for page and layer transitions | **adopt** | native, compositor-driven, zero bytes, declarative — so it is measurable. Same-document transitions are supported on the target platform |
| A JS animation library for **page transitions** | **refuse** | it buys what the platform gives, costs tens of kilobytes, and moves motion out of the stylesheet (rule 1) |
| A JS animation library for **one interruptible spring** that follows a finger and settles | **allowed, scoped** | CSS cannot express interruptible pointer-driven physics. One component, never a transition strategy |
| A gesture library **replacing** the press/drag/scroll arbitration | **refuse** | that arbitration is written and proved here; the library solves the plumbing, not the hard part (rule 2) |
| A gesture library for a **new** gesture needing velocity, inertia or multi-pointer maths | **allowed, scoped** | maths nobody has written (rule 2) |
| **Haptics** | **refuse the capability, build the seam** | the target platform exposes no public API; the workarounds ride an implementation detail that has already been tightened once. One `feedback()` call site all gestures pass through, visual today — so adopting it later changes one file |
| **`onTouchStart` for pressed states** | **refuse** | it lights the pressed state when the finger is starting a SCROLL, so a list flickers as it is scrolled. `:active` is cancelled by the browser when the gesture becomes a scroll, which is the wanted behaviour, for free |
| **`@media (hover: hover)`** to keep hover off touch | **adopt** | the sticky-hover problem is real; this is its declarative remedy |
---

## 3. Invariants — true at the end of every wave

1. **The URL and the interface never contradict each other.** D1's rule holds in both
   directions: no page identity in the query, no sort or filter in the path. And D1b's: opening a
   surface pushes, adjusting one replaces, switching a top-level page replaces, and the parent is
   the floor only where no stack entry exists. The cases are held separately — a hold that walks
   only the cold load leaves the others unmeasured.
2. **No rule selects on a style class.** (After L02.)
3. **No value outside the scale.** A raw `padding: 13px` or `font-size: 15px` is refused, the way
   an undeclared `var()` already is.
4. **Server state is never copied into client state.** Server data lives in its query cache;
   the address lives in the router; only genuinely ephemeral UI state lives in a store.
5. **No data fetching inside `useEffect`.**
6. **A module stays small.** Hard ceiling 400 non-blank lines for a component or module, soft
   warning at 250. Files above it today are grandfathered until their surface's wave converts
   them — never extended.
7. **`ui/` never imports a feature. Two features never import each other.** They compose in the
   route.
8. **No import cycle, and no module-hub.** A cycle makes every other dependency rule
   unenforceable, because the cycle *is* the violation. A module outside `ui/` and `lib/`
   imported by more than a set number of features is refused — the executable form of "no god
   module", and the only guard in this file that acts before its defect exists.
9. **No `any`, no `ts-ignore`.** A ratchet held from zero (L04).
10. **No French in the code and no interface text in the code.** Unchanged
   (`scripts/check-no-french.py`), and it applies to everything written here.
11. **Every change lands with a rule that bites**, mutation-tested: break the behaviour on
   purpose, confirm the rule falls and names the right defect, restore.
12. **A component asks the width it HAS, not the width of the window.** Container queries, not
    media queries, for anything below the shell. A media query reads the viewport, so a 390 px
    frame sitting on a 1280 px desktop is told it has room for six columns it does not have —
    which is why a harness deviation once had to pin three columns by hand. The shell keeps its
    media queries; a component does not get one.
13. **Motion is declared, not scripted** (D9). The single exception is a pointer-driven
    interruptible spring, and it is named where it is used.
14. **Reduced motion is a designed state, not a fallback.** Every transition and every gesture
    has a defined appearance under `prefers-reduced-motion`, drawn like any other state — the
    interface being frozen includes it.

---

## 4. The lots

Status is one word and nothing else: `NOT STARTED` · `IN PROGRESS` · `LANDED`. Anything richer —
which PR, which measurement, which proof — belongs in `IMPLEMENTATION.md`.

### Phase 0 — The safety net

Nothing else may start. Every lot after this one changes mechanism while promising the rendering
is unchanged, and that promise is currently unprovable: `fidelity.py` cannot run — the renderers
it compared are deleted, no recording is committed, and the state ids have been renamed in two
separate waves since.

#### L01 — The recorded oracle · `LANDED`

**Objective.** One command that says whether the maquette renders today what it rendered at a
known-good commit.

> **Where the measurement technique lives now, because it is no longer in the tree.** Retiring
> the translation layer removed `parity-probe.py`, the extraction and, with them, the `probe`
> block of `regions.json` — correctly: they served the abandoned surface-by-surface model. But
> `probe` also held the only replayable measurement recipe this repository ever proved, and it
> is **recovered from history, not reinvented**:
>
> ```
> git show <last commit before the untranslate merge>:frontend/maquette/regions.json
> ```
>
> Six keys, and each earns its place: `viewport` (390 × 844, DPR 2, mobile, touch — a geometry
> read at another width answers a question nobody asked), `assertBeforeMeasuring` (refuse to
> measure if the viewport is not really that), `computedStyleSubset` (**17 properties**;
> amended to **19** by L01 — `opacity` and `visibility` — because `#scrim` opening changes
> neither the other 17 nor its rectangle, so an overlay could stop appearing and the oracle
> would stay green. Evidence in `docs/features/maquette-l01/DESIGN.md`),
> `knownAbsent`, `neutralise` (what to switch off before reading — this is friction
> counter-measure 1, already solved once), and `allowlist` (justified divergences).
>
> Recover it deliberately, with a comment saying where it came from. Rebuilding the list by
> judgement re-opens a question that was already settled by measurement.

**What it measures.** Per *(named state × region)*: the bounding rectangle, plus the fixed subset
of computed style properties above. States come from `states.js` — the single source, **never
counted by regex**: some entries are written out and others generated by a `.map()`, so a pattern
match undercounts, and has already reported a wrong figure in this repository. Regions are
re-declared for this purpose: one region per block a user perceives as a unit. The 51 regions of
the retired probe were chosen for the extraction contract and are not automatically the right
list.

**What it does not do.** It is not a functional test — the rule suite is, and it now runs by
itself: `frontend/maquette/harness/run.sh` builds the prototype, copies it where the harness
reads it, and runs the rules in two tiers — `--contracts` (minutes, on every pull request) and
the full suite (the gate before a wave merges). The oracle is a **third** tier and
does not duplicate either: rules say the behaviour still holds, the oracle says the rendering did
not move. It is not a screenshot (D8).

**Its shape.** Three modes: record the reference, compare and fail on divergence, accept a
reviewed change. The reference is **a committed JSON**, stably sorted and formatted, so a visual
change is read **in the pull request's diff**, region by region.

**Friction is the risk, and it is designed against.** Five causes, each already met here:
animations and asynchronous image decode (animations off, reduced motion forced, images decoded
before measuring, and an explicit settle signal rather than a delay in milliseconds);
non-deterministic data (frozen clock, frozen fixtures — a rule has already failed here because a
scheduler fired); slowness (one browser, one context, states driven in-page); unreadable diffs
(sorted JSON, report grouped by state, naming the property and its before/after); and false
positives, which disarm an oracle within weeks (an allowlist, each entry carrying its written
reason).

**Done when.** It runs in one command; it fails on a deliberate one-pixel padding change and
names the right region; its reference is committed; it is wired into the gate; and its five
friction counter-measures are each exercised rather than asserted.

**Two notes for later, so the oracle is not caught out by lots that come after it.** When real
data replaces the fixtures (L09), determinism moves to the mock layer — **the oracle then depends
on L08**, so plan the two together rather than against each other. And once L12 lands view
transitions, a transition in flight moves the very rectangles this measures: the oracle reads
**at rest**, which its settle signal must guarantee rather than assume.

#### L02 — Test anchors move to `data-*` · `LANDED` · *depends on L01*

**Objective.** No rule selects on a style class. 280 calls move onto `data-*` contracts.

**Why before the visual language.** If the anchors move during the conversion, a falling rule
cannot be attributed — anchor or style. Separated, each failure has one possible cause.

**Half of D4's contract is already held, and this lot must not duplicate it.**
`scripts/check-markup-contracts.py` refuses a `data-*` VALUE the markup emits that no reader
understands — the three-ends defect, and it was written after a rename that looked contained
broke six contracts while `make lint`, `make test` and `make check` all stayed green. What it
does not hold is the other half, which is this lot: **what a rule is allowed to anchor on.**
Extend the existing guard rather than adding a second one beside it.

**Done when.** The classification measured in D4 reports zero class-anchored selection calls; a
rule refuses the next one; every moved contract has its three ends moved in the same commit; the
suite is green at unchanged hold counts.

### Phase 1 — The contracts of markup and structure

#### L03 — Accessibility · `LANDED` · *depended on L01*

**Objective.** Landmarks, roles, accessible names, focus order, focus visibility, keyboard paths,
and focus management on every layer opening and closing.

**Done when.** Every screen has its landmark; every interactive element has an accessible name; a
layer traps and restores focus; the whole application is reachable by keyboard; an automated
audit runs in the gate; and the oracle is green — the non-visual part of this lot must move
nothing.

**Landed** — branch `feat/maquette-l03`, design and plan in `docs/archive/features/maquette-l03/`.
`axe-core` over the 83 named states went from **744 violations over 7 rules to 0**, with the
oracle at **0 divergence over 2 739 measurements**: the non-visual part moved nothing, measured
rather than asserted. The gate is `frontend/maquette/harness/run.sh --a11y` — a fourth tier, in
the full suite and in CI on every maquette pull request — and its floor is a hard zero, no
threshold and no tolerated list.

**What an audit cannot see is held by R81** (`harness/focus.py`, 15 holds): focus entering a layer
and returning to the control that opened it, `Escape`, the skip link landing FOCUS and not merely
scroll, `aria-busy`, and every error surface announcing. An audit reads the markup of one moment;
these are sequences, and the two instruments do not overlap.

**Two rules are asked only where they can be answered**, and it is a condition rather than a list
of excepted states: `landmark-one-main` and `page-has-heading-one` describe the document AT REST,
and with a modal layer open the background is deliberately `inert`, therefore out of the
accessibility tree. The split is printed on every run — 65 states asked, 18 could not.

#### L04 — Boundaries and the tree · `LANDED` · *depended on L01*

**Why here.** Every lot after this one creates files. Deciding afterwards means moving them
twice. **And why it depends on the oracle**: this lot breaks two import cycles, which is a change
to code and not a move — without the oracle nothing proves the rendering survived it.

**What was wrong, and what the lot did to it.** The left column is the measurement that
SCHEDULED this lot; the right one is what the same command reports now. Refreshing it is the
wave's duty rather than an amendment (§ 7.1): what was decided is untouched, and a figure left
standing after the work that falsified it is the stale-directive disease this file exists to
fight.

| Defect | Measured before | Now |
| --- | --- | --- |
| **Two import cycles** | `components/panel.tsx ↔ data.ts` and `screens/add.tsx ↔ shell.tsx` — 3 simple cycles over 2 back-edges | **0**, held by `check-frontend-boundaries.py --arm cycles`. The first back-edge's whole substance was a DUPLICATE: `data.ts` declared a `Panel` type byte-identical to the one already in `seams.ts` |
| **One hub module** | `data.ts`, **17 importers** of ~21 modules — 4 store hooks, ~30 domain types and the engine's 108-member surface at once | **it does not exist.** The store hooks are `lib/store-access.ts`, the engine's surface is two `lib/engine-*.ts` layers plus one slice per feature, and 10 members no component read are gone from the type |
| Its symptom | 6 files import `data` twice, once for types and once for values | **0**, held by `--arm duplicate-import` |
| **Grouped by technical kind** | changing one feature means opening `pages/…`, `components/…`, `data.ts` and `i18n/fr.json` | grouped by SUBJECT: `features/<domain>/` holds its page, its screens and its slice |
| A split about to become a lie | `pages/` ÷ `screens/` encodes a distinction D1 removes | both folders are gone |
| **No bundle splitting at all** | zero `lazy()`, zero dynamic `import()` | **unchanged, and deliberately** — it belongs to L12, which changes loading behaviour where this lot changed nothing observable |
| No unit-level test | all proof is the browser harness; a pure function is proved through a browser | **unchanged.** Arbitrated by the operator on 2026-08-22 and OWNED BY L09 — see the note under that lot: the mock layer a non-vacuous test rests on is L08's, and tests written before it would invent their own fakes |
| Names that say nothing | `data.ts`, `store.ts`, `panel.tsx` — and `media.tsx` is a screen while `library.tsx` is a page | each file is named for what it holds, inside the subject that changes it |

<sub>every figure: `python3 scripts/check-frontend-boundaries.py`, which prints what each of its eight arms derived</sub>

**What was right and is now HELD**: 0 `any`, 0 `as any`, 0 `@ts-ignore`, 0 `@ts-expect-error` —
a ratchet from zero, which was free then and impossible to introduce later. `--arm typing` holds
it at a hard zero.

**The target tree.**

```
src/
  app/          boot, providers, the router tree, service worker
  routes/       one address, one file — thin: it loads and composes
  features/<domain>/   components, hooks, model.ts (its types),
                       queries.ts (its reads and mutations), *.test.ts
  ui/           CVA primitives — no domain knowledge
  lib/          domain-free helpers
  styles/       tokens.css · base.css   (D3)
  mocks/        handlers and fixture seeds   (L08)
```

**The rule that decides where a file goes.** A tree only survives if there is a decision
procedure; without one every agent invents their own.

> **A file lives with what makes it change.**
> One surface makes it change → `features/<that surface>/`. Two surfaces make it change for
> their own reasons → either it knows no domain and belongs in `ui/` or `lib/`, or **it is two
> files**. It knows no domain → `ui/` if it renders, `lib/` if it does not.
>
> **Never create a folder for a KIND of file.** No root `hooks/`, no `types/`, no `utils/`.
> That is what produced `data.ts`.

Its corollary is what dissolves the hub: **a type belongs to the feature that owns the concept**,
never to a shared module. `data.ts` is not slimmed, it stops existing.

**The order inside this lot.** A single-shot move of the tree is unreviewable.

1. **Break the two cycles** — the only real code change here, so it lands alone and is proved
   alone.
2. **Split `data.ts`** — types to their features, store hooks to `app/`, fixtures where L08 will
   pick them up.
3. **Move to the target tree.** No logic changes, so the oracle proves zero divergence.
   Renames go through `scripts/rename-identifiers.py`: a rename needs a parser, not a regex.
4. **Install the guards**, each mutation-tested.
5. **Record the files over the ceiling** with the lot that will convert each.

**What this lot does NOT touch.** Bundle splitting belongs to L12: it changes loading behaviour,
and nothing here may change anything observable.

**And one known defect deliberately left alone**: the harness is **54 `.py` files flat, with no
subdirectory** (53 rules plus `common.py`, the shared plumbing), so nothing says which rule
covers which surface without reading it. It is the same disease one level up.
<sub>`ls frontend/maquette/harness/*.py | wc -l`</sub>
Moving them means changing as many paths cited across documents and briefs
— a real cost for a gain in comfort. It is recorded here so it is known, and it is not scheduled;
it waits for a stronger reason than tidiness.

**Done when** — seven guards, each failing on a deliberate violation and wired into the gate:

1. **no import cycle** (the two above are gone);
2. **a fan-in ceiling** — a module outside `ui/` and `lib/` imported by more than a set number of
   features is refused. This is the one that would have stopped `data.ts` at four importers
   instead of seventeen, and it is the only guard here that acts *before* the defect exists;
3. **layering** — `ui/` and `lib/` never import `features/` or `routes/`; two features never
   import each other;
4. **size** — the module ceiling (invariant 6), covering the frontend;
5. **the typing ratchet** — no `any`, no `ts-ignore`, from today's zero;
6. **no duplicate import** from one module;
7. **one address, one file.**

Plus: the tree matches the target, `data.ts` no longer exists, and grandfathered files are listed
with their converting lot.

#### L05 — Routing · `LANDED` · *depended on L01, L04*

**Objective.** D1 in force. Every page and screen on a real path, state in the query, layers
ranked in three tiers.

**Why it is worth more than it looks, and why it is not deferred.** It pays twice. Lifting
navigation out of the engine is the first subtraction of D5 — and once every named state has an
address, **the harness can drive by URL instead of through `window.__go`**, which detaches it
from the 254 republished globals. That detachment is what makes L13 finishable, and it is also
what lets **the oracle outlive the engine**: an oracle that drives through a seam dies with the
seam. Deferring this lot costs both.

**Done when.** No page identity survives in a query and no state in a path, both checked; a deep
address lands on its state cold; Back and Forward behave on every tier; R69 is renegotiated with
its reason recorded; the oracle is green.

### Phase 2 — The visual language

#### L06 — The scale · `LANDED` · *depended on L01*

**Objective.** One declared scale — space, type, radius, duration, easing — and every declaration
folded onto it. **What landed is 32 tokens in one `:root` block** at the top of BLOCK 2: nine
spacing steps, eight text steps plus one display size, five radii, and, for motion, four
touch-response durations, three loop periods and two named curves. The contract forecast the 65
padding values onto « roughly eight » steps, the 21 type sizes onto « about seven » and the 17
radii onto « about five »; that forecast is written down here rather than quietly replaced,
because space and type each needed ONE step more than it allowed and the operator arbitrated both
(space keeps 24px, type keeps the 10px step). All four families read zero off-scale declarations, and
`check-css-tokens.py --arm scale` refuses the next one outright — no baseline file, no mode that
can write one, and the motion family held in two dimensions at once because a curve is not a
number.

**A family of tokens is not CSS at all, and this lot had to decide their fate.** `--tm-*` names
are *measured and published at runtime*, never declared in a stylesheet, which is why
`scripts/check-css-tokens.py` treats them apart and demands a fallback at every use — a runtime
token with no fallback resolves to nothing until the script has run, which is a visible flash.
The engine dies in L13, so these needed a home before then. **D-L06-4 gave them one: the SHELL
publishes `--tm-bottom-bar-h`** (`design/src/app/bar-height.ts`), the engine keeps no copy of it,
and the eight `var()` uses keep their `, 0px` fallback — the guard still demands it. R84
(`runtime_tokens.py`, 8 holds) holds the three ends: exactly one publisher and it lives under
`app/`, counted over the whole source tree rather than grepped in the engine, because a rule
reading « the engine does not publish » stays green over a second publisher added anywhere else;
the published value equal to the bar's own rendered height; and it still equal once the bar is
forced to a height no state draws.

**L03 HANDED THIS LOT A MEASUREMENT, and D-L06-5 paid it: 42 findings → 0.** Colour contrast is
an accessibility criterion that lands on the palette, so L03 measured it, recorded it and
deliberately did not enforce it (D-L03-4): `frontend/maquette/a11y-contrast.json` held
**42 `color-contrast` findings over 18 of the 83 named states, on 10 distinct elements.** The
split written here was « 27 of the 42 are the count badge »; the record is LIVE rather than
frozen, and by the time the repair ran it read **34 of 42** on that badge — which is the whole
reason a figure in this file carries the command that reproduces it. The badge's defect was not a
tone at all but an **opacity blend**: secondary was written as `opacity`, so what reached the eye
was a colour the palette never declared. The danger family gained `--danger-fill` for the ground a
solid destructive control paints, the light theme's `--primary-foreground` override was REMOVED —
dark text on the brand fill in both themes, one decision instead of two that happened to agree —
and four label sites moved to `--primary-text`. `color-contrast` now sits INSIDE the enforced
hard-zero floor rather than beside it in a record.
<sub>`python3 frontend/maquette/a11y.py --check` runs the floor, contrast included.</sub>

**A SECOND THING L03 HANDS OVER, and it is the price of a decision the operator took knowingly.**
L03 removed `maximum-scale=1, user-scalable=no` from the viewport meta — 83 of its 744 violations,
one per state, WCAG 1.4.4. Those directives were forbidding the pinch-zoom a low-vision reader
depends on, and the hard-zero floor left no third option: excluding the rule would have been a
tolerated list of one.

What they were also buying, measured rather than assumed: **`.search input` was `font-size: 13px`**,
below the 16px threshold at which iOS auto-zooms a focused field, so focusing the search field on
an iPhone zoomed the page. The repair is 16px, and it belonged here because it moves the type
scale — which L03 could not do under a floor of zero oracle divergence. **D-L06-6 was arbitrated
on its wide reading**: not that one field but all THREE, because a field that zooms is a field
that zooms whichever screen draws it. R83 (`type_scale.py`, 9 holds) measures the rendered size in
the browser rather than the declaration, since only the browser says what a token resolves to
under the cascade.

**And one thing L03 measured that this lot does NOT inherit**: touch-target size (WCAG 2.5.8) was
expected to be a debt and is not. `target-size` runs, is applicable — 49 nodes evaluated in a
single state, none of them skipped — and reports **0 violations over the 83 states**.

**Done when.** The scale is declared in one place; no declaration sits outside it; a check refuses
the next one; the `--tm-*` family has a decided home and its fallbacks still hold; the 42 contrast
findings are gone and `a11y.py`'s contrast run is empty; `.search input` reads at least 16px so a
focused field no longer zooms iOS; the oracle records the intended visual changes as accepted, each
reviewed.

#### L07 — Tailwind and CVA, surface by surface · `LANDED` · *depended on L02, L04, L06*

**Objective.** D2 in force. Each surface converts on its own, oracle green at every step.

**Why surface by surface.** A single-shot conversion of 4 043 lines produces one unreviewable
diff and one unattributable failure.

**BLOCK 1 must not travel.** The prototype's stylesheet is split in two on purpose: BLOCK 1 is
the phone frame, the demo bars and the design notes — scaffolding that stops existing at
switchover — and BLOCK 2 is the application's own CSS. Converting BLOCK 1 into components would
carry the scaffolding into the product. It is deleted, not converted, and its disappearance is
part of this lot's proof rather than a later tidy-up.

**This lot fixes the surface ORDER, and L09 reuses it.** Both lots walk every surface; walking
them in the same sequence means the second pass reuses the understanding the first one built.
Write the order down in this wave's plan.

**The risk this lot carries, and it has already gone off once.** Some CSS here is
**load-bearing, not cosmetic**, and a utility conversion is exactly how it disappears without a
sound. `user-drag: none` and `user-select: none` are the known case: deleting one selector from a
group once took the whole `user-drag` block with it, native image drag came back and **swallowed
the pointer stream** — one down, two moves, never an up — and three gesture tests failed for a
reason that looked nothing like a CSS deletion. Anything the compositor reads (`touch-action`,
`user-drag`, `user-select`, `overscroll-behavior`, `-webkit-tap-highlight-color`) belongs in the
base layer and is held by a rule, before a single surface converts.

**Done when.** No hand-written component stylesheet remains; CSS is in its three layers (D3); the
compositor-facing declarations above are in the base layer and a rule refuses their removal; the
Tailwind scan is confined and proved not to reach production output; §15 of the constitution is
amended to name the new visual reference; the oracle is green on every state at every step.

### Phase 3 — The application

This phase is the bulk of the remaining work. The pages are finished; the application is not:
11 API modules against 0, 65 network calls against 1, 24 WebSocket files against 0, a service
worker against none.
<sub>commands in `IMPLEMENTATION.md` § THE OBJECTIVE</sub>

#### L08 — The data contract and the mocks · `NOT STARTED` · *depends on L04*

**Objective.** D7 in force. The contract the interface requires, plus a mock layer serving it, so
the maquette codes against a real shape with no backend touched.

**The mocks are seeded from the fixtures that exist today, and this is binding.** A mock that
returns exactly what the current fixture returns makes L09 provable: wiring a surface to it
renders the same thing, so **the oracle proves the wiring at zero divergence**. It turns the
largest lot of the plan from an unverifiable rewrite into a refactor with a proof, surface by
surface — and it costs nothing extra, because those fixtures have to be read anyway to know the
shapes. Invented mock data would forfeit that proof for no gain.

**Done when.** The contract exists as its own artefact; every shape the mock layer serves is
seeded from the fixture it replaces, and a check holds that correspondence; the layer also serves
failure and latency; divergences from the existing backend contract are recorded as demands;
determinism is sufficient for the oracle to depend on it.

#### L09 — The data layer, surface by surface · `NOT STARTED` · *depends on L01, L05, L08*

**Objective.** Server state in its query cache, mutations with their optimistic paths and their
rollbacks, the two state-ownership invariants (4 and 5) in force. Each surface takes its data and **its share of the
fixture dies with it** (D5). Surfaces are walked in the order L07 fixed.

**Its proof comes from L08.** Because the mocks are seeded from the fixtures they replace, a
wired surface renders what it rendered before, and the oracle holds the wiring at zero
divergence. If a surface cannot be wired at zero divergence, the difference is understood and
accepted explicitly — never waved through as "the data changed".

**The largest single lever on how native this feels sits in this lot, and it is not a library.**
An action must answer the finger before the network does. Every mutation carries its optimistic
path and its rollback; a surface that waits for a round trip to acknowledge a tap feels like a
web page, and no amount of animation later repairs that.

**THIS LOT OWES THE UNIT-TEST LAYER, and the debt is L04's, deliberately handed here.** The
maquette has no test runner at all: every proof is a browser rule, so a pure function is proved
through a browser. L04 measured **11** pure functions worth testing — the meatiest being
`epState`, whose **8 branches** are touched today by **3 assertions in one browser rule** — and
the operator arbitrated on 2026-08-22 that nothing be installed then. The reason is this lot's
own dependency: **L08 builds the mock layer**, seeded from the fixtures it replaces, and tests
written before it exists would invent their fakes by hand — which is precisely what makes a test
vacuous, twice paid for in this repository. The target tree already reserves
`features/<domain>/*.test.ts`; what is missing is the runner and the tests, and they belong here.

**Done when.** No surface reads a fixture; the fixture literals are gone from the engine; state
ownership is settled — no ambient mutable object read from everywhere; every mutation has an
optimistic path and a rollback, or a written reason why it cannot; the oracle is green
against the mocks, or its divergences are accepted one by one with reasons.

#### L10 — The live relay · `NOT STARTED` · *depends on L09*

**Objective.** The event stream, and the cache invalidations it drives.

**Done when.** A server event refreshes exactly what it should and nothing else; reconnection and
loss are handled visibly; no polling remains where an event exists.

#### L11 — Offline and PWA · `NOT STARTED` · *depends on L09*

**Objective.** Service worker, offline shell, queued mutations that depart on reconnection, and
the platform entry points a media application owes — receiving a shared link, and being the
handler its links deserve.

**Done when.** The application opens and reads offline; a mutation issued offline departs on
reconnection, exactly once; installation and its entry points are exercised on a real device.

### Phase 4 — The finish

#### L12 — Native interaction · `NOT STARTED` · *depends on L05, L07*

**Objective.** View transitions, gestures, mobile geometry, and the performance floor beneath
them. D9 governs every library question in this lot; its verdict table is the answer, not a
starting point for a new argument.

**Transitions.** Declared, through the platform's own view transitions — including the shared
element that carries a poster from a card into its sheet. Not scripted.

**Gestures.** The press / drag / scroll arbitration already written here is kept and moved, not
replaced. It encodes two things a general library does not know: a long press and a drag are
**opposite** cases for the compositor and one rule cannot serve both — a drag is claimed on the
first movement and cancels immediately, a press only once the finger has really travelled, and
the tolerance must live on the pointer stream because Chrome delivers **no `touchmove` at all**
for a drift of a few pixels. And the click a long press causes is swallowed **by its point**, not
by a delay and not by a target: that click arrives 1 ms after the lift, so no timer can tell it
from a deliberate tap.

**A hard-won constraint applies throughout**: a synthetic event is not a finger. It is never
cancelled, so it cannot tell whether a gesture survives the compositor. Two gestures were lost
that way and no script noticed. A real mouse on a browser with no touch at all found two more.

**Pressed states.** `@media (hover: hover)` for hover, `:active` for pressure, no JavaScript
(D9). Verify on a device whether `:active` still needs a touch listener to fire; if it does, the
remedy is one empty listener, never a per-component JavaScript state.

**Feedback seam.** One `feedback(kind)` call site that every gesture passes through, visual
today. It is what makes haptics a one-file change if the platform ever allows them (D9).

**Mobile geometry.** Safe areas, dynamic viewport units, contained overscroll, no accidental zoom
on focus — **and that one is now LIVE rather than theoretical**: L03 removed `maximum-scale=1,
user-scalable=no` from the viewport meta, rightly, since they forbid the pinch-zoom WCAG 1.4.4
requires and iOS Safari has ignored `user-scalable=no` since version 10. But they also masked a
defect nobody fixed: the maquette's fields are **13 px (`.search input`), 14 px (`.fieldinput`)
and 12 px (`.fieldinput.mono`)**, all under the 16 px threshold at which iOS zooms a focused
input. The removal did not create that; it stopped hiding it. The fix is the 16 px this lot
already owes, not the meta coming back.
<sub>`awk '/(input\|textarea\|select)[^{}]*\{/{r=$0} /font-size/{print r" → "$0}' frontend/maquette/design/refonte.html`</sub>
Then: contained overscroll, the virtual keyboard resizing content rather than the viewport, scroll restored per
history entry.

**The performance floor**, because none of the above survives a slow surface. The library holds
1 861 titles, so no long list renders unvirtualised. Images that a transition carries are decoded
before they are needed — the same asynchronous decode that makes the oracle flicker makes a
shared-element transition tear.

**Done when.** Every transition is declared rather than scripted, the one named spring excepted;
every gesture is proved against a real pointer stream **and** against a real mouse; reduced motion
is defined for each of them (the reduced-motion invariant); the feedback seam has exactly one call site; no
unvirtualised long list remains; and the interaction budget is measured on a real device, not in
a headless browser.

#### L13 — The engine's residue · `NOT STARTED` · *depends on L07, L09, L12*

**Objective.** What did not die by subtraction: the document-level delegation, the boot
handshake, `/login` and the splash as components, and the republished `window` surface once the
harness no longer drives through it.

**Done when.** `legacy.js` no longer exists; nothing reads a `window.__` seam; the suite is green
at unchanged hold counts; the oracle is green.

**Carried here by L07, 2026-08-25 — the prototype fragment, and R72's renegotiation.** L07 emptied
`frontend/maquette/design/refonte.html` of every style rule and did **not** delete it. Two reasons,
both recorded in that wave's `plan/phase-16-the-scaffolding-dies.md`: the file now carries the
wave's **conversion ledger** — one entry per region, saying where its rules went and why — and a
third of those entries name `src/styles/legacy.css`, whose death is this lot's; and **R72's hold
(a) is the verbatim injection of that file**, so removing it retires a hold, which is a rule
renegotiation recorded in `regions.json` rather than a file deletion. Twelve live readers name the
path. **Done when** the fragment is gone, R72 is renegotiated with its two surviving holds
mutation-tested, and the ledger has a home that outlives it. **Any earlier wave may take it** —
nothing depends on waiting — provided it carries both, and folds neither into a conversion commit.

---

## 5. The method every lot follows

**The wave.** One lot, one branch, one squash merge onto `main` after green CI and a clean final
adversarial review. This holds for a two-line documentation fix as much as for a conversion.

**The proof.** A change lands with its rule, and the rule is mutation-tested — break the
behaviour on purpose, confirm the rule falls and names the right defect, restore. A rule that
never bit proves nothing. A rule must cover the path actually walked: cold load, real finger,
real browser menu.

**The gate.** Before every wave's closing commit: `make lint` at zero errors, `make test` with no
failure and **no error** (an error means collection crashed and everything after it was skipped),
`make check`, the **full** rule suite via `frontend/maquette/harness/run.sh` — not the
`--contracts` tier, which is the per-pull-request one — and the oracle green or its divergences
accepted with reasons. The suite runs itself now; it used to run only when someone remembered,
and on the day it did not, six contracts broke under three green gates.

**Write the landed row when the pull request opens, not after the merge.** A wave edits
`IMPLEMENTATION.md` on its own branch, so a row that waits for the merge to be written is a row
that never gets written — three consecutive waves left the table announcing themselves « in
flight » after landing, and each time the next reader was told the previous lot was still running.
The pull request number exists the moment the pull request does. Being an hour ahead of the merge
is a smaller error than being permanently behind it, and it is self-correcting: a wave that does
not merge fixes its own row.

**That rule fixed one half of the problem and the count did not move: four waves out of four.**
It answers « the row is missing while the pull request is open ». It cannot answer « the row is
wrong once the pull request has merged », because the only branch that could write the landed row
is the one the merge has just consumed. So the row is now written twice, and the second write is
the one nobody is holding: **moving a wave from « In flight » to « Last landed » belongs to the
post-merge steps below, beside re-recording the references** — same moment, same person, same
list that already says it is not optional.

Recording it there is necessary and, on the evidence, not sufficient: that list has been skipped
three times out of four as well. **What would settle it is a check rather than a sentence**, and
the shape is cheap because the row already carries the wave's version: if `personalscraper/__init__.py`
on `main` has reached the version the « In flight » row names, that wave has landed and the row is
stale — offline, exact, and it stays green on the wave's own branch, where the two differ by
construction. It would say nothing between waves, when no row names a version, and whoever builds
it should make that silence legible rather than let a vacuous pass read as a verdict. It is written
here as a diagnosis with its mechanism, **not built**: a guard is code, and the steward who found
this does not carry code (§ 7.2).

**The oracle is a LOCAL gate, and that changes who can close a wave.** Its measurements are bound
to the machine that took them — the same unmodified tree reads differently on a Linux runner — so
`--check` refuses to compare across a mismatch and the oracle is never wired into CI. An agent
working anywhere but that machine can establish that a wave *claims* the rendering held, and how,
but cannot certify it. Plan the wave knowing the certification happens where the oracle runs.

**And re-record the reference after the squash merge.** The reference names the commit it
measured; squashing replaces that commit, so on a fresh clone the pointer names nothing and
`--check` refuses to run at all. **It is two commands, and the first is not optional:**

```
make maquette-oracle                            # builds, copies to the served root, starts 8899
python3 frontend/maquette/oracle.py --record    # then records against what is actually served
```

`make maquette-oracle` runs `--check`, so it FAILS on a dangling reference — that is expected, and
it is run for its preparation: `oracle.py` reads `http://127.0.0.1:8899/`, and without
that build and copy it would measure the previous build, or nothing. There is no make target for
`--record`; `make maquette-oracle --record` passes the flag to `make`, not to the oracle.

This is written here rather than in the state section because that is where it was written when
the wave that had just written it merged without doing it — a mandatory manual step recorded only
in a file about *where things stand* is a step the next wave never reads.

**The same moment owes a third thing: move the wave's row from « In flight » to « Last landed »**,
and name the next lot. It sits here, with the two commands, for the reason the paragraph above
gives — it is the only step of the three that cannot be done from the wave's own branch.

**The maquette first.** Nothing about a surface is decided anywhere else. A surface is drawn
before it is coded, with named states and a rule that bites.

### One lot at a time

**The lots run strictly in sequence — one lot, one branch, one merge, then the next.** The
operator ruled this on 2026-08-22, and it settles a question this file used to leave open.

The temptation to parallelise is real and this plan indulged it: it defined a criterion — a lot
may run alongside another only if it never writes the oracle's reference — applied it to the
thirteen lots, and found exactly one qualifying pair, L08 beside the rendering track. The gain
was costed in the same breath as **a fraction of the calendar, not a transformation**, with part
of it spent on the second branch rebasing and re-running a full adversarial review. Weighed
against a failure mode nothing announces, that trade was refused. **Sequence is the ruling; the
pair no longer exists to be scheduled.**

**The risk that decided it is worth keeping, because it is the one that does not announce
itself.** The oracle's reference is the single shared proof artefact. Two branches that each
accept divergences merge two "validated" states, and **one can mask the other's regression** with
nothing to show for it. Every other collision — two branches editing one file — arrives as a
conflict someone has to resolve. This one arrives as green.

**What is refused, and why it stays refused:**

- **Two agents on one lot.** Conflicts on the same markup, and failures nobody can attribute.
- **Merging L07 and L09 into one per-surface wave.** It is the tempting optimisation — it halves
  the number of waves — and it destroys both proofs. L07 proves the rendering did not change;
  L09 changes where the data comes from. Together, a conversion defect and a wiring defect are
  indistinguishable. Sequence does not make this one safe: it is not a scheduling question.
- **Skipping the oracle to move faster.** It is what makes everything else provable. Removing it
  does not save time; it removes the ability to know.

**Which lot is next is decided by § 0's selection rule** — not `LANDED`, every dependency
`LANDED` — and never by which one happens to be unblocked earliest. Where two are eligible, the
lower number goes first unless this file says otherwise.

---

## 6. The traps that cross lots

Every one of these has already gone off in this repository. They are recorded in full in
`frontend/maquette/regions.json` → `$adversarialReview.$methodLessons` and in
`frontend/maquette/README.md`; what is added here is **which lot each one threatens**, so it is
met before it fires rather than after.

| Trap | Threatens | The short version |
| --- | --- | --- |
| A screenshot is not an oracle | **L01** | two captures of the same unmodified file diverge on 8 to 15 states |
| A synthetic event is not a finger | **L12** | it is never cancelled, so it cannot tell whether a gesture survived the compositor |
| Compositor-facing CSS is load-bearing | **L07** | deleting one selector from a group took `user-drag: none` with it; native image drag then swallowed the pointer stream |
| A media query answers for the window, not the component | **L07, L12** | a 390 px frame on a 1280 px desktop is told it has room it does not have |
| A rule that greps one file greps the wrong thing | **all** | four rules stayed green over evidence that had simply moved to another file |
| A rule can certify the defect | **all** | writing down the behaviour that exists is not the same as writing down the one that is wanted |
| Renaming needs a parser, not a regex | **L02, L07** | the same short name means different things in different scopes; a global replace preserves behaviour while lying about meaning |
| A failed command is not a no-op | **all** | it is an edit that did not happen, and the next read is evidence rather than scenery |
| A derivation must not read back its own output | **L06** | a size computed against the median of what it sets returns its own answer |

**And one that has not gone off yet, named because its shape is known**: a `var()` naming a token
nobody declared renders as nothing rather than failing. It is a landmine, not a crash, and it sat
in this codebase undetected across 449 `var()` calls. `scripts/check-css-tokens.py` refuses it
today, and L06 kept it true as the token source moved: `--tm-bottom-bar-h` is published by the
shell now, the fallback is still demanded at every use, and R84 holds the publisher to being one.

---

## 7. Amending this file, and who watches it

### 7.1 Amending

**A plan that runs for months will outlive some of its own decisions.** That is not a failure of
the plan; executing a decision that has lost its subject is.

**When you find a lot that no longer has a subject** — its problem was solved elsewhere, its
premise was reversed, its tooling has no reader — **stop and report it. Do not execute it.** The
report goes to the operator with what changed and what becomes void. This is the whole lesson of
the tooling that survived a reversed decision by seven months: nobody dared delete machinery
nobody could justify.

**Who may change this file.** The operator arbitrates; an agent proposes. A decision in § 2 is
amended by adding what replaces it and naming what it makes void — never by quietly editing the
old text, and never in a wave that also implements it.

**One thing that is NOT an amendment, and the distinction is load-bearing.** A decision's
*measured rationale* expires when a wave does the work that decision scheduled — D6 said
accessibility was « nearly absent » and L03 made that false by construction. Refreshing that
measurement, in the wave that caused it, is the wave's DUTY, not an amendment: what it decided is
untouched, and leaving the old figure standing is the stale-directive disease this file exists to
fight. **The decision is the operator's; the measurement under it belongs to whoever made it
move.** This paragraph exists because the rule above, read literally, would have obliged L03 to
leave D4 asserting that the markup could not carry roles on the day it made it carry them — and
the wave rightly ignored it. It refreshed D4 and missed D6, which is a lapse of execution, not of
principle.

**When a decision changes, the implementation directives change in the same move.** What loses
its subject is removed, not kept "just in case".

**Deferred, on purpose.** An executable check — one that refuses a lot marked `LANDED` whose
files do not exist, or a cross-reference pointing at a dead path — is wanted and is not built
yet. It is built once this plan has proved its shape, and not before: a guard written against a
structure still moving guards the wrong thing. This paragraph is its record, so that "we meant to"
does not become "we forgot".

### 7.2 Someone audits this file against the work — and it is not you

**A standing audit checks each landed lot against this plan. It is held by a steward, and the
steward is never the agent who implemented the lot.** That separation is the point: an
implementer auditing their own lot compares their intention with their work, and those two always
agree.

**So nothing in that office is yours.** Do not audit your own wave, do not fold an audit into it,
and do not read the steward's licence to contest this plan as yours — mid-wave, a lot that has
lost its subject is reported and stopped (§ 7.1), not re-argued. What you owe your wave is § 0 and
your lot's **Done when**.

The office is written down in `docs/reference/frontend-steward.md`, which is addressed to the
steward and to the operator who instantiates one. It is deliberately not in this file: everything
here is binding on the agent doing the work, and a procedure meant for someone else, sitting in
that same reading, becomes an instruction nobody asked for.
