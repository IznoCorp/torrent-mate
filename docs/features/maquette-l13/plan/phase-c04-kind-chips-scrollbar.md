# Phase c·4 — The kind chips hide their bar

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
