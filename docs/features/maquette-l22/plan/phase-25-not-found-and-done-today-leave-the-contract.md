# Phase 25 — `notFound` and `doneToday` leave the contract (F40)

**Born 2026-09-27 from the cut of phase 23 at its opening.** The coherence triage's F40: round 7 removed the readers of
the `notFound` and `doneToday` families, and the contract still requires them, so the register demands them of the
engine. What loses its subject is removed.

**Opening measure (estimate — RE-MEASURED at the opening): ≈ 7.** A MOVE: `notFound` and `doneToday` leave
`AcquisitionQueue` (`contract/openapi.json`), the mock state (`mocks/state.ts`), the seeds and the handlers
(`mocks/handlers/acquisition.ts`) and `lib/queue.ts`; `npm run generate-contract-types`; `compare-contracts.py --write`
then `--check`; `check-mock-seeds`' classification updated. `takeable` keeps its reader (`follow-facts.ts`).

## Rule

A move: the gate's contract rules and guards, and a proof that no reader remains (`git grep` of both names over
`frontend/maquette/design/src` outside the generated types, zero).

## Commit

`refactor(maquette-l22): notFound and doneToday leave the contract`
