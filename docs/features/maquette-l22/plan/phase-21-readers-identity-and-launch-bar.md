# Phase 21 — Readers re-aimed: the page's identity and the launch bar

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n -E 'data-page="arr"|PAGE_PATHS\["arr"\]|ARRIVALS' -- 'frontend/maquette/harness/*.py'` →
  `back.py:98`, `common.py:518` (`ARRIVALS = PAGE_PATHS["arr"]`), `locks.py:157` (`ARRIVALS_TAB`) and `:274,283`,
  `queued_by_hand.py:206,268,272,319`, `sweep.py:15`, `url_state.py:167`. `git grep -c 'data-pipe' -- 'frontend/maquette/harness/*.py'`
  → `arrivals.py` 6, `locks.py` 2, `page_host.py` 11, `queued_by_hand.py` 3 — the four files that START the pipeline by a
  finger on the bar. `page_host.py:706-770` is the page's own delegation block and its « crossref » hold.
  `queued_ask_mark.py` (R138) and `selection_survives_the_tab.py` name « Arrivées » in prose; `machine.py` (R67) carries
  « a medium in trouble is Arrivées » as its premise.
- **Found (2026-09-26).** **B-371's shape holds for the SEASON path only if OPEN 6 reads A**: the walk that started a
  pass from Arrivées (R185) re-aims onto a maintenance command holding the lock, then a season asked
  (DESIGN § 6.1). Under reading B the launch buttons live on Système and R185 keeps a finger on them. The phase
  is drawn to cost the same under either reading and says which one it took.
- **Points ≈ 14.** `back.py`, `common.py`, `sweep.py`, `url_state.py`, `locks.py` (the tab reference and the start/stop
  walk, a second touch after phase 17) at 1 each plus 1 for the walk 6; `page_host.py` (11 `data-pipe` sites and the
  crossref block) 3; `queued_by_hand.py` (R185 re-aimed, a second touch) 3; `queued_ask_mark.py` (R138's screen half
  re-pointed at Système's levers, B-514) 1; `machine.py`'s premise sentence 1; R66's surviving holds re-homed, the rest
  reported as dying 0 → 14.

`arrivals.py` (R66) is NOT edited here: its pilot's-bar half dies with the bar, its « says what really happened » half
read the operator's live databases and dies with the page, its stuck-cards half is R-L22-g's and R-L22-h's. **The
phase's report says, hold by hold, where each of R66's holds went** — a rule is never deleted without saying where its
subject lives (DESIGN § 6.3).

## Red today

**No new rule.** Each re-aimed rule is replayed and must hold what it held; `scripts/harness-hold-counts.py --compare`
with `failed` read FIRST. R185 (`queued_by_hand.py`) is the exception that matters: it is written RED against the
launch-bar-free path it will walk (the maintenance-held queue and `season/queued`) before it is moved.

## Move

Re-aim the nine files onto Acquisition (the page id and path → the Acquisition ones; the launch walks → the path OPEN 6
selects); re-point R138's screen half and B-514 with it; state R66's holds' destinations in the report.

## Mutation

R185 keeps its own: the pastille removed → the network hold falls (`scripts/mutate.sh`, after the commit). The others keep
theirs, one per file, reported.

## Register

B-371 (`fixed #603`, its walk re-aimed), B-514 (closed or re-pointed, said in the report).

## Oracle: states that diverge, declared by name

**None.** Any divergence is STOP A.

## Gate

Per INDEX « Gates »; the nine files run by name.

## Commit

`test(maquette-l22): the rules that named the Arrivées page or its launch bar name their successors`
