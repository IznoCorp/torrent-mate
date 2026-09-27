# Phase 4 — The refusal — the guard mechanism, and the original write families

**Amended 2026-09-27** (renumbered from the first drawing's phase 4; this file's OWN cut clause anticipated the
split it now takes — F28, F30): this phase keeps the guard's SIGNATURE, the ONE guard function, R-L18-c's rule
and mutations, and the write sites this document's first drawing already counted (acquisition, pipeline,
configuration, accounts — ≈ 29–32 by the time it runs). **Two new siblings carry what grew past this phase's own
15-point ceiling**: phase 5 names the write families F28 adds (`library.delete`/`.rescrape`, `trackers.control`,
the staging writes, `setAcquisitionPause`); phase 6 (F30) adds the READ side — no phase named it before, and
`see.others` stays a subset filter on a 200, never a right this sweep 403s. Re-estimated at **14** (was 15,
trimmed now that the newer write families have their own phase to grow in).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `git grep -c 'route(' -- frontend/maquette/design/src/mocks/handlers` sums **64** (63 operations and the definition in `shared.ts`, 61 lines) over 13 handler files: `acquisition.ts` 15, `pipeline.ts` 9, `configuration.ts` 7, `system.ts` 7, `library.ts` 5, `decisions.ts` 4, and seven others of 3 or fewer.
- `git grep -c "refused(" -- frontend/maquette/design/src/mocks ':!*.test.ts'` → `acquisition.ts` 1, `pipeline.ts` 2, `router.ts` 1 (the definition): **the mock refuses with a `403` nowhere**, though 62 operations declare one.
- The 29 writes, by contract: `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted(o['operationId'] for v in d['paths'].values() for m,o in v.items() if m in ('post','put','patch','delete')))"` → 29 (plus the three phase 1 declares, so 32 by the time this phase runs; **the sweep counts what the contract holds at that moment, not this figure**).
- `frontend/maquette/design/src/mocks/router.ts` — `refused(status, detail)` and `settled()`; `answered.ts` records what was answered.
- **Points ≈ 15.** `route()` takes the right — the signature and its callers' type, ≈ 15 lines edited in `shared.ts` and `router.ts` (3) + the ONE guard function, ≈ 30 new lines (3) + 29 write sites name their right, one line each (6) + R-L18-c with its mutations (3).
- **What to cut if the opening measure exceeds 15.** At 15 already. If the opening measure of the 29 sites exceeds 15, the naming of the 29 sites becomes its own phase BEFORE this one, and this phase keeps the signature, the guard and the rule (9).

**DESIGN § 2.2, « The refusal — ONE guard, not thirty ».** NE-DOIT-PAS-7 kept in the mock as in the engine: **one authorisation path**, thirty handler sites that only NAME their right. The guard imports the model of phase 3, reads the dialled identity and the ceiling, and answers `refused(403, …)` with the contract's `Problem` body, recorded by `answered()`. **The table of write → right is § 1.2's**; an act the table misclassifies is reported (STOP D), not reclassified.

## Red today

**R-L18-c — the refusal side, everywhere**: for each write and each identity lacking its right, the call forced by `fetch` is answered `403` with the `Problem` body and `answered()` records `403`; for the Operator the same call answers as before.

**Red against `main`**: the mock answers 200 to every write, for every identity.

## Move

`route()` takes a right; the guard; the 29 sites. The Operator holds every right, so **no existing behaviour moves**.

## Mutation

With the commit made first: drop the right from one route's declaration → the sweep names that operation; make the guard let an option through unread → the option's pair falls; answer the Operator `403` → the resting hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** — the guard lets the Operator through everywhere. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): one guard in the mock refuses a write the account has no right to`
