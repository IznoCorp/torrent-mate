# Phase 10 — The close

## The measurements

1. **The oracle, over the 84 recorded states.** Divergence is reported, not predicted (§ 5 of the
   design). Any divergence is named and explained before it is accepted — an unnamed one is a
   rendering change nobody decided. The four new states bring the reference to 88 and that is
   growth, stated as growth.
2. **The full rule suite**, `frontend/maquette/harness/run.sh`, with per-rule hold counts compared
   against `hold-counts-baseline.json`. The new rules declare their counts; no existing count may
   fall.
3. **`--a11y`** over every state including the four new ones. A connection warning nobody can hear
   is §8 half-kept.
4. **`make check`** at exit 0.
5. **Invariant 10 re-measured for `app/`** — § 7.1 makes refreshing a measurement the wave that
   moved it owes. `app/live-updates.ts` names features; the delta is stated.
6. **B-085 recounted** in `BUGS.md` § Guards green over what they do not read, with this wave's
   figure and the entry that establishes it. **Zero is a real answer** and is written with the same
   authority as six.

## The register

Every finding of the wave is already in `BUGS.md` — filed in the phase that found it, never
collected here. This phase verifies that and files nothing new that a phase should have.

## The pull request

Title and body in English, citing the constitution §§ served (§8 first, then §2, §13, §15,
NE-DOIT-PAS-1 and -5) and the `Done when` clauses with what makes each checkable. Adversarial
review before the merge — the standing operator instruction.

**The row is written when the pull request opens, not after the merge**: `IMPLEMENTATION.md`
« In flight », with the pull request number, which exists the moment the pull request does.

## The post-merge gestures — five, and the list has been skipped three times out of four

1. `make maquette-oracle` (builds, copies, serves; it runs `--check` and FAILS on the dangling
   reference — that is expected, it is run for its preparation).
2. `python3 frontend/maquette/oracle.py --record`, against what is actually served.
3. Move the wave's row from « In flight » to « Last landed », and name the next lot.
4. **Archive** `docs/features/maquette-l10/` under `docs/archive/features/`, with every
   cross-reference moved in the same step.
5. Recount B-085.

**The re-record can only happen on the machine that owns the reference** —
`oracle-reference.json` carries `"platform": "Darwin/arm64"` and `--check` refuses to compare
across a mismatch. This wave runs there (`uname -sm` → `Darwin arm64`). A wave that does not hands
the gesture back to the operator and says so in its pull request.
