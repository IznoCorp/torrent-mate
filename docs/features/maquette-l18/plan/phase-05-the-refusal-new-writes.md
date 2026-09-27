# Phase 5 — The refusal — the new write families

**New phase, born of F28** (the coherence audit: « enumerate every act from the contract as it will stand when
L18 opens, each as its own ACL right »). Phase 4 named the guard mechanism and the write families the first
drawing already knew about; this phase names the families § 1.2's growth added, on the SAME guard — one route
table, no second mechanism.

**Opening measure — re-take at this phase's own opening, against the head it actually runs on (L16 and L17 have
landed; L22b may not have by then):**

- **Commands.** `git grep -c 'route(' -- frontend/maquette/design/src/mocks/handlers/trackers.ts frontend/maquette/design/src/mocks/handlers/staging.ts` (post-L16/L17/L22b) for the tracker-control and staging-write sites; `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([o['operationId'] for v in d['paths'].values() for m,o in v.items() if m in ('post','put','patch','delete')])"` diffed against phase 4's own list to find exactly what is new.
- The families this phase names, per DESIGN § 1.2: `library.delete` / `library.rescrape` (the split of the first
  drawing's single `library.write` — two sites re-declaring their right, not new operations); `trackers.control`
  (the tracker cross-seed switch and its confirmation option, « Retirer de qBittorrent », « couper le cross-seed »
  per torrent/tracker, « Chercher un cross-seed », « Ne plus partager ce titre » — L16/L17's own writes as they
  stand once L18 opens, F28); `pipeline.control`'s growth (`reclassifyStagedMedia`, `restoreReclassifiedMedia`,
  `resolvePlexMatch`, round 8 Q16's staging delete — all Operator/Admin-default per F28); `setAcquisitionPause`
  (phase 1's own new operation, demand P).
- **Points ≈ 10.** ≈ 10–13 write sites naming their right, one line each (2–3) + the two `library.write` sites
  re-declared to the split rights (1) + R-L18-c's sweep extended over the new families, no new rule (its
  mutation is re-run, not re-written) (1) + the source hold that `trackers.control` and `pipeline.control`'s
  growth match § 1.2's table exactly (2).
- **What to cut if the opening measure exceeds 15.** Split staging writes (pipeline.control's growth) into their
  own phase, cut BEFORE this one — the tracker-control family alone is unlikely to exceed 10.

**DESIGN § 1.2's rights table, the `trackers.control` and `pipeline.control` rows.** The guard of phase 4 is
UNCHANGED in shape; only the route table grows.

## Red today

The families this phase names answer 200 to every write, for every identity — no route on `/api/staging`,
tracker-control or `setAcquisitionPause` names a right yet.

## Move

Name the right on each new write site; no existing behaviour moves (Admin holds every right).

## Mutation

Drop a right from one of the new sites' declarations → the sweep (re-run from phase 4, extended) names that
operation.

## Register

—

## Oracle: states that diverge, declared by name

**None** — Admin passes through everywhere. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the guard covers the tracker-control, staging and pause write families`
