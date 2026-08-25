# Phase 1 — The extractor, and the classification of all 88

## Scope

- `scripts/extract-maquette-fixtures.mjs` — reads `legacy.js` with the TypeScript parser and
  prints, for a named family, its literal as JSON; with `--measure`, the inventory.
- `frontend/maquette/fixture-register.json` — the classification of every family, beside the
  other guard inventories (`legacy-css-residue.json`, `compositor-css.json`).

## Why a parser and not a regex

The precedent is written down twice in this repository. `scripts/source-spans.mjs` exists because
« no heuristic separates them reliably », and `refresh-maquette-fixture.py` says a regex cannot
find the end of an object because three shapes proved it. A fixture literal holds French copy
full of apostrophes, nested objects, and template pieces; a bracket counter that does not follow
quotes reads the first apostrophe as a string opening — which is B-075's second instance, found
in the reader of the rule L07-bis was writing at that moment.

The parser is already a dependency (`frontend/node_modules/typescript`), reached the same way
`source-spans.mjs` reaches it.

## What the extractor must handle, and it is checked rather than assumed

- Declared **`const`**. That is the discriminator, and a first version used a three-line size
  floor instead — which hid `CADENCE_CRON` and `STRIP_LABELS`, both real fixtures on one line.
  A `let` is a variable the engine WRITES; freezing its initial value would record a starting
  point as though it were a fact.
- At MODULE level, or inside a NAMED function under a qualified name. Inside an anonymous one
  they are counted and not inventoried: a name built on a line number is renamed by every edit
  above it.
- A literal is a FIXTURE only if it is pure — no call, no identifier reference other than a
  property key. `SERVICES_PANNE = SERVICES.map(...)` is code and must not be extracted.
- The output is canonical JSON: keys in source order, two-space indent, newline at end. Two runs
  produce byte-identical output or the guard that compares them is measuring the serializer.

## The classification

`fixture-register.json` names every family, its class (`served` · `asset` · `interface` · `unserved`)
and, for the last one, the reason. The two function-local literals are entered by hand and marked
so the guard knows the extractor cannot see them.

**The classification is a judgement, and it is the phase's real work.** A family is `interface`
when a server sending it would be sending the interface its own words — `ST_LABEL`,
`REASON_LABEL`, `TRIS`, `EP_LABEL`, `VIA_LABEL`, `MOIS`, the tone maps. It is `served` when it is
state the operator's system holds. It is `asset` when it is an artwork or trailer map. Each entry
carries one line saying why.

## Done when

- `node scripts/extract-maquette-fixtures.mjs --measure` prints 77 module-level families over
  28 789 lines, names the 11 inside a named function, and counts the 5 inside anonymous ones.
- Extracting the same family twice gives byte-identical output.
- `fixture-register.json` classifies 88 names, and every `unserved` entry carries a reason.
- ACC-01, ACC-02, ACC-03 green.
