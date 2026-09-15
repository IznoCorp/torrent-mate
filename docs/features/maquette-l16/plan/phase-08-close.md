# Phase 8 — The close

Re-reads `product-intent-map.md` and `BUGS.md` rather than trusting what phases 1–7 claimed — the
same discipline every prior lot's closing phase holds.

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `grep -n "DOIT-13\|DOIT-2\b\|DOIT-3\b" docs/reference/product-intent-map.md` — the
  three rows this lot touches, their CURRENT wording, so the closing phase diffs against what it
  actually moved rather than what DESIGN § 6 predicted. `grep -n "B-143\|B-144\|B-145\|B-257\|B-298"
  BUGS.md` — five rows, of which this lot closes B-144's reading half at phase 1–3 and its
  remaining half at 4–6, and B-298 in full at phase 7; B-143 and B-145 are untouched, named so the
  report says why. `python3 -c "import
  glob,re;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"',open(f).read(),re.M)) for f in
  glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"` — the live named-state total at
  this design's writing (the command DESIGN inherits from L20's own re-pointed measurement,
  `docs/features/maquette-l20/DESIGN.md@60c6d9b1d` § 5), to be re-run after phase 7 and reported as
  a before/after pair.
- **Points ≈ 5.** The map's three rows re-read and reported ≈ 2; the register's five rows re-read
  ≈ 1; the states counted before/after ≈ 1; the report itself ≈ 1. Under 15, no cut.

A DOCUMENTATION-of-the-close change: no surface, no rule, no mock moves here.

## The proof FIRST

No new rule. The close is proved by re-running what phases 1–7 already left green, not by a new
hold:

- `frontend/maquette/harness/run.sh` (full suite, no flag) — expected no failure.
- `--a11y` tier — 0 over the new named states.
- `scripts/harness-hold-counts.py --compare`, `failed` read FIRST (B-291).
- `python3 scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py`, read by OUTPUT
  (B-346 — the closure arm reads an entry's body up to the first paragraph opening with another
  identifier; a report that trusts the exit code alone can misread a close beside a `**B-NNN's …`
  paragraph, as B-346 itself records).

## The move

- **The map.** `product-intent-map.md`'s DOIT-13, DOIT-2 and DOIT-3 rows are PROPOSED for
  amendment (the map's own header — this lot proposes, the operator amends): DOIT-13 to `served`
  with the rules that hold it (R-L16-a through R-L16-h, bound in phase 1); DOIT-2 to its ratio half
  `served`, its space half untouched and said so explicitly, never left to read as if it had
  landed; DOIT-3 to its tracker-policy half `served`.
- **The register.** B-144 closes in full (both read and write halves land across phases 1–6);
  B-298 closes in full (phase 7); B-257 stays `fixed #534`, unedited, cited as the confirmation
  that L16 is its named consumer; B-143 and B-145 stay `open`, named as L18's and L17's respectively
  — this lot does not touch either.
- **The states.** The before/after count, and which of the sixteen named states DESIGN §§ 4.1–4.7
  declares actually landed (a design's count is a plan; the close reports what shipped).
- **The report.** Head, the pull request number and its CI run id, the phase table with points,
  the mean, the rule-label-to-number binding from phase 1, the guards' exit codes, the gauge — the
  same shape every builder's final report to its orchestrator already takes.

## Mutation

None — this phase asserts nothing new; it reads what the seven before it already proved.

## Register

Closes B-144 and B-298 in full; amends DOIT-13, DOIT-2 (ratio half only) and DOIT-3 (policy half
only) as proposals for the operator.

## Oracle: states that diverge, declared by name

**None expected.** Every state this lot touches was already recorded new by its own landing phase
(2–7); the close runs the full suite to confirm no OTHER state — one this lot never named — moved,
which is exactly what turns a phase-by-phase green into a lot the steward can audit. Any divergence
found here that no phase already accepted is **STOP A**, and the close does not paper over it with
a blanket acceptance.

## Gate

The full suite, `--a11y`, `--compare`, the pre-push pytest — per INDEX « Gates », the pre-PR set,
not local `make check` (measure 19).

## Commit

`docs(maquette-l16): the close — the map's three rows, B-144 and B-298, the states counted`
