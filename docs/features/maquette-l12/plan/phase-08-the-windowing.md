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
