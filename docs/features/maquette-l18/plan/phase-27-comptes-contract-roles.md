# Phase 27 — « Comptes » — the contract and the mocks: roles

**New phase, born of ruling 20** (« Comptes gère les rôles (leurs droits) et l'attribution d'un rôle à chaque
compte »). The first drawing had no roles editor because it assumed three fixed roles with per-account options;
this phase declares the operations an ORDINARY role needs: create, rename, set its own rights from § 1.2's list.
Never Default's name, never Admin at all — its row is not editable by any operation this phase declares.

**Opening measure — re-take at this phase's own opening:**

- **Points ≈ 10.** three operations declared new — create a role, rename a role, set a role's rights (6) + the
  `Role` schema, its rights as a closed enum matching § 1.2's list exactly, ≈ 20 new lines (2) + the register
  regenerated (1) + a source hold that the enum and § 1.2's table never drift (1).
- **What to cut if the opening measure exceeds 15.** Not expected; if the rights enum needs its own generated
  file rather than a hand-kept list, that is a tooling question for the steward, not a point-count risk here.

**DESIGN § 1.2.1, § 3.9 points 2–3.** Two system roles are NOT reachable through these operations: Default's rights
ARE settable (a fourth operation, or the same `set a role's rights` operation applied to its own row — the phase
decides which at its own opening and records it) but its NAME and its undeletable status are not; Admin has no
row here at all.

## Red today

No role-level operation exists in the contract; `seeds/accounts.json` (phase 2) has no companion `seeds/roles.json`
to answer a roster read against.

## Move

Three new operations; `seeds/roles.json`, one row per seed role of § 2.2 (Household member, Plex guest, and the
two variants), each carrying its own rights list; `Role`'s schema.

## Mutation

**Nothing to mutate** — a contract is not a behaviour, per the first drawing's own phase 1 convention. The
mutation is by hand: drop a right from the enum that § 1.2 lists → `compare-contracts.py --check` and
`check-mock-seeds.py` fall.

## Register

—

## Oracle: states that diverge, declared by name

**None** — no surface reads any of it yet. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`docs(maquette-l18): the contract of roles — create, rename, set an ordinary role's own rights`
