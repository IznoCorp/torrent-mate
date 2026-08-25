# Phase 1 — The extractor, and the classification of all 66

## Scope

- `scripts/extract-maquette-fixtures.mjs` — reads `legacy.js` with the TypeScript parser and
  prints, for a named family, its literal as JSON; with `--measure`, the inventory.
- `frontend/maquette/design/src/mocks/register.json` — the classification of every family.

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

- A `const NAME = [...]` / `= {...}` at MODULE level. A literal inside a function is NOT a family:
  `steps` and `TONS` are exactly that, and they are the reason the distinction is made in code
  rather than in prose.
- A literal is a FIXTURE only if it is pure — no call, no identifier reference other than a
  property key. `SERVICES_PANNE = SERVICES.map(...)` is code and must not be extracted.
- The output is canonical JSON: keys in source order, two-space indent, newline at end. Two runs
  produce byte-identical output or the guard that compares them is measuring the serializer.

## The classification

`register.json` names every family, its class (`served` · `vocabulary` · `asset` · `unserved`)
and, for the last one, the reason. The two function-local literals are entered by hand and marked
so the guard knows the extractor cannot see them.

**The classification is a judgement, and it is the phase's real work.** A family is `vocabulary`
when a server sending it would be sending the interface its own words — `ST_LABEL`,
`REASON_LABEL`, `TRIS`, `EP_LABEL`, `VIA_LABEL`, `MOIS`, the tone maps. It is `served` when it is
state the operator's system holds. It is `asset` when it is an artwork or trailer map. Each entry
carries one line saying why.

## Done when

- `node scripts/extract-maquette-fixtures.mjs --measure` prints 64 module-level families over
  28 776 lines, and names the 2 function-local ones separately.
- Extracting the same family twice gives byte-identical output.
- `register.json` classifies 66 names, and every `unserved` entry carries a reason.
- ACC-01, ACC-02, ACC-03 green.
