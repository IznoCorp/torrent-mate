# Phase 8 — The windowing

**Kind: BEHAVIOUR.** **Owns P24** — no long list renders unvirtualised (1 861 titles).

**Depends on phase 7** (D-L12-2). It is the lot's most constrained phase: it settles a library
question, and it edits one of **L14's four files**.

## Step 1 — MEASURE the geometry. Nothing is adopted or written before this

The library page draws two modes:

- **grid** — tiles, `aspect-ratio: 2/3`, uniform by construction;
- **list** — `.card`, `grid-template-columns: auto 1fr`, height following the text. §12 requires a
  long title to take the whole line and **wrap rather than truncate**, so a two-line title is a
  taller card.

**Measure the rendered heights of both modes over the 1 861-title fixture.** The measurement decides
which arm of the D9 row applies to which mode. This design refuses to guess it: assuming uniformity
and being wrong produces a list that **jumps under the reader**, which no green gate would show.

## Step 2 — SURVEY the candidates and put them to the operator

**⚠ This step said the opposite until 2026-08-31.** It proposed a two-armed verdict whose first arm
was a **refusal** — « windowing a uniform list is arithmetic, so write it ». **The operator reversed
D9's rule 2** that day: hand-written code is for maths NOBODY has written, and a reliable,
maintained, proven, widely used library that solves EXACTLY the problem is **preferred** to
re-coding it. The first question is « does such a library exist? », and if it does the candidates
are **proposed with their criteria** so the operator chooses. DESIGN.md § 2 carries the reversal in
full and names what it makes void.

**So this step does not decide. It surveys, and it reports.**

Survey the field — TanStack Virtual, react-virtuoso, react-window, and whatever else the survey
turns up; the list is not closed by this plan. For each candidate, record:

| Criterion | What to establish |
| --- | --- |
| **Solves exactly our problem** | windows a long list in BOTH modes — the uniform grid and the content-height card list |
| **Maintained** | last release, issue response, not archived — with the date the survey read it |
| **Proven / reputation** | adoption, not promise |
| **Headless** | **rule 1 is UNCHANGED and this is its criterion**: a virtualiser shipping its own markup or CSS moves drawing out of the stylesheet and out of the design reference. The operator's list does not name this one and this lot must not drop it |
| **Fixed AND measured heights** | step 1's measurement says which mode each surface needs |

**Adopt the one the operator names. Nothing is installed before that.** The row lands in D9's table
as « candidates to propose » — the steward is transcribing the amendment itself.

**What this does NOT reopen**: rule 1 stands, so the View Transitions API is still adopted for
transitions (phase 9) and a JavaScript animation library for page transitions is still refused. That
verdict never rested on rule 2.

## The survey, run 2026-08-31 — and the measurement that preceded it

**Step 1's measurement, and it corrected the design in BOTH directions.** Driven on the served
prototype at 390 × 844:

| Mode | Items | Distinct heights | Reading |
| --- | ---: | ---: | --- |
| grid — `[data-part="tile"]`, raw | 27 | **2** (171 · 203.34) | looked variable |
| grid — real tiles only (`.tile`, excluding `.sk`) | 24 | **1** (203.34) | **uniform** |
| list — `[data-part="card"]` | 24 | **1** (126) | **uniform** |

**The two heights were SKELETONS.** `[data-part="tile"]` selects `.sk.tile` — the loading
placeholder — as well as the real tile, and a skeleton is 171 px against a tile's 203.34. A
virtualiser configured from the first reading would have been put in variable-height mode, paying
measurement cost per row, for a spread that no rendered list ever contains.

**And the design's other guess was wrong too.** It reasoned that the card list would be VARIABLE
because §12 requires a long title to wrap rather than truncate. Measured, every card is exactly
126 px: the title's box is fixed and the wrap happens inside it. **Both modes are fixed-height**, so
whatever is adopted runs in its fixed-size mode, and the measurement — not the reasoning — is what
says so.

<sub>method: `window.__go(state)`, then `getBoundingClientRect().height` over every item, rounded to
2 decimals and counted distinct.</sub>

### The candidates

Facts from `https://registry.npmjs.org/<package>` on 2026-08-31; the description column is the
registry's own, not a summary of it.

| Candidate | Latest | Published | Releases | Unpacked | Runtime deps | Headless? |
| --- | --- | --- | ---: | ---: | --- | --- |
| **`@tanstack/react-virtual`** | 3.14.10 | 2026-08-18 | 135 | **55.2 KB** | `@tanstack/virtual-core` | **yes** — the registry description is literally « **Headless** UI for virtualizing scrollable elements in React » |
| `react-virtuoso` | 4.18.12 | 2026-08-17 | 313 | 237.0 KB | none | **no** — « a virtual scroll React **component** »: it renders the scroller and the items' wrappers itself |
| `react-window` | 2.3.0 | 2026-07-20 | 77 | 211.3 KB | none | **no** — renders `<List>` and writes inline styles onto each child |

All three are MIT and all three are actively maintained — none is archived, and the three latest
releases are within six weeks of each other. **Maintenance does not separate them; rule 1 does.**

### Against the criteria

| Criterion | `@tanstack/react-virtual` | `react-virtuoso` | `react-window` |
| --- | --- | --- | --- |
| Solves exactly our problem (both modes, fixed height) | yes | yes | yes |
| Maintained | yes | yes | yes |
| Proven / reputation | yes | yes | yes |
| **Headless (rule 1)** | **yes** | no | no |
| Fixed **and** measured heights | yes | yes | yes |
| Already trusted in this tree | **three TanStack packages ship here today** — `react-query`, `react-router`, `store` | no | no |

**The recommendation, and the reasoning is rule 1's rather than a preference.** A virtualiser that
renders the scroller and writes inline styles onto its children moves drawing out of the stylesheet
and out of the design reference — which is what rule 1 exists to prevent, and it is refused
*whatever rule 2 says*. `@tanstack/react-virtual` returns measurements and renders nothing, so every
drawing decision stays in the variants where the oracle can read it. It is also a quarter of the
size and its family is already three packages deep in this tree.

**THE OPERATOR NAMES THE ADOPTED CANDIDATE. Nothing is installed before that** — this is the one
stop the plan reserves by name.

## Step 3 — Build it as VOCABULARY

The windowing is a **`ui/` primitive** (invariant 10). The page does not learn to virtualise; it
uses a component.

## The gate that makes § 3's promise checkable

`features/library/page.tsx` is grandfathered to **L14** at **613** non-blank lines, and this wave
may not extend an L14 file. Its change here is a **substitution** — the `IntersectionObserver` block
(`:371`) and the raw `.map()` go out, the component comes in.

**It must leave this phase at ≤ 613 non-blank lines**, by
`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/library/page.tsx`.
Its grandfather label stays **L14**: L14 still owes the decomposition and this lot does not claim to
pay it.

**If the count cannot be held, the phase STOPS and reports** rather than extending an L14 file
quietly (§ 0's third rule).

**The adopted library is wrapped by the `ui/` primitive, never imported by the page.** That keeps
invariant 10's placement true and gives the dependency exactly one call site — the same reason the
feedback seam has one (phase 4).

## The rule

One driven rule: **rendered rows are counted against the data length** over the 1 861-title
fixture — far fewer nodes than items — **and the list is scrolled with a real touch stream** and
still shows the right items at the right offsets.

**What it must not read**: a rule that only counts nodes on the cold load is green over a
virtualiser that renders correctly at rest and tears on scroll. The scroll half is the half that
bites.

## Mutation

Render the full list → the count case falls. Break the offset arithmetic by one row → the scrolled
case falls, and it must name the offset rather than the count. Restore.

## Done when

P24 reads true; the D9 row is written and flagged; `library/page.tsx` is at ≤ 613; both mutations
bit; the oracle's divergences (the list now renders a window) are named in this phase's commit.
