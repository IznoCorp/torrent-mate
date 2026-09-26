# Phase 15 — The close

Re-reads `product-intent-map.md` and `BUGS.md` rather than trusting what phases 1–14 claimed — the same discipline every prior lot's closing phase holds.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `grep -n 'DOIT-13\|DOIT-2 \|DOIT-3\b' docs/reference/product-intent-map.md` — the three rows this lot touches, their CURRENT wording, so the closing phase diffs against what it actually moved
  rather than what DESIGN § 6 predicted: DOIT-13 `to draw`, owner **L16**; DOIT-2 `partly`, citing `features/arrivals` (the stuck queue) — **the surface L22 proposes to move to `features/acquisition`
  (its § 6.3)**, and the map is the operator's, so the close reports the row against whichever wording stands when the lot closes; DOIT-3 `partly`, citing the pilot's bar (which dies at L22b; L22 proposes `features/system` — the levers — for the row, its § 6.3). `grep -n '^| B-143\|^| B-144\|^| B-145\|^| B-257\|^| B-298' BUGS.md` — five rows: B-143 `open`, B-144 `open`, B-145 `open`, B-257 `fixed #534`, B-298 `open`;
  this lot closes B-144 in full (phases 1–12) and B-298 in full (phase 14); B-143 and B-145 are untouched, named so the report says why. The named-state total on `dafe29ec1` is **114** (`python3 -c
  "import glob,re;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"',open(f).read(),re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"`), to be re-run after
  phase 14 and reported as a before/after pair — **DESIGN §§ 4.1–4.7 declares seventeen** (`trackers-empty`, `-list`, `-loading`, `-error`; `tracker-detail`, `-loading`, `-error`, `-empty-active`;
  `tracker-alert-active`; `tracker-policy-panel`; `obligation-release-confirm`, `obligation-released-externally`; `bar-trackers-alert`; `acq-card-ratio-reason`; `ranking-editor`, `-loading`, `-error`).
- **Points ≈ 7.** The map's three rows re-read and reported 3; the register's two closes (B-144, B-298) 2; the states counted before/after 1; the report itself 1.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 8) 5 → this phase **7**: moved by **the scale** (a documentation row is a point, and the close reads five register rows and three
  map rows). Its « sixteen named states » is now seventeen (`bar-trackers-alert` is new, ruling 12; the S6 state moved to `acq-card-ratio-reason`).

A DOCUMENTATION-of-the-close change: no surface, no rule, no mock moves here.

## The proof FIRST

No new rule. The close is proved by re-running what phases 1–14 already left green, not by a new hold:

- `frontend/maquette/harness/run.sh` (full suite, no flag) — expected no failure.
- `--a11y` tier — 0 over the new named states.
- `scripts/harness-hold-counts.py --compare`, `failed` read FIRST (B-291).
- `python3 scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py`, read by OUTPUT (B-346 — the closure arm reads an entry's body up to the first paragraph opening with another
  identifier; a report that trusts the exit code alone can misread a close beside a `**B-NNN's …` paragraph, as B-346 itself records).

## The move

- **The map.** `product-intent-map.md`'s DOIT-13, DOIT-2 and DOIT-3 rows are PROPOSED for amendment (the map's own header — this lot proposes, the operator amends): DOIT-13 to `served` with the rules that
  hold it (R-L16-a through R-L16-h, bound in phase 2 and after); DOIT-2 to its ratio half `served` on the acquisition card, its space half untouched and said so explicitly, never left to read as if it had
  landed; DOIT-3 to its tracker-policy half `served`.
- **The register.** B-144 closes in full (the read and write halves land across phases 1–12); B-298 closes in full (phase 14); B-257 stays `fixed #534`, unedited, cited as the confirmation that L16
  is its named consumer; B-143 and B-145 stay `open`, named as L18's and L17's respectively — this lot does not touch either.
- **The states.** The before/after count, and which of the seventeen named states DESIGN §§ 4.1–4.7 declares actually landed (a design's count is a plan; the close reports what shipped).
- **The open questions.** DESIGN § 5's three OPEN questions, and the reading each phase took (phases 2 and 10) — reported, so the operator's rulings and the lot's drawing can be read together.
- **The report.** Head, the pull request number and its CI run id, the phase table with points, the mean, the rule-label-to-number binding from phase 2, the guards' exit codes, the gauge — the same shape
  every builder's final report to its orchestrator already takes.

## Mutation

None — this phase asserts nothing new; it reads what the fourteen before it already proved.

## Register

Closes B-144 and B-298 in full; amends DOIT-13, DOIT-2 (ratio half only) and DOIT-3 (policy half only) as proposals for the operator.

## Oracle: states that diverge, declared by name

**None expected.** Every state this lot touches was already recorded new by its own landing phase; the close runs the full suite to confirm no OTHER state — one this lot never named — moved, which is exactly what
turns a phase-by-phase green into a lot the steward can audit. Any divergence found here that no phase already accepted is **STOP A**, and the close does not paper over it with a blanket acceptance.

## Gate

The full suite, `--a11y`, `--compare`, the pre-push pytest — per INDEX « Gates », the pre-PR set, not local `make check` (measure 19).

## Commit

`docs(maquette-l16): the close — the map's three rows, B-144 and B-298, the states counted`
