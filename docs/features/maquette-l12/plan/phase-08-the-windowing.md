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

## Step 2 — The D9 verdict row

Write it under § 7.1 with its full reasoning, **as a proposal flagged in the pull request** — see
INDEX.md, « One thing the operator must rule on ». Its two arms:

- **uniform, declared box → refuse a library.** Windowing a uniform list is
  `floor(scrollTop / rowHeight)` and two spacers: arithmetic, not maths nobody has written
  (rule 2). A library would also measure item height in JavaScript, moving geometry out of the
  stylesheet and out of the oracle's field (rule 1).
- **variable, content-dependent height → allowed, scoped.** A measurement cache and scroll
  anchoring across a post-paint height change are maths nobody here has written (rule 2). Scoped to
  the list that is actually variable — never adopted as the tree's list strategy.

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
