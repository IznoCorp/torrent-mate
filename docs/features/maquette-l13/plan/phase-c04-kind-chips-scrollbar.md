# Phase c·4 — The kind chips hide their bar

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** `grep -n pillScroll design/src/ui/variants/controls.ts` → the `pillScroll` cva
  already carries `"… overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden touch-pan-x
  touch-pan-y pr-4"`; `grep -n pillScroll design/src/features/library/library-head.tsx` →
  `<div className={pillScroll()} data-part="pill/list">{state.libLens === "cat" ? CATS.map(…}` — the
  category-chip strip (« Tout · Films · Séries », `B-336`'s own subject per its BUGS.md entry) ALREADY
  wears the variant that carries the two declarations. `grep -n webkit-scrollbar
  design/src/styles/base.css` → a global, lower-specificity `::-webkit-scrollbar` rule (`thin`,
  visible) that a per-element `[&::-webkit-scrollbar]:hidden` utility outranks. No tsc probe: no type
  change. `grep -ln pillscroll harness/*.py` → 0 rule files read the idiom by name today. `grep -n
  B-336 BUGS.md` → `open`, 1×.
- **Points ≈ 4.** 1 site if the amendment's named home (a domain-free `ui/` variant, frame-domain
  ceiling 0) still needs a distinct declaration from `pillScroll` itself, else 0; one new rule (the
  three readings: still scrolls, `scrollbar-width: none`, no WebKit bar) with its mutation ≈ 3.
- **Found (2026-09-15).** The strip B-336 named already draws through `pillScroll()`, which already
  carries `[scrollbar-width:none] [&::-webkit-scrollbar]:hidden` — the same two declarations the
  phase's move says to add. This measure cannot see a rendered scrollbar (no browser, per this
  session's Forbidden list) so it does not close B-336 itself; it flags that the
  phase's "Red today on readings 2 and 3" premise may already be false on this tree, which is a STOP
  for the phase's own opening reading, not a rewrite here.

A BEHAVIOUR change: the library's kind chips' strip, converted in a·10, takes `pillscroll`'s two
declarations so that it scrolls without showing a bar (DESIGN § 10, B-336).

## The proof FIRST

B-336's entry names the idiom but not a rule, so the rule is written from the defect. Its label is
bound to the next free number.

- **What it drives.** Open « Médiathèque » at 390 px wide and at the operator's 369 px, with the
  seeds whose kind counts overflow the strip.
- **What it reads**:
  1. the strip still SCROLLS (`scrollWidth > clientWidth`, and a horizontal scroll moves it), so the
     chips stay reachable;
  2. its computed `scrollbar-width` is `none`;
  3. no WebKit scrollbar is drawn, measured as the strip's `offsetHeight - clientHeight` reading 0.
- **Red today** on readings 2 and 3.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes the two declarations.
  Readings 2 and 3 fall, naming the bar.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on library states whose strip overflows**, each accepted with
  « B-336 » (D8).

## The move

- **The strip wears the idiom.** The strip's variant carries `pillscroll`'s
  `[scrollbar-width:none] [&::-webkit-scrollbar]:hidden`, reused from `ui/variants/controls.ts`
  and never retyped.
- **D11.** A scrollbar is styled, never replaced. A strip of chips is the one place it is hidden,
  because the chips themselves are the affordance, and the phase says so in the variant's comment.
- **Out of scope.** No other scroll container changes.

## Gate

Per INDEX « Gates ». In addition, B-336 closes with the rule's red reading and its mutation.

## Commit

`fix(maquette-l13): the library's kind chips scroll without showing a scrollbar`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** name the strip variant's home; in `ui/` it may carry no `library`/`lib`/domain word (frame-domain ceiling 0).
