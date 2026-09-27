# Phase 6 — The refusal — the read side

**New phase, born of F30**: « the refusal side of every page-view right (the reads) has no phase: phase 4 names
rights on writes only. » A right that gates a VIEW must refuse a forced read exactly as a right that gates a write
refuses a forced call (§ 17 « des deux côtés et séparément » names no exception for reads).

**Opening measure — re-take at this phase's own opening:**

- **Commands.** `git grep -c 'route(' -- frontend/maquette/design/src/mocks/handlers/system.ts frontend/maquette/design/src/mocks/handlers/maintenance.ts frontend/maquette/design/src/mocks/handlers/trackers.ts frontend/maquette/design/src/mocks/handlers/configuration.ts` for the read sites under `/api/system`, `/api/maintenance`, `/api/trackers` and the configuration reads (`/settings/*`, including `/settings/ranking` per F31).
- **Points ≈ 9.** ≈ 8–10 read sites naming their right, one line each (2) + R-L18-c EXTENDED to cover reads, one
  mutation added (« drop a view right → the read sweep names it ») (1) + the hold that `acquisition.see.others`
  stays a SUBSET FILTER on a 200 and is never itself a 403 producer (2) + the contract's `403` response added to
  each named read operation (2).
- **What to cut if the opening measure exceeds 15.** Split Réglages' own reads (`configuration.view`, the larger
  family per F31) into their own phase.

**DESIGN § 1.2, the refusal column of `trackers.view`, `system.view`, `configuration.view`.** § 17: the Member has
« ni visualisation ni modification de la configuration » — a VIEW right that is never offered still needs its
call refused, because a forced `GET` past the absent offer is exactly the shape § 17 point 1 forbids in the other
direction.

## Red today

Every read under `/api/system`, `/api/maintenance`, `/api/trackers`, the configuration reads: 200 for every
identity, no `403` declared.

## Move

Name the right; add `403` to the operation; no existing behaviour moves for Admin.

## Mutation

Drop a view right from a read site → the sweep names it; make `acquisition.see.others` answer `403` instead of a
filtered 200 → the subset-filter hold falls (the mutation that proves reads and see-others are NOT the same
mechanism).

## Register

—

## Oracle: states that diverge, declared by name

**None**. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the refused reads — Système, Maintenance, Trackers and the configuration answer 403`
