# Phase 1 — The base layer, and what the compositor reads

**Converts nothing.** It builds the ground every later phase stands on, and it exists because the
lot says so in its own words: what the compositor reads « belongs in the base layer and is held by
a rule, **before a single surface converts** ».

## What lands

1. **`design/src/styles/base.css`** — the base layer of D3, created empty and filled from BLOCK 1
   and BLOCK 2 in this phase only. It carries, each rule with the reason it is there:
   - the `@font-face` for Geist, the `login:socle` reset, the `a`/`button` resets,
     `:focus-visible`, `.visually-hidden`, `.skip-link` (D-L07-1's six app regions of BLOCK 1);
   - the **17 compositor-facing declarations**, listed below;
   - the five `@keyframes`, and the four `:has()` selectors Tailwind cannot express.
2. **`scripts/check-compositor-css.py`** — the rule that refuses their removal.
3. **`harness/common.py`'s `DESIGN_SOURCES`** gains the component tree and the new stylesheets.

## The 17 declarations, and where they are today

| property | sites | today |
| --- | --- | --- |
| `touch-action` | 6 | `pan-x pan-y` ×2, `pan-y` ×3, `none` ×1 |
| `user-select` / `-webkit-user-select` | 4 | on the pressable surfaces |
| `user-drag` / `-webkit-user-drag` | 3 | the block whose accidental deletion swallowed the pointer stream |
| `overscroll-behavior-y` | 2 | one of them in BLOCK 1's `login:socle` |
| `-webkit-touch-callout` | 2 | refusing the browser's own long press where ours lives |
| `will-change` | 1 | `transform` |

<sub>`grep -nE '(^\|[;{[:space:]])(-webkit-)?(touch-action\|user-drag\|user-select\|overscroll-behavior[a-z-]*\|touch-callout\|will-change)\s*:' frontend/maquette/design/refonte.html` → 17 lines.</sub>

**They do not all move.** A declaration whose selector belongs to a surface stays with that
surface's rule until that surface converts — what phase 1 guarantees is that the *set* is known and
that nothing may leave it unnoticed. `check-compositor-css.py` reads the whole design source (the
stylesheets AND the component tree, so a `touch-action` written as a utility still counts) and
compares against a committed inventory of 17 entries, each keyed by property and selector.

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
