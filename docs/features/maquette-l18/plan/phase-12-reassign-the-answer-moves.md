# Phase 12 — The reassign gesture — the answer moves

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([o['operationId'] for v in d['paths'].values() for o in v.values() if isinstance(o,dict) and 'reassign' in o.get('operationId','').lower()])"` → `[]` today; phase 1 declares it (keyed by the card's identity — one row or two).
- `sed -n 1,30p frontend/maquette/design/src/mocks/state.ts` — every value of the mutable state comes from a seed; a reassignment must MOVE what the next read returns (D7).
- The invented cards of phase 8 give the reassignment somewhere to go.
- **Points ≈ 8.** the `reassignRequester` handler, new; its right named (2) + the lists re-derive from the moved requester (1) + the toast's sentence (1) + one state, `acq-reassign-done` (1) + R-L18-j with its mutations (3).

**DESIGN § 3.5, § 2.2 (« the mocks MOVE »).** The reassignment changes whose list the card is on and the requester line it draws; **the tunnel is unaffected** — a tunnel belongs to the medium (§ 20), the requester is a property of the medium's acquisition. The refusal half: forced by the Member, the call answers `403` (the guard, phase 4).

## Red today

**R-L18-j — the reassignment moves**: a reassignment is ANSWERED on the network (`window.__mocks.answered()`), the card is on the new account's list and off the old one's, its line reads the new name; forced by the Member, the call answers `403`.

**Red against `main`**: no operation is answered.

## Move

The handler, the re-derivation, the toast, the state.

## Mutation

With the commit made first: toast without calling → the network hold falls; do not move the card → falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-reassign-done` is new. **None** otherwise. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): a reassigned request changes hands — its card, its line, its list`
