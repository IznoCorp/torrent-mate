# Phase 16 — The title alone, every card (DOIT-9, § 12)

**No STOP C.** A PROOF: § 12's engraved card composition, read over every card rather than printed over four.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -n "title alone" frontend/maquette/harness/follows.py` → line **28**, a `print` over
  `.slice(0,4)` follow cards, asserting nothing; `git grep -ln '"card"' -- frontend/maquette/design/src/features
  frontend/maquette/design/src/ui` → **14** files drawing a card.
- **Points ≈ 5.** R-L24-g 3, over every named state drawing a `data-part="card"`: `card/title` alone on its line,
  above `card/meta`, never truncated (its `scrollWidth` within its box); `follows.py`'s print retired, said out loud
  1; the report 1.
- **Readers.** R15 (`harness/audit2.py`) counts cards across the three follow modes — untouched.

## Red today

Read at the opening over every state; a card already failing is a DEFECT found, reported to the steward before the
phase goes on.

## Move

The rule only; the print goes.


## Register

The map's DOIT-9 « unproved » card half; proposed at phase 20.


## Commit

`test(maquette-l24): the title stands alone on every card`
