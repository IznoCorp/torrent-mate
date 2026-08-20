# Frontend architecture — the target the maquette is built towards

**This file says what the maquette must BECOME, and in what order. It never says where the work
stands** — that is `IMPLEMENTATION.md` § THE OBJECTIVE, and it is the only file that says it.

The maquette is the next version of the frontend and it REPLACES the shipped one: on switchover
day `frontend/src` is archived and `frontend/maquette/` takes its place (`product-intent.md`
§15). So every page and every MECHANISM the shipped app has must eventually exist here. The pages
are the part that is finished. What remains is most of what makes an application, and this file
is the plan for it.

---

## 0. Picking up work — read this first

1. Read `IMPLEMENTATION.md` § THE OBJECTIVE. It carries the measured inventory and the state.
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
  written here. See § 6.

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

**What it costs, and it is accepted.** The maquette stops opening from `file://`. Path routing
needs a host that rewrites unknown addresses onto the document; `harness/server.py` already does,
`serve.py` serves the build, and the reverse proxy will. Opening the file by double-click is the
single use lost.

**What becomes void.** R69 holds the opposite rule today. It is renegotiated in the same wave
that lands D1, with the reason written down — never left to contradict this.

**Layers are ranked in three tiers**, and the tier decides the addressing:

| Tier | Example | Addressing |
| --- | --- | --- |
| Content | a media sheet, its releases, a resolution | its own **path** |
| Screen state | an actions panel, a filter drawer | a **query parameter** |
| Transient | a sort menu, a confirmation | **no URL**, but Back still closes it |

### D2 — Tailwind v4 provides the implementation; CVA components provide the API

**Decision.** Styling goes through Tailwind utilities. The design vocabulary is expressed as
**typed component variants** (`class-variance-authority`), not as hand-written CSS class names:
`<Card variant="compact" tone="warning">`, not `class="card card--compact"`.

**Replaces.** The 4 043-line hand-written semantic stylesheet of `refonte.html`.
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
280 harness selection calls to re-anchor. A handful of selectors Tailwind cannot express
(`:has()`, deep descendant combinators) stay in the base layer. Visual diffs become noisier —
they move from CSS rules into JSX.

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

**Measured today**: 684 selection calls in `harness/*.py` — 280 anchored on a CSS class (40 %),
276 on an id, 92 on `data-*`, 32 on a bare tag, 4 on a role.
<sub>method: extract the string argument of every `querySelector|querySelectorAll|locator|matches` call in `harness/*.py` and classify it</sub>

**Why not accessible roles**, which would be the modern default: the markup cannot carry them
yet — 13 `role=`, 1 `<nav>`, **0 `<main>`, 0 `tabindex`** across the maquette. Roles become a
legitimate anchor once L03 lands; they are not a prerequisite for anything.

**A `data-*` contract has three ends** — the markup that emits it, the `dataset.x` that reads it,
and the rule that taps it. They move in ONE step, or the interface half-works in a way no single
file reveals.

### D5 — The engine dies by subtraction, surface by surface

**Decision.** The legacy engine is not a lot of its own to be executed after the application. Its
cross-cutting parts are lifted once and early; the rest dies with each surface as that surface is
converted and wired.

**Why, and this is a measurement rather than a preference.** `legacy.js` is 34 627 lines, of
which **27 678 (79 %) are fixtures** — `SHEETS_RAW` alone is 20 538 lines of episode catalogue.
The engine's actual code is about **6 949 lines**.
<sub>method: bracket-match every `const X = [` / `const X = {` declaration and sum the spans over 100 lines</sub>
Most of that fixture stops existing when real data arrives. Killing the engine before the data
layer means facing 34 627 lines; killing it as surfaces convert means facing seven thousand,
in pieces, each with the oracle green.

**What is cross-cutting and does NOT strangle surface by surface**: navigation (`__go` and the
82 named states, lifted by L05), the document-level event delegation, the boot handshake, and the
254 top-level declarations republished on `window` for the harness to drive through. The
delegation, the boot, `/login` and the splash close the plan as L13.

### D6 — Accessibility is a lot, not a side effect

**Decision.** Accessibility is planned, proved and landed as its own wave (L03), not absorbed
into other lots.

**Why.** It is nearly absent — 0 `<main>`, 0 `tabindex`, 13 `role=`.
<sub>`grep -rc 'tabindex' frontend/maquette/design/src frontend/maquette/design/*.html`</sub>
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

---

## 3. Invariants — true at the end of every wave

1. **The URL and the interface never contradict each other.** D1's rule holds in both
   directions: no page identity in the query, no sort or filter in the path.
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
8. **No French in the code and no interface text in the code.** Unchanged
   (`scripts/check-no-french.py`), and it applies to everything written here.
9. **Every change lands with a rule that bites**, mutation-tested: break the behaviour on
   purpose, confirm the rule falls and names the right defect, restore.

---

## 4. The lots

Status is one word and nothing else: `NOT STARTED` · `IN PROGRESS` · `LANDED`. Anything richer —
which PR, which measurement, which proof — belongs in `IMPLEMENTATION.md`.

### Phase 0 — The safety net

Nothing else may start. Every lot after this one changes mechanism while promising the rendering
is unchanged, and that promise is currently unprovable: `fidelity.py` cannot run (the renderers
it compared are deleted, no recording is committed, and 38 of the 82 state ids were renamed).

#### L01 — The recorded oracle · `NOT STARTED` · **runs alone**

> ⚠ **Its exact form is settled once the `chore/maquette-untranslate` PR lands.** That branch
> retires the tooling built for the abandoned surface-by-surface model. `regions.json` → `probe`
> holds the viewport, the computed-style subset and the justified-divergence allowlist —
> **that measurement technique must survive**, whatever happens to the file around it. It is the
> only replayable oracle this repository has ever proved.

**Objective.** One command that says whether the maquette renders today what it rendered at a
known-good commit.

**What it measures.** Per *(named state × region)*: the bounding rectangle, plus a fixed subset of
computed style properties. States come from `states.js` — the single source, 82 of them, never
recounted by hand. Regions are re-declared for this purpose: one region per block a user
perceives as a unit. The 51 regions in use today were chosen for the retired extraction contract
and are not automatically the right list.

**What it does not do.** It is not a functional test — the 51 rule scripts are. It is not a
screenshot (D8).

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

**Note for later.** When real data replaces the fixtures (L09), determinism moves to the mock
layer. **The oracle then depends on L08** — plan the two together, not against each other.

#### L02 — Test anchors move to `data-*` · `NOT STARTED` · *depends on L01*

**Objective.** No rule selects on a style class. 280 calls move onto `data-*` contracts.

**Why before the visual language.** If the anchors move during the conversion, a falling rule
cannot be attributed — anchor or style. Separated, each failure has one possible cause.

**Done when.** The classification measured in D4 reports zero class-anchored selection calls; a
rule refuses the next one; every moved contract has its three ends moved in the same commit; the
suite is green at unchanged hold counts.

### Phase 1 — The contracts of markup and structure

#### L03 — Accessibility · `NOT STARTED` · *depends on L01*

**Objective.** Landmarks, roles, accessible names, focus order, focus visibility, keyboard paths,
and focus management on every layer opening and closing.

**Done when.** Every screen has its landmark; every interactive element has an accessible name; a
layer traps and restores focus; the whole application is reachable by keyboard; an automated
audit runs in the gate; and the oracle is green — the non-visual part of this lot must move
nothing.

#### L04 — Boundaries and code conventions · `NOT STARTED` · **runs alone**

**Objective.** The folder structure, the dependency rules and the size ceilings that every later
lot puts its files into. `ui/` · `features/` · `routes/`, invariants 6 and 7 made executable
rather than documented.

**Why here.** Every lot after this one creates files. Deciding afterwards means moving them
twice.

**Done when.** The structure exists; a dependency check fails on a violation and is wired into
the gate; the size check covers the frontend; grandfathered files are listed with the lot that
will convert each.

#### L05 — Routing · `NOT STARTED` · *depends on L01, L04*

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

#### L06 — The scale · `NOT STARTED` · *depends on L01*

**Objective.** One declared scale — space, type, radius, duration, easing — and every declaration
folded onto it. The 65 padding values collapse to roughly eight steps, the 21 type sizes to about
seven, the 17 radii to about five.

**Done when.** The scale is declared in one place; no declaration sits outside it; a check refuses
the next one; the oracle records the intended visual changes as accepted, each reviewed.

#### L07 — Tailwind and CVA, surface by surface · `NOT STARTED` · *depends on L02, L04, L06*

**Objective.** D2 in force. Each surface converts on its own, oracle green at every step.

**Why surface by surface.** A single-shot conversion of 4 043 lines produces one unreviewable
diff and one unattributable failure.

**This lot fixes the surface ORDER, and L09 reuses it.** Both lots walk every surface; walking
them in the same sequence means the second pass reuses the understanding the first one built.
Write the order down in this wave's plan.

**Done when.** No hand-written component stylesheet remains; CSS is in its three layers (D3); the
Tailwind scan is confined and proved not to reach production output; §15 of the constitution is
amended to name the new visual reference; the oracle is green on every state at every step.

### Phase 3 — The application

This phase is the bulk of the remaining work. The pages are finished; the application is not:
11 API modules against 0, 65 network calls against 1, 24 WebSocket files against 0, a service
worker against none.
<sub>commands in `IMPLEMENTATION.md` § THE OBJECTIVE</sub>

#### L08 — The data contract and the mocks · `NOT STARTED` · *depends on L04* · **Track B**

This is the one lot that may run alongside the rendering track (§ 5): it creates its own files
and changes no rendering, so it never writes the oracle's reference.

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
rollbacks, invariants 4 and 5 in force. Each surface takes its data and **its share of the
fixture dies with it** (D5). Surfaces are walked in the order L07 fixed.

**Its proof comes from L08.** Because the mocks are seeded from the fixtures they replace, a
wired surface renders what it rendered before, and the oracle holds the wiring at zero
divergence. If a surface cannot be wired at zero divergence, the difference is understood and
accepted explicitly — never waved through as "the data changed".

**Done when.** No surface reads a fixture; the fixture literals are gone from the engine; state
ownership is settled — no ambient mutable object read from everywhere; the oracle is green
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

**Objective.** View transitions, gestures (drag to dismiss, swipe), mobile geometry — safe areas,
dynamic viewport, contained overscroll, no accidental zoom on focus, scroll restored per history
entry.

**A hard-won constraint applies throughout**: a synthetic event is not a finger. It is never
cancelled, so it cannot tell whether a gesture survives the compositor. Two gestures were lost
that way and no script noticed.

**Done when.** Every transition is declared rather than scripted, except the drag; every gesture
is proved against a real pointer stream; the interaction budget is measured on a real device.

#### L13 — The engine's residue · `NOT STARTED` · *depends on L07, L09, L12*

**Objective.** What did not die by subtraction: the document-level delegation, the boot
handshake, `/login` and the splash as components, and the republished `window` surface once the
harness no longer drives through it.

**Done when.** `legacy.js` no longer exists; nothing reads a `window.__` seam; the suite is green
at unchanged hold counts; the oracle is green.

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
`make check`, and the oracle green or its divergences accepted with reasons.

**The maquette first.** Nothing about a surface is decided anywhere else. A surface is drawn
before it is coded, with named states and a rule that bites.

### Running two lots at once

The plan is long and the temptation to parallelise is real. **One criterion decides it, and it is
the only one:**

> A lot may run alongside another **only if it never writes the oracle's reference.**

The reference is the single shared proof artefact. Two branches that each accept divergences
merge two "validated" states, and **one can mask the other's regression** with nothing to show
for it. Every other collision — two branches editing one file — announces itself as a conflict.
This one does not.

**Exactly one pair qualifies**, and it is not a scheduling preference but the result of applying
the criterion to the thirteen lots:

```
Track A (rendering)   L02 → L03 → L05 → L06 → L07 ──┐
                                                     ├──→ L09 → …
Track B (data)               L08 ───────────────────┘
```

**L01 and L04 run alone.** Nothing is verifiable before the oracle exists, and L04 moves files,
so anything running beside it collides.

Costed honestly: the gain is a fraction of the calendar, not a transformation, and part of it is
spent on the second branch rebasing and re-running a full adversarial review.

**What is refused, and why it stays refused:**

- **Two agents on one track.** Conflicts on the same markup, and failures nobody can attribute.
- **Merging L07 and L09 into one per-surface wave.** It is the tempting optimisation — it halves
  the number of waves — and it destroys both proofs. L07 proves the rendering did not change;
  L09 changes where the data comes from. Together, a conversion defect and a wiring defect are
  indistinguishable.
- **L10 beside L11.** Both touch the cache configuration. Small gain, real risk.
- **Skipping the oracle to move faster.** It is what makes everything else provable. Removing it
  does not save time; it removes the ability to know.

---

## 6. Amending this file

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

**When a decision changes, the implementation directives change in the same move.** What loses
its subject is removed, not kept "just in case".

**Deferred, on purpose.** An executable check — one that refuses a lot marked `LANDED` whose
files do not exist, or a cross-reference pointing at a dead path — is wanted and is not built
yet. It is built once this plan has proved its shape, and not before: a guard written against a
structure still moving guards the wrong thing. This paragraph is its record, so that "we meant to"
does not become "we forgot".
