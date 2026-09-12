# Phase 1 — The contract (D7)

Every surface of this lot calls an operation. Four of them the maquette's contract does not declare,
three carry a shape the backend contradicts, and one configuration key does not exist anywhere. This
phase settles all of it, and it is FIRST because `scripts/compare-contracts.py --check` refuses the
three artefacts apart and because the demands are what make DESIGN § 3.2's divergences decisions
rather than discoveries.

## First, bind the rule numbers

    git remote update origin >/dev/null && grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1

Re-take it against this branch's base at the moment this phase runs, then bind `R-L20-a` … `R-L20-j`
(DESIGN § 6) to consecutive free numbers and write the mapping into the report. **A number taken
from the design document without re-measuring is a collision**: R161–R164 are on #585's unmerged
branch and the `maquette-settings` micro-wave takes R165+.

## No rule in this phase, and that is stated rather than skipped

A contract is not a behaviour: what holds it is `scripts/compare-contracts.py --check`, the generated
`contract/types.d.ts`, and `scripts/check-mock-seeds.py`. The rules that read these operations are
written in phases 3 to 8, each beside the surface that calls it. **A phase with no rule says so;
it does not invent one to look complete.**

## The move

### 1. Declare the four missing operations in `frontend/maquette/contract/openapi.json`

| operation | operationId | answers |
| --- | --- | --- |
| `POST /api/pipeline/watcher` | `setWatcher` | `{watcherEnabled: boolean}`, body `{enabled: boolean}` |
| `GET /api/pipeline/history/{runUid}` | `readRun` | `RunDetail` — DESIGN § 3.1 |
| `GET /api/maintenance/locks` | `readLocks` | `{pipelineLock, sentinels, sweep}` |
| — | — | the bound is NOT an operation: it is a configuration key, point 4 below |

Names are camelCase, as every other operation of this contract is; the path parameter is `runUid`,
not `run_uid` (the register's « path parameter spelled differently » column exists for that and
carries 14 entries already).

### 2. Re-shape the three the backend contradicts

- **`readPipelineHistory`** — from a bare array to `{runs: RunSummary[], total, degraded}` with
  `limit`, `offset`, `sort`, `kind`. **`degraded` is load-bearing**: it means the read failed and
  the list may be silently short, and printing a short list as complete is NE-DOIT-PAS-5.
- **`runDetection`** — from `{detected, available, grabbed}` at 200 to `{runUid}` at **202**. The
  figures are then read from `readRun`. DESIGN § 3.2 point 2 carries the reason and the backend
  docstring that states it.
- **`runPipeline`** — the interface follows the backend: a second PIPELINE run is answered **409**
  (§6's strict duplicate), and the queued answer happens only when a MAINTENANCE run holds the lock.
  **The mock's handler changes in phase 8, not here** — it moves a named state's precondition, and
  that belongs with the phase that repairs the path (DESIGN § 3.2 point 3).

### 3. The mocks, and each MOVES something

`frontend/maquette/design/src/mocks/handlers/` — the pipeline routes live in `staging.ts` today,
which is **156 non-blank lines** (`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/staging.ts`),
comfortably under the 400 ceiling. **So the new handlers are a new file
`mocks/handlers/pipeline.ts` for a reason of SUBJECT, not of size**: the pipeline's levers, its
history and its locks are not staging, and `staging.ts`'s own name is the argument. The file is
registered in `mocks/handlers/index.ts` and the pipeline routes move out of `staging.ts` with the
subject they belong to — which is a move, so it lands with the `--check` that proves the route
table is unchanged in COUNT.

What each must move (D7 — « a mock that answers without moving certifies nothing »):

- `setWatcher` writes ONE field, which `readLocks` projects as `sentinels.watcherPaused` and
  `readPipeline` projects as `watcherEnabled`. **Two projections of one field, never two fields** —
  §13, and R-L20-g reads the agreement.
- `pausePipeline` / `resumePipeline` move `pipelineState` AND the `pause` sentinel with an age.
- `readLocks` derives `pipelineLock.held` from `pipelineState` and carries `stale`, `ageS`, and the
  sweep's `status: "pending"` → `"ready"` transition on the layer's own deterministic clock (never
  jittered — `mocks/scenario.ts` says why).
- `runDetection` appends a run to the history with `outcome: "running"`, then ends it with its
  counts, so `readRun` has something to answer and `veille-running` is a real state.
- `readRun` answers from the same appended rows — one source, so the list and the detail cannot
  disagree.

Seeds: `mocks/seeds/pipeline-executions.json` gains a `runUid` per row (it has none today:
`python3 -c "import json;print(sorted(json.load(open('frontend/maquette/design/src/mocks/seeds/pipeline-executions.json'))[0].keys()))"`
reads `['cause', 'result', 'succeeded', 'when']`), and a seed for the locks. Every seed is derived,
never invented — `python3 scripts/build-mock-seeds.py --write` then `python3 scripts/check-mock-seeds.py`
in the SAME commit; the correspondence arm re-derives on every run, so a hand-written seed is a red
guard.

### 4. The parallelism bound — a demand, not a read

It exists in no configuration file (DESIGN § 8.3, with its commands). Declared as a configuration
key the settings read answers: file `pipeline`, key `pipeline.tunnels.max_parallel`, type `number`,
topic `service` (« Ce qui tourne »), note « Combien de médias peuvent être traités en même temps. »
The mock's settings seed carries it so Système can DRAW it and its panel can edit it. **The topic
assignment is named here so nobody invents a seventh topic for one key**; the settings catalogue
confirms it.

### 5. Regenerate, and read what came out

    python3 scripts/compare-contracts.py --write     # rewrites docs/reference/frontend-backend-demands.md
    python3 scripts/compare-contracts.py --check
    npm --prefix frontend/maquette/design run generate-contract-types   # → src/contract/types.d.ts

**Read the regenerated register's counters and put them in the report**, before and after. « required
and missing » was 14 and must move; a register that did not move means the contract edit did not
land, and a failed command is an edit that did not happen.

## Gate

`HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh l20 frontend/maquette/harness/run.sh --contracts`
(announced to the steward before and after); `python3 scripts/check-mock-seeds.py`;
`compare-contracts.py --check`. The oracle: **zero divergence everywhere** — no surface changed.

## Commit

`feat(maquette-l20): the contract of the global levers, the history and the locks`
