# Phase 17 — The close

Re-reads `product-intent-map.md`, `BUGS.md` and `frontend/maquette/README.md`'s own cut table rather
than trusting what phases 1–16 claimed — the same discipline every prior lot's closing phase holds,
extended here to a THIRD document (the README's row, C9) the prior reading's own closing phase never
named.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `grep -n 'DOIT-13\|DOIT-2 \|DOIT-3\b' docs/reference/product-intent-map.md` — the three
  rows this lot touches, their CURRENT wording, so the closing phase diffs against what it actually
  moved rather than what DESIGN § 6 predicted: DOIT-13 `to draw`, owner **L16**; DOIT-2 `partly`,
  citing `features/arrivals` (the stuck queue) — the surface L22 proposes to move to
  `features/acquisition` (its § 6.3), and the map is the operator's, so the close reports the row
  against whichever wording stands when the lot closes; DOIT-3 `partly`, citing the pilot's bar (which
  dies at L22b; L22 proposes `features/system` — the levers — for the row, its § 6.3). `grep -n '^| B-143\|^| B-144\|^| B-145\|^| B-257\|^| B-298'
  BUGS.md` — five rows: B-143 `open`, B-144 `open`, B-145 `open`, B-257 `fixed #534`, B-298 `open`;
  this lot closes B-144 in full (phases 1–10, the reads and the alert) and B-298 in full (phase 16,
  the ranking's read, save and preview); B-143 and B-145 are untouched, named so the report says why.
  `grep -n 'A medium in trouble' -A2
  frontend/maquette/README.md` — the cut table's own row, four kinds, no Trackers row (C9); this
  phase's move adds it. `python3 -c "import
  glob,re;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"',open(f).read(),re.M)) for f in
  glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"` — the named-state total, to be
  re-run after phase 16 and reported as a before/after pair; **DESIGN §§ 4.1–4.7 declares
  TWENTY-EIGHT**: `trackers-page`, `-loading`, `-error` (3); `trackers-roster`, `-roster-empty`,
  `-entry-open`, `-policy-unset`, `tracker-alert-active`, `tracker-identifier-refused` (6);
  `tracker-broken-obligations`, `-broken-obligations-open` (2, round 10 Q4); `torrents-list`,
  `-list-filtered`, `-empty`, `-empty-filtered`, `torrent-obligation-breached` (5);
  `torrent-remove-confirm`, `-shared`, `-obligation` (3, the third round 10 M4's own broadened
  confirmation); `bar-trackers-alert` (1); `acq-card-deferred-ratio`, `-space`, `-missing` (3);
  `ranking-editor`, `-loading`, `-error`, `-saving`, `-save-conflict` (5).
- **Points ≈ 8.** The map's three rows re-read and reported 3; the register's two closes (B-144, B-298)
  2; the README's own new row (C9) 1; the states counted before/after 1; the report itself 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's own phase 15 (7) grows by one for the
  README row (C9) this redraw's own audit found missing — a directive that must change IN THE SAME
  MOVE as the decision that creates the surface it maps (`CLAUDE.md` § Design Reference), not left for
  L17's own close to invent, per the triage's own instruction. **Re-cut again, same day, on the
  auditor's rulings-coherence round**: phase 9 (broken obligations, round 10 Q4) is inserted, shifting
  every phase after it up by one; this close's own commands and counts are re-taken against the
  SEVENTEEN-phase plan, not the sixteen this paragraph's own point count was first measured against.

A DOCUMENTATION-of-the-close change: no surface, no rule, no mock moves here.

## The proof FIRST

No new rule. The close is proved by re-running what phases 1–16 already left green, not by a new hold:

- `frontend/maquette/harness/run.sh` (full suite, no flag) — expected no failure.
- `--a11y` tier — 0 over the new named states.
- `scripts/harness-hold-counts.py --compare`, `failed` read FIRST (B-291).
- `python3 scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py`, read by OUTPUT
  (B-346).

## The move

- **The map.** `product-intent-map.md`'s DOIT-13, DOIT-2 and DOIT-3 rows are PROPOSED for amendment
  (the map's own header — this lot proposes, the operator amends): DOIT-13 to `served` with the rules
  that hold it (R-L16-a through R-L16-h, bound in phase 2 and after); DOIT-2 to its ratio, space and
  missing-content thirds `served` on the acquisition card (F14's own widened scope), its remaining gaps
  said so explicitly, never left to read as if the whole row had landed; DOIT-3 to its tracker-policy
  half `served`.
- **The register.** B-144 closes in full (the reads and the alert land across phases 1–10); B-298 closes
  in full (phase 16, F16's read-save-preview trio); B-257 stays `fixed #534`, unedited, cited as the
  confirmation that L16 is its named consumer; B-143 and B-145 stay `open`, named as L18's and L17's
  respectively.
- **`frontend/maquette/README.md`'s cut table (C9).** The row this lot's own surface needs, added in
  the SAME move as the surface itself lands: « A tracker in trouble (ratio, obligation) → **Trackers**
  », naming organisation ruling 12. L17's own close extends this SAME row to cross-seed failures
  (per its own plan's citation) rather than writing a second one.
- **The states.** The before/after count, and which of the twenty-eight named states DESIGN §§ 4.1–4.7
  declares actually landed (a design's count is a plan; the close reports what shipped).
- **The open question.** DESIGN § 5's OPEN 4 (the default tab), and the reading phase 2 took —
  reported, so the operator's ruling and the lot's drawing can be read together.
- **The report.** Head, the pull request number and its CI run id, the phase table with points, the
  mean, the rule-label-to-number binding from phase 2, the guards' exit codes, the gauge — the same
  shape every builder's final report to its orchestrator already takes.

## Mutation

None — this phase asserts nothing new; it reads what the sixteen before it already proved.

## Register

Closes B-144 and B-298 in full; amends DOIT-13, DOIT-2 (all three thirds, widened against F14) and
DOIT-3 (policy half only) as proposals for the operator; adds the README's own missing row (C9).

## Oracle: states that diverge, declared by name

**None expected.** Every state this lot touches was already recorded new by its own landing phase; the
close runs the full suite to confirm no OTHER state — one this lot never named — moved, which is
exactly what turns a phase-by-phase green into a lot the steward can audit. Any divergence found here
that no phase already accepted is **STOP A**, and the close does not paper over it with a blanket
acceptance.

## Gate

The full suite, `--a11y`, `--compare`, the pre-push pytest — per INDEX « Gates », the pre-PR set, not
local `make check` (measure 19).

## Commit

`docs(maquette-l16): the close — the map's three rows, B-144 and B-298, the README's own row, the states counted`
