# maquette-l20 — REPORT

L20, « The global levers and the history » (`docs/reference/frontend-architecture.md` § 4). Nine phases
on `feat/maquette-l20`, with L13b merged in at 9025348e6 (a merge, never a rebase). Rulings
`RULINGS-L20.md` 1–9; the running record is `RESUME-L20.md`'s ledger. Logs cited below live under
`~/Library/Logs/tm-l20/`.

## 1. The rule numbers, and each rule's red

| Label | Number | Script | Red reading |
| --- | --- | --- | --- |
| R-L20-a — a lever ACTS | R178 | `harness/levers.py` | 26 holds, 19 violations (phase 4, before the move) |
| R-L20-b — DOIT-4 on a lever | R179 | `harness/levers.py` | same run |
| R-L20-c — DOIT-6's figures | R180 | `harness/watch_run.py` | **NOT READ before the move** — rule and code were written in one pass (phase 5's deviation, said in its commit); its mutations below cover its claims |
| R-L20-d — §13, no answer that is not held | R181 | `harness/levers.py` | same run as R178 |
| R-L20-e — the history and its detail | R182 | `harness/run_history.py` | list half 14 / 13 (phase 6); detail half 23 / 9 (phase 7) |
| R-L20-f — B-296, the fold | R183 | `harness/raw_log.py` | 13 / 11 (phase 7) |
| R-L20-g — B-297, the locks and the agreement | R184 | `harness/locks.py` | 21 / 20 (phase 3); the agreement half 23 / 2 (phase 4) |
| R-L20-h — B-371, the path a hand takes | R185 | `harness/queued_by_hand.py` | **red against main does not exist: main has the path** (L13b's b·12). Red by MUTATION (ruling 8's Q2); its later holds (rulings 8 and 9) read red before their code |
| R-L20-i | R186 | — | unused (DESIGN § 6) |
| R-L20-j — the addresses | R187 | `harness/screen_addresses.py`, `harness/back.py` | 58 / 3 and 21 / 2 (phase 7) |

## 2. Every mutation, the hold that fell, and its words

| Phase | Mutation | Fell | Log |
| --- | --- | --- | --- |
| 3 | a skeleton over the whole locks block | R184 « locks/pipeline · pause-sentinel · watcher-sentinel still answers while the sweep is pending » (4 violations) | `p3-mutation-1.log` |
| 3 | the age dropped from a held lock | R184 « a held lock says so AND says since when » — `Pris —` | `p3-mutation-2.log` |
| 4 | the pause/resume verbs call nothing | R178 « pressing it CALLS pausePipeline — [] », « … resumePipeline — [] » | `p4-mut12.log` |
| 4 | the mock answers 409 to the pause | R179 « nothing was answered 409 — ['409 pausePipeline'] » | `p4-mut34.log` |
| 4 | the lever disagrees with the pause sentinel | R184 « levers-paused: the lever offered agrees with that sentinel » | `p4-mut34.log` |
| 5 | the veille's send removed | R180 « pressing it CALLS runDetection — [] », and its counts holds | `p5-mut.log` |
| 5 | the zero case drawn as three zeros | R180 « a veille that found nothing says so — '0 nouveaux épisodes détectés, 0 disponibles, 0 récupérés.' » | `p5-mutc.log` |
| 6 | the incomplete list stops admitting it | R182 « an incomplete list admits it » | `p6-mut.log` |
| 6 | a constant count where the layer said 1 | first run: **NO RULE FELL** — a weak hold, repaired; then R182 « the row's line is made of THOSE figures … must carry '1 rangé' » | `p6-mutb.log`, `p6-mutb2.log` |
| 7 | the fold `open` at rest | R183 « at rest its lines are NOT rendered » | `p7-mutation-a.log` |
| 7 | the missing log drawn as an empty box | R183 « a passage whose output was not kept says so » | `p7-mutation-b.log` |
| 7 | the fold pushes a history entry | R187 (`back.py`) « stacks nothing » (4 → 5) | `p7-mutation-c.log` |
| 7 | steps ahead said « pas faite » | R182 « each says — » | `p7-mutation-d.log` |
| 8 | the pipe verb's send made a no-op | R185 « the RUN OPERATION is answered … runPipeline answered [], status 'idle' » and « the « En file » pastille is PRESENT … 0 mark(s) » | `p8-mutation-a.log` |
| 8 | the mock re-queues a second pass | R185 « a second PIPELINE pass is answered 409 … [200, 200], status 'queued' » and its sentence hold | `p8-mutation-b.log` |
| 8 | the « ⋮ » panel's target back to `standby` | `panel.py` « the watch's panel offers its run » | `p8-mutation-c.log` |
| 9 | `disabled` removed from « Lancer » while running | R185 « « Lancer » is drawn INACTIVE … {'disabled': False} » and « asks nothing … [200, 409] » | `p9-mutation-d.log` |

**R181 has no mutation of its own on record** — its holds were run red with R178's and green after,
and no log shows a mutation aimed at §13's loading clause. Said rather than implied.

## 3. The figures this wave re-measured

- **Named states**: 87 before this lot (the `60530dbd8` blob of `engine/states.js`, and the eleven
  `harness/states/*.ts` files on the base), **113 on the final head** — the plan's own command:
  `python3 -c "import re,glob;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open(f).read(), re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"`.
- **`frontend/maquette/README.md`** said 54 three times; corrected on this branch WITHOUT a new
  number (a count written there goes stale — the line now says to ask `window.__states()`).
- **`docs/reference/product-intent.md`** says 82 (l. 330). **The operator's document; reported, not
  edited.**
- **The register's « required and missing »**: 15 before phase 1 (the plan's 14 was stale), 15 after
  it, 16 after L13b's merge (its own membership read).
- **Rule numbers**: the plan's « R160 » was stale; R177 was the highest at the base.

## 4. « Guards green over what they do not read » — this wave's recount

**7, all found by the wave, 0 by readers yet** (the reader round follows the pull request):

1. R184 « the row carries a value » compared the row's whole text against its part name's length —
   « Pause » + « Inactive » read as a value (phase 3).
2. R181's `levers-loading` drove the PAGE's loading phase and was green over the page-wide skeleton,
   proving nothing about the section (phase 4).
3. R180's counts probe read « the newest run », a real snapshot row older clocks put first, not the
   veille's (phase 5).
4. R180's success-word hold read the whole page, where the passages list says « réussi » about other
   runs (phase 5).
5. R182's count hold was satisfied by ANY number in the line — mutation B's constant 9 stayed green on
   the « 1 » of « 1 min 44 » (phase 6; `mutate.sh` said « NO RULE FELL »).
6. R183 read `offsetParent` alone, which is non-null over a CLOSED `<details>`' content (phase 7; the
   trap is now in `frontend/maquette/README.md`).
7. **The oracle is green over a control's WORD and LOOK changing**: ruling 9 turned « Relancer
   ensuite » into a disabled « Lancer » and `oracle.py --check` read 0 — it measures geometry, not the
   label nor the opacity. The divergence declared before that run did not occur (phase 9).

## 5. The debts this lot names and does not pay

- **The three raw `<details>` sites** (DESIGN § 9): `features/acquisition/add-screen.tsx:353`,
  `features/media/season-list.tsx:256`, `features/media/panel-seasons.tsx:142`, still raw after
  `ui/disclosure.tsx` exists. No lot claims them on this tree: **B-253's species**, filed for the
  steward's docs pull request (the register row numbers of ruling 4 collide — see § 8).
- **The composed passage line's counts**: `RunSummary` carries none; the line loses « 1 bloqué »
  because the real verify step has no blocked count — a backend demand, not invented.
- **A failed run's steps with the failing one named**: the contract's demand line (ruling 7).

## 6. Divergences, named

- Phases 3–7: each accepted inside one heavy invocation and verified by name (the ledger carries each
  reading): 87×34 → 92×35 → 104×36 → 107×37 → 113×38.
- Phase 8: zero, as the plan expected (`arr-queued`'s drawing unchanged).
- Phase 9: ruling 9 — zero (see § 4 item 7); the accessibility repair — 130 geometric divergences on
  exactly the 26 Système states × `system/levers`, `system/locks`, `system/runs`, `system/body`,
  `shell/page`: the levers' `cardFoot` buttons add 16 px, the locks and the passages move down, the
  body and the page grow by 18–19 px. Accepted at bae474c9, verified by name.

## 7. Hold counts

The repository's baseline is NOT re-recorded on this branch (the steward's word at phase 9: the
squash baseline lands with L13b's docs pull request). Compared against a copy whose
`taken_at_commit` is re-pointed at 5df76af33 — the movements and their causes are in the pull
request's body, measured on the final head.

## 8. What the steward's docs pull request carries

- The clause-map proposal (DESIGN § 10), **proposed here, amended by the operator**: DOIT-3 the levers'
  half `served` (R178, R179); DOIT-4 `partly` → `served` (R185, R138 unchanged at 7 holds); DOIT-6
  `served`, naming two operations (R180, R182, R183); NE-DOIT-PAS-2 the locks called (R184), who holds
  the lock behind « En file » stays L19's line; NE-DOIT-PAS-5 unchanged, `degraded` a new instance
  (R182). **DOIT-5 not touched.**
- **Register row numbers**: ruling 4 gave L20 B-530 onward, and `main` has since used B-530
  (`fixed #598`). The next free number on this tree is B-531.
- The register row for ruling 9's control, and the `IMPLEMENTATION.md` « In flight » row.
- B-383 is already `fixed #592` on `main` in full; its veille half needs no closure here.
