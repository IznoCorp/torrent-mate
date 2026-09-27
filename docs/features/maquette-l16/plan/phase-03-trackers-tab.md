# Phase 3 — The « Trackers » tab: one entry per tracker

One collapsed row per tracker: its ratio, its trend, its Download / Upload volumes (DESIGN § 4.2) —
read from the summary read phase 1 declared, never averaged (§ 18's first clause, NE-DOIT-PAS-1). The
disclosure's own policy fields are phase 4's; the alert badge and the refused-identifier chip are
phase 8's. This phase fills the collapsed row and gives the tab its own states.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `ls frontend/maquette/design/src/features/trackers/` at this phase's opening → `page.tsx`
  only (phase 2's). `grep -n -i 'tracker' frontend/maquette/design/src/i18n/fr.json` → four lines, all
  `settings.labels` of the search configuration, unrelated to this domain. `grep -c enabled
  config.example/tracker.json5` → `2` — `c411` and `tr4ker`, the roster the mock answers, in their
  declaration order (never re-sorted by ratio, DESIGN § 4.2). `python3 -c "import
  glob,re;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"',open(f).read(),re.M)) for f in
  glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"` → **114** on `5e5ecd052` (before
  this lot).
- **Points ≈ 13.** The collapsed rows in `trackers-tab.tsx` (≈ 50 new; a row carries the ratio, the
  trend in words, the volumes, a header slot for the alert badge and the refused-identifier fact
  phase 8 wires) 5; **one new rule, R-L16-a's roster half** (NE-DOIT-PAS-1: every ratio drawn compared
  against the mock's own field) with its mutation 3; three states — `trackers-roster` re-using phase
  1's summary seed 1, `trackers-roster-empty` needing a new seed row (a config with zero trackers) 2;
  `fr.json` (`screens.trackers.ratio`, `.trend` with its three words, `.volumes`, `.empty`) 1; the
  region's record in `regions.json` ½.
- **Re-cut (2026-09-27, on `5e5ecd052`).** Unchanged in shape from the prior re-read's phase 3 (the
  roster page): the row's own facts are the same three (ratio, trend, volumes); what changed is
  WHERE it draws — inside a tab, not a whole page — which does not move its own point count.

A BEHAVIOUR change: the tab did not exist; it now reads the summary read and draws one row per
tracker.

## The proof FIRST

- **What it drives.** Navigate to `/trackers?tab=trackers`.
- **What it reads.** Each row's ratio, trend and volumes, compared against the mock's own field for
  that tracker — never a client-side mean across rows (R-L16-a).
- **Red today.** The rows do not exist to read: the rule fails for that reason against `main` (and, on
  the branch, against phase 2's shell, which draws none).
- **Mutation.** `scripts/mutate.sh` makes a row compute its ratio from a DIFFERENT tracker's field (a
  swapped index). The rule must fall, naming the mismatched tracker.

## The move

- **`features/trackers/trackers-tab.tsx`** — the roster, one collapsed row per tracker
  (`data-part="trackers/entry"`), its ratio (`trackers/ratio`), trend (`trackers/trend`, in words),
  volumes (`trackers/volumes`) — a header slot for the alert badge (`trackers/alert`) and the refused
  identifier (`trackers/identifier-refused`), both EMPTY until phase 8 wires their derivation.
- **`features/trackers/queries.ts`** — the summary read's query, declared by the feature (the frame
  never names it).
- **`harness/states/trackers.ts`** — `trackers-roster`, `trackers-roster-empty`.
- **`i18n/fr.json`** — `screens.trackers.ratio`, `.trend`, `.volumes`, `.empty`.

## Mutation

`scripts/mutate.sh` swaps one row's drawn tracker for its neighbour's field. The rule must fall,
naming which tracker's ratio was drawn under the wrong name.

## Register

DOIT-13's row moves from `to draw` toward its first half `served` — the per-tracker roster, not yet
the policy (4), the Torrents tab (5) or the alert (8, 9). The closing phase (16) reads and reports the
exact wording.

## Oracle: states that diverge, declared by name

**None.** `trackers-roster` and `trackers-roster-empty` are NEW — the reference records them and
proves nothing about them (D8). No EXISTING state's region changes. Any divergence elsewhere is
**STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for both new states.

## Commit

`feat(maquette-l16): the Trackers tab, one entry per tracker, never averaged`
