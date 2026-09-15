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

## 5 — `locks-orphans` and `locks-stale` (steward, 2026-09-14)

Option (a), with its provenance SAID. The orphan entry is the one real name pipeline_run's captured
output holds — `/Volumes/Disk1/medias/films documentaires/_tmp_dispatch_Big Chicken Le complot de la
malbouffe (2026)`, run `ccc29054` — its age taken from that run's timestamps, and the seed's note reads
« the `_tmp_dispatch_` folder of run ccc29054 as its captured output names it; the run succeeded, so the
folder is a transient read as an orphan for the drawing — the backend's locks read will list real
orphans with their age », that sentence also a backend demand line in the register. The 26 states
stay. (b) — dropping the state — refused. `locks-stale` by a layer dial (+3 lines in `mocks/index.ts`).

## 6 — the oracle acquires the served copy (steward, 2026-09-14)

After phase 4's gate, a small tooling commit of L20's: `oracle.py --accept` and `--record` ACQUIRE the
served copy (`served_copy.py --acquire`, as `run.sh` and `mutate.sh` do) and assert its stamp is the
current head before writing. A bare accept over a foreign build must REFUSE, never rewrite the
reference. Its test is written FIRST, in the oracle's own test file, and seen red.

## 7 — phase 7: a run in flight, a run nobody holds, a failed run's steps (steward, 2026-09-14)

As the implementer proposed. (1) `run-detail-running` is DERIVED from the snapshot's first pipeline row
(2b598104) by a layer dial, `setRunInProgress`: its first five steps verbatim, the sixth live and
knowing nothing, the rest absent — the provenance in the dial's comment and the ledger, ruling 5's
shape; the remaining steps are named from the interface's own pipeline step order. (2) `readRun`
answers 404 for an unknown run through a `refused(404, detail)` helper in `mocks/router.ts`,
`mocks/index.ts` at zero net lines; the screen draws the sentence and a way back to Système. (3)
`run-detail-failed` draws the error whole and marks NO step — the only real failed row records none;
the rule does not hold « a step marked » there, and the contract carries one demand line: a failed
run's steps with the failing one named.

## 8 — phase 8: a second pipeline pass is refused, and the queue is the maintenance lock's (auditor, § 10, relayed by the steward, 2026-09-15)

Q1 = A. The mock answers 409 to a second PIPELINE pass and queues only under a MAINTENANCE lock
(DESIGN § 3.2 l.222–228, validated at #587); the verb gains one fr.json sentence for the 409 (never
« arrêté »); b·12's comment in `features/arrivals/verbs.ts` is rewritten to say so; `arr-queued`'s
precondition becomes a maintenance lock, its drawing unchanged, oracle 0 expected (any divergence is
STOP B); R138 re-read with its hold count unchanged; second mutation: the mock re-queues a second
pass → the 409 hold falls by name. Q2: R185's red is a mutation-red (the verb's send made a no-op →
holds 4 and 7 fall by name), said as « red against main does not exist: main has the path ». Phase 8
= R185 + this; then the FULL suite at `TM_HARNESS_JOBS=2` (B-369's precondition moves), `--a11y`,
and phase 9 closes.

## 9 — « Lancer ensuite » while a pass runs (auditor, § 10, relayed by the steward, 2026-09-15)

« Lancer ensuite » becomes « Lancer » DISABLED while a pass runs (§ 12: an inactive action looks
inactive), enabled again at idle; the queue is offered only under a maintenance lock. Owner: L20
phase 9 — the lot that moves the premise carries its consequence in the same pull request. About 3
points, one hold, red first (the disabled state under `running`), one mutation; the register row goes
in L20's own docs pull request. Phase 8 stays as ruled 8 says; this is not folded into it.
