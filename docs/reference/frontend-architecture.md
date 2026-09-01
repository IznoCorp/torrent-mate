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
2. Come back here and find **the first lot that has not landed and whose dependencies all
   have**. That is the work. There is no other selection rule, and lots are not reordered for
   convenience.

   **The two halves live in two files on purpose, and that is what makes the rule reliable.** This
   file names the ORDER and the DEPENDENCIES — « *depends on L01, L05, L08* » — and it carries **no
   status**, because a status here is a second copy of something `IMPLEMENTATION.md` already owns
   as *the only state*. It was removed on 2026-08-28 after L09 merged and left `NOT STARTED` behind
   in this file, so this very rule elected the lot that had just landed. Adding the update to the
   post-merge list was the obvious answer and was refused on the evidence written in § 5: that list
   has been skipped three times out of four, and a sixth entry on a skipped list changes nothing.
   **A fact that exists once cannot go stale.**
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

**L10-ter — the application template** (operator, 2026-08-28). A design phase whose deliverable is
this file rather than any code: an inventory, computed rather than kept by hand, of every surface
the dying engine still draws; a model of the application's frame, part by part, each saying where it
lives under invariant 10; the PWA's « as close to a mobile application as possible » restated as
testable properties; and every lot from L11 to L14 re-read against that model and marked unchanged,
re-cut or replaced. **It is not a lot**: it writes no code, nothing schedules it, and § 0's
selection rule must not reach it. **Where and when its findings are converted is the phase's own to
decide**, and it may amend this file's lots and their order under § 7.1. Invariant 10 had been
binding since L09 with its subject — the frame — never modelled; **that was the debt, and this
phase paid it**: the frame is modelled in thirteen parts in `MODEL.md` § 2, as the paragraph below
records. Its definition and its agent's brief are `docs/features/maquette-l10-ter/`.

**It RAN on 2026-08-29, and this is what it decided** — its products are `SURVEY.md`, `MODEL.md`,
`QUESTIONS.md` under that folder and `docs/reference/product-intent-map.md`; the lots below are
the conversion. **The engine draws no page** (`PAGES_OF()` has eight entries, all `shellOwned`,
none with a `render`) and no screen (`#screen` is opened by nothing); what it still owns is **the
frame's chrome** — tab bar, drawer, dialog, toast, the selection slot, the popover layer — **the
entry** (splash, login, install, appearance), **the ladder's handler**, **all ten bottom-panel
producers** (zero on the React side), the Découvrir feed, and the 71 verbs of its click delegation.
Six of those are the frame; the frame is modelled in thirteen parts in `MODEL.md` § 2; and the
plan changes in five places: **L15 — the frame** is inserted before L11, because an offline shell
(L11) caches the chrome and the chrome must be the product's before it is cached, and a transition
between two layers (L12) needs both layers to be components; **L19 — the producers** is inserted
after L12, because D5's « surface by surface » was applied to the pages and never to the sheets'
content, so sixty fixture families had no owner (B-236); **L20 — the control station** is `/control` and `/pipeline`, which item 1 below kept
outside this file and the clause map (`product-intent-map.md`) could not leave ownerless — four
DOIT clauses hang on them, placed right after L19; **L16, L17, L18** are §18, §19 and §17,
placed after L20 so a new surface inherits the producer template rather than being converted
twice; and **L13 is re-cut** to what really did not die by subtraction. The
order is the file's order, below. Every lot from L11 to L14 carries what the model does to it,
under its own heading. **The where and the when are here; the progress is `IMPLEMENTATION.md`.**

**THREE LOTS WERE OWED AND ARE DECLARED — §17, §18 and §19 of the constitution.** The operator
dictated three sections on 2026-08-26 and no lot of this file answered any of them; on 2026-08-29
they were recorded here without a number, an order or a position, so § 0's rule could not reach
them, and **L10-ter placed them the same day: L16 (§18), L17 (§19), L18 (§17)**, in Phase 5 below,
after L20.
The measurement that scheduled them stays here as the record of what existed on the day:

| Section | What exists today | What it is asked for |
| --- | --- | --- |
| **§18 — the ratio is a resource, and it is steered** | `min_ratio` and `min_seed_time` per tracker, read at the grab and at the cross-seed; `obligations`, `stalled-grabs` and `downloads` all answering | **wire them** — nothing calls any of the three — plus one write, since setting a tracker's policy from the surface that shows its ratio exists in neither contract |
| **§19 — cross-seed is seen and decided** | 797 lines of engine injecting at third parties, emitting `CrossSeedInjected` and `CrossSeedRejected` | **everything**: zero routes in either contract, no event relayed to the stream. D7's case — the interface declares what it requires and the backend follows (§15) |
| **§17 — accounts, rights and Plex identity** | one role, one account, `GET /api/auth/me` saying nothing of rights | **a model, then surfaces.** None of the 53 declared operations concerns another user, a role or a permission. And one requirement on existing code: the read-only role must be ABSORBED by the rights model, never sit beside it — two authorisation paths is NE-DOIT-PAS-7 |

**Why they sit where they sit.** §17 and §19 need new screens, and a screen is the template
L10-ter defined (`MODEL.md` § 1: four kinds of surface, one table, a slot and a verb per layer).
Placing them before the template exists is drawing them twice — so they follow L15; and placing
them before the sheets' producers have a React template (L19) would draw §18's per-tracker panel
in the engine's style, so they follow L19 too. The order §18 → §19 → §17 stands — cheapest first,
largest last — and one measured reason is added: §19 is « the direct continuation of §18 »
(the constitution's own words) and extends the tracker surface L16 draws, so L17 depends on L16.

**One thing that could not wait, and it is why this paragraph exists at all.**
`frontend-backend-demands.md` § 4 lists `obligations` among the operations « the switchover MAY
retire », and nothing in that list distinguishes an operation the new design outgrew from one it
has not reached yet. **Retiring `obligations` would have retired §18's subject.** The case is real
and it would have gone the wrong way, which is the verdict column B-142 asks for.

**And B-142 is the reason all four were invisible.** Three instruments measure this interface —
`IMPLEMENTATION.md` § THE OBJECTIVE, the demands register, `audit_design_coverage.py` — and **all
three compare the interface to what already exists**: pages against pages, the maquette against the
running backend, design documents against tests. **None reads `product-intent.md`**, the only
document saying what the product must BE. A capability the constitution requires, that neither the
maquette nor the backend has, is invisible to every gate here. Without it, the next section the
operator dictates is invisible the same way — and three were dictated in one day.

**Its mapping is written and its instrument is placed** (2026-08-29). The arm needs a declared
mapping from each DOIT clause to the surface that serves it, and **a mapping is a design decision,
not a grep** — so L10-ter wrote it: `docs/reference/product-intent-map.md`, one row per DOIT and
NE-DOIT-PAS clause, a verdict, a proof or an owning lot — three rows `to draw`, five more with a
« to draw » half. The arm that reads it is specified in
`MODEL.md` § 4 and **built by L15**, the first lot after the phase — a phase forbidden to write a
guard does not write one, and a wave's arm gets a wave's adversarial review.

**Also named here and deliberately unscheduled — the SEMANTIC SCROLL INDEX** (operator,
2026-08-26). A list would offer an index shaped by its own sort: letters when sorted
alphabetically, month markers when sorted by date. It is **not a scrollbar** — D11 settles that
one — but a separate control, the shape a phone's fast-scroller has. It is written down so the
objective is not lost, and it is **not a lot**: nothing schedules it, and § 0's selection rule must
not reach it.

**Three things keep the door open, and they cost nothing now.** The list must expose its sort key
in an INDEXABLE form — first letter, month — in the DATA CONTRACT rather than in the markup, which
is L09's decision to make when it wires the library. The scroll container must stay one identified
element (`#port`, already true). And programmatic scrolling must have one path — which is a debt
today: **B-140** records that the mechanism knew one port out of two — L10 repaired that, so this
function is now the one path for HISTORY-driven scrolling, and an index that jumps to a letter
would write through it. **The clause is still not paid**: `app/focus.ts` writes `#port.scrollTop`
from the skip link, on the very element that function owns, and `ui/sheet.tsx` resets a panel's own
offset. ⚠ This sentence cited **B-104** until 2026-08-28, which is about the generated contract
types living under `mocks/` and has nothing to do with scrolling. The wrong number was copied out
of here into the repair's own comment — a mis-citation in a binding file propagates.

**The design risk, stated with the objective**: a control that both scrolls AND jumps teaches two
things in one object, and on a six-pixel-wide thumb the margin between « I am scrolling » and « I
jumped to M » is thin. Two functions, two objects — the bar stays a bar, the index appears when it
serves.

**Item 1 is a lot since 2026-08-29 — L20, the control station.** `/control` (8 panels) and
`/pipeline` (10 panels) were kept outside this file as « surfaces still to be drawn, blocked by
nothing ». The clause map could not leave them there: DOIT-1, DOIT-3, DOIT-5 and DOIT-6 each have
a half that only those pages serve, and a clause whose surface has no lot is a clause nobody
owes. They follow the existing method — drawn in the maquette first, named states, a rule that
bites — and where their panels land stays the operator's open UX question (`IMPLEMENTATION.md`),
written into L20 as its blocking note. **What this makes void**: « not blocked by any lot below »
— L20 depends on L15 and L19, so the standing freedom to draw those two pages at any moment is
withdrawn, deliberately: drawn before the producer template, they would be drawn twice. Whether
they wait behind the three constitution lots as well is the operator's (`QUESTIONS.md` Q9); the
plan places them before.

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

**Two more sheets shipped than this decision names — recorded by the steward's audit of L07,
2026-08-25.** « Three layers, and nowhere else » is the text; five stylesheets exist:

| Sheet | What it is | Standing |
| --- | --- | --- |
| `styles/theme.css` | the Tokens layer | D3, as written |
| `styles/base.css` | the Base layer | D3, as written |
| the surfaces' `variants.ts` | « everything else, in the component » | D3, as written |
| `styles/legacy.css` | the dying engine's residue, bounded and dated, dies with L13 | **arbitrated by the operator** in L07's `DESIGN.md` § 2, and held by `check-legacy-css-residue.py` |
| `styles/harness.css` | the phone frame — imported once, and the only sheet that never ships | **a departure from L07's letter**, taken in the wave and carried by its merge |

**Arbitrated by the operator, 2026-08-25: D3 is WIDENED, and the two are named as transitory.**
Three layers remain the target and the destination. Beside them, and only them, live two sheets
that exist to disappear, each carrying the date it dies. « Nowhere else » now means: no SIXTH
sheet, and no transitory sheet without its end named here.

The distinction that makes this a widening and not a dilution: a layer is where CSS is meant to
live; a transitory sheet is CSS that has not finished leaving. `legacy.css` is what the dying
engine still needs and it dies with **L13**; `harness.css` is the phone frame and it dies at
**switchover**. Neither may grow, and when their date arrives the absence is checked against this
paragraph.

**« Both are held by a guard » was half true, and the correction wave between L08 and L09 is what
read it.** `legacy.css` is held — `check-legacy-css-residue.py`, classes, declarations and rules,
at the ceiling. **`harness.css` is held by nothing at all**: no guard measures its size, its rule
count or its growth, and the only script that names it (`check-compositor-css.py`) names it to
EXCLUDE it. So the sentence read as a pair of held files when one of them was on trust — which is
the arm-less directive `CLAUDE.md` § Language warns about, one file over.

**And « may not grow » needs its one exception stated, because that wave grew it.** B-081 restored
the design-note pair — `.note { display: none }` and `:root.notes .note { display: block }` — which
L07 deleted with BLOCK 1 and which belongs to this sheet: the notes are the prototype's
annotations and they ship nowhere. **Restoring what was wrongly taken out of a sheet is not the
accumulation this decision forbids**; taking new work INTO it would be. Whoever writes the guard
this paragraph now admits is missing should measure from after that repair, not from before it.

**Why it is not cosmetic.** L13 removes `legacy.css` and the switchover removes `harness.css`.
Whoever reads D3 on that day must be able to tell that the three layers were always the target
and that two sheets were passing through — not that the decision was quietly ignored twice.

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

**Why, and this is a measurement rather than a preference.** `legacy.js` was 34 650 lines when
this was decided, of which **27 678 (79 %) are fixtures** — `SHEETS_RAW` alone is 20 538 lines of
episode catalogue — and the engine's actual code about **6 949 lines**. **Re-measured on
2026-08-29 (L10-ter)**: 33 449 lines, **33 026 non-blank**
(`grep -cve '^\s*$' frontend/maquette/design/src/engine/legacy.js`), of which **26 366** sit in
the **9** declarations over 100 lines the method below finds — L09's « sixty families » counts
every fixture constant whatever its size, which is a different figure and not this one.
<sub>method: bracket-match every `const X = [` / `const X = {` declaration and sum the spans over 100 lines</sub>
Most of that fixture stops existing when real data arrives. Killing the engine before the data
layer means facing 34 650 lines; killing it as surfaces convert means facing seven thousand,
in pieces, each with the oracle green.

**Measured again on 2026-08-29, at L10-ter, and the subtraction has a shape nobody had drawn.**
The engine draws no page and no screen any more; it still draws the FRAME (tab bar, drawer,
dialog, toast — `SURVEY.md` § 1.2) and still PRODUCES every sheet's content (ten `panel.open`
producers, zero on the React side) — which is why sixty fixture families outlived L09: their
readers are producers, not markup. « Surface by surface » therefore has two more passes to make,
and they are lots: **L15** for the frame's chrome and entry, **L19** for the producers. What stays
cross-cutting is smaller than this decision first said, and it is L13's.

**What is cross-cutting and does NOT strangle surface by surface**: the document-level event
delegation, the boot handshake, and the 254 top-level declarations republished on `window` for the
harness to drive through. **Navigation was on this list and is LIFTED**: L05 took the address
model out of the engine — `URL_DEFAULTS`, `urlFromState`, `stateFromUrl` and the `baseAddress`
plumbing — leaving it the navigation LOGIC (when to record an arrival, what the entry carries, how
a back unwinds the layers). `openScreen` went with them, having lost every caller. `__go` and the
named states remain the harness's own driving seam and belong to L13. The
delegation and the boot are L13's, which is the last lot of the engine's death. **`/login` and
the splash were on this list until 2026-08-29 and are L15's now** — they are the frame's entry
(`MODEL.md` § 2 Part 9), and §17 redraws the gate, which cannot happen while it is engine code.

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
reads the rectangle and the computed properties **of the element itself**. A `::before` or
`::after` that stops being painted changes neither, so the oracle stays green — correctly, by its
own contract. L07 phase 15 produced the lived example: a legibility gradient written across four
concatenated string literals was never generated, leaving hero text on the bare image, and
**R26 caught it** because R26 reads `getComputedStyle(element, "::after")`.

The oracle is not widened: the measurement count and the two machine-bound references stay as
they are. **A pseudo-element that carries a function is covered by a named rule instead** — that
is the contract, and a surface that relies on one without such a rule is the defect, not the
oracle.

**The same clause covers DESCENDANTS, and L15 produced the lived examples (2026-08-30).** A region
resolves to the nodes its selector names and the 19 properties are read on those nodes — never on a
child. Two defects the adversarial review of #528 found by eye were replayed by the steward with the
oracle green over both: `dialogParagraph` stripped of its colour, and `selectionAction` carrying
`bg-transparent` in its base (white on white under the light theme, contrast 1.00) — 167 divergences
before, 167 after, all on `shell/sheet-content`, in both cases
(`sed -i '' 's/ text-muted-foreground\"/\"/' frontend/maquette/design/src/ui/variants/frame.ts && make maquette-oracle`).
The oracle is still not widened: **a child node that carries a function is covered by a named rule**,
exactly as a pseudo-element is, and the two surfaces above are held by none today (B-252).

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
| **`onTouchStart` for pressed states** | **refuse** | it lights the pressed state when the finger is starting a SCROLL, so a list flickers as it is scrolled. `:active` is cancelled by the browser when the gesture becomes a scroll, which is the wanted behaviour, for free |
| **`@media (hover: hover)`** to keep hover off touch | **adopt** | the sticky-hover problem is real; this is its declarative remedy |

### D10 — The dying engine's CSS is a bounded residue with a date of death

**Decision.** The CSS the legacy engine still needs does not convert and does not disperse: it is
one file, `design/src/styles/legacy.css`, deliberately **unlayered** so it wins over
`@layer utilities` on the markup the engine draws. It may not grow, a guard
(`check-legacy-css-residue.py`) refuses any addition, and it dies with **L13**.

**Arbitrated by the operator on 2026-08-24**, during L07, under the name **D-L07-5**. Promoted
here on 2026-08-25 by the steward's audit, because the only definition of it lived in
`docs/archive/features/maquette-l07/DESIGN.md` — and `docs/archive/` is frozen history that is
never revised, so the sole justification for keeping a 2 470-line stylesheet alive could no
longer be corrected if its terms changed. `legacy.css`'s header cites **this** address.

**What it costs, and it is recorded rather than discovered.** Unlayered normal declarations beat
every cascade layer whatever the specificity — including on markup that COMPONENTS draw. B-067
found **seven** shared identity anchors carrying both a residue rule and a typed variant, so on
those elements a variant can be edited and change nothing on screen. **The guard that answers it
found sixteen** — the seven is the finding's tally, kept because it is what the register records,
and the measured count is below. The declarations are identical term
for term today and the oracle says so; what is not held is the day one drifts. **The guard that
cross-checks each variant against the rule shadowing it is arbitrated (operator, 2026-08-25)**,
and it dies with this decision.

**It is built, and it is `R80`** — `frontend/maquette/harness/residue.py`, in the per-phase
contracts tier. It pairs each residue selector with the typed variant wearing the same identity
anchor and compares `getComputedStyle` IN THE DOCUMENT, on two sibling probes, for exactly the
properties the residue declares — never as text, because `flex: 0 0 auto` and `flex-none` are one
value written twice and a guard carrying Tailwind's mapping by hand would be a table that rots.
**Sixteen pairs stand where the finding named seven.**

**Its own proof is that the oracle cannot supply one.** With `emptyNote()`'s `rounded-3` moved to
`rounded-2`, R80 falls naming the anchor and the term — « residue « 8px » vs variant « 6px » » —
while the oracle runs green over the same tree, 2 739 measurements, no divergence. That is B-067
demonstrated rather than asserted, and it is why this guard is not something the oracle could have
been widened into.

**It measures under BOTH motion preferences, and that is not thoroughness for its own sake.** Part
of the residue sits inside `@media (prefers-reduced-motion: no-preference)`; a utility carries no
such condition unless it is written `motion-safe:`. The two sides then agree to the character
under one preference and disagree under the other — which is how the hero's entrance was found
animating for a reader who had asked for no motion (B-076), against invariant 14, with the oracle
and the accessibility tier both green.

**What it does not stage is counted and named on every run**, not left to be discovered: the
selectors wearing an anchor no variant claims (the engine's own markup — the residue's whole
purpose); the qualifiers the ENGINE writes through `classList`, which no variant emits; and the
descendant pairs, whose one- and two-letter anchors collide across contexts — `.dcard .t` and
`.sechead .t` would both pair with `sectionTitle()` and only one of them is that variant. It holds
a FLOOR on the number of pairs found, because a pairing that found nothing would print « no
divergence » and mean « I compared nothing » — which a first version of it did.

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

    **Measured on 2026-08-26, outside comments**: `ui/` carries **one** domain word across 1 162
    lines, `lib/` carries them only in `addresses.ts` and in `engine-drawing.ts` (which dies with
    L13), and `app/` concentrates them in three files — `shell.tsx`, `page-host.tsx`,
    `reference.d.ts` — all three being the list of pages, which every framework has somewhere.
    **This invariant freezes a property that is already true; it does not ask for a refactor.**

    **Re-measured on 2026-08-27, at L09's close, and it MOVED — §7.1 makes saying so the wave's
    duty.** Two new files carry domain words, and one of them carries a great many:

    | File | Domain words | Why |
    | --- | ---: | --- |
    | `lib/queue.ts` | 169 | The staging and acquisition queue, shared by Arrivées and Acquisition. Invariant 7 is absolute — two features may not import each other — so a queue both read had nowhere else to go. |
    | `app/engine-data.ts` | 34 | What the dying engine reads with no component to ask for it: four addresses and ten family names. |
    | `app/history-bridge.ts` | 17 | A slice of `shell.tsx`, whose words came with it. |
    | `app/live-updates.ts` | 18 | L10. Six features named three times each — the import, the
      spread and the type. It names no EVENT and no KEY: which events refresh which data lives in
      `features/<domain>/live.ts`, with the domain. |

    **Re-measured again at L10's close, and it moved by 18 — §7.1 makes saying so the wave's
    duty.** `app/live-updates.ts` is one import per feature, which is the same species as
    `router-tree.tsx`'s one import per page: the frame naming its pages, the exception this
    invariant blesses by name. What would have been a violation is the file production has — a
    central map carrying forty event names and twenty query keys, belonging to no domain at all —
    and it is what D-L10-1 refuses. `app/connection-notice.tsx`, the other file L10 adds to `app/`,
    carries **zero**: it reads a condition and draws it, and could not name a media item.

    <sub>method: strip comments per line, count occurrences of the nine feature names in
    `app/live-updates.ts` and `app/connection-notice.tsx`. ⚠ The first attempt stripped `//.*`
    under `re.DOTALL`, which swallows the file from its first comment to the end, and reported
    **0** — a measurement that read nothing, in the wave that filed three entries about exactly
    that.</sub>

    **169 is not « one reviewed line », and calling it that would be the dishonest reading.**
    `lib/queue.ts` argues its own case in its header, and the case is sound — but what it really
    is, is the frame carrying a subject because the ONLY alternative available today was worse.
    Two arbitrations follow from it, and neither is this lot's to take: whether a shared domain
    module belongs in a `domain/` bucket of its own rather than in `lib/`, and whether B-100 (this
    invariant is unarmed) is worth arming now that there is something for an arm to refuse.
    Recorded here so the next wave decides it rather than inheriting it.

    **Its subject is MODELLED since 2026-08-29** — `docs/features/maquette-l10-ter/MODEL.md`
    § 2, thirteen parts, each saying where it lives under this invariant, what it owns and what it
    never knows. The invariant was binding for three lots before its subject had a definition;
    that debt is paid, and a fourteenth part is a hole in the model, said so in the wave that
    finds it.

    **Why it is not written for the extraction.** A frame that does not name its subject is easier
    to read, easier to test and easier to move between waves — that alone pays for it. Reusing it
    on another product is a consequence, never the justification, and the day a measure here can
    only be defended by that future is the day it has gone too far.

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
> would stay green. Evidence in `docs/archive/features/maquette-l01/DESIGN.md`),
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

#### L02 — Test anchors move to `data-*` · *depends on L01*

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

#### L03 — Accessibility · *depended on L01*

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

#### L04 — Boundaries and the tree · *depended on L01*

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

#### L05 — Routing · *depended on L01, L04*

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

#### L06 — The scale · *depended on L01*

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

#### L07 — Tailwind and CVA, surface by surface · *depended on L02, L04, L06*

**Objective.** D2 in force. Each surface converts on its own, oracle green at every step.

**Why surface by surface.** A single-shot conversion of 4 043 lines produces one unreviewable
diff and one unattributable failure.

**BLOCK 1 must not travel.** The prototype's stylesheet is split in two on purpose: BLOCK 1 is
the phone frame, the demo bars and the design notes — scaffolding that stops existing at
switchover — and BLOCK 2 is the application's own CSS. Converting BLOCK 1 into components would
carry the scaffolding into the product. It is deleted, not converted, and its disappearance is
part of this lot's proof rather than a later tidy-up.

**What L07 actually did, recorded 2026-08-25 after the lot landed.** BLOCK 1 was **separated, not
deleted**: it is `design/src/styles/harness.css`, imported once and by nothing that ships. The
wave's reason, and it holds: the phone frame is the frame inside which every measurement in this
repository is taken, so the instrument that proves the rest of the lot cannot be what the lot
destroys on its way out. The paragraph above is kept as written — **the intent is unchanged, and
the sheet still must not travel** — but « deleted » is now « separated and provably unshipped »,
and the proof is the single import rather than the absence. `refonte.html` likewise survives, and
its removal is carried into L13 with R72's renegotiation, above.

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

This phase is the bulk of the remaining work. The pages are finished; the application is not.
Measured when the phase opened: 11 API modules against 0, 65 network calls against 1, 24 WebSocket
files against 0, a service worker against none. **L08 moves the second of those** — the maquette
declares 53 operations of its own and answers every one of them from a mock layer — and moves
none of the others: no surface is wired to any of it, which is L09's.
<sub>commands in `IMPLEMENTATION.md` § THE OBJECTIVE</sub>

#### L08 — The data contract and the mocks · *depended on L04*

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

**Landed** — PR **#503**, merged 2026-08-26, version 0.98.42, squash `ce1d7b5a`. Design and plan
in `docs/archive/features/maquette-l08/`. The
contract is `frontend/maquette/contract/openapi.json`: 49 paths, 53 operations, 43 schemas, its
TypeScript types generated and held against drift two ways. 46 seeds, built from `legacy.js` by a declared
projection and held by `scripts/check-mock-seeds.py` — seven arms, each of which says what it
does NOT read before it says what it does. The demands are COMPUTED, not written
(`docs/reference/frontend-backend-demands.md`, `scripts/compare-contracts.py --check`).

**The oracle reads 0 divergence over 2 739 measurements with the layer live**, which is this
lot's own proof: it displays nothing. The oracle is a LOCAL gate (§ 5), so that reading is the
operator's machine's and is not reproducible on a runner.

**Two limits are recorded rather than glossed.** The seam replaces the network call in process, so
what a real one does with caching, redirects and abort signals is not proved here (D-L08-2's
stated cost). And the layer LIFTS OUT, measured on demand: 2 807 428 bytes with it built in,
1 571 705 with the flag off.

**What it cost to get right, and it is the reason the arms are what they are.** Two families
shipped UNPROJECTED while the builder reported success and « lossless » — a leaf-value check
cannot see a projection that never ran. The contract was wrong about its own data in five places,
each found by validating the seeds against it. `serie` is a show's RUN STATUS and was renamed
`series`, which no automatic check could have caught. And the extractor's own reader judged
`const settle = afterUnwind` a literal, because it walked an initializer's children and never the
initializer.

#### L09 — The data layer, surface by surface · *depended on L01, L05, L08*

**Objective.** Server state in its query cache, mutations with their optimistic paths and their
rollbacks, the two state-ownership invariants (4 and 5) in force. Each surface takes its data and **its share of the
fixture dies with it** (D5). Surfaces are walked in the order L07 fixed.

**Its proof comes from L08.** The mocks are seeded from the fixtures they
replace — 46 of them, held byte for byte against `legacy.js` by
`scripts/check-mock-seeds.py --arm correspondence` — so a wired surface renders what it rendered
before, and the oracle holds the wiring at zero divergence. Three things L08 built are this lot's
to use: `window.__mocks.reset()`, so a named state is reached from a known store; the scenario
surface, so a surface's loading and error states are driven by the same failure the interface will
really meet; and `window.__mocks.quiet()`, which `oracle.py`'s settle already reads — it resolves
immediately today because nothing fetches, and it is what stops a wired surface being measured
mid-flight. If a surface cannot be wired at zero divergence, the difference is understood and
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

#### L10 — The live relay · *depends on L09*

**Objective.** The event stream, and the cache invalidations it drives.


**Where it lives (invariant 10).** A relay, its reconnection policy and its replay window are the application's SHAPE, not its subject: they belong in `lib/`, never under a `features/` folder because that is the surface the work was tested against.
**Done when.** A server event refreshes exactly what it should and nothing else; reconnection and
loss are handled visibly; no polling remains where an event exists.

#### L15 — The frame · *depends on L07, L09*

**Objective.** The engine draws nothing of the frame, and the template exists: one navigation
table, four kinds of surface, a slot and a verb for every layer. Declared by L10-ter on
2026-08-29 — `docs/features/maquette-l10-ter/MODEL.md` is its design, part by part, and
`SURVEY.md` § 1.2 is its inventory. It is numbered after L14 and placed before L11 because
**this file's order decides, not the number** (§ 5), and renumbering moves citations (B-103).

**Why before L11 and L12, measured.** L11's offline shell CACHES the chrome, and the chrome is the
engine's today — an offline shell built first would cache `legacy.js`, 33 026 non-blank lines of
which 26 366 are fixtures, and be rebuilt when the chrome moved. L12's transition between two
layers needs both layers to be components; the drawer and the dialog are engine markup.

**What it converts** — six surfaces, the entry, and the table:

| Part (`MODEL.md` § 2) | What moves | From | To |
| --- | --- | --- | --- |
| 5 — the table | `PAGES_OF` and `NAVIGATION` (engine), `PAGES` (page host), `PAGE_PATHS` (addresses) — **four copies of one fact** | the engine, twice | **one** `app/navigation.ts`: id · path · component · label key · icon · group · in the bar · action button · `badge()` — invariant 10's third exception, and the engine holds no copy |
| 6 — the chrome | the tab bar (`renderNav`, rebuilt on every `render()` — B-231), the drawer's chrome, the FAB's toggle, the selection **slot** | engine `innerHTML` | `app/tab-bar.tsx`, `app/drawer.tsx`, `app/action-button.tsx`, `app/bottom-slot.tsx`; the library's selection bar becomes its own component portalled into the slot |
| 7 — the layers | the dialog (`openDlg(html)`, 2 producers — `grep -n "openDlg(" legacy.js`, minus the definition), the toast (34 callers — 29 `toast(`, 5 `toastUndo(`, definitions subtracted), the popover LAYER | engine `innerHTML` | `ui/dialog.tsx`, `ui/toast.tsx`, `ui/popover.tsx` behind DESCRIPTORS on the seam the sheet already uses (`app/panel-host.ts` is the precedent: facts cross, markup is the component's); **the scrim gets one owner**; **the dialog gets its rung** on the ladder (B-229, D1's third tier) and its place in the z-order (B-237: it paints under the tab bar) |
| 9 — the entry | splash, login gate, install proposal, appearance (`legacy.js:9678–9915`, `10116`) | engine logic over static markup | `app/splash.ts`, `app/sign-in.tsx`, `app/install.ts`, `app/appearance.ts`; `theme-color` follows the theme (B-233); the viewport fallback that re-adds `user-scalable=no` is removed (B-230) |

**One kind of change, and how it stays one.** The conversions above are DRAWING moves, proved by
the oracle at zero divergence — the sheet's own conversion (SP4b) is the precedent. **Six things
in this lot are BEHAVIOUR changes, and each lands in its own commit with its own rule, never inside
a conversion commit**: the dialog's rung on the ladder (B-229), the dialog's z-order (B-237),
`theme-color` following the theme (B-233), the removal of the viewport fallback (B-230), **the sheet
covering the tab bar (B-248, P31 — dictated by the operator on 2026-08-30: a bottom layer rises
from the screen's bottom edge OVER the bar, which is not seen while the layer is open; the oracle
WILL diverge on the sheet's open states and every divergence is named as this decision's)**, and **the flash between a sheet
action and the page it opens (B-249, reported by the operator the same day)**. The
ladder's HANDLER (`onEngineBack`, `unwindLayer`, `hideLayers`, `__closeLayers`) stays in the
engine until L13 — the drawer and the dialog REGISTER with it through the seam, exactly as the
sheet does through `window.__panel`. Every engine edit is a subtraction or a call through a seam;
a line added to the engine that is neither is the defect.

**What it must not do.** Extend a grandfathered file — `features/acquisition/page.tsx` and
`features/library/page.tsx` are two of L14's four, and the selection bar and the Découvrir
containers live beside them in new files. Draw a desktop rail: **Q1 was answered on 2026-08-30 —
the drawer alone, at every width, and not frozen**; a rail is drawn only if real use asks for it. Move a producer (L19). Move the handler (L13). Draw a
pixel differently: the rendering of every part is validated (mission of 2026-08-19).

**It builds B-142's instrument.** The map is `docs/reference/product-intent-map.md`; the arm is
`MODEL.md` § 4 — it refuses a clause with no row, a row naming a surface absent from the tree, a
« to draw » row naming no lot, a « served » row naming no proof; it prints one line per clause and
never a count alone; it runs in the contracts tier, over the `docs` filter, and its mutation is
seen red before it merges.

**Where it lives (invariant 10).** `app/` for hosts, chrome and entry; `ui/` for primitives;
`lib/` for nothing new. The table is the exception the invariant names; a badge is a FUNCTION the
row points at, exported by the feature, so the frame names the feature once and its counters never.

**Done when.** The inventory command (`SURVEY.md` § 1.1) lists only the Découvrir feed, the
popover's content and the harness panel — nothing of the frame; `#nav`, `#drawer`, `#dlg` and
`#toast` are React-rendered at their ids; one navigation table, and `grep -n "PAGES_OF\|NAVIGATION"
legacy.js` lists the seam's read sites only — no declaration of either; P1, P2, P3's dialog rung, P14's landmine and P21
(`MODEL.md` § 3) are each held by a rule seen to bite; the B-142 arm is in the contracts tier with
its mutation; the oracle is green at every step or its divergences are accepted with reasons; the
hold counts are unchanged; the accessibility tier reads zero over every named state.

#### L11 — Offline and PWA · *depends on L09, L15*

**Objective.** Service worker, offline shell, queued mutations that depart on reconnection, and
the platform entry points a media application owes — receiving a shared link, and being the
handler its links deserve.


**Where it lives (invariant 10).** The service worker, the offline shell, the mutation queue and the install entry points are frame, not feature. They live in `app/` or `lib/`. A service worker under `features/` is the single most likely misplacement of this whole plan, because the page one happens to be testing is not the thing being built.

**Re-read against the model by L10-ter (2026-08-29): UNCHANGED in objective, RE-CUT in its
dependencies and its proof.** It now depends on L15, for the reason written there. Its design is
`MODEL.md` § 2 Part 13 — what the worker caches (the shell: document, bundles, icons, fonts; never
`/api/*` nor the stream), the update discipline production already proved (`web-ui.md` § PWA:
`registerType: 'prompt'`, a check on load, on visibility and every 15 minutes, one reload) — **with
the signal and the ORDER changed by L11**: `/build.json` against a build identity baked into the
bundle, never `/api/version`, because the mock layer answers only the contract and a poll there
could not fail; and the reload following `controllerchange` rather than the poll, because
`registration.update()` resolves when a worker begins installing and reading `waiting` straight
after it swaps nothing (B-262), and a queue that holds opaque envelopes a feature's
`queries.ts` enqueues. Its « Done when » is made measurable by **P7, P8 and P9** of `MODEL.md`
§ 3, and the entry points it names are the operator's **Q4** (`QUESTIONS.md`): `share_target`
landing on `/add`, `launch_handler`, `handle_links` — recommended all three, decided by nobody yet.
**Done when.** The application opens and reads offline (P7); a mutation issued offline departs on
reconnection, exactly once (P8); the entry points Q4 selects are declared in the manifest and
reached by a rule; and installation and its entry points are exercised on a real device.

**Two of those clauses were written naming an instrument, and L11 disproved one and could not use
the other — recorded here because a plan that keeps prescribing a disproved instrument sends the
next reader to it.** `context.set_offline` does NOT reach the requests a service worker makes in
Chromium, so P7 measured that way is green because the NETWORK answered; R105 raises its own scratch
server and stops it. « L10's fake transport » is the relay's, and a mutation is not a relay event —
P8 runs on the mock layer's own `setOffline`, which rejects the way an outage does rather than
answering a status. **And the device clause is the one L11 did NOT satisfy**: the operating-system
half of `share_target`, the standalone reading and P30's runtime half are all device-only,
written down and dated rather than claimed (`REPORT.md`). It is L11's declared deferral, not a
clause quietly dropped. **Q4 was answered on 2026-08-30: all
three** — `share_target` landing on `/add` pre-filled, `launch_handler`, `handle_links` — and a
principle with it: **every entry point the platform offers an installed application is declared,
unless a written reason says why not.** « La meilleure intégration possible » is the operator's
phrase and the lot's bar.

### Phase 4 — Native interaction

#### L12 — Native interaction · *depends on L05, L07, L15*

**Objective.** View transitions, gestures, mobile geometry, and the performance floor beneath
them. D9 governs every library question in this lot; its verdict table is the answer, not a
starting point for a new argument.

**Transitions.** Declared, through the platform's own view transitions. Not scripted.

**The shared element that carried a poster from a card into its sheet was BUILT AND WITHDRAWN**
(operator, 2026-08-31): he watched it on his own phone and declined it. What ships instead is
transition A, which shares nothing — the arriving fanart fades while the body rises — on the
reasoning `MODEL.md`'s P6 row already carried: there is nothing honest to share between a 2:3
poster and a wide banner, and morphing one into the other is an animation pretending two pictures
are one. The sentence is kept in this form, rather than deleted, so no later reader takes the
absence for an oversight.

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
on focus. **The focus-zoom half is PAID and held — measured on 2026-08-31, not read.** L07 (#494,
2026-08-25) put every field on `text-6` = 16 px, and R83 (`harness/type_scale.py`) refuses a focused
field under 16 px: `MODEL.md` P13 reads true. This paragraph carried, until the steward's L11 audit,
three field sizes (13, 14 and 12 px) and a command reading `refonte.html` — which has held no style
rule since L07 — so it was stale six days before L11 opened, and the wave that paid the debt did not
correct the plan that still charged it (§ 7.1's duty). What the episode taught still stands:
`maximum-scale=1, user-scalable=no` had MASKED the defect rather than fixed it, L03 was right to
remove them, and `scripts/check-viewport-directives.py` keeps both out of the tree.
Then: contained overscroll, the virtual keyboard resizing content rather than the viewport, scroll restored per
history entry.

**The performance floor**, because none of the above survives a slow surface. The library holds
1 861 titles, so no long list renders unvirtualised. Images that a transition carries are decoded
before they are needed — the same asynchronous decode that makes the oracle flicker makes a
shared-element transition tear.


**Where it lives (invariant 10).** A gesture arbitration is vocabulary: it belongs to `ui/` or `lib/`. What stays feature-local is which gesture a given surface offers, never how a press, a drag and a scroll are told apart.

**It also owes B-252's two rules (operator, 2026-08-30)**: one reading `color` of the dialog's
paragraph under both themes, one reading the danger action's contrast under `data-theme="light"`
— the two child-node defects D8's descendants clause records.

**Re-read against the model by L10-ter (2026-08-29): UNCHANGED in objective, RE-CUT in what it
may assume.** It depends on L15 now: a view transition between the drawer, a dialog and a page
needs each of them to be a component, and they are engine markup until L15. The arbitration moves
to `lib/` here; **each surface's USE of it moves with its producer in L19**, so this lot converts
the vocabulary and the React surfaces (the sheet's drag, the screens) and leaves the deck's and
the rows' engine-side callers to L19. Its properties are **P5, P11, P16, P17, P20, P24, P25, P26 and P29** of
`MODEL.md` § 3; **B-234** (no `interactive-widget` on the viewport meta, so the keyboard resizes
the viewport by default) is its. The interaction budget is a device-only protocol, written and
dated — not a gate (`MODEL.md` § 3.1).
**Done when.** Every transition is declared rather than scripted, the one named spring excepted;
every gesture is proved against a real pointer stream **and** against a real mouse; reduced motion
is defined for each of them (the reduced-motion invariant); the feedback seam has exactly one call site; no
unvirtualised long list remains; and the interaction budget is measured on a real device, not in
a headless browser.

### Phase 5 — The producers, and what the constitution owes

Declared by L10-ter on 2026-08-29, ordered by the operator's answers of 2026-08-30. L14 first
(pulled forward, Q3); then D5 applied to the sheets — the pass « surface by surface » never made;
then the global levers; then the constitution's three, each drawn in the maquette first like every
surface — L16 and L17 still blocked on a dictated answer, L18 no longer.

#### L14 — The surfaces that outgrew their file · *depends on L07, L09*

**Objective.** The four feature surfaces that sit over the 400-line hard ceiling come back under
it, by decomposition: `features/acquisition/page.tsx` (756), `features/media/media-screen.tsx`
(796), `features/library/page.tsx` (613), `features/arrivals/resolution-screen.tsx` (430).

**Why it exists as a lot rather than as a line in someone else's.** It was one, and the promise
expired unpaid. Those four files carried the label « L09 — the data layer takes it » in
`check-frontend-boundaries.py`'s grandfather list, and L09 landed having reduced the largest of
them by **thirteen lines out of the three hundred and fifty-six it owed**. The premise was simply
wrong: what makes those files long is not the fetching L09 moved out, it is markup and variants —
`page.tsx` holds four whole tabs, `media-screen.tsx` holds a season list and an icon set, and the
same `Icon` component is written out twice in two different files.

**Why nobody noticed.** The label was held against the plan's own per-lot status, and that status
said `NOT STARTED` for L09 for a full wave after L09 merged. A guard reading a stale word reported
a promise that had already expired. The status left the plan on 2026-08-28 for that reason among
others; this lot is the debt the stale word was hiding.

**Where it lives (invariant 10).** Each extracted component stays inside its own feature folder
unless a second feature already reads it. The duplicated `Icon` is the one exception in sight: a
component two features draw is vocabulary, and vocabulary lives in `ui/`.

**Its position in this file was last, deliberately, and the operator pulled it forward on
2026-08-30** (Q3): nothing depends on it, but L19 — the lot that moves the producers out of two of
these four files — works far better in files already cut. It sits at the head of Phase 5 now.

**Re-read against the model by L10-ter (2026-08-29): UNCHANGED in objective; the sentence above
was refreshed** (it named « L10 to L13 » as the lots worked in oversized files, and the list has
grown). Two lots now write beside its four files before it runs — L15 (the selection bar, the Découvrir containers) and L19 (the
producers) — and neither may extend them; each creates its files beside the page. **Q3 was answered on 2026-08-30: before L19** — this lot now sits at the head of Phase 5, so the
producers move into files already cut.

**It also owns half of B-247** (2026-08-30, from L15's review): a store bump replaces a feature
page's DOM nodes, so a write between `pointerdown` and `click` destroys the tap. The repair is in the
surfaces — a page whose nodes keep identity across a store write — and the four files this lot
decomposes are where two of them live; L19 owes the same for the producers it moves.

**It also owns B-283** (2026-08-31, from L12's review): while the media sheet's read is in flight,
the screen prints its UNKNOWN parts as ANSWERS — « aucun synopsis », « aucune distribution », « pas
de bande-annonce », seasons « unknown » — assertions about data that has not arrived, which §13
refuses. The maquette cannot exhibit it: its placeholder is the engine's COMPLETE sheet, so no
field is ever missing during priming, and the real backend's projection carries `{t, f}`. The
repair is a line in `features/media/media-screen.tsx`, one of the four files this lot decomposes
and that no earlier wave may extend — which is why L12 filed it rather than fixing it.

**Done when.** No file under `frontend/maquette/design/src` is at or over 400 non-blank lines with
the sole exception of the dying engine's two, `engine/legacy.js` and `engine/states.js`, which
L13 removes; no component is written out twice; every extraction is proved by the oracle, whose
whole subject is that nothing moved on the screen.

#### L19 — The producers · *depends on L15, L09, L12*

**Objective.** Every surface the engine still PRODUCES moves to its feature, with its share of the
fixture dying (D5): the ten `panel.open` producers (the follow sheet, the journey, the « ⋮ », the
account menu, a setting, the seasons, the acquisition status — `grep -n "panel\.open("
legacy.js`), the Découvrir feed (list, poster, deck, footer — the one feature surface still
drawn by `innerHTML` after L15), the episode popover's content, and the delegation verbs those
surfaces own (`data-cancelsetting` is the settings feature's; `data-take` is the arrivals'). The
frame's own verbs (`data-drawer`, `data-navgo`, `data-sheet`) are not this lot's.

**Why it exists as a lot.** L13 said the sixty fixture families « belong to surfaces the ENGINE
still draws — their literals cannot leave before their markup does ». The markup left with the
pages; the families stayed because their readers are producers, and no lot owed those. **A debt
with no named owner is a debt nobody pays, and it reappears in the last lot** — this is the
last lot's debt, named and moved.

**Where it lives (invariant 10).** `features/<domain>/` — a producer is a function from the
cache to a descriptor, and it lives with what makes it change. It reads the query cache, never
the engine's accessors; each moved producer takes its `installX` seam out of `app/shell.tsx`.

**One kind of change.** A descriptor rendered by `ui/panel` from a React producer is the same
descriptor rendered from the engine's — the oracle proves each move at zero divergence, surface
by surface, in L07's order. A verb that moves is a behaviour move and lands in its own commit with
the rule that held it before, unchanged in count.

**What it must not do.** Extend a grandfathered file (L14's four) — a producer becomes a new file
beside its page. Add a feature: DOIT-4, DOIT-8, NE-DOIT-PAS-3 and NE-DOIT-PAS-9's missing
INSTRUMENTS are built here because these are the producers that draw those surfaces, but no
surface changes.

**Two debts named here so they have an owner (2026-08-30).** The other half of **B-247**: a producer
moved into its feature keeps its nodes across a store write, so a tap between `pointerdown` and
`click` survives — held by R100's `isSameNode` shape on the producer's surface. And the producer half
of **B-249**: the 260 ms `setTimeout` beside `data-mediasheet` that R103 measures and PRINTS is
removed with the producer that carries it, and R103 then REFUSES the gap instead of printing it.
**That one is already discharged, and the line is kept saying so rather than deleted** (L12,
2026-08-31): the `data-mediasheet` branch lost its close-and-wait entirely — the panel now leaves
inside the navigation's own commit, which is what the delay was standing in for — so what L19
inherits here is the SHAPE, at the other `setTimeout(…, 260)` sites the delegation still holds, not
this one.

**Done when.** `grep -c "panel\.open(" legacy.js` reads 0; the inventory command lists only the
harness panel; the fixture families that fed the producers are gone (D5's bracket-match method
reads the difference); the delegation handles only the frame's verbs; the four map rows above
read `served` with a rule that bit; the oracle is green or its divergences accepted with reasons.

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

**Blocking note.** Where the levers land — a page of their own, or a section of Système — is the
operator's UX question, answered in the wave's design before it opens; the per-media half is no
longer a question, §20 answers it.

**Where it lives (invariant 10).** `features/pipeline/` for the levers and the history, or the
Système feature if the design puts them there; the bound is a setting and reads through the
settings feature's contract.

**Done when.** DOIT-3's « relancer le watcher », DOIT-5's progress to the library and DOIT-6's
figures read `served` in the map with a rule; the bound, the pause and the watcher are called and
mocked; the history renders every named state at 390 px with no overflow; the oracle records the
surfaces as new.

#### L16 — §18, the ratio · *depends on L15, L19, L10*

**Objective.** DOIT-13: the ratio is read PER TRACKER, obligations are a « rien » with their
reason, and a tracker's policy is set from the surface that shows it. Three operations answer and
nothing calls them (`GET /api/acquisition/obligations`, `/stalled-grabs`, `/downloads`); one
write — the policy — exists in neither contract and will be recorded as a demand (D7). The stream's
`RatioMeasured` and `SeedObligation*` events reach the browser and no surface claims them
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

**Where it lives (invariant 10).** `features/trackers/` — a tracker is a domain of its own, read
by the acquisition and the media sheet, and invariant 7 forbids either from importing the other.
A page with its row in `app/navigation.ts` (bar or drawer — the wave's design says which, drawn
first), a per-tracker panel through `ui/panel`.

**Done when.** The map's DOIT-13 row and DOIT-2's ratio half read `served` with a rule; the three
operations are called and mocked (seeded from the running backend's shapes, D7); the policy write
is in the demands register; the events are claimed by a rule (R91's fan-out); the ratio shown is
the tracker's (NE-DOIT-PAS-1, held by the mock's own value, never a local computation).

#### L17 — §19, cross-seed · *depends on L16*

**Objective.** DOIT-14: an injection is seen, a refusal is explained, a title says where it seeds,
and the operator can prevent or provoke it. **Nothing exists to call**: this is D7's first real
case — the maquette declares the routes its experience requires, the demands register carries
them, the mocks are INVENTED because no fixture exists (L08's « seeded from the fixture it
replaces » does not apply, and the oracle records the new surfaces as new rather than proving
them unchanged). `CrossSeedInjected` and `CrossSeedRejected` are claimed by its `live.ts`.

**Dictated (operator, 2026-08-30) — the blocking note is lifted.** AUTOMATIC: the engine
cross-seeds alone, on by default, with a PER-TRACKER off switch (a config write, NE-DOIT-PAS-6
made into a setting). Seen: for EACH torrent, the cross-seed state per tracker — « actif »,
« stoppé », « tracker sans cross-seed », « erreur de cross-seed ». Lives: the per-tracker state in
the trackers page, plus a per-tracker block in the media sheet **visible to the administrator
profile only** — which reads §17's role model: if this lot runs before L18, the block lands behind
the served role the backend already exposes, and L18 redraws it on the full model.

**Where it lives (invariant 10).** `features/trackers/` extended (the per-tracker state), a block
in the media sheet's descriptor (a title seeds elsewhere — the media feature's `panel-seasons`
precedent: a feature ADDS a block kind), and a feed if the operator chooses one.

**Done when.** The map's DOIT-14 row reads `served` with a rule; the declared routes are in the
maquette's contract and in the demands; the two events are claimed; a refusal is readable from
the surface with its reason (NE-DOIT-PAS-5 applied to a success).

#### L18 — §17, accounts, rights and Plex identity · *depends on L15, L19*

**Objective.** DOIT-12: the interface shows what THIS account can do, and what it cannot is
visible and explained where hiding it would mislead. A rights MODEL first, then surfaces; the
sign-in gate redrawn for Plex SSO; the read-only role ABSORBED by the model — one authorisation
path (NE-DOIT-PAS-7). `GET /api/auth/me` diverges to carry rights (D7, a demand).

**Its four open points were dictated on 2026-08-30** — §17 « Ce que cela tranche »: three roles
(Operator bypasses ACLs; Household member; Plex guest) and two per-account options; a requester
on every acquisition; SSO added, not substituted, with e-mail linking; a rights-less Plex user
admitted read-only on the library; the Acquisition section absent for an account that can neither
request nor see others' requests, as the named exception to §17 rule 2. **No blocking note
remains.** The lot is last of the three because it is the largest and because it is the one
that edits the FRAME after L15 (the gate, the drawer's identity block), by design. The backend's
share is `docs/reference/backend-demands-architecture.md` § 2–3.

**Where it lives (invariant 10).** `features/account/` for the model and the surfaces; the gate
stays `app/sign-in.tsx` and is redrawn here — the only lot after L15 that edits frame CODE (L16
and L20 add rows to the navigation table, which is the template working as designed), and the
plan says so rather than discovering it.

**Done when.** A right is proved on BOTH sides and separately (§17 « Ce que cela impose à la
preuve »): the action absent from the surface for the account without it, the call refused for
one that forces it; the map's DOIT-12 row reads `served` with that rule; the read-only role has
no path of its own left.

### Phase 6 — The finish

#### L13 — The engine's residue · *depends on L07, L09, L12, L15, L19*

**Objective.** What did not die by subtraction, measured by L10-ter on 2026-08-29 rather than
listed from memory: the ladder's HANDLER (`onEngineBack`, `unwindLayer`, `hideLayers`,
`__closeLayers` and **`switchPageFromLayer`**, which is the one B-275 and B-290 both name as their
cause — it REPLACES a layer's entry rather than pushing over it — `MODEL.md` § 2 Part 4, to
`app/layers.ts`), the document-level delegation's
FRAME verbs, the boot handshake (`__startEngine`), the engine-side seams (`__address`, `__bridge`,
`__panel`, `__screens`, `__store`), the dead `#screen` layer with its three readers and the
mount-node placement that rests on it (B-232), `refonte.html` and R72's renegotiation,
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

**The instruments' own debts, and who takes them (2026-08-31).** A register entry naming no lot is
B-253's species: the plan is where a lot's obligations live, so a defect nobody's lot names is a
defect nobody schedules. **The harness and the repository's guards belong to no lot** — every wave
uses them and none owns them — so their debts are named here, with one rule that decides them:
**the next wave that touches the tool takes its debt**, in the same pull request, and says so in
its report.

- **B-269** — five corpus floors in `served_copy.py` calibrated by hand, one figure per corpus.
- **B-272's open form** — nothing RE-TAKES a floor, so every floor in the repository drifts under a
  green guard until somebody measures it. The compositor manifest's floors were re-taken in L12;
  the mechanism that would keep them true does not exist.
- **B-273** — `scripts/mutate.sh` cannot judge a GUARD: it decides by reading journal `FAIL` lines,
  which a guard in `scripts/` never prints, so it answers « no hold fell » whatever the guard says
  and whatever its exit code. Two arms were rewritten on that false reading before it was found. It
  also exits SILENTLY when a mutation breaks the build, which reads the same way.
- **B-276** — a delay set by hand in an instrument outlives the drawn duration it was set against.
  Three rules were repaired for it in L12 alone; the species stays open because nothing refuses the
  next one.
- **B-277** — `exits.py`'s frame-count control flakes under the suite's parallel load.
- **B-278** — the drawer's dismiss acknowledges itself twice, unexplained, with the decisive
  experiment written down in the entry.
- **B-287** — 266 maquette/harness comments name a date, a lot or a phase, against the rule in
  `CLAUDE.md` § Language, and nothing counts them. The arm's shape is already in this repository
  twice: a per-file baseline that refuses the count going up.

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
three times out of four as well, and the steward went on to measure a miss at the close of L09, of
L10 and of L10-bis in a row. **What settles it is a check rather than a sentence**, and the shape is
cheap because the row already carries the wave's version: if `personalscraper/__init__.py` on `main`
has reached the version the « In flight » row names, that wave has landed and the row is stale —
offline, exact, and green on the wave's own branch, where the two differ by construction. It says
nothing between waves, when no row names a version, and it prints what it read there rather than
letting a vacuous pass read as a verdict. **And it says nothing about a prose-only wave either**:
a `no-version-bump` pull request names no version, so its « In flight » row was cleared by hand and
held by nothing — B-238, found by the first such row (L10-ter's). **Closed by the steward on
2026-08-30**: the row also names its pull request, and a squash merge writes that number into the
subject `main` carries — `… (#521)` — so a row whose pull request `main` already holds in a
subject has landed, offline and exactly like the version. A row in flight that names neither is
refused outright: nothing could hold it. The wave's pull request is the FIRST `#NNN` in the cell.

**BUILT on 2026-08-29 as `scripts/check-implementation-state.py`, and building it corrected this
paragraph twice.** « Has reached » is an ORDERING, not an equality: written as equality — the
reading the sentence above invites, and the first one implemented — the arm reported clean over the
very defect it was written for, because L10-bis's row named `0.98.51` while `main` carried `0.98.52`
after a follow-up pull request re-anchored the oracle and bumped once more. **A wave that merges
alongside any other change overshoots by construction.** And the guard is wired into the contracts
tier with `IMPLEMENTATION.md` added to the workflow's `docs` filter, because
`tests/scripts/test_ci_filter_covers_the_guards.py` refused it otherwise: a guard whose subject no
filter names runs in no job, and a post-merge gesture is *precisely* a pull request touching that
file alone.

**The steward built it, and § 7.2's boundary moved to allow that — on the operator's instruction,
2026-08-29.** The sentence this paragraph used to end on said a guard is code and the steward does
not carry code. That held for four waves and produced four misses; the office now carries an
instrument when the defect it measures is the office's own subject and no wave will take it.

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

**And a fourth: ARCHIVE the wave's design and plan** — `docs/features/<codename>/` moves under
`docs/archive/features/`, and every cross-reference to it moves in the same step. **One folder is
exempt, by name: `docs/features/maquette-l10-ter/`.** It is not a wave's design — it is the frame's
model and the survey this file cites twenty-four times (`grep -o "maquette-l10-ter\|MODEL\.md\|SURVEY\.md" docs/reference/frontend-architecture.md | wc -l`, 2026-08-30), L15's, L11's, L12's and L13's design starts
from it, and `docs/archive/` is frozen history that a lot may not amend. It archives when L13
lands, with the engine whose death it measured; until then a lot that finds the model wrong
amends it under § 7.1 like this file. Added on
2026-08-26 by B-083, after the third wave out of eight where this gesture slipped: the L06 audit
had to do it retroactively, L07 did it in the move, L08 did not and the correction wave did it a
wave late. The operator arbitrated a step here rather than a guard — the check is cheap to
imagine and this list is not, on the evidence, cheap to remember, so whoever finds it skipped a
fourth time has the count above to argue with.

**And a fifth, and it is a measurement rather than a gesture: recount « guards green over what
they do not read »** in `BUGS.md` § Guards green over what they do not read, adding the wave's own
figure with the pull request or register entry that establishes it. B-085's whole finding is that
seventeen instances across three consecutive waves were each recorded as an incident of their own
wave and no figure anywhere carried the total — so the shape read as bad luck three times instead
of as the dominant failure mode of this repository's instruments. A total nobody recounts is a
total that stops being true at the next wave. **Zero is a real answer and it is written down**: a
wave that found none says so, in its row, with the same authority as a wave that found six.

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

**Which lot is next is decided by § 0's selection rule** — the first lot in this file's order
that `IMPLEMENTATION.md` does not record as landed and whose every dependency it does — and never
by which one happens to be unblocked earliest. Where two are eligible, **this file's order decides,
not the number**: L14 is written after L13 and runs after it.

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
| An entry animation replays AFTER the transition that already drew it | **L12** | CSS animations on a tree mounted under `startViewTransition` do not START until it ENDS — rendering is frozen for the capture — so an element-side entry replays over a snapshot showing the final state. Appear, flash, reappear. `:active-view-transition` cannot guard it: by the time the animation starts the transition is over and the selector no longer matches. **An entry has ONE OWNER**, and on a surface reached by a transition that owner is the transition |

**The oracle's silence over a BEHAVIOUR wave is evidence of nothing — a wave that writes
behaviour is held by rules or by nobody.** Measured at L11: no divergence over 2 958 measurements
while four adversarial rounds found ~40, 13, 7 and 0 product defects under a permanently green
gate — correct on the oracle's part (nothing drew a pixel differently), and exactly why its green
says nothing about such a lot. D8 states what the oracle proves; this trap is the converse, and
it bit a wave whose every tier was green.

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

**Deferred, on purpose.** An executable check — one that refuses a lot recorded as landed whose
files do not exist, or a cross-reference pointing at a dead path — is wanted and is not built
yet. **The paragraph above cost something the day the status left this file**: five sentences here
went on describing a `LANDED` token that no longer existed, this one among them, and one guard read
it. « The directives change in the same move » is not advice; it is the whole of B-150. It is built once this plan has proved its shape, and not before: a guard written against a
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
