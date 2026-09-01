# L14 — The surfaces that outgrew their file · PLAN

**Design**: `docs/features/maquette-l14/DESIGN.md`. **Contract**: `docs/reference/frontend-architecture.md`
§ 4, `#### L14 — The surfaces that outgrew their file` — its « Done when » is the definition of
finished. **Brief**: `docs/features/maquette-l14/BRIEF.md`.

**PHASES CHAIN WITHOUT PAUSE — a global constraint, and it outranks the urge to report.** After a
phase's gate is green and its work committed, **start the next phase in the same turn**. Never end
a turn to announce that a phase is complete, and never end one asking whether to continue. **The
only stops this wave has are the ones this plan NAMES**: an anomaly that would require deviating
from the plan (deviation only on anomaly plus sign-off), a red gate that cannot be repaired within
the plan, and the pull request's readiness — at which point the steward is messaged for the
independent review and the reviewers' findings are waited for. The operator arbitrates the
PERIMETER, never the cadence.

**The self-check, because this rule has been broken repeatedly**: before ending a turn, read the
last paragraph written. If it announces a phase finished, or asks whether to go on, then the next
phase should have started in that same turn. Rigour per phase is unchanged — each still lands as a
green commit with its proof; it is the chaining that changes, not the method.

**Eight phases.** Each is ONE kind of change (D-L14-5): a **conversion** phase moves code and
proves the rendering did not change — oracle green, zero divergence; a **behaviour** phase changes
what the interface does and lands with the rule that drives it, seen red under its mutation. **No
phase does both.** The kind is written in every row below and at the head of every phase file.

**Every phase gate**: the oracle (`make maquette-oracle`), `frontend/maquette/harness/run.sh
--contracts` (the contracts tier and the repository's cheap guards, both counts printed by the
script), `npm run check` in `frontend/maquette/design` (`tsc -b`, eslint, vitest, the build — the
frontend's gate, `tsc --noEmit` proves nothing), and **every rule of that phase mutation-tested —
seen red, naming the right defect, restored**. `scripts/mutate.sh` refuses a dirty tree and
restores from the index, so the phase's work is committed before its mutation runs; a GUARD is
mutated by hand and read by its exit code (B-273).

**The harness is mine for the length of the wave** (the steward, 2026-09-01), and every run of
`run.sh`, the oracle, `mutate.sh` or `harness-hold-counts.py` is still announced by message. A
listener on 8899 this session did not start is a reason to stop and ask.

|   # | Phase                                  | Kind           | Owns                                                                                                         | New rules                                |
| --: | -------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------- |
|   1 | `Icon` is written once                 | **conversion** | the three private copies deleted; `PanelActionButton`; the `twice` arm                                       | 1 guard arm                              |
|   2 | The resolution screen                  | **conversion** | `resolution-cards.tsx`; the file's grandfather entry leaves                                                  | — (oracle + size arm)                    |
|   3 | The media screen                       | **conversion** | six files beside the screen; the entry leaves; `markup_dressing.py`'s `img` site moves with the cast         | — (oracle + size arm + R115)             |
|   4 | B-283 — a skeleton for what is unknown | behaviour      | `inFlight`, `skeletonLine`, the field-level skeletons                                                        | **R119** `harness/priming.py`            |
|   5 | The library page                       | **conversion** | five files beside the page; the entry leaves                                                                 | — (oracle + size arm + R117)             |
|   6 | The acquisition page                   | **conversion** | five files beside the page; the entry leaves; the `button` site in `markup_dressing.py` moves with Découvrir | — (oracle + size arm)                    |
|   7 | B-247's surface half                   | behaviour      | `ui/markup.ts`, `useMarkup` at every site, the library's `drawKey`                                           | **R100 (f)** in `harness/persistence.py` |
|   8 | The close                              | —              | the register, the report, the hold counts, the full suite, the row, the steward                              | —                                        |

**Phase 4 depends on phase 3** (it edits the files phase 3 cuts). **Phase 7 depends on phases 5 and
6** (the sites it memoises live in the files they cut). Phases 1, 2, 3, 5, 6 are independent of
each other and run in the order written — smallest file first after the shared deletion, so the
method is exercised on 430 lines before it meets 796.

---

## What this plan does not do, and why

- **It does not open `app/shell.tsx`** (398 of 400) nor either of the engine's two files. Nothing
  here needs them; recorded so « we looked and it was unnecessary » is not read as « nobody looked ».
- **It does not move a producer, an engine-side gesture caller (L19), or the ladder's handler
  (L13).** `discover-tab.tsx` carries the containers and the fill effect as they are (D-L14-9).
- **It does not claim the instruments' debts** (D-L14-10): no phase opens `served_copy.py`,
  `mutate.sh`, `harness-hold-counts.py` or `exits.py`.
- **It does not add a named state** to `engine/states.js` (D-L14-8).
- **It skips no lot.** § 0's selection rule elects L14 and `IMPLEMENTATION.md` records it as Next.

## What the operator rules on — at the review, not before

**D-L14-3**: an open swipe survives an unrelated store write once nodes keep identity. Named in
the design and in the pull request; overruling it is one line (`drawKey`) and does not stop the
wave. No phase waits on it.

## The close (phase 8) owes six things, and the sixth is a measurement

1. The « In flight » row in `IMPLEMENTATION.md` — **written when the pull request opens**, pull
   request number first, then the version (`check-implementation-state.py` holds the row by both).
2. The register, written **during** the wave, not at the close: B-295 filed at the design, B-283
   and B-295 `fixed #NNN`, B-247's surface half written into its body.
3. `REPORT.md`, in this folder beside the design and the plan, before the pull request is marked
   ready — **`git add -f`, then `git ls-files` as the check** (B-251); the post-merge gesture
   deletes the folder and cites it by the squash's sha.
4. `scripts/harness-hold-counts.py --compare` with every movement written down, and `failed` read
   in the totals before any record is trusted (B-291).
5. The message to the steward: the pull request's number and head sha, so the independent readers
   are launched on a worktree pinned at that head. **Plan for more than one round**, each aimed at
   the previous round's repairs.
6. **The recount of « guards green over what they do not read »** in `BUGS.md`, with the pull
   request or entry that establishes this wave's figure. **Zero is a real answer.**
