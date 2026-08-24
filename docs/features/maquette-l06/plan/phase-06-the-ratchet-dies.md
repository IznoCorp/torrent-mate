# Phase 6 — The ratchet dies, the gate closes

**A baseline is a tolerance, and a tolerance nobody removes is how the disorder comes back one
declaration at a time.** The ratchet existed to let four folding phases land independently; all
four have landed, every family reads zero, and the file that records the counts now says only
« zero is allowed ». It goes, and the arm changes what it refuses.

This phase also carries the half of the « Done when » that no test reports, and that half has been
skipped in three waves out of four.

## 6.1 — The baseline is dropped, the arm refuses outright

**Files touched**: `scripts/check-css-tokens.py`, `frontend/maquette/scale-baseline.json`
(deleted).

1. Delete `frontend/maquette/scale-baseline.json` and the `--record-scale-baseline` mode with it.
   A recorder with nothing to record is machinery nobody can justify, and this repository has
   already paid, once, for keeping a layer of tooling that had lost its subject.
2. **The named exemptions do not disappear with the baseline** — they are the part of that file
   that still has a subject. They move into `check-css-tokens.py` beside the other exemption
   lists, each with the reason it was kept, exactly as `regions.json`'s `$vocabulary` holds its
   frozen class names.
3. The arm's refusal changes and its message changes with it: not « the count went UP against its
   baseline » but « this declaration is on no step ». The message names the selector, the property,
   the literal, and the step the value is nearest to — the next reader has to be able to fix it
   without reading this plan.
4. **The absence of the baseline must be a REFUSAL, never a silence.** An arm that finds no
   baseline and decides it has nothing to compare against is an arm that passes vacuously — which
   is the exact shape of the failures this repository keeps finding. No baseline means the floor is
   zero.

**The mutation**, after the phase is committed: add one off-scale `padding` in BLOCK 2.
`--arm scale` must exit 1 with the outright message, **not** the ratchet one. Restore.

## 6.2 — The records

| File                                      | What changes                                                                                                                                                                                                                                                                                                                                 |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/maquette/README.md`             | the scale and where it is declared; the rule table gains `type_scale.py` and `runtime_tokens.py`; the traps this wave paid for — the composed sign-in page not getting BLOCK 2, and a contrast repair verified on one theme only                                                                                                             |
| `frontend/maquette/regions.json`          | any `$methodLessons` entry this wave earned                                                                                                                                                                                                                                                                                                  |
| `docs/reference/frontend-architecture.md` | L06 → `LANDED`. **And the measurements this wave falsified are refreshed in the same move** — the padding/type/radius counts in the lot's objective, the « 27 of the 42 » split (see phase 5), the `--tm-*` paragraph, which now names the shell as the publisher, and the § 6 line saying L06 must keep the `var()` rule true, which it did |
| `IMPLEMENTATION.md`                       | the « In flight » row, **written when the pull request opens**, not after the merge — the merge consumes the branch that could write it. Plus this wave's phases table beside the previous ones                                                                                                                                              |
| `docs/reference/product-intent.md`        | **nothing.** Only the operator amends the constitution. A conflict found here is reported, not edited                                                                                                                                                                                                                                        |
| `scripts/code-vocabulary.txt`             | already carries the words phase 1 added; re-read it and confirm nothing crept in unlisted                                                                                                                                                                                                                                                    |

## 6.3 — The gate, and the pull request

Every one of these, in this order, with its output pasted rather than summarised. A verdict without
an executed run is refused.

1. `make lint` — 0 error (ACC-14)
2. `make test` — `NNNN passed`, 0 failed **and 0 error**. An error means collection crashed and
   everything after it was skipped (ACC-15)
3. `make check` (ACC-16) — it runs `check-css-tokens.py`, so both new arms ride it
4. `python3 scripts/check-no-french.py` (ACC-17)
5. `cd frontend/maquette/design && npx tsc -b` (ACC-18)
6. `frontend/maquette/harness/run.sh` — the **full** suite, not `--contracts` (ACC-19)
7. `frontend/maquette/harness/run.sh --contracts` (ACC-20)
8. `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json`
   — no movement (ACC-21). The two phases that added a rule re-recorded it; this compare is against
   the last recording, and the phase report says which
9. `make maquette-oracle` — `no divergence` against the reference re-recorded on this branch
   (ACC-22)
10. `python3 frontend/maquette/a11y.py --check` — hard zero, contrast included (ACC-23)
11. ACC-01 … ACC-13 and ACC-24, the criteria in the plan's index

**The pull request lists, and neither is optional:**

- **D-L06-1 … D-L06-6 and the plan's P-1 and P-2**, each with what it decided, because none of them
  was implemented before the design was committed and the operator's arbitration is what the list
  is for.
- **Every accepted oracle divergence**, copied from `ACCEPTED-DIVERGENCES.md` — the whole table,
  with its reasons. A wave that moves pixels on purpose is reviewed on that list or it is not
  reviewed.

## After the squash merge — and the first command is not optional

The squash replaces the commit the references name, so on a fresh clone the pointer names nothing
and `--check` refuses to run at all. From the **tip of `main`**, after the merge:

```bash
make maquette-oracle                            # builds, copies, serves; FAILS on the dangling
                                                # reference — that is expected, it is run for its
                                                # preparation
python3 frontend/maquette/oracle.py --record    # then records against what is actually served
python3 scripts/harness-hold-counts.py --record frontend/maquette/hold-counts-baseline.json
```

Then **verify both pointers are ancestors of `HEAD`**, and move the wave's row in
`IMPLEMENTATION.md` from « In flight » to « Last landed », naming the next lot. That row is the one
step of the three that cannot be done from the wave's own branch, which is exactly why it is the
one that gets forgotten.

## Done when

- Every line of the lot's « Done when » in `docs/reference/frontend-architecture.md` § L06 is true:
  the scale is declared in one place; no declaration sits outside it; a check refuses the next one;
  the `--tm-*` family has a decided home and its fallbacks still hold; the 42 contrast findings are
  gone and `a11y.py`'s contrast run is empty; the fields read at least 16 px so a focused field no
  longer zooms iOS; the oracle records the intended visual changes as accepted, each reviewed.
- ACC-05 holds: the baseline file is gone, and the mutation proved the arm refuses without it.
- The eleven gate commands above have been run with their output pasted.
