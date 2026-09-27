# Phase 15 — « Suivre » and the request

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `wc -l frontend/maquette/design/src/features/acquisition/add-screen.tsx frontend/maquette/design/src/features/acquisition/add-verbs.ts frontend/maquette/design/src/features/acquisition/panel-add.ts frontend/maquette/design/src/features/acquisition/discover-tab.tsx` → **391, 120, 96, 216**; the maquette's only way to ask is `createFollow` (`POST /api/acquisition/followed`).
- L22's ruling 1 keeps a PUNCTUAL acquisition distinct from a follow; L22 phase 17 proposes « Suivre » on an arrival's card, phase 18 ends a film's follow alone.
- **Reads OPEN 6.** Reading A — the guest follows like the Member, the phase only gates the offers by role. Reading B — a « Demander » act, an operation of its own and no « Suivis » tab for the guest: **the phase is CUT at its opening into 15 and 15-bis** (below).
- **Points ≈ 6** (reading A: 6 · reading B: 17). The base counted here: the offers by role on the follows tab and Découvrir — three sites, ≈ 15 lines (3) + R-L18-m with its mutations (3).

**DESIGN § 3.4 point 6.** Under reading A the guest's « demande d'acquisition » IS the follow: the phase gates the offers by role and the roles differ by the quality option and the rest of § 17. **Under reading B** the phase becomes two: **15** — the operation `requestAcquisition` (declared 2, handler 2), the « Demander » act on Découvrir ≈ 30 new lines (3), two sentences (2), one state (1) = 10; **15-bis** — the offers by role (3), one state (1), R-L18-m (3) = 7. The sum with B is +11.

## Red today

**R-L18-m — « Suivre » and the request**: per the ruled reading, the offer per role and the guest's act as ruled; forced `createFollow` for an account without `acquisition.follow` answers `403`.

**Red against `main`**: every account is offered « Suivre ».

## Move

The offers' filter (A), or the act and its operation (B).

## Mutation

With the commit made first: offer « Suivre » to the guest under reading B → R-L18-m falls; under A, offer it to the rights-less account → falls.

## Register

—

## Oracle: states that diverge, declared by name

**None for the Operator.** Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the follow and the request are offered by role`
