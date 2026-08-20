# Phase 2 — The regions, declared on `data-*`

## Goal

One region per block a user perceives as a unit, across the 8 pages, 5 screens and 3 shared
components — anchored on `data-*` attributes and structural ids, never on a CSS class.

## Why not the 51 of the retired probe

They were chosen for the extraction contract, and they were anchored on classes (`.viewtabs`,
`.seg`, `.strip`, `.crossref`). Importing them would break the oracle at the exact moment it is
needed: this instrument exists to prove **L07** changed no rendering, and L07 replaces those very
classes with Tailwind utilities.

They are read as a **corpus of what was worth measuring** — their keys still name real blocks.

## Work

1. **Walk each surface** (`design/src/pages/*.tsx`, `screens/*.tsx`, `components/*.tsx`) and list
   its perceived blocks. Record the list in `regions.json` under `regions`, keyed
   `<surface>/<part>`, each entry carrying `selector` and the states that reach it.

2. **Where no anchor exists, add `data-region="<surface>/<part>"`** to the block's root — and
   move its three ends in the SAME commit: the markup that emits it, `regions.json` that declares
   it, and `oracle.py` that reads it. That third end is what makes
   `scripts/check-markup-contracts.py` accept the value; a `data-*` no reader understands is
   exactly the defect that guard exists for.

3. **Report resolution coverage per state** — how many declared regions actually resolved, not
   how many were declared. A confident `exit=0` over an empty measurement is this lot's main
   failure mode.

4. **Re-verify `knownAbsent`.** Its three entries describe interaction-gated regions
   (`add/footer`, `matrice/popover-date`, `arrivees/empty`). Two name French keys from before the
   English rename — check each still corresponds to a real region under the new names, and update
   the entry rather than carrying a stale one.

## Done when

- `regions.json`'s `regions` has zero class-anchored selectors (ACC-07).
- `python3 scripts/check-markup-contracts.py` exits 0 (ACC-08).
- Every declared region resolves in at least one of the 82 states, or is listed in `knownAbsent`
  with a written reason.
- The coverage report is printed and its figures are recorded in `DESIGN.md`.

## Traps

- **A `data-region` added for measurement is markup that exists for the instrument.** Keep the
  bound explicit: one per perceived block, and each addition visible in the same commit as its
  declaration.
- **English names.** `data-region` values are `<surface>/<part>` identifiers someone chose, so
  they are names, not data — English, and `scripts/check-no-french.py` reads them.
- The 82 states are obtained from `window.__states()`, never from a regex over `states.js`.
