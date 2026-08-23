# Phase 7 — The records, and the gate

**A lot is not finished because its code exists.** This phase is the half of the « Done when » that
no test reports, and it has been skipped in three waves out of four.

## What is written, and where

| File | What changes |
| --- | --- |
| `frontend/maquette/regions.json` | R69's reason, rewritten naming D1 as what replaces its premise — the query justification is not deleted, it is superseded on the record. Any new `$methodLessons` entry this wave earned |
| `frontend/maquette/harness/url_state.py` | the docstring carries the same renegotiation |
| `frontend/maquette/README.md` | the address table; the harness host is `server.py`, not a plain `http.server`; the rule-table row for `url_state.py` |
| `docs/reference/frontend-architecture.md` | L05 → `LANDED`. **And the measurements this wave falsified are refreshed in the same move** — that is the wave's DUTY under § 7.1, not an amendment: D1's « the maquette stops opening from `file://` » becomes a fact rather than a cost to come, and D5's list of what is cross-cutting loses navigation, which this wave lifted |
| `IMPLEMENTATION.md` | the « In flight » row, **written when the pull request opens** — § 5, because a row that waits for the merge is a row the merge consumes. Plus this wave's phases table, in the frontend section, beside the previous ones |
| `CLAUDE.md` § Language | the sentence claiming `/deconnexion` is still French on the design host — `serve.py:753/757` serve `/logout` and `/login`, and `logout.py` holds them (D-L05-8) |
| `docs/reference/product-intent.md` | **nothing.** Only the operator amends the constitution. If this wave finds a conflict with it, it is reported, not edited |

## The gate — before the closing commit

Every one of these, in this order, and none is optional:

1. `make lint` — 0 error (ACC-15)
2. `make test` — `NNNN passed`, 0 failed **and 0 error**. An error means collection crashed and
   everything after it was skipped (ACC-16)
3. `make check` (ACC-17)
4. `frontend/maquette/harness/run.sh` — the **full** suite, not `--contracts` (ACC-03)
5. `python3 scripts/harness-hold-counts.py --compare` — green **at unchanged hold counts**, except
   the deltas phase 5 named (ACC-04)
6. `make maquette-oracle` — green, or every divergence accepted with its written reason (ACC-05)
7. `python3 frontend/maquette/a11y.py --check` — hard zero (ACC-20)
8. `git log --oneline main..HEAD -- back.py screens.py bridge.py` — empty (ACC-21)

## After the squash merge — and the first command is not optional

The squash replaces the commit the references name. From the **tip of `main`**, after the merge:

```
make maquette-oracle                            # builds, copies, serves; FAILS on the dangling
                                                # reference — that is expected, it is run for its
                                                # preparation
python3 frontend/maquette/oracle.py --record    # then records against what is actually served
```

Then the hold-count baseline the same way, and **verify both pointers are ancestors of `HEAD`**.

Then move the wave's row from « In flight » to « Last landed » and name the next lot. It is the one
step of the three that cannot be done from the wave's own branch, which is exactly why it is the
one that gets forgotten.

## Done when

Every line of the lot's « Done when » is true, and the eight gate commands above have been run with
their output pasted — not summarised. A verdict without an executed run is refused by §méthode
rule 2.
