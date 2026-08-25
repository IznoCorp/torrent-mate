# Phase 2 — The contract, and its generated types

## Scope

- `frontend/maquette/contract/openapi.json` — OpenAPI 3.1, the maquette's own (D-L08-1).
- `frontend/maquette/contract/README.md` — what it is, what it is not, and how to change it.
- `frontend/maquette/design/src/mocks/contract-types.d.ts` — generated, never hand-edited.

## What the contract declares

Every read and every mutation the interface requires, across the nine pages and five screens
(D-L08-3). It STARTS from `frontend/openapi.json`: where an operation already exists there, its
path, method and schema are taken as they are unless the interface genuinely needs otherwise.

**Where it must diverge, it diverges deliberately and the divergence is a demand** — phase 9
computes them. The largest is already known: there is no library endpoint of any kind in the
backend contract, so the whole Médiathèque is new surface.

## What the contract does NOT do

It does not decompose a pre-formatted fixture value into facts (D-L08-5). Where `DISKS` holds
`"1,8 To libres · 15 To · rempli à 88 %"`, the contract declares the field that holds it and the
register records the demand: the backend must supply the numbers and the interface must format
them. Inventing the decomposition here would make L09 unwireable at zero divergence — and it is
L09's own Done-when that asks for that proof.

## Generation

`openapi-typescript` — already this repository's tool (`frontend/package.json` → `gen-api`). The
generated file is committed and a gate refuses drift between it and the document, exactly as
`make openapi` does for production.

## Done when

- `frontend/maquette/contract/openapi.json` parses as OpenAPI 3.1 and declares every operation
  the interface requires.
- The generated types compile: `npx tsc -b` at exit 0.
- Regenerating produces no diff.
- ACC-20, ACC-01, ACC-02, ACC-03 green.
