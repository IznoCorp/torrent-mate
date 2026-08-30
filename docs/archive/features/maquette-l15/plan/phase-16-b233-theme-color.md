# Phase 16 — B-233: `theme-color` follows the theme

**Kind BEHAVIOUR.** Alone, with its own rule.

## What is wrong

`<meta name="theme-color" content="#0b0b0d">` is a constant while the document paints light under
`data-theme="light"`. The status bar of an installed light-theme application is dark. P21 of
`MODEL.md` § 3 is false.

## What changes

`app/appearance.ts` — which phase 15 made the one owner of the theme — writes the meta when it
writes the attribute. The value is read from the token the document actually paints, never a hex
retyped beside it: a second copy of a colour is a colour that drifts.

Two declarations, not one: the document keeps a `theme-color` for the first paint (before any
module runs), and the appearance owner updates it. The static one is the dark value, which is what
the default paints.

## The rule

A rule reads the meta under both themes and asserts they DIFFER, and that each matches the painted
background of the surface behind the status bar — measured as painted, through a canvas, never
parsed from `getComputedStyle`'s own colour space. **Mutation**: make the light value equal the
dark one and confirm the rule falls naming the two that agreed.

## What the oracle will show

Nothing: a `<meta>` has no rectangle and no computed style. Another change that is invisible to it
by construction, and another rule that has to exist for that reason.
