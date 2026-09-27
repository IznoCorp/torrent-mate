# Phase 38 — Readers re-aimed: the page's identity and the launch bar

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n -E 'data-page="arr"|PAGE_PATHS\["arr"\]|ARRIVALS' -- 'frontend/maquette/harness/*.py'` →
  `back.py:98`, `common.py:518` (`ARRIVALS = PAGE_PATHS["arr"]`), `locks.py:157` (`ARRIVALS_TAB`) and `:274,283`,
  `queued_by_hand.py:206,268,272,319`, `sweep.py:15`, `url_state.py:167`. `git grep -c -E 'data-pipe([^l]|$)' -- 'frontend/maquette/harness/*.py'`
  → `arrivals.py` 6, `locks.py` 2, `page_host.py` 11, `queued_by_hand.py` 3 — the four files that START the pipeline by a
  finger on the bar (the pattern keeps Système's `data-pipeline-pause` and `-resume` out, which the bare prefix would match). `page_host.py:706-770` is the page's own delegation block and its « crossref » hold.
  `queued_ask_mark.py` (R138) and `selection_survives_the_tab.py` name « Arrivées » in prose; `machine.py` (R67) carries
  « a medium in trouble is Arrivées » as its premise.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: `data-pipe` (start and stop)
  in the same four files at 6, 2, 11, 3; the identity command answers **15 lines in 8 files, not the 11 lines in 6 files listed
  above** — the first drawing missed `journey.py:90,419`, which reads the page's path through the `ARRIVALS` constant (an import
  and `path(pg.url) == ARRIVALS`), neither of the design's commands matches that spelling; `add_screen_opens_fresh.py:40` and
  `back.py:107` only carry the word in comments. **Points 14 → 15: OPEN 6 (ruled A) moved the drawing, and the re-measure found
  the ninth reader** (+1 for `journey.py`, which re-aims with `common.py`'s constant). What to cut if the opening measure
  exceeds 15: `journey.py` and `common.py` (the constant) form a phase of their own after this one.
- **Found (2026-09-26).** **OPEN 6 is ruled A: « Lancer » and « Arrêter » a pass die with the bar, and no lever takes them over.**
  The four rules that started a pass by a finger on the bar therefore RE-AIM, and **this phase says out loud, file by file, where
  each goes** — the report carries the same table with the site counts re-taken:

  | File (rule) | `data-pipe` sites | Where it goes |
  | --- | ---: | --- |
  | `queued_by_hand.py` (R185) | 3 | onto the path a hand still has: a maintenance command holds the lock, then a season is asked — the `season/queued` pastille (DESIGN § 6.1). Written RED against that path before it is moved; B-371's « no `__go` between the hand and the pastille » holds for the season path only |
  | `locks.py` (R-L20-g) | 2 | its start and stop walk loses the bar's buttons; the walk keeps Système's lock reading and reaches a held lock by the maintenance path, said in the report |
  | `page_host.py` (R77) | 11 | its delegation block (`:706-770`, `:908`) proves that a page migrated to React still has its document-level handler write — here, on the bar's two buttons. Hold by hold, each is RE-AIMED onto another migrated page's delegated act, or reported as dying with its subject (the two acts); the report names which, for each of the eleven sites |
  | `arrivals.py` (R66) | 6 | NOT edited here: it dies with the page in phase 37, and the phase-25 report says where each of its holds went |

  B-371's shape holds for the SEASON path only, by the operator's acceptance of the cost.
- **Points ≈ 15.** `back.py`, `common.py`, `sweep.py`, `url_state.py`, `locks.py` (the tab reference and the start/stop
  walk, a second touch after phase 19) at 1 each plus 1 for the walk 6; `journey.py` 1; `page_host.py` (11 `data-pipe` sites and
  the crossref block) 3; `queued_by_hand.py` (R185 re-aimed, a second touch) 3; `queued_ask_mark.py` (R138's screen half
  re-pointed at Système's levers, B-514) 1; `machine.py`'s premise sentence 1; R66's surviving holds re-homed, the rest
  reported as dying 0 → 15.

`arrivals.py` (R66) is NOT edited here: its pilot's-bar half dies with the bar, its « says what really happened » half
read the operator's live databases and dies with the page, its stuck-cards half is R-L22-g's and R-L22-h's. **The
phase's report says, hold by hold, where each of R66's holds went** (phase 37 removes the file) — a rule is never deleted
without saying where its subject lives (DESIGN § 6.3).

## Red today

**No new rule.** Each re-aimed rule is replayed and must hold what it held; `scripts/harness-hold-counts.py --compare`
with `failed` read FIRST. R185 (`queued_by_hand.py`) is the exception that matters: it is written RED against the
launch-bar-free path it will walk (the maintenance-held queue and `season/queued`) before it is moved.

## Move

Re-aim the ten files onto Acquisition (the page id and path → the Acquisition ones; the launch walks → the path the ruling
leaves, table above); re-point R138's screen half and B-514 with it; state R66's holds' destinations in the report.

## Mutation

R185 keeps its own: the pastille removed → the network hold falls (`scripts/mutate.sh`, after the commit). The others keep
theirs, one per file, reported.

## Register

B-371 (`fixed #603`, its walk re-aimed), B-514 (closed or re-pointed, said in the report).

## Oracle: states that diverge, declared by name

**None.** Any divergence is STOP A.

## Gate

Per INDEX « Gates »; the ten files run by name.

## Commit

`test(maquette-l22): the rules that named the Arrivées page or its launch bar name their successors`
