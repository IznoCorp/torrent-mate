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

## 0. Picking up work

Read `IMPLEMENTATION.md` for what landed, then take the first lot of § 4 that has not landed and whose
dependencies all have (a blocked lot is skipped, and the plan says why); its **Done when** is the contract.
Lots run one at a time — one lot, one branch, one squash merge (operator, 2026-08-22). One kind of change
per phase: a conversion proves the rendering did not change, a behaviour change proves the behaviour did.
The method is `docs/reference/method.md`.

---

## 1. What this file covers, and what it does not

| Document | Owns |
| --- | --- |
| `docs/reference/product-intent.md` | what the product must BE (constitution, binding, dictated by the operator) |
| **this file** | what the frontend must BECOME technically, and in what order |
| `IMPLEMENTATION.md` | where the work stands — the only state, with its commands |
| `docs/features/<codename>/DESIGN.md` · `plan/` | the scope and the steps of ONE wave — deleted at merge, cited by commit |
| `frontend/maquette/README.md` | how the prototype runs, its named states, the traps already paid for |

This file covers items 2, 3 and 4 of `IMPLEMENTATION.md` § THE OBJECTIVE → REMAINS — the visual
language, the application itself, and the legacy engine — plus the safety net they all need and
the method they all follow.

**L10-ter — the application template** (operator, 2026-08-28, ran 2026-08-29). A design phase, not
a lot — it writes no code, nothing schedules it, § 0's selection rule must not reach it, and it may
amend this file's lots and their order. Its products: `docs/reference/frame-survey.md`
(the inventory of every surface the engine still draws — chrome, entry, the ladder's handler, all
ten bottom-panel producers, the Découvrir feed, 71 delegation verbs), `docs/reference/frame-model.md`
(the frame modelled in thirteen parts under invariant 10), and `docs/reference/product-intent-map.md`
(the DOIT/NE-DOIT-PAS clause map). It reordered the plan in five places: **L15** (the frame) inserted
before L11; **L19** (the producers) inserted after L12; **L20** (the control station) placed after
L19; **L16, L17, L18** placed after L20; **L13** re-cut to what did not die by subtraction. Story:
`docs/reference/frontend-architecture.md@6a47304a4` § 1.

**THREE LOTS WERE OWED AND ARE DECLARED — §17, §18 and §19 of the constitution**, dictated
2026-08-26, unanswered by any lot until L10-ter placed them 2026-08-29: **L16 (§18), L17 (§19),
L18 (§17)**, in Phase 5, after L20 — cheapest first (§18 → §19 → §17), because L17 depends on the
tracker surface L16 draws. The measurement that scheduled them, as the record of what existed on
the day it was taken:

| Section | What exists today | What it is asked for |
| --- | --- | --- |
| **§18 — the ratio is a resource, and it is steered** | `min_ratio` and `min_seed_time` per tracker, read at the grab and at the cross-seed; `obligations`, `stalled-grabs` and `downloads` all answering | **wire them** — nothing calls any of the three — plus one write, since setting a tracker's policy from the surface that shows its ratio exists in neither contract |
| **§19 — cross-seed is seen and decided** | 797 lines of engine injecting at third parties, emitting `CrossSeedInjected` and `CrossSeedRejected` | **everything**: zero routes in either contract, no event relayed to the stream. D7's case — the interface declares what it requires and the backend follows (§15) |
| **§17 — accounts, rights and Plex identity** | one role, one account, `GET /api/auth/me` saying nothing of rights | **a model, then surfaces.** None of the 53 declared operations concerns another user, a role or a permission. And one requirement on existing code: the read-only role must be ABSORBED by the rights model, never sit beside it — two authorisation paths is NE-DOIT-PAS-7 |

**Its mapping is written and its instrument is placed** (2026-08-29): `docs/reference/product-intent-map.md`,
one row per DOIT/NE-DOIT-PAS clause, a verdict, a proof or an owning lot. The arm that reads it is
specified in `docs/reference/frame-model.md` § 4 and built by L15. Story:
`docs/reference/frontend-architecture.md@6a47304a4` § 1.

**Also named here and deliberately unscheduled — the SEMANTIC SCROLL INDEX** (operator,
2026-08-26): a list index shaped by its own sort (letters, month markers), not a scrollbar (D11
settles that), the shape a phone's fast-scroller has. **Not a lot** — nothing schedules it. Three
things keep the door open at no cost now: the sort key must be exposed in an INDEXABLE form in the
data contract (L09's decision), the scroll container stays one identified element (`#port`), and
programmatic scrolling has one path (**B-140**, not fully paid — `app/focus.ts` and `ui/sheet.tsx`
still bypass it). A control that both scrolls and jumps teaches two things in one object, so it
stays two objects: the bar, and the index that appears when it serves.

**Item 1 is a lot since 2026-08-29 — L20, the control station.** `/control` (8 panels) and
`/pipeline` (10 panels), kept outside this file as pageless, could not stay there once the clause
map found DOIT-1, DOIT-3, DOIT-5 and DOIT-6 each owed a half only those pages serve. They follow the
existing method (drawn in the maquette first); where their panels land is the operator's open UX
question (`IMPLEMENTATION.md`). L20 depends on L15 and L19 — drawn before the producer template,
they would be drawn twice.

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
the L05 repair wave's phase 11 (`docs/archive/features/maquette-l05/plan/phase-11-navigation-path.md@79ccebe2`),
merged in PR #484. The constitution's `product-intent.md` § 16 is the authority; this entry says
what the implementation owes and records what was built. Three rules stand; a fourth was
considered and rejected — see rule 4 below.

1. **Back pops, and the stack holds only deliberate arrivals.** Opening a surface — a sheet, a
   resolution, a panel — pushes. Adjusting one — a filter, an inner tab, a sort, a lens — replaces.
2. **The rule reads by DESTINATION and by where the tap was made.** A page of the bottom bar
   (Acquisition, Médiathèque, Trackers, Découvrir) chosen from the bar or the side menu UNWINDS the
   trail onto the floor, from any depth: the stack under it is `[guard, /acquisition]`, or
   `[guard, /acquisition, /page]` for a bar page other than the entry, and Back from it lands on
   `/acquisition` — Android's `popUpTo(startDestination)` in this codebase's terms. **A page the side
   menu or the account menu opens STACKS** on the page left — Système, Réglages, Maintenance, Profil —
   the menu's entry and any rubric open under it given back first, and Back replays the arrival path.
   **A link placed inside a page, a screen or a panel STACKS, even when it leads to the entry page**,
   and the exit guard arms only when the entry page is at the bottom of the stack. **A page already
   on the trail moves to its top, never stacked twice** (the operator's ruling of 2026-09-30). § 16 as
   amended on 2026-09-29 (#635, #643); delivered by the navigation lot: every entry carries its trail
   (`lib/navigation-entry.ts`, `app/trail.ts`), and the verb says how a tap lands
   (`app/frame-verbs.ts`). Held by R-navigation-a and R-navigation-b (`frontend/maquette/harness/journey.py`).
3. **Where no stack exists, synthesise it from the hierarchy.** A cold link poses the real parent
   under the screen — read off the emitter of the screen's own opener, not guessed — and that
   parent is **rendered**, not merely recorded (`SCREEN_PARENTS` in `lib/addresses.ts`).
4. **Up is a separate gesture, and it is drawn.** Back pops; Up climbs one level whatever the
   path. **NOT delivered** — no lot carries it yet; a surface to be drawn in the maquette first.

**Replaces** the reading under which every screen resolved to the home page (D-8.1) — the
mechanism behind a reviewed defect where a cold screen address composed a panel's entry over the
home page and the sheet unmounted behind it. **The trap this decision exists to forbid**: sending
Back to the declared parent while a stack entry exists — history first, the parent is a floor,
never a destination. **Deliberately not done**: per-page stacks — leaving the library with a sheet
open and returning lands on the library's root, added only if real use asks. Story:
`docs/reference/frontend-architecture.md@6a47304a4` § D1b.

### D-L13-1 — A layer left for an arrival keeps its entry; Back onto it reopens it

**Decision, ratified by the operator on 2026-09-13 (Q3 = A). Delivered by L13b phases 9–10 and
L13c** (`docs/features/maquette-l13/DESIGN.md@763f15cf9` § 8 carries the arbitration in full —
B-290's two shapes, B-397, the rejected reading).

1. **Opening a panel is an arrival** (D1b rule 1): the entry it pushes is kept, not popped, when
   the operator leaves it for an arrival screen — « Voir la fiche », `releases`, `profile`,
   `take` alike, one shape for all of them. The entry records what reopens it —
   `{ layer, kind, subject }`, written by `app/panel-host.ts` — so a transient panel reopens as
   surely as an addressed one.
2. **Back onto that entry REOPENS the layer**, drawn under `::view-transition-new(leaving-panel)`
   running `panel-down` in reverse (no animation under `reduce`).
3. **Re-producing on an entry that already records the panel REPLACES** (D1b rule 1 — a redraw is
   an adjustment), not pushes — B-397's shape.

**Replaces** the two-shape reading where « Voir la fiche » kept its entry and its siblings
popped-then-pushed 240/260 ms later — the mechanism the operator rejected (below).

**The rejected reading, so it is not re-proposed**: every sibling pops first (the entry removed,
Back returns to the list). It keeps « one entry per gesture » true and makes B-275 unanswerable —
the panel is gone from the stack, so Back cannot return to it.

**What it makes void.** The close-then-wait pattern and its ten timers (no subject once Back
reopens directly); `openOnCurrentEntry`'s special case in `producePanel`'s deferred path became
the general path.

**Held by** R188 `ladder_entries.py` (the pops are counted), R189 `redraw_entry.py` (a redraw does
not stack), and R103 `exits.py`'s reversal (the return is drawn) — DESIGN's own R-L13-a/b/c, bound
to these numbers when the phase ran.

### D2 — Tailwind v4 provides the implementation; CVA components provide the API

**Decision.** Styling goes through Tailwind utilities. The design vocabulary is expressed as
**typed component variants** (`class-variance-authority`), not as hand-written CSS class names:
`<Card variant="compact" tone="warning">`, not `class="card card--compact"`.

**Replaces.** The 4 052-line hand-written semantic stylesheet of
`frontend/maquette/design/refonte.html@60530dbd8` (deleted at L13a).
<sub>`awk 'NR>=188' frontend/maquette/design/refonte.html | wc -l`</sub> — read at `60530dbd8`

**Why.** Three reasons, in order of weight. Tailwind **enforces a scale by construction**, which
is exactly the defect measured for the visual language — 21 distinct font sizes, 17 radii, 65
padding values, 18 gaps.
<sub>`cd frontend/maquette/design && grep -oE "padding:[^;]+;" refonte.html | sort -u | wc -l`</sub> — read at `60530dbd8`
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

**What became void.** `frontend/maquette/design/refonte.html@60530dbd8` stopped carrying the
stylesheet, then was itself deleted at L13a. §15 of the constitution named that file as the
visual reference; with the CSS gone from it, the reference became **the tokens plus the component
catalogue**, and §15 was amended in the same move rather than left pointing at a file that no
longer holds its subject.

**Arbitrated by the operator, 2026-08-25: D3 is WIDENED.** Five stylesheets exist, not three:
the three layers above, plus two named as TRANSITORY, each carrying the date it dies —
`styles/legacy.css` (the dying engine's residue, bounded by `check-legacy-css-residue.py`, dies
with **L13** as a conversion surface by surface, not a deletion) and `styles/harness.css` (the
phone frame, imported once, ships nowhere, dies at **switchover**, held by no guard today).
« Nowhere else » now means: no sixth sheet, and no transitory sheet without its end named here.
Neither may grow — `legacy.css`'s one exception is restoring what a prior wave wrongly deleted
from it (B-081), never new work. Story: `docs/reference/frontend-architecture.md@6a47304a4` § D3.

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

**AMENDED 2026-09-03 (operator's to overrule): the engine may be added to only to stop a defect
that destroys or loses the operator's data, and every such edit is amended here with its commit.**
L14 (`9ce9b0508`) added lines to repair a bulk-delete defect that named and destroyed media the
reader had never ticked — a data-destroying bug, so the edit stands under the exception. Anything
else waits for the surface that kills the code. The size arm holds this since 2026-09-05:
`scripts/frontend_size_ledger.py` gives every grandfathered file a recorded count, refused upward,
so an addition to the engine has to be declared to land. **Two more additions are declared and
ruled covered** (L19, `9fa13da57`, operator « D5 couvert » 2026-09-05): `closest.dataset.reloadsettings`
and `closest.dataset.confirmrestart`, both inside a net −816 non-blank lines, both leaving with the
settings' other verbs when `legacy.js` no longer exists (L13).

**Why — measured, not preferred.** Most of `legacy.js` is fixture data (79 % at the decision's
writing), and killing the engine before the data layer (L09) means facing all of it at once;
killing it surface by surface means facing it in pieces, each with the oracle green. **The
subtraction has two more passes than first thought, both now landed**: **L15** took the frame
(tab bar, drawer, dialog, toast, entry) and **L19** took the ten `panel.open` producers — both
confirmed at zero remaining call sites in the engine. What still stays cross-cutting, until L13:
the document-level event delegation, the boot handshake, and the top-level declarations republished
on `window` for the harness to drive through (navigation itself left with L05). Story:
`docs/reference/frontend-architecture.md@6a47304a4` § D5.

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

**What it does NOT see, and the operator arbitrated keeping it that way (2026-08-25).** The probe
reads the rectangle and the computed properties of the element itself — never a `::before`/`::after`
pseudo-element, and never a descendant (a region's 19 properties are read on the nodes its selector
names, not their children; amended 2026-08-30 with the same rule). **A pseudo-element or a
descendant that carries a function is covered by a named rule instead** — the oracle is not
widened, and a surface relying on one without such a rule is the defect, not the oracle.

**A RULE may read pixels; the ORACLE never does — amended by the steward's L12 audit, 2026-09-01.**
L12's R118 (`frontend/maquette/harness/chrome_pixels.py`) compares one region with itself at two
moments of one run (mid-transition against settled, with a control) — a different comparison from
the oracle's two-runs-of-an-unmodified-page measurement, so it does not widen the oracle. A rule
that needs a pixel says why in its own file and carries a control. Story:
`docs/reference/frontend-architecture.md@6a47304a4` § D8.

### D9 — What a library is adopted for, and where motion lives

**Two rules, and between them they settle every "should we use library X" question without
re-opening the argument.**

1. **What is declarative lives in the stylesheet** — therefore in the design reference, therefore
   under the oracle. Motion written in JavaScript leaves the field of measurement, and a design
   decision nobody can measure is a design decision nobody can defend.
2. **A reliable library that solves EXACTLY our problem is preferred to re-coding it; code is
   written by hand only for maths nobody has written.** Dictated by the operator on 2026-08-31,
   and it REVERSES the rule that stood here (« a library is adopted for maths nobody has written,
   never for an arbitration already proved »). The question is asked first and in this order: does
   a library exist that solves exactly this problem, is maintained and followed, is proven and
   has standing? **If yes, the wave PROPOSES THE CANDIDATES** — each with the criteria it meets —
   and the operator chooses; if none exists, or none solves exactly the problem, the code is
   written here. « Exactly » is the whole test: a library that solves the plumbing and not the
   hard part (the gesture row below) does not qualify, and that is a measured answer, not a
   preference for our own code.

**Applied, with the verdicts they produce.** These were argued against real alternatives; the
reasoning is kept so the alternatives are not proposed again as if new.

| Candidate | Verdict | Because |
| --- | --- | --- |
| **View Transitions API** for page and layer transitions | **adopt** | native, compositor-driven, zero bytes, declarative — so it is measurable. Same-document transitions are supported on the target platform |
| A JS animation library for **page transitions** | **refuse** | it buys what the platform gives, costs tens of kilobytes, and moves motion out of the stylesheet (rule 1) |
| A JS animation library for **one interruptible spring** that follows a finger and settles | **allowed, scoped** | CSS cannot express interruptible pointer-driven physics. One component, never a transition strategy |
| A gesture library **replacing** the press/drag/scroll arbitration | **refuse — unless a candidate meets rule 2's « exactly »** | the hard part is two things a general library does not know: a long press and a drag are opposite cases for the compositor, and the click a long press causes is swallowed by its POINT (§ 4, L12). A library that carries both, maintained and proven, is a candidate to propose; one that solves the plumbing only does not meet « exactly » (rule 2, as reversed 2026-08-31) |
| A gesture library for a **new** gesture needing velocity, inertia or multi-pointer maths | **preferred, scoped** | a proven library beats writing that maths here (rule 2, as reversed) — candidates proposed, the operator chooses |
| A **list virtualiser** for the library's 1 861 titles (P24, L12) | **adopted: `@tanstack/react-virtual`** (operator, 2026-08-31 — « Ok pour @tanstack/react-virtual », relayed in writing) | **DECIDED, not a proposal.** Three candidates were surveyed with their registry facts: `@tanstack/react-virtual` 3.14.10, `react-virtuoso` 4.18.12, `react-window` 2.3.0. All three MIT, all maintained, all released within six weeks — **solves-exactly, maintained and proven separate none of them.** RULE 1 DOES, and it is untouched by the reversal of rule 2: `react-virtuoso` renders its own scroller and `react-window` writes inline styles onto every child, both moving drawing out of the stylesheet and out of the design reference. `@tanstack/react-virtual` is HEADLESS — the registry's own description — so it returns measurements and renders nothing. Secondary, and not decisive: 55 KB against 237 and 211, and its family already ships three packages here. **Used in its FIXED-SIZE mode**: both list modes were measured uniform (tiles 203.34375 px, cards 126 px), the two heights the gallery first showed being skeletons. L12 wraps it in `ui/virtual-rows.tsx` so the dependency has one call site |
| **Haptics** | **refuse the capability, build the seam** | the target platform exposes no public API; the workarounds ride an implementation detail that has already been tightened once. One `feedback()` call site all gestures pass through, visual today — so adopting it later changes one file |
| **`onTouchStart` for pressed states** | **refuse** | it lights the pressed state when the finger is starting a SCROLL, so a list flickers as it is scrolled. `:active` is cancelled by the browser when the gesture becomes a scroll, which is the wanted behaviour, for free. **What this row refuses is a mark on the RAW pointerdown.** The press acknowledgement the operator chose on 2026-08-31 (L12) is placed by the ARBITRATION once its settle has ruled a scroll out and released when the panel arrives — a fact about the gesture, not the surface — and R113 holds that a flick starting on a tile is never acknowledged. Amended by the steward's L12 audit, 2026-09-01: written before that gesture existed, the row read, unamended, as refusing it |
| **`@media (hover: hover)`** to keep hover off touch | **adopt** | the sticky-hover problem is real; this is its declarative remedy |

### D10 — The dying engine's CSS is a bounded residue with a date of death

**Decision.** The CSS the legacy engine still needs does not convert and does not disperse: it is
one file, `design/src/styles/legacy.css`, deliberately **unlayered** so it wins over
`@layer utilities` on the markup the engine draws. It may not grow, a guard
(`check-legacy-css-residue.py`) refuses any addition, and it dies with **L13**.

**Arbitrated by the operator on 2026-08-24**, during L07, under the name **D-L07-5**.

**What it costs.** Unlayered normal declarations beat every cascade layer whatever the specificity
— including on markup that COMPONENTS draw, so a variant can be edited and change nothing on
screen while the residue still wins. Held by `R80` (`frontend/maquette/harness/residue.py@60530dbd8`,
contracts tier): it pairs each residue selector with the typed variant wearing the same identity
anchor and compares `getComputedStyle` in the document, on two sibling probes, for exactly the
properties the residue declares — **sixteen pairs**, and it measures under both motion preferences
(a utility with no `motion-safe:` disagrees with the residue under reduced motion, which is how
B-076 was found). It counts what it does not yet stage on every run rather than leaving it to be
discovered, and holds a floor on the number of pairs found so an empty pairing cannot read as
« no divergence ». Story: `docs/reference/frontend-architecture.md@6a47304a4` § D10.

### D11 — The scrollbar is STYLED, never replaced (operator, 2026-08-26)

**Decision.** The scroll container's bar is given the design system's appearance through
`scrollbar-width`, `scrollbar-color` and `::-webkit-scrollbar` — declarative, in `base.css`,
therefore under the oracle. **A scrollbar rebuilt in JavaScript is refused.**

**Why, and each reason is already a rule here.** A rebuilt bar loses the keyboard (PageUp/Down,
Home/End, the gutter click), the middle-click, and the native role — against L03, whose floor is
zero findings over 83 states. Its thumb would be positioned by a `scroll` handler, which is D9
rule 1 exactly: motion written in JavaScript leaves the field of measurement. And the scroll path
is compositor-facing, the category § 6 records as load-bearing — deleting one selector from that
family once swallowed the whole pointer stream.

**What styling does NOT solve, recorded so it is not rediscovered as a defect**: on a desktop the
bar still occupies its gutter. That is the platform behaving correctly, and the phone frame the
operator compares against is `harness.css`, which ships nowhere — a declared deviation, not the
target. A real phone paints an overlay bar that fades.

**A risk to measure before the change lands, not after.** `scrollbar-width: thin` narrows the
gutter, so the content beside it widens by a few pixels. Every measured rectangle in that container
may move. Whether it does is a run of the oracle on the machine that owns the references — it is
not asserted here, and a wave that assumes either answer is doing what B-101 records.

---


### D12 — Two production surfaces do not survive the switchover (operator, 2026-09-02)

**Decision.** The global event feed (`EventFeed`, `RecentEventsTable` — a scrollable list of every
event the stream carries, on production's Système) and the standalone configuration validation
(`POST /api/config/validate`) are NOT redrawn. They are the two of the nine ownerless surfaces of
the 2026-09-02 inventory that the operator wrote off; the seven others have a lot each (Phase 5's
re-cut, B-296 to B-302).

**Replaces.** The standing reading of the mission — « every production screen with no page in the
maquette is a page still to be drawn » — for these two, by name. The mission is unchanged for
everything else.

**Why.** A feed of every event has no axis: it is the old dashboard's model, refused on 2026-08-19
with Contrôle (« a medium in trouble is Arrivées, a machine in trouble is Système »). Its two halves
are already served where the rule puts them — an event about a medium reaches its card and its
journey (L19), a service that changes state reaches Système (`frontend-backend-demands-stream.md` §
4) — and production's panel was an instrument demonstration (a virtualised list over the event
ring), not a product surface. The validation call is a backend convenience: the save already returns
its warnings, and a separate « validate » has no surface of its own.

**What it makes void.** Any future inventory listing these two as missing. The absences already on
the record stand beside them and are not repeated here: the desktop rail (Q1 — drawer alone, not
frozen), the Pipeline tab and badge (Q6 — none), per-file configuration editing (settings navigate
by topic), the trigger legend (the trigger is written in words), push notifications (B-257 —
declined, consumer L16).
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
10. **The frame does not name the domain**, except in the three tables whose job is to. `ui/`,
    `lib/` and `app/` may carry the application's SHAPE — a shell, a page host, an address model,
    a component vocabulary — and not its SUBJECT. The three exceptions are named because they
    cannot be anything else: `lib/addresses.ts` (an address IS the page's identity, D1),
    `routes/*` (a route names the page it mounts), and whatever table the shell reads to compose
    navigation. Held by a count per directory, refused upward — never by an interdiction, so a
    shared component that genuinely needs a domain word is one reviewed line, not a wall.

    **This invariant freezes a property that was already true (measured 2026-08-26) and has since
    drifted twice, tracked rather than silently accepted** (§7.1's duty): `lib/queue.ts` (169 domain
    words — the staging/acquisition queue two features both read, with nowhere else to go under
    invariant 7), `app/engine-data.ts` (34 — what the dying engine reads with no component to ask
    for it), `app/history-bridge.ts` (17), `app/live-updates.ts` (18, one import per feature — the
    same species as the frame naming its pages). **169 is not "one reviewed line"**: it is the frame
    carrying a subject because the only alternative today was worse, and it leaves two open
    arbitrations — a `domain/` bucket of its own, and whether B-100 (this invariant is unarmed) is
    worth arming. **Its subject is MODELLED since 2026-08-29** — `docs/reference/frame-model.md` § 2,
    thirteen parts, each saying where it lives under this invariant. Story:
    `docs/reference/frontend-architecture.md@6a47304a4` § 3, invariant 10.

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
15. **No French in the code and no interface text in the code.** Unchanged
    (`scripts/check-no-french.py`), and it applies to everything written here. **It carried the
    number 10 until 2026-08-29**, alongside the invariant about the frame naming the domain, and
    it is the one that moved because every citation of « invariant 10 » in this file, in the
    register, in the archive and in the maquette's own comments means the other one. Renumbering
    the sequence instead would have moved ten live citations and quietly falsified three archived
    documents, which are frozen. Held from here by
    `scripts/check-bug-register.py --arm invariant-numbers` (B-103).

---

## 4. The lots

**No lot below carries a status**, since 2026-08-28. What a lot carries here is its ORDER — its
position in this file — and its DEPENDENCIES. Whether it has landed is `IMPLEMENTATION.md`'s
« Landed, in order » row and nowhere else, along with everything richer: which pull request, which
measurement, which proof. **A fact that exists once cannot go stale**, and this one had: `L09` read
`NOT STARTED` here for a full wave after it merged, which elected the lot that had just landed and
left four size promises green that nobody owed any more (B-148, B-150).

### Phase 0 — The safety net

Nothing else may start. Every lot after this one changes mechanism while promising the rendering
is unchanged, and that promise is currently unprovable: `fidelity.py` cannot run — the renderers
it compared are deleted, no recording is committed, and the state ids have been renamed in two
separate waves since.

#### L01 — The recorded oracle

**Landed** — PR #467, squash `59931d45c`. The oracle is one command: it records, per named state × region, the bounding rectangle and a fixed subset of computed style, replays it on demand, and is wired into `run.sh` as its third tier. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L01.

#### L02 — Test anchors move to `data-*` · *depends on L01*

**Landed** — PR #470, squash `77811666a`. 280 selector calls moved off CSS classes onto `data-*` contracts; the classification this lot measured now reports zero class-anchored selections. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L02.

### Phase 1 — The contracts of markup and structure

#### L03 — Accessibility · *depended on L01*

**Landed** — PR #475, squash `737ce5e94`. `axe-core` over the 83 named states went from 744 violations over 7 rules to 0, oracle at 0 divergence over 2 739 measurements, held by `run.sh --a11y`'s hard-zero floor. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L03.

#### L04 — Boundaries and the tree · *depended on L01*

**Landed** — PR #478, squash `668130636`. The two import cycles and the `data.ts` hub are gone; the tree is grouped by domain under `features/`, and seven guards (`check-frontend-boundaries.py`) hold the target tree in the gate. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L04.

#### L05 — Routing · *depended on L01, L04*

**Landed** — PR #482, squash `c4e52ca54`. Every page and screen sits on a real path with state in the query and layers ranked in three tiers; navigation logic left the engine for `lib/`. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L05.

### Phase 2 — The visual language

#### L06 — The scale · *depended on L01*

**Landed** — PR #490, squash `a4418e6a9`. One declared scale (32 tokens) replaced 65 padding values, 21 type sizes and 17 radii; the 42 colour-contrast findings and the auto-zooming search field are both at zero. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L06.

#### L07 — Tailwind and CVA, surface by surface · *depended on L02, L04, L06*

**Landed** — PR #494, squash `5fdbfc9a6`. Every surface converts to Tailwind utilities behind typed CVA variants, oracle green at each step; BLOCK 1 survives as the harness-only `harness.css`, and the compositor-facing declarations are held by a rule. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L07.

### Phase 3 — The application

This phase is the bulk of the remaining work. The pages are finished; the application is not.
Measured when the phase opened: 11 API modules against 0, 65 network calls against 1, 24 WebSocket
files against 0, a service worker against none. **L08 moves the second of those** — the maquette
declares 53 operations of its own and answers every one of them from a mock layer — and moves
none of the others: no surface is wired to any of it, which is L09's.
<sub>commands in `IMPLEMENTATION.md` § THE OBJECTIVE</sub>

#### L08 — The data contract and the mocks · *depended on L04*

**Landed** — PR #503, squash `ce1d7b5a4`. The contract (`frontend/maquette/contract/openapi.json`: 49 paths, 53 operations) and its 46 fixture-seeded mocks exist; the oracle reads 0 divergence over 2 739 measurements with the layer live. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L08.

#### L09 — The data layer, surface by surface · *depended on L01, L05, L08*

**Landed** — PR #509, squash `27096f31c`. Server state moved into the query cache with optimistic mutations and rollbacks on every surface; each surface's share of the fixture died with it (D5). Body: `docs/reference/frontend-architecture.md@6a47304a4` § L09.

#### L10 — The live relay · *depends on L09*

**Landed** — PR #512 and #513, squash `3c66dd36f`. The event stream drives exactly the invalidations it should, loss and reconnection are visible, and no polling remains where an event exists. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L10.

#### L15 — The frame · *depends on L07, L09*

**Landed** — PR #528, squash `212faf0ae`. The engine draws none of the frame's chrome any more — tab bar, drawer, dialog, toast, popover and the entry (splash/sign-in/install/appearance) are React, against the model in `docs/reference/frame-model.md`. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L15.

#### L11 — Offline and PWA · *depends on L09, L15*

**Landed** — PR #534, squash `39363e1da`. Service worker, offline shell and a mutation queue that departs on reconnection are in place; all three Q4 entry points (`share_target`, `launch_handler`, `handle_links`) are declared. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L11.

### Phase 4 — Native interaction

#### L12 — Native interaction · *depends on L05, L07, L15*

**Landed** — PR #540, squash `7f2ec99a4`. View transitions, the press/drag/scroll gesture arbitration, mobile geometry and the interaction budget landed; the library's 1 861 titles are virtualised through `@tanstack/react-virtual`. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L12.

### Phase 5 — The producers, and what the constitution owes

Declared by L10-ter on 2026-08-29, ordered by the operator's answers of 2026-08-30. L14 first
(pulled forward, Q3); then D5 applied to the sheets — the pass « surface by surface » never made;
then the global levers; then the constitution's three, each drawn in the maquette first like every
surface — L16 and L17 still blocked on a dictated answer, L18 no longer.

**Re-cut on 2026-09-02, on the steward's inventory of every production surface against the
maquette.** Nine surfaces had no owner — production draws them, the maquette does not, and no lot
named them. The operator placed each (D12 records the two that do not survive): the settings' two
banners with L19; the three verbs a tunnel owes in a lot of their own, **L21**, because a verb is
behaviour and L19 is a conversion; a passage's raw log and the locks with L20; the ranking editor
with L16. **The order is now L14 · L19 · L21 · L20 · L16 · L17 · L18 · L13**, and no dependency
already written moved.

**Re-ordered on 2026-09-12, by the operator's seventh measure (« L13 — la mort du moteur — en
priorité après les vagues en vol »).** The engine's death runs NEXT, once the micro-waves in flight
on that day land, and before L20: **the order is now L14 · L19 · L21 · L13 · L20 · L16 · L17 · L18**,
and no dependency already written moved — L13's five (L07, L09, L12, L15, L19) are all landed. What
it makes void: « L20 opens after the `maquette-settings` micro-wave merges » — L20's design and plan
stay on `main` (#587) and the lot opens after L13. The measure and its six siblings are recorded in
`docs/reference/frontend-steward.md@638ebcfc` § « The operator's measures of 2026-09-12 »; reversal is his.

**Re-cut again on 2026-09-15, by the auditor's lot-order delegation (C10).** L22 (Arrivées dans
Acquisition) is inserted before L16, after L13: the order was L14 · L19 · L21 · L13 · L20 · L22 ·
L16 · L17 · L18, and no dependency already written moved. L16 opens after L22b, its own two sub-lots'
head. **Extended on 2026-09-27 (round 8 Q18): an upload-to-tracker lot, drawn ahead of time in the
second slot after L18**, per the operator's own separation of that function from L17. **Its design
and plan, written 2026-09-27, name it L23: the order is now L14 · L19 · L21 · L13 · L20 · L22 · L16 ·
L17 · L18 · L23**, and no dependency already written moved. **L24 (the orphans), drawn 2026-09-29, follows L23;
after it, the desktop milestone** (operator, 2026-09-29, L24's OPEN 6) — the final entry of this section, not a lot.
**L16-bis (the Trackers page's correction and Découvrir's header, on the operator's feedback of 2026-09-29), drawn 2026-09-29, is inserted between L16 and L17, which draws on its torrent rows: the order is now L14 · L19 · L21 · L13 · L20 · L22 · L16 · L16-bis · L17 · L18 · L23 · L24** — `docs/features/maquette-l16bis/DESIGN.md`, `docs/features/maquette-l16bis/plan/INDEX.md`. **Amended 2026-09-29 (the operator's nine rulings, PR #637): L16-bis *depends on the conformity train*** — the train builds the app's one tab component first, on the existing validated tab bars (Acquisition first), then arms the guard; L16-bis's own code waits for the train and then uses the component for Trackers, never building it — the phase that once built it here is removed (DESIGN § 5, DECIDED 7). **Amended 2026-09-29: the conformity train (its entry after L16's) runs before the case catalogue, L16-bis's code and L17.**

**The navigation lot (`maquette-navigation`, B-577 and every edge read against the amended § 16), drawn 2026-09-30 in PR #651, is inserted directly after the conformity train: its code opens only once the train has merged**, because the train's phases 5 and 10 touch Système and the drawer, the surfaces its first phase rewires (its DESIGN § 0.3, its plan's INDEX). It changes behaviour, so it is not a conversion. **The order is now L14 · L19 · L21 · L13 · L20 · L22 · L16 · the conformity train · maquette-navigation · L16-bis · L17 · L18 · L23 · L24**, and no dependency already written moved.

**C1 — the settings save bar, placed AFTER L16 (operator, 2026-09-29, ruling C1, verbatim: « On parle de toutes les
pages de réglages ? Si oui alors oui. Si on veux quitter réglages un message de confirmation s'affiche, avec
enregistrer, abandonné les modif, ou fermer rester sur réglages »; on Trackers: « Oui »).** The save bar becomes a
FRAME part, visible on every Settings page while a change waits (never on every app page, refused); leaving
Settings or Trackers with a change waiting opens ONE confirmation with three choices — « Enregistrer » / «
Abandonner les modifications » / « Rester sur Réglages ». **A MICRO-WAVE, not a lot** — unrelated to L17's own
scope (cross-seed) and small enough by § 0's own selection rule to take nobody's turn, on the pattern of
`maquette-settings` and the other same-scale corrections of § 4's history. Runs before L17 opens or beside it, never
inside its plan. **Named states (proposed, not built): `settings-save-bar-frame`** (the bar drawn by the frame
itself, replacing L16's `lib/save-bar-door.tsx` door — C2's own compromise, superseded) **and `settings-leave-confirm`**
(the three-choice confirmation). **One rule**, holding both. **The existing pending-edits signal is REUSED** — the
door's `onEditsWritten` / `editsWritten` pair (`frontend/maquette/design/src/lib/save-bar-door.tsx`) already knows
whether a change waits; the leave confirmation reads THAT, never a second dirty-tracker. **Delivered 2026-09-30** on
`feat/maquette-c1`: the bar is drawn by the frame's bottom slot over the pages whose row says `holdsEdits`
(`app/navigation.ts`: Réglages, Trackers); the door became `lib/pending-edits-door.ts`, the one table of pending
edits, which also answers how many wait, the save and the drop; the confirmation is `app/leave-confirm.ts`, asked
by the frame's three page verbs and by the Back ladder, which holds a Retour that would leave; the named states
`settings-save-bar-frame` and `settings-leave-confirm` are built, and rule R-C1-a (`harness/settings_leave.py`)
holds both, red on `4f6704ccd`.

#### L14 — The surfaces that outgrew their file · *depends on L07, L09*

**Landed** — PR #547, squash `9ce9b0508`. The four feature files over the 400-line ceiling are decomposed back under it, by domain. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L14.

#### L19 — The producers · *depends on L15, L09, L12*

**Landed** — PR #558, squash `9fa13da57`. Every surface the engine still produced (ten `panel.open` producers) moved to its own feature component; the engine's remaining edits are declared D5 exceptions. Body: `docs/reference/frontend-architecture.md@6a47304a4` § L19.

#### L21 — The tunnel's verbs · *depends on L19*

**Landed** — PR #572, squash `2ffdc4ba3`. The acquisition tunnel's verbs — grab a season, re-queue, re-scrape — are wired through a domain-free tap registry (`lib/verbs.ts`). Body: `docs/reference/frontend-architecture.md@6a47304a4` § L21.

#### L20 — The global levers and the history · *depends on L15, L19, L10*

**Objective.** What remains of « the control station » once §20 is dictated: the **global
levers** — the parallelism bound (how many tunnels run at once), pause and resume of everything,
« relancer la veille » (`POST /api/pipeline/watcher`) — and the **history** of passages with a
run's figures (`GET /api/pipeline/history/{run_uid}`, DOIT-6). It was declared on 2026-08-29 as
« `/control` (8 panels) and `/pipeline` (10 panels) »; **on 2026-08-30 the operator dictated §20
— a tunnel per media — and a page showing THE run lost its subject**: the pipeline is followed
per media, through the acquisition tunnel the maquette already draws (a card's progress, the
journey sheet, the Arrivées' blocked queue with its reasons). What those two production pages
carried is therefore split: the per-media half is **L19's** (the producers of exactly those
surfaces), the global half is this lot's, and there is **no Pipeline tab and no pipeline badge**
(the operator's Q6 answer) — the chrome shows what awaits the operator, and the Acquisition and
Arrivées badges already do.

**Two surfaces placed here on 2026-09-02** (the operator, on the steward's inventory). **The raw log
of an execution** — production's `RunLogFeed`, the `run_log` lines verbatim — lands inside the run's
detail in the history, FOLDED by default: DOIT-1 asks for clear French, and the narrative of a
passage is per media under §20 and is L19's (the journey, DOIT-5); what stays global is the raw
lines, a secondary disclosure for diagnosis, never the default view (B-296). **The locks** — `GET
/api/maintenance/locks` answers the pipeline lock, the pause sentinel and the watcher's pause, which
are exactly the STATE of this lot's own levers, plus the tmp-orphan sweep, which is a machine fact
and renders as a block of Système; its repair stays a Maintenance command, as the index's does today
(B-297). Who holds the lock behind « En file » remains L19's line.

**Blocking note — LIFTED 2026-09-12, the operator ruled « Q1 : B ».** The levers land in a
« Pipeline » section of **Système**; the history stays Système's (it already draws « Les passages »
from `GET /api/pipeline/history`) and gains a run's DETAIL, an addressed screen, with its figures;
start / stop stay on Arrivées' pilot's bar, which becomes the surface B-371 wires. A page of its
own was refused: it recreates the destination §20 removed. The design and the nine-phase plan are on
`main` at `docs/features/maquette-l20/` (#587, squash `d9221ebf9`); the operator reads the drawing
there before the lot opens, after the `maquette-settings` micro-wave merges.

**Amended 2026-09-12 from that design's measurements (§ 8 of `docs/features/maquette-l20/DESIGN.md@60c6d9b1d`),
and each line below replaces what the entry said before it:**

- **« relancer la veille » is NOT `POST /api/pipeline/watcher`.** That operation takes `{enabled}`
  and creates or removes the `watcher.paused` sentinel — the directory watcher's on / off, a lever
  with no figure. The veille with DOIT-6's figures (`{detected, available, grabbed}`) is
  `POST /api/acquisition/detect`, already in the maquette's contract as `runDetection` and already
  mocked; its button « Lancer la veille maintenant » is one of B-383's four « said, not done » verbs.
  **Both are L20's**: the watcher's switch AND the veille's relaunch with its figures — and that half
  of B-383 moves here from the mock-layer micro-wave, which keeps the other verbs.
- **DOIT-6 is served by TWO operations, each with the numbers its own run answers**: the veille's
  (`detect`) and a pipeline run's per-step counts and `reasons[]` in the history's detail
  (`history/{run_uid}`); the history ROW keeps the composite line it already draws. The map's DOIT-6
  row says so.
- **The parallelism bound exists in no configuration file** (`grep -rn "parallel\|concurren\|tunnel"
  config.example/*.json5` finds only the indexer's disk workers): it is a NEW setting and a backend
  demand; the design proposes its key, type and settings topic (`service`) so nobody invents a
  seventh topic for one key. It is edited by the settings feature's existing `number` field — no
  new control.
- **`GET /api/pipeline/stages` — the Flow Board, THE run's eight stations — is not this lot's, by the
  operator's ruling « Q3 : B » of 2026-09-12**: the pipeline's stages are read PER MEDIA, on the card
  of a medium in the pipeline (Acquisition › En cours already draws « pris · téléch. · ingéré · scrapé
  · rangé » on such a card). The map's row moves to the tunnel (L19's family) and the operation becomes
  a backend demand for a per-media form. Neither L20's Système section nor a write-off.
- **`engine/states.js` is at its ledger (786 non-blank) and `check-frontend-boundaries.py` refuses
  the count going up**, so the 26 named states this lot declares cannot enter the engine's table:
  phase 2 of the plan moves Système's own slice of that table to `design/src/states/system.ts` and
  re-records the ledger DOWNWARD — the engine shrinks (D5), and `window.__recordStates` (which
  REPLACES the table, `legacy.js:8683`) is not made to accumulate.
- **The raw log's fold needs a disclosure primitive that `ui/` does not have**; three feature files
  write `<details>` raw (`features/acquisition/add-screen.tsx`, `features/media/season-list.tsx`,
  `features/media/panel-seasons.tsx`, plus `legacy.js:30695`). L20 adds the primitive for its own
  fold; converting the three sites is a conversion debt, not this behaviour lot's.

**Where it lives (invariant 10).** `features/system/` — the design put the levers and the
history there (ruled, above); the bound is a setting and reads through the settings feature's
contract.

**Done when.** DOIT-3's « relancer le watcher », DOIT-5's progress to the library and DOIT-6's
figures read `served` in the map with a rule; the bound, the pause and the watcher are called and
mocked; the history renders every named state at 390 px with no overflow; a run's detail carries its raw
log folded and the levers read the lock and the sentinels (B-296, B-297); the oracle records the
surfaces as new.

#### L22 — Arrivées dans Acquisition · *depends on L13, L19, L20, L21*

**Objective.** A BEHAVIOUR lot on existing surfaces — the Acquisition page, the card and its one
ladder, the candidates screen — and the death of Arrivées as a destination of its own. Inserted by
the auditor's lot-order delegation (2026-09-15) before L16, after L13; startable stacked on L13c's
head at its PR READY. Its design is dictated by the operator's fifteen organisation rulings of
2026-09-15 and 2026-09-26, in `docs/reference/operator-method.md`, and by his eleven rulings of
2026-09-26 on the design's open questions (DESIGN § 7.2).

**Where it lives (invariant 10).** The Acquisition page — the card, its one ladder, and the
candidates screen; Arrivées itself dies as this lot lands.

**Done when.** The Acquisition page draws the card, its one ladder and the candidates screen as
the operator's rulings dictate, and Arrivées no longer exists as a destination of its own.

**Design and plan written 2026-09-26, PR #612** — `docs/features/maquette-l22/DESIGN.md@232a908ca`, its plan
`docs/features/maquette-l22/plan/INDEX.md@232a908ca`; the rulings number fifteen, not nine (the six of 2026-09-26 are in it).
**Cut into two sub-lots** (auditor's method decision, 2026-09-26 — L13's precedent): **L22a** = phases 1–14
plus 14-bis and 14-ter (176 points; the two added on the operator's rulings of 2026-09-26 evening, « En cours »
holding « En vol » alone — DESIGN § 7.3), **L22b** = phases 15–27 (151 points), stacked on L22a's head at its
pull request's READY; one reader round each; the folder dies at L22b's gesture.

#### L16 — §18, the ratio · *depends on L15, L19, L10, L22*

**Objective.** DOIT-13: the ratio is read PER TRACKER, an obligation is a « rien » with its reason
carried as a MARK on its own torrent's row (never a second, doubling list — organisation ruling 18),
and a tracker's policy is set from the surface that shows it. `GET /api/acquisition/obligations` and
`/downloads` answer and nothing calls them; a tracker-level summary read exists nowhere and is this
lot's own demand. **The policy write is NOT a new operation** (corrected 2026-09-27, C10, F11):
`updateConfigurationFile` already writes the tracker's `economy` block, and Réglages already offers
`min_ratio` / `min_seed_time` as settings rows — only the alert threshold is a missing KEY in that
same family, a config-shape demand, never a second write path. The stream's `RatioMeasured` and
`SeedObligation*` events reach the browser and no surface claims them
(`frontend-backend-demands-stream.md` § 3); this lot's `live.ts` does.

**Dictated (operator, 2026-08-30) — the blocking note is lifted.** One action: RELEASE an
obligation early — including when the stop happens by removing the torrent in qBittorrent by hand,
a HANDLED case the obligation closes by saying so, never a silent anomaly (the reconciliation is a
backend demand). A per-tracker ratio ALERT with a threshold — later a push notification (FCM, iOS
and Android; a platform demand that plugs into L11's entry points). Ranking may subtract points
from releases on low-ratio trackers (a scoring demand). Shown beyond the ratio: Download / Upload
volumes, the trend, and per ACTIVE torrent its deadline and its ratio. **No proposed decision**:
the interface exposes, the operator judges. The backend's share is recorded in
`backend-demands-architecture.md` § 4.

**Reshaped 2026-09-27 (organisation ruling 18, round 9 Q7).** The « release » action IS the gesture
the operator described, not a verb of its own: **« Retirer de qBittorrent »**, on the torrent's
qBittorrent entry, files deleted by default and decheckable, a confirmation naming every shared
consequence and every tracker with a running obligation when files ARE deleted. An obligation ends
when its torrent leaves qBittorrent, by this gesture or by the operator's own hand outside the
interface; its trace lives in Système's history (ruling 12), never a second « released » list.

**And the ranking editor (operator, 2026-09-02, on the steward's inventory; corrected 2026-09-27,
F16).** « Le ranking suit le ratio »: the weights that rank a release gain a ratio term, and the
surface where that term is set is the ranking editor production has — `RankingPanel`, reading and
saving `ranking.json5` through the SAME `GET` / `PUT /api/config/files/{name}` operation the settings
feature already declares and mocks, with a live preview through `POST
/api/acquisition/ranking/preview`. The maquette's own twin had drawn neither the read nor the save
(F16 — the settings rubric « Classement des releases » promised « un écran à part » and the quality
screen's button was a toast, B-298); it is drawn here, reading and writing the real file, with its own
address under the settings page (D1) and the live preview the backend already computes; the toast
goes with it.

**Where it lives (invariant 10).** `features/trackers/` — a tracker is a domain of its own, read
by the acquisition and the media sheet, and invariant 7 forbids either from importing the other.
**One page, two tabs** (organisation ruling 19, 2026-09-27) — « Torrents » (every torrent active in
qBittorrent, once, filterable by tracker) and « Trackers » (one entry per tracker, an accordion —
the wave's own choice, § 3 of its design, a dedicated page only if too long) — a bar row **inserted
between Médiathèque and Découvrir** (organisation ruling 20), never a fifth place appended after a
free slot.

**Done when.** The map's DOIT-13 row and DOIT-2's row (all three deferral kinds — ratio, space,
missing content, F14) read `served` with a rule; the reads are called and mocked (seeded from the
running backend's shapes, D7); the alert-threshold key and the removal operation are in the demands
register; the events are claimed by a rule (R91's fan-out); the ratio shown is the tracker's
(NE-DOIT-PAS-1, held by the mock's own value, never a local computation, and computed on the
torrent's own size for a cross-seeded entry); the ranking editor reads, saves and previews live, and
the quality screen's toast is gone (B-298).

**Design and plan written 2026-09-15, re-read against the organisation rulings 2026-09-26 (PR #614);
RE-DRAWN 2026-09-27 against organisation rulings 18–20 and rounds 7–9 of the coherence audit, this
docs pull request.** `docs/features/maquette-l16/DESIGN.md@f3d8fed01` and `plan/INDEX.md@f3d8fed01` (16 phases, mean
≈ 11.4). Its prior OPEN 1–3 are ruled (Trackers in the bar at L16 with the ratio alone; no right
declared before L18; the badge's three components — threshold, breach, and, since round 9 Q1, a
refused identifier); one new OPEN question is born of ruling 19 itself (which tab opens by default,
DESIGN § 5, OPEN 4) and is not chosen here. The lot
opens after L22b.

#### The conformity train — one need, one component; every state at every width · *depends on L16*

**Not a lot: a train of conversions and one rule** (auditor's orders 80 and 85, the operator's 2026-09-29 reports:
« 1 design système, 1 composant, de la cohérence ! », « tout doit être responsive … sur tous ! »). **It runs BEFORE
the case catalogue, L16-bis's code and L17**, which waits for it (L16-bis DECIDED 7): it builds the app's one tab
component from Acquisition's validated bar and arms its guard, then converts every need the design reading counted
as « one need, N modules » to the one component. Its first move is the **responsive rule** — every named state at
320, 360, 369, 390, 412, 768 and 1280 px, no horizontal overflow and no cut — which replaces order 60; every red it
finds and the train does not repair is declared by name, with its owner. A conversion proves nothing observable
changed except the one visible change its item names. Design: the conformity reading
(`review-archive/conformity-80/REPORT.md` § B, § D); plan `docs/features/maquette-conformity/plan/INDEX.md` (13
phases, one per surface, a harness consolidation before the close). Four conversions (report D.1 #2, #7, #14, #15) wait for the operator's round and are not in it.

#### L17 — §19, cross-seed · *depends on L16*

**Objective.** DOIT-14: an injection is seen, a refusal is explained, a title says where it seeds,
and the operator can prevent or provoke it. **Nothing exists to call**: this is D7's first real
case — the maquette declares the routes its experience requires, the demands register carries
them, the mocks are INVENTED because no fixture exists (L08's « seeded from the fixture it
replaces » does not apply, and the oracle records the new surfaces as new rather than proving
them unchanged). `CrossSeedInjected`, `CrossSeedRejected` and a search-outcome event are claimed by
its `live.ts`.

**Dictated (operator, 2026-08-30; amended 2026-09-27, product-intent.md § 19 point 5) — the
blocking note is lifted.** AUTOMATIC: the engine cross-seeds alone, active by default AT THE
SWITCHOVER, with a PER-TRACKER off switch (a config write, NE-DOIT-PAS-6 made into a setting) that
cuts NEW cross-seeds only. Seen: for EACH torrent, the cross-seed state per tracker, in SIX words —
« actif », « stoppé », « tracker sans cross-seed », « erreur de cross-seed », « sans
correspondance », « pas encore cherché ». Lives: the per-tracker state as a MARK on the Trackers
page's « Torrents » tab (organisation ruling 19, 2026-09-27 — the page is two tabs, not a page plus
a per-tracker detail screen); a per-tracker block in the media sheet **visible to the
administrator profile only** is HELD FOR L18 (round 8, L17 OPEN 1 = B), whose rights model exists —
no account carries a role in either contract today, only the instance's own deployment role, so
« the served role the backend already exposes » was never this lot's to read. A separate
upload-to-tracker lot (round 8 Q18 = B), publishing a torrent to a tracker to open a cross-seed, is
proposed as **L23**, after L18, drawn ahead of time in a later slot; L17 keeps only a reserved slot
in its closed failure list for it.

**Where it lives (invariant 10).** `features/trackers/` extended — the roster's line and a MARK on
each torrent's own row of the « Torrents » tab, never a section or a page of L17's own (ruling 19
kills the `/trackers/$name` detail screen the first drawing of this entry assumed). **No feed**
(round 8, OPEN 4 = A): the mark's own rows already carry the date of an injection and the reason of
a refusal, and organisation ruling 12 keeps Système's history as the only trace of the past. The
media sheet's block is L18's (above).

**Done when.** The map's DOIT-14 row reads `partly` at L17's close (the roster, the mark, the
badge, proof R-L17-a … k) and `served` only once L18 draws the media sheet's block on its own
rights model; the declared routes are in the maquette's contract and in the demands; the three
events are claimed; a refusal is readable from the surface with its reason (NE-DOIT-PAS-5 applied
to a success); the Trackers badge counts the cross-seed FAILURES only, with a reserved slot for the
future upload lot.

**Design and plan AMENDED 2026-09-27** on the operator's rulings of round 8 (L17 OPEN 1–8, Q18),
round 9 (Q5, Q7 in part, Q8, Q9, Q10, Q11) and round 10 (Q3, Q5), and the auditor's
rulings-coherence round (M4, M5, M6) —
`docs/features/maquette-l17/DESIGN.md` and `plan/INDEX.md` (18 phases, mean ≈ 11.2). All eight OPEN
questions the first drawing carried are ruled; the media sheet's block and its route move to L18
entirely (above); the plan drops the feed's two phases and the media block's two phases, and adds
three — cutting one tracker's cross-seed, the exclusion memory, and the virtual window the mark's
own growth costs.

**Design and plan written 2026-09-27, PR #617** — `docs/features/maquette-l17/DESIGN.md`, `plan/INDEX.md` (19 phases, mean ≈ 10.9); eight open questions.

#### L18 — §17, accounts, rights and Plex identity · *depends on L15, L19, L22, L16, L17*

**Objective.** DOIT-12: the interface shows what THIS account can do, and what it cannot is
visible and explained where hiding it would mislead. A rights MODEL first, then surfaces; the
sign-in gate redrawn for Plex SSO; the read-only role ABSORBED by the model — one authorisation
path (NE-DOIT-PAS-7). `GET /api/auth/me` diverges to carry per-account ACL rights, with roles as
default sets (D7, a demand).

**Amended 2026-09-27** (organisation rulings 20–23; round 8/9/10; F49). **Rights belong to ROLES,
never directly to an account**: an account holds one role, and a role's rights are configuration
(Comptes) — not the three-role-plus-two-options table dictated 2026-08-30, which now names only
the DEFAULT seed values (Household member, Plex guest), not the mechanism. Two roles are the
system's, indelible: Default (every new account's; its rights are configurable) and Admin (no
rights list — it bypasses the ACL entirely, including rights created later). A requester on every
acquisition MAY BE SEVERAL, each with per-requester settings; SSO added, not substituted, with
e-mail linking and a password right (`auth.password`) rather than a hardcoded Operator check; a
rights-less Plex user is a Default-only account, admitted read-only on the library by
construction, not a distinct mechanism; the Acquisition section absent for an account holding
neither `acquisition.request` nor `.see.others`; the staging ceiling generalised to a per-instance
list of forbidden writes (preprod). **No blocking note remains; all seven of the first drawing's
open questions, plus L17's OPEN 1, are ruled** (`docs/features/maquette-l18/DESIGN.md` § 7.2). The
backend's share is `docs/reference/backend-demands-architecture.md` § 2–3.

**Where it lives (invariant 10).** `features/account/` for the model and the surfaces. **The gate
is `app/entry.ts` plus `index.html`'s `login:markup` region, extracted by `serve.py`** — there is
no `app/sign-in.tsx` and there never was (F49); L18 edits the drawer's ENTRIES and the header
avatar's identity, never a drawer "identity block" (that block is the host's served identity,
`lib/served-identity.ts`, untouched by this lot). **L18 is NOT the only lot after L15 to edit frame
code** (F49 corrects the claim this entry used to make): L22 and L16 both edit `app/` first (the
tab bar, the drawer's badges, the navigation table's rows); L18 re-reads what they left rather than
opening untouched frame code.

**Done when.** A right is proved on BOTH sides and separately (§17 « Ce que cela impose à la
preuve »): the action absent from the surface for the account without it, the call refused for
one that forces it; the map's DOIT-12 and DOIT-14 rows read `served` with that rule; the read-only
role has no path of its own left; the media sheet's cross-seed block (§19, taken over from L17's
own held design) is gated on the same model.

**Design and plan written 2026-09-27, PR #618; amended 2026-09-27, same PR** —
`docs/features/maquette-l18/DESIGN.md`, `plan/INDEX.md` (36 phases, mean ≈ 12.47, cut in two at
phase 20); no open question remains.

#### L23 — §19 point 5, upload to a tracker · *depends on L17, L18*

**Objective.** § 19 point 5, dictated 2026-09-27: the application MAY create a torrent from a
medium's own files and publish it on a tracker, to open a cross-seed where the engine's own search
found none; a failure of the creation or the publication is a cross-seed failure, counted as such.
Drawn AHEAD of its own turn (round 8 Q18 = B), so the operator answers its own five open questions —
what may be uploaded, to which trackers, what a tracker's own rules require, what a failed or
refused publication leaves behind, how the ratio counts an uploaded torrent — before an implementer
has to guess. **A sixth question the brief itself posed, who holds the upload right by default, is
NOT among them**: organisation ruling 21 makes a right's default holder configuration (Comptes),
never a design choice, so the design draws the right's own name (`trackers.upload`, distinct from
`trackers.control`) and a proposed starting value instead of asking. **No blocking note is lifted
here**: unlike L16, L17 and L18, this lot's own design is published WHILE its note is still on, and
no phase of its plan opens until the five questions are ruled.

**Where it lives (invariant 10).** `features/trackers/` extended, once more — the SAME per-pair
mark L17 draws on the Torrents tab's origin row (`features/trackers/torrents-tab.tsx`) gains a
second act beside « Chercher un cross-seed », on the SAME three eligible states; L17's own closed
reason set gains the two codes its reserved slot was named for (`creation_failed`,
`publish_failed`), joining the SAME counted family as `inject_failed` and `obligation_write_failed`.
No new page, no new tab, no new address.

**Done when.** The two new codes are declared in the contract and sentenced in `fr.json`, never
drawn as a bare code; the gesture is offered only where nothing already cross-seeds and absent for
an account without `trackers.upload`; the Trackers badge's cross-seed term already counts both
codes with no new summed component (L17's own `R-L17-g`, re-aimed, not re-derived); the two engine
events already claimed by `features/trackers/live.ts` also move on an upload's own outcome, never a
third event; the five open questions are ruled, each amended into the design in one line.

**Design and plan written 2026-09-27** — `docs/features/maquette-l23/DESIGN.md`, `plan/INDEX.md` (9
phases, mean ≈ 7.8); five open questions, none chosen — the design states each one's two readings and
their cost, and no phase depending on one opens before the operator rules it.

#### L24 — the orphans, what no lot draws · *depends on L22, L20, L16, L18*

**Objective.** What the mission of 2026-08-19 says must be redrawn and no lot names: production's « Décisions » tab
(the journal of every decision, every state), Contrôle's two panels — « Santé », measured drawn in substance on
Système (R67) save each section saying its own read failed, and « Activité scraping », read per medium on the card —
the former production addresses `/control`, `/pipeline` and their siblings, which reach the maquette on the day of
the switchover; the seven owed halves of the map's `partly` rows whose owner has merged (DOIT-1, 5, 7, 9, 11 and
NE-DOIT-PAS-1 — L19; NE-DOIT-PAS-6 — L15); and DOIT-9's desktop half (« pleinement fonctionnel »). One surface for
DOIT-7 (« Corriger », a doubted match sent to arbitration, `enqueue`), the rest proofs.

**Ruled by the operator on 2026-09-29, the six open questions of its design.** OPEN 1 = C: a settled decision lives
on its medium's card — no « Décisions » screen, no global list, nothing on Système; pending decisions stay « À
traiter » cards. OPEN 2 = A: a filling disk and an index anomaly count in the menu's Système badge. OPEN 3 = A: no
global « en ce moment », the activity is read on each card. OPEN 4 = A: `/medias`, `/systeme`, `/controle` answer the
not-found page. OPEN 5 = B: « enrichi » unfolds on the journey sheet. OPEN 6 = A: the desktop half is a proof only;
the desktop adaptation is the milestone after the drawn lots.

**Where it lives (invariant 10).** `features/acquisition/` (the decision block of the journey sheet with its
« Corriger », and the unfolded « enrichi »); `features/media/` (the same block on the Médiathèque sheet);
`features/system/` (the failed sections, and the badge's two terms); a table of former addresses in `lib/`, beside
`lib/addresses.ts` (395 non-blank lines of 400), read by `destinationOf` before the not-found fall. No new page and no
new screen address.

**Done when.** Every production route answers a maquette page, a named successor or — for the three French aliases —
the not-found page; a settled decision reads on its medium's journey sheet and Médiathèque sheet — what was chosen,
among how many candidates, by whom, when, with « Corriger »; a Système section whose read failed says so, and a
filling disk counts in the badge; « Corriger » on a medium the engine identified alone arrives with candidates; the
seven rows' owed halves are proved by a rule each, and their new reading is proposed to the operator; every named
state holds at a desktop width, the galleries widening; the three questions the rulings raised (OPEN 7–9) are ruled,
each amended into the design in one line.

**Design and plan written 2026-09-29, on `e65130ab1`; re-cut the same day on the six rulings, on `77e7b8436`; amended
a second time, same day, on the operator's second round** (`docs/features/maquette-l24/rulings-2026-09-29.md`) —
`docs/features/maquette-l24/DESIGN.md`, `plan/INDEX.md` (20 phases, 151 points, mean ≈ 7.6); the three open questions
the rulings raised (OPEN 7–9) are now ALL RULED = A, plus the no-backward-compatibility PRINCIPLE (OPEN 9), which
kills S4's redirect table and its five states. The version before the rulings is
`docs/features/maquette-l24/DESIGN.md@e6d63bffe`.

### Phase 6 — The finish

#### L13 — The engine's residue · *depends on L07, L09, L12, L15, L19*

**Objective.** What did not die by subtraction, measured by L10-ter on 2026-08-29 rather than
listed from memory: the ladder's HANDLER (`onEngineBack`, `unwindLayer`, `hideLayers`,
`__closeLayers` and **`switchPageFromLayer`**, which is the one B-275 and B-290 both name as their
cause — it REPLACES a layer's entry rather than pushing over it — `docs/reference/frame-model.md` § 2 Part 4, to
`app/layers.ts`), the document-level delegation's
FRAME verbs, the boot handshake (`__startEngine`), the engine-side seams (`__address`, `__bridge`,
`__panel`, `__screens`, `__store`), the dead `#screen` layer with its three readers in the engine (and eight more in the harness — L13's design § 4.5, measured 2026-09-13) and the
mount-node placement that rests on it (B-232), `frontend/maquette/design/refonte.html@60530dbd8`
(deleted at L13a) and R72's renegotiation,
`legacy.css` and its guard, `__go`'s driving (which moves into a harness module of its own — it
is the harness's, not the product's), and whatever fixture families L19 could not kill.

**Re-read against the model by L10-ter (2026-08-29): RE-CUT.** « `/login` and the splash as
components » left this lot for L15 — they are the frame's entry (Part 9) and §17 redraws the gate,
which cannot happen while the gate is engine code. « The sixty fixture families … belong to
surfaces the ENGINE still draws » was wrong in its reason: their readers are PRODUCERS, and L19
owns them; this lot inherits only what L19 measures it could not remove.

**Done when.** `legacy.js` no longer exists; no PRODUCT code reads a `window.__` seam — the
harness's driving seams (`__go`, `__states`, `__queries`, `__relay`, `__mocks`) live in a harness
module and die at switchover with `harness.css`; the suite is green at unchanged hold counts; the
oracle is green.

**Two inheritances written in here by L19, ratified by the operator on 2026-09-05** (an
addition, not an edit of the sentence above).

- **The nine fixture families L19 measured it could not kill** — 9 declarations over 100 lines,
  26 375 lines, unchanged across that wave. They survived because a producer was never their last
  reader: they sit behind `sheetFor`, `allSettings`, `cardHTML`, `tileHTML` and `posterBox`, so
  they die with the DRAWING, and the drawing is this lot's. The measurement and its method are in
  L19's entry.
- **The delegation's surface-opening verbs** — `data-mediasheet`, `data-journey`, `data-resolve`,
  `data-releases`, `data-profile`. The objective above gives this lot « the document-level
  delegation's FRAME verbs »; these five are not the frame's, and they move with the delegation
  rather than with the producers that emit them, because what they do is open a surface.

**Done when**, for both, and it is written as a command because the two bullets above are not
ones: `python3 scripts/check-frontend-boundaries.py --arm size` no longer lists `engine/legacy.js`
in `GRANDFATHERED` at all — the file is gone, which is this lot's own first clause, and nine
declarations of 26 375 lines inside a file that does not exist is zero by construction; and
`grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)"
frontend/maquette/design/src/engine/legacy.js` reads **0**, which is L21's own addendum written the
same way.

**Carried here by L12, 2026-09-01 — B-290, the ladder's two shapes.** A layer closed inside a
navigation's commit keeps its history entry, so Back from a media screen opened that way crosses TWO
entries where every sibling action crosses one. The outcome is the same and the mechanism is not,
and a ladder with two shapes for one gesture is a ladder nobody can reason about. **Done when** the
arbitration is written, the two shapes are one, and a rule COUNTS the entries crossed on the way
back — the five ladder rules count entries going FORWARD and none counts pops.

**Carried here by L12, 2026-08-31 — the panel's RETURN, and B-275.** Arriving at a media screen
from an open panel is drawn: the panel is captured leaving and its snapshot slides down
(`::view-transition-old(leaving-panel)`). The mirror is not, and cannot be from outside this lot.
Back lands on the list with the panel shut — measured on 2026-09-01 — so
`::view-transition-new(leaving-panel)` had no subject and was removed rather than left waiting.
Reopening a panel on a backward step is the ladder's HANDLER, named at the head of this lot, and
the panel's own history entry is what decides it. **Done when** Back from a media screen reopens
the panel over the list (§16, B-275) and the reverse of `panel-down` is written with a rule that
falls when it does not play.

**Carried here by L09, 2026-08-28 — the sixty fixture families it could not kill.** L09's « Done
when » says each surface's share of the fixture dies with it (D5). Twenty-one families died and
`legacy.js` lost 1 814 lines; **sixty remain**, and they belong to surfaces the ENGINE still draws —
their literals cannot leave before their markup does. The wave declared the gap plainly and it is
recorded here rather than in its session report, because a deferral that lives in a squashed pull
request body stops existing for the next reader. **Done when** those sixty die with the producers
that read them, which is this lot's subject. **No earlier wave can take it**: unlike the fragment
above, this one is not separable from the engine's death.

**Carried here by L07, 2026-08-25 — the prototype fragment, and R72's renegotiation.** L07 emptied
`frontend/maquette/design/refonte.html@60530dbd8` of every style rule and did **not** delete it. Two reasons,
both recorded in that wave's `plan/phase-16-the-scaffolding-dies.md`: the file now carries the
wave's **conversion ledger** — one entry per region, saying where its rules went and why — and a
third of those entries name `src/styles/legacy.css`, whose death is this lot's; and **R72's hold
(a) is the verbatim injection of that file**, so removing it retires a hold, which is a rule
renegotiation recorded in `regions.json` rather than a file deletion. Twelve live readers name the path — **sixteen on 2026-09-13** (L13's design § 7: `tests/scripts/test_build_identity.py` and `i18n/fr.json:14` joined the fourteen a `grep` of the path literal finds). **Done when** the fragment is gone, R72 is renegotiated with its two surviving holds
mutation-tested, and the ledger has a home that outlives it. **Any earlier wave may take it** —
nothing depends on waiting — provided it carries both, and folds neither into a conversion commit.
**Done, at L13a** (`e2f510a8b`, `56da59aee`): the file is deleted, R72 keeps its two surviving
holds mutation-tested, and `residue.py`'s reader half moved to `harness/factories.py` (ruling 59).

**L13 is LANDED, COMPLETE** — its four squashes: L13a (PR #596, version 0.98.92), L13b (PR #601,
version 0.98.94), L13r (squash `08400a22a`, PR #605, version 0.98.96), L13c (squash `763f15cf9`,
PR #607, version 0.98.98, merged 2026-09-16).

### After the drawn lots

#### Desktop adaptation of the screens — a milestone, not a lot

**Dictated by the operator on 2026-09-29** (L24's OPEN 6), verbatim: « A dans un premier temps, mais prévoir une
phase final d'adaptation des écrans pour une utilisation plus agréable sur desktop. On en décidera des contours en
temps et en heure quand la maquette sera prête ». It follows every drawn lot, L24 included.

**« Contour à décider par l'opérateur quand la maquette sera prête. »**

**Contours decided by the operator on 2026-10-01** (DECIDED 1–7, `docs/features/maquette-desktop/DESIGN.md` § 3; dated in `operator-method.md` § 3). **Delivered** by the desktop milestone, `feat/maquette-desktop`, phases 1–10, rules R480–R488 and R413 re-aimed: the menu pinned beside a 760 px reading column and foldable to its icons, the confirmation 480 px, the panel a 440 px side sheet on the right, galleries by the tile's width and the deck a 2:3 poster, « + » and the bottom bars bounded to the column, the declared keys and the hover ground; the phone untouched below 64 rem.

---

## 5. (removed — the method is `docs/reference/method.md`)

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
| An entry animation replays AFTER the transition that already drew it | **L12** | CSS animations on a tree mounted under `startViewTransition` do not START until it ENDS — rendering is frozen for the capture — so an element-side entry replays over a snapshot showing the final state. Appear, flash, reappear. `:active-view-transition` cannot guard it: by the time the animation starts the transition is over and the selector no longer matches. **An entry has ONE OWNER**, and on a surface reached by a transition that owner is the transition |

**The oracle's silence over a BEHAVIOUR wave is evidence of nothing — a wave that writes
behaviour is held by rules or by nobody.** D8 states what the oracle proves; this trap is the
converse (measured at L11: zero divergence while four adversarial rounds found real defects under
a permanently green gate).

**And one that has not gone off yet, named because its shape is known**: a `var()` naming a token
nobody declared renders as nothing rather than failing — a landmine, not a crash. `scripts/check-css-tokens.py`
refuses it today, and R84 holds every publisher of a runtime token to being the only one.
