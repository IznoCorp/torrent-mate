# Phase 3 — The mocks that move

**No STOP C.**

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -cv '^\s*$' frontend/maquette/design/src/mocks/handlers/{decisions,staging,system,acquisition}.ts`
  → **112, 399, 31, 348**. `staging.ts` sits one line under the ceiling: no line lands there.
- **Points ≈ 12.** `enqueueForResolution` in `decisions.ts` — a new route 2 that files a pending decision with the
  candidates the search answers, or none (≈ 25 lines) 2½; `readFollowCompleteness` in `acquisition.ts`, a new route
  2 (≈ 12 lines) 1; a named scenario failing ONE of Système's reads — services, disks, index, dependencies — each a
  handler re-answered 1 × 4 = 4; the report ½.
- **Readers.** `features/system/queries.ts:53–61` (the four reads); `mocks/handlers/index.ts:11` (the route table).

## Red today

None — the rules that read these answers are written in phases 4, 7 and 13, red against this phase's mocks.

## Move

1. `enqueueForResolution` moves the seed: the folder gains a pending decision; a second call on the same folder
   answers the existing one (idempotence — the only refusal DOIT-4 allows).
2. The failure scenario is a dial of the layer (`window.__go` resets it, `frontend/maquette/README.md` § « The mock
   layer »), never a flag a surface reads.

## Mutation

None.

## Register

None.

## Oracle: states that diverge, declared by name

None — no state walks the new scenario before phase 4.

## Commit

`feat(maquette-l24): the mocks answer enqueue, completeness and one failed system read`
