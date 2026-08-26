# The contract the interface requires

`openapi.json` in this directory is **the maquette's own data contract** — what the next version
of the frontend needs a server to answer, declared by the interface rather than read off the one
that exists. It is D7 of `docs/reference/frontend-architecture.md` in force, and it is written by
hand.

## What it is not

**It is not `frontend/openapi.json`.** That file is generated FROM the running backend and
describes what the backend does today. This one describes what the interface requires. The two
differ on purpose, and every difference is a **demand**, computed by
`scripts/compare-contracts.py` into `docs/reference/frontend-backend-demands.md`.

**It is not a backend task list anybody is working on.** No backend work happens until the
interface is frozen (D7). The register IS the future specification, delivered as a diff rather
than a blank page.

## Why some of its fields are ugly

A field like `secondaryLine: "1,8 To libres · 15 To · rempli à 88 %"` is not what a server should
send. It is what the maquette's fixture holds today, and the contract carries it **verbatim** for
one reason, which is the whole of L08's value:

> A mock that returns exactly what the current fixture returns makes L09 provable. Wiring a
> surface to it renders the same thing, so the oracle proves the wiring at **zero divergence**.

Decomposing that string into free bytes and total bytes would be a better contract and would
forfeit that proof, because rendering it back would depend on formatters nobody has written yet.
So the value is carried, the ugliness is **recorded as a demand**, and the demand is what the
backend eventually builds. See D-L08-5.

## How to change it

1. Edit `openapi.json`.
2. Regenerate the types: `npm run generate-contract-types` in `frontend/maquette/design/`.
3. Recompute the demands: `python3 scripts/compare-contracts.py --write`.
4. Commit all three together. `--check` refuses a register that does not match the contract, so
   they cannot separate.

## What holds it

|                                                   |                                                    |
| ------------------------------------------------- | -------------------------------------------------- |
| the seeds match the fixtures they were taken from | `scripts/check-mock-seeds.py --arm correspondence` |
| every fixture family is classified                | `scripts/check-mock-seeds.py --arm classification` |
| the register equals the computed diff             | `scripts/compare-contracts.py --check`             |
| the layer answers the contract, deterministically | `frontend/maquette/harness/mocks.py` (R85)         |
