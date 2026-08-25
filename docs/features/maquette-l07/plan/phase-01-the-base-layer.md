# Phase 1 — The base layer, and what the compositor reads

**Converts nothing.** It builds the ground every later phase stands on, and it exists because the
lot says so in its own words: what the compositor reads « belongs in the base layer and is held by
a rule, **before a single surface converts** ».

## What lands

1. **`design/src/styles/base.css`** — the base layer of D3, created empty and filled from BLOCK 1
   and BLOCK 2 in this phase only. It carries, each rule with the reason it is there:
   - the `@font-face` for Geist, the `login:socle` reset, the `a`/`button` resets,
     `:focus-visible`, `.visually-hidden`, `.skip-link` (D-L07-1's six app regions of BLOCK 1);
   - the **18 compositor-facing declarations**, listed below;
   - the five `@keyframes`, and the four `:has()` selectors Tailwind cannot express.
2. **`scripts/check-compositor-css.py`** — the rule that refuses their removal.
3. **`harness/common.py`'s `DESIGN_SOURCES`** gains the component tree and the new stylesheets.

## The 18 declarations, and where they are today

| line | property | value | selector |
| --- | --- | --- | --- |
| 33 | `overscroll-behavior-y` | `none` | `html, body` (BLOCK 1) |
| 538 | `overscroll-behavior-y` | `none` | `.port` |
| 679 | `touch-action` | `pan-x pan-y` | `.pillscroll` |
| 838–839 | `user-select` / `-webkit-user-select` | `none` | `.deck` |
| 849–850 | `-webkit-user-drag` / `user-drag` | `none` | `.tile img` |
| 863 | `touch-action` | `pan-y` | `.swipe` |
| 1421 | `touch-action` | `pan-y` | `.sugwrap` |
| 1459 | `touch-action` | `pan-y` | `.deck` |
| 1480 | `will-change` | `transform` | `.dcard` |
| 1866–1868 | `-webkit-touch-callout`, `user-select` ×2 | `none` | the pressable-surfaces group |
| 1874–1875 | `-webkit-user-drag`, `-webkit-touch-callout` | `none` | the same group's images |
| 2364 | `touch-action` | `none` | `.sheetgrab` |
| 2636 | `touch-action` | `pan-x pan-y` | `.cast` |

Six properties, 18 sites. **The figure was written 17 in this plan's first draft** — the
per-property counts were right and their sum was not. It is corrected here rather than quietly,
because a plan is read as a specification and the whole point of a figure carrying its command is
that someone re-runs it.

**They do not all move in this phase.** A declaration whose selector belongs to a surface stays
with that surface's rule until that surface converts — what phase 1 guarantees is that the SET is
known and that nothing may leave it unnoticed. Only line 33's is BLOCK 1's, and it moves with the
`login:socle` reset.

**The two entries at 849–850 and 1874 are the incident.** Deleting one selector from that group
took `user-drag: none` with it; native image drag came back, swallowed the pointer stream — one
down, two moves, never an up — and three gesture tests failed for a reason that looked nothing
like a CSS deletion.

## Why the rule reads more than one file

`DESIGN_SOURCES` is a three-file tuple — `refonte.html`, `index.html`, `engine/legacy.js` — and it
does not include `design/src/**`. Six harness rules read `design_source()`. The moment styling
moves into components, every source-level hold among them measures a file the evidence has left.
**That is the trap « a rule that greps one file greps the wrong thing », and it fires in phase 5 if
this is not done in phase 1.**

<sub>`grep -rl 'design_source()' frontend/maquette/harness/*.py` → 6 files.</sub>

## Mutation tests

- Delete `user-drag: none` from the base layer → `check-compositor-css.py` exits 1 and names the
  property AND the selector it went missing from. Restore, green.
- Delete `design/src/features/library/page.tsx` → at least one rule reading `design_source()` fails
  loudly rather than passing over a file it no longer reads.

## Gates

ACC-01, ACC-02 (zero divergence — nothing rendered changes here), ACC-03, ACC-12.
