# Phase 19 — The close

**Kind** gate. It writes no feature and it is not optional.

## The « Done when », line by line

Each line of `frontend-architecture.md` § 4's L15 entry is re-derived by its own command, and the
output is pasted into the pull request:

1. **The inventory command** (`SURVEY.md` § 1.1) lists only the Découvrir feed, the popover's
   content and the harness panel — nothing of the frame.
2. `#nav`, `#drawer`, `#dlg` and `#toast` are **React-rendered at their ids**.
3. **One navigation table**: `grep -n "PAGES_OF\|NAVIGATION" legacy.js` lists the seam's read sites
   only — no declaration of either.
4. **P1, P2, P3's dialog rung, P14's landmine and P21** are each held by a rule seen to bite.
5. The **B-142 arm** is in the contracts tier with its mutation.
6. The **oracle** is green at every step, or its divergences are accepted with named reasons.
7. The **hold counts are unchanged** — no rule lost a hold. Counted per file, not in total: a total
   hides one rule losing three while another gains three.
8. The **accessibility tier reads zero** over every named state.

## The three measurements this wave owes elsewhere

- **`app/`'s domain-word ceiling** is re-read and written into
  `scripts/frame-domain-baseline.json` with its reason (D-L15-6), and the four files that carried
  the page list before the table are re-read in the same move.
- **B-085's figure for this wave** goes into `BUGS.md` § « Guards green over what they do not
  read », added to the running total of 98. **Zero is a real answer**; so is six.
- **The register** is complete — every finding filed as it was found, never in a commit message.

## The gates

`frontend/maquette/harness/run.sh` (the FULL suite, no flag), `run.sh --a11y`, and `make check` at
zero failures and **zero errors**. An ERROR means collection crashed and everything after it was
skipped.

## And the row

`IMPLEMENTATION.md`'s « In flight » row was written the moment the pull request opened — pull
request number first, then the version — and `scripts/check-implementation-state.py` is what holds
it. Moving it to « Last landed » is a POST-MERGE step and belongs to whoever merges, with the two
oracle re-record commands.
