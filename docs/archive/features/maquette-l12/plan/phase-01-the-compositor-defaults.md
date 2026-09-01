# Phase 1 — The compositor defaults

**Kind: BEHAVIOUR.** It changes what a finger sees. Its divergences, if the oracle reads any,
are named in this phase's commit.

**Owns P25** (no tap flash) and **P26** (a long press selects no text on a tile or a card).

## What it does

Both are document-wide defaults, so both land in `styles/base.css`'s base layer — the precedent
`spin` and `pulse` set: *a name the document defines once belongs to the base layer rather than to
whichever component happens to need it first.*

- `-webkit-tap-highlight-color: transparent` on every interactive element. Measured at **0**
  occurrences in the tree today (`grep -rn "tap-highlight" design/src design/index.html`).
- `user-select: none` on the pressable surfaces, and `-webkit-touch-callout: none` for iOS Safari.
  Partly true today — `legacy.css` carries some and one `select-none` sits on the drawer — so this
  phase makes it a **declared default in the base layer** rather than a scattering, and does not
  add to `legacy.css`, which `check-legacy-css-residue.py` refuses to let grow (D10).

**A text field keeps its menu and its selection.** Pasting into one has no other route and the
interface offers nothing of its own there. The engine already reasons exactly this way about
`contextmenu` (`legacy.js:8210`), and this phase must not contradict it.

## The trap this phase walks into

**Compositor-facing CSS is load-bearing** (§ 6, threatens L07 and this): deleting one selector from
a group once took `user-drag: none` with it, and native image drag then swallowed the whole pointer
stream. `legacy.css:319` carries `-webkit-user-drag: none` on `.tile img` for that reason.
**Nothing in this phase may remove it**, and the rule below reads it.

## The rule

One static rule in the compositor-CSS guard's shape (the instrument P12, P25 and P26 already name),
asserting on the built stylesheet: the tap-highlight declaration is present and transparent; the
selection refusal covers the pressable surfaces; **and `-webkit-user-drag: none` is still there**.

## Mutation

Remove the tap-highlight declaration → the rule falls naming it. Remove `-webkit-user-drag: none`
→ the rule falls naming *that*, not something adjacent. Restore. Both seen red before the phase
closes.

## Done when

P25 reads true; P26 reads true for tiles and cards; `legacy.css` has not grown; the rule bit twice.
