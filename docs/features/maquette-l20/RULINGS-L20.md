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
