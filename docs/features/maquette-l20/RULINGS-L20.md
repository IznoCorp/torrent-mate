# maquette-l20 — rulings

Numbered from 1, appended by the steward and by the implementer when a decision is made on the day.
Never rewritten: a ruling that changes is superseded by a later one naming it.

## 1 — the rule numbers (steward, 2026-09-14)

No reservation beyond R177 exists on any branch (L13b's grep for R178+ is empty; `R177` is the
highest on this branch, `grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1`).
L20 binds its labels to R178–R187; L13b's future rules start at R188.

| label | number |
| --- | --- |
| R-L20-a — a lever ACTS | R178 |
| R-L20-b — DOIT-4 on a lever | R179 |
| R-L20-c — DOIT-6's figures | R180 |
| R-L20-d — §13, no answer that is not held | R181 |
| R-L20-e — the history and its detail | R182 |
| R-L20-f — B-296, the fold | R183 |
| R-L20-g — B-297, the locks and the agreement | R184 |
| R-L20-h — B-371, the path a hand takes | R185 |
| R-L20-i — does not exist (DESIGN § 6); its number stays unused | R186 |
| R-L20-j — the addresses | R187 |

## 2 — standing method points (steward, 2026-09-14)

Gate logs under `~/Library/Logs/tm-l20/`. The shared mutex is shared with `Agent : l13b 2`: one line
to the steward before and after every wrapped harness run, never a build beside its run. Harness
tiers as SEPARATE invocations (`run.sh --contracts`, then `oracle.py --check`), `TM_HARNESS_JOBS=2`,
until L13b's tooling reaches `main`. Phase 8 opens only on the steward's word, after L13b merges.

## 3 — where the runs' and the locks' data come from (steward, 2026-09-14)

Option A. `PIPELINE_RUNS` → `seeds/pipeline-runs.json`, a converted-class family with no engine
origin (« L20 phase 1 — a SNAPSHOT of real pipeline_run rows, read-only from library.db, never an
engine literal »). The rows are taken ONCE from `library.db` read-only (`sqlite3 "file:<path>?mode=ro"`,
the exact query in the commit body), never at check time; trimmed to what `RunSummary`/`RunDetail`
need — steps from `steps_json`, an `outputTail` only where a row has one, `error` as stored. A field
the contract needs that no real row carries is ABSENT from the seed and said in the register as a
backend demand, never made up. The locks handler is `x-unseeded`, deriving from state and the scenario
clock; the sweep from the same snapshot or none. `EXECUTIONS` stays untouched until phase 6.
B (subtract `EXECUTIONS` from legacy.js now) refused — phases 1–7 are engine-free and L13b would
conflict. C (authored rows) refused — « never invented ».
Secondary: phase 1 re-shapes `readPipelineHistory`, `features/system/queries.ts` unwraps `.runs` in the
same commit, oracle at zero; the history items carry `EXECUTIONS`' verbatim fields beside `runUid`
until phase 6. The register's « required and missing » is 15 measured (the plan's 14 is stale).

## 4 — the register's row numbers (steward, 2026-09-14)

`main`'s `BUGS.md` ends at B-511 (the docs PR #597, squash `4f242ecb3` — this branch's base); L13b holds
B-512–B-529; L20's rows start at **B-530**, counted up, so the two open branches never collide.
