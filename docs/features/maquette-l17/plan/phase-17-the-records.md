# Phase 17 — The records

**No OPEN question**; the count of states it records is fixed now that every OPEN question is ruled — twelve
(DESIGN § 4), not a conditional nine-to-eighteen.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `python3 -c "import json;o=json.load(open('frontend/maquette/oracle-reference.json'));print(o['counts'])"`
  → today's counts (L22 and L16 move both before L17 opens); `python3 -c "import json;d=json.load(open('frontend/maquette/a11y-debt.json'));print(list(d))"`
  → `takenAtCommit`, `platform`, `counts`, `states` (the same keys in `a11y-light-debt.json`);
  `frontend/maquette/hold-counts-baseline.json` and `python3 scripts/harness-hold-counts.py --compare`; `python3 -c
  "import json;r=json.load(open('frontend/maquette/regions.json'));print(len(r['regions']))"`. The region this lot
  adds: `torrents/cross-seed` (phase 6).
- **Points ≈ 8.** The oracle reference records the new states (a re-record, NOT an acceptance — new states have no
  prior reading) 1; `regions.json` gains one region 1; the accessibility tier over the new states in both themes 2
  (their debts, if any, recorded and never lowered); the hold-counts baseline re-recorded AFTER `failed` reads zero
  (B-291) 1; the `harness/states.py` seed list 1; the fixture-register's last read 1; the ratchets that must not
  fall 1.
- **Found.** The records are the tooling's memory of the lot; the phase that leaves them stale hands the next lot a
  false zero.

## Red today

None — records are not rules.

## Move

1. Re-record the oracle reference for the new states only; **read every existing state's divergence FIRST against
   the FULL list of phases § 4.1 now names (1 through 16, not merely up to 13, F61)** and stop (STOP A) on any not
   named there.
2. `regions.json`, the accessibility records, the hold-counts baseline (after `failed` is read).

## Mutation

None.

## Register

—

## Oracle: states that diverge, declared by name

None — this phase records; it accepts nothing.

## Gate

Per INDEX « Gates »; `python3 scripts/harness-hold-counts.py --compare` with `failed` read FIRST.

## Commit

`chore(maquette-l17): the oracle, the accessibility and the hold counts record the cross-seed states`
