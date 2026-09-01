# Phase 12 — The close

## The gates, in this order

1. The **full** rule suite — `frontend/maquette/harness/run.sh`, **not** the `--contracts` tier.
2. The **`--a11y`** tier.
3. `scripts/harness-hold-counts.py --compare` — **no rule loses a hold by accident, and every
   movement is written down**.
4. `make check` at **zero failures and zero errors**. An ERROR means collection crashed and
   everything after it was skipped.
5. The oracle — green, or its divergences accepted with reasons, each named in the behaviour commit
   that produced it.

**Announce on the harness before each of these.** One machine, one harness; `served_copy.py` is its
lock and its stamp. A rule that falls while another session held the harness is **re-run alone**
before it is read as anything.

## The device-only protocols — written and dated, never claimed as passed

`MODEL.md` § 3.1 is explicit that these are protocols, not gates. A headless browser's frame timing
says nothing about a phone's.

- **The interaction budget**, measured on a real device — a written run with a date, like the
  oracle's certification. It is in the Done-when **as written**, and it is not a gate.
- **Whether `:active` still needs a touch listener** (phase 5). If it does, the remedy is **one
  empty listener, never a per-component JavaScript state**.

**Neither is recorded as passed.** L11's P9 is the precedent: « the half only a device settles is
DECLARED as device-only and NOT yet exercised ».

## The five things the close owes

1. **The « In flight » row** — written when the pull request **opens**, not here: pull request
   number first, then the version. `check-implementation-state.py` refuses a row naming neither.
2. **The register** — written **during** the wave. **B-234** (phase 2) and **B-252** (phase 11)
   close. New entries land as they are found.
3. **`REPORT.md`** beside this plan, before the archive move takes the folder. **`git add -f`, then
   `git ls-files` as the check** — the global ignore hides `docs/` from `git add -A` and from
   `git status`, and L11's report lived on one disk only until someone asked (B-251).
   `scripts/check-docs-cited-paths.py` refuses a directive citing a path git does not hold.
4. **The § 7.1 duty** — every measurement this wave made move is refreshed **in this wave**: the
   `MODEL.md` § 3 rows for P5, P6, P11, P16, P17, P20, P24, P25, P26 and P29, and the L12 entry's
   own stale figures. That is not an amendment; leaving an old figure standing is the disease.
5. **The recount** of « guards green over what they do not read » in `BUGS.md`, with the pull
   request or entry that establishes this wave's figure. The counter stands at **143**.
   **Zero is a real answer, written with the same authority as six.**

## The adversarial review

**Plan for more than one round.** L11's second and third rounds found their sharpest defects
**inside the first round's repairs** — a security regression, an update discipline that never
swapped the worker, a refused replay destroyed silently, a 401 treated as final, a button that said
« Réessayer maintenant » while clearing the refusal. **None of the three was found by a gate**, and
every gate was green throughout.

The wave does not close on a green gate. It closes on a clean round after the repairs.

## Post-merge (§ 5), and it is not this branch's to do

`make maquette-oracle` then `python3 frontend/maquette/oracle.py --record`; move the row from
« In flight » to « Last landed » and name the next lot; archive `docs/features/maquette-l12/`
(**`maquette-l10-ter/` is exempt by name**); and send the steward this wave's report.
