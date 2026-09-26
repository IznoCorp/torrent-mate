# L22 — the lot's rulings (the steward's, on the implementers' STOPs), one numbered file, non-reopenable

The operator's rulings are not here: organisation rulings 1–15 are in `docs/reference/operator-method.md`, the eleven
on the design's open questions in DESIGN § 7.2. This file holds the steward's rulings on the lot's STOPs, from 1.

## 1 — a state id inside a `page.evaluate` string (auditor, 2026-09-26 16:3x; phase 3)

**The STOP.** `scripts/rename-identifiers.py --values` moves a Python string only when its whole body is an id token, and
its non-values path skips hyphen-adjacent words by design; so `arr-resolution` / `arr-decision` inside
`pg.evaluate("()=>window.__go('…')")` (and one JS array inside a Python string) stayed in five rule files: `actions.py`,
`attrs.py`, `bugs.py`, `decision.py`, `hiding.py` — seven occurrences.

**Ruled A.** Those seven move by an exact substitution of the QUOTED form only (single and double quotes), said out loud
in the commit, and the proof lives outside the tool: (1) the count before on `main` (`frontend/maquette`: 15
`arr-resolution`, 11 `arr-decision`, no other id sharing those prefixes) and ZERO after on the whole repository, every
occurrence kept as history listed by `file:line` with its reason; (2) both quote forms searched; (3) a mutation putting
one old id back into one of the five rules, which must make that rule FALL by name. **B** — a tool arm reaching a state
id inside an evaluate string — goes to the documentation pull request's register as a candidate, not built here.
