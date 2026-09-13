# Phase b·4 — Arrivals verbs

A BEHAVIOUR move: `pipe`, `manual`, `resolve`, `leave`, `next`, `act=resolve` and the `.cfoot`
class branch are registered by the arrivals feature, and their engine branches are deleted.
`resolve` is a surface-opening verb (DESIGN § 6, row b·4; § 2.3).

## The proof FIRST

- **Re-take the rows before moving anything** (DESIGN § 6 method). The emitters are
  `features/arrivals/page.tsx`, `features/arrivals/resolution-screen.tsx`,
  `features/arrivals/resolution-cards.tsx`, the target in `features/acquisition/follow-actions.ts`,
  and the card foot.
- **Rules green before and after, counts unchanged**:
  - `pipe`: `arrivals.py` and `page_host.py`;
  - `manual`: `ident.py`, `bugs.py` and `resolution_window.py`;
  - `resolve`: its five files, `take.py` among them;
  - `leave`: its readers.
- **The name no rule holds gets its hold FIRST**: `next` (DESIGN § 6).
  - On the resolution screen with more than one pending decision, « next » opens the NEXT decision's
    resolution. The hold reads the subject after the act. With none left, the act says so.
  - **Red first**: the engine branch is deleted on purpose, and the hold falls naming the subject
    that did not change.
- **Timers are kept as they are.** `manual` keeps its 260 ms, and `resolve`, `leave` and `next` keep
  their 240 ms (DESIGN § 6). Holds read the outcome after the timer.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes each registration in turn,
  and the holding rule falls naming the missing act. For `pipe`: `arrivals.py` names the pipeline
  state that did not move.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new hold named.

## The move

- **Registered with `registerVerb` in `features/arrivals/`**, imported from `app/feature-verbs.ts`.
- **`act=resolve` is split, and `.cfoot` takes no new name** (DESIGN § 6, « One name, one owner »).
  The `resolve` value of `act` becomes the arrivals feature's own English name, renamed with
  `scripts/rename-identifiers.py` across its three ends (the `add:N` half is split in b·5). The
  `.cfoot` class branch dies: the card foot emits `data-take` (already registered, L21) for
  « Récupérer » and `data-resolve` (registered here) for « Résoudre ».
- **Queue actions.** The forwarders `actionResolve` and `actionLeave` die: the verbs call
  `lib/queue.ts`'s queue actions by import, not `__queueActions`.
- **`next`** reads the pending decisions from the cache by import.
- **Deleted from `legacy.js`**: the branches and their forwarders. `scripts/frontend_size_ledger.py`
  is re-recorded DOWNWARD in the same commit.
- **The contract's count moves.** The `resolve` lines leave
  `grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)"`.

## Gate

Per INDEX « Gates ». In addition, the oracle shows zero divergence (STOP B otherwise), and the red
reading of the `next` hold and the mutations go in the report.

## Commit

`feat(maquette-l13): the arrivals feature answers its own delegation names`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** route through `app/panel-contributions.ts`'s side-effect line (cost 0) rather than `app/feature-verbs.ts` (+2); new `data-*` names into the vocabulary in the same commit.
