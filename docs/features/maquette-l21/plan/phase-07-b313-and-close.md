# Phase 7 — The panel's doubled action, and the close

## B-313 — « Voir le parcours », twice

Measured in `features/acquisition/follow-actions.ts`: `primaryAction` falls through to
`{ text: say("seeJourney"), target: { journey } }` for a medium with no sheet that is not
followed, and `secondaryActions` emits `{ text: say("seeJourney"), … }` **unconditionally** —
where « Voir la fiche » beside it is guarded by `facts.hasSheet && (…)`.

**The rule FIRST, and it is named in B-313's body so it is not invented twice**: a panel's actions
are counted **BY LABEL**, and a label appearing twice is refused. **Red on `main`'s follow panel
for a medium that has no sheet** — no mutation needed.

**Then one condition**, mirroring the `seeSheet` guard. One line.

## B-247's producer half

The panels this wave touched are added to `persistence.py` (f)'s list: a moved surface keeps its
nodes across a store write. Seen red on a producer that re-keys its rows.

## The close

1. **The register is written DURING the wave, not after.** B-301, B-302, B-313, B-322, B-323 read
   `fixed #<n>` **by rule 3 — the rule, the mutation, the run.** The DOIT-3 and DOIT-4 rows of
   `docs/reference/product-intent-map.md` read `served`.
2. **Recount « guards green over what they do not read »** in `BUGS.md` for this wave, **zero
   included** — a wave that found none says so, because an uncounted exemption is
   indistinguishable from an oversight.
3. **`IMPLEMENTATION.md`**: the « In flight » row when the pull request opens — **pull request
   number first, then the version**; `scripts/check-implementation-state.py` holds it by both.
   Move « Next » to the lot after L21.
4. **`REPORT.md`** in this folder, with named sections, landing **before the pull request is
   marked ready**, beside the design and the plan.
5. Version bump, **patch**.

## The full gate, before merging

Told to the steward BEFORE it runs; the harness is one per machine.

| Gate | Expected |
| --- | --- |
| `frontend/maquette/harness/run.sh` (FULL, not `--contracts`) | **no failure** |
| `run.sh --a11y` | 0 |
| `scripts/harness-hold-counts.py --compare` | **`failed` read FIRST** (B-291); every movement written down |
| `make check` | zero failures **and zero errors** |
| the oracle | divergences only on the accepted set, each with its reason (D8) |
| `python3 scripts/frontend_size_ledger.py` | `legacy.js` strictly below **31 591** |
| `grep -cE "closest\.dataset\.(follow\|pause\|remove\|dropsug\|sugmore\|take)\b"` | **0** (from 12) |

## Then STOP C — the pull request

Title and body in **English**. Cite the constitution's §§ this work serves. Message the steward:
the readers come from round one, on a worktree pinned at the head, building the head AND a control
of `main`, **walking the verbs** under the busy scenario. **I alone write.**
