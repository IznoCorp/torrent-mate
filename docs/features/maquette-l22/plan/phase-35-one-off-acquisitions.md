# Phase 35 — One-off acquisitions: a hand-added arrival joins the follow it matches; a season of an unfollowed series

**Born 2026-09-27 from the operator's round 10, questions 1 and 2 (A and A)**, placed by the steward beside the one-off
arrival card. **One phase if the total holds under 15, else cut in two at its opening.**

**Opening measure (estimate — RE-MEASURED at the opening):**

- **Q1 = A — the steward says it may be FROZEN here**: a hand-added arrival that matches, by provider identity after
  identification, an item a follow waits for JOINS that follow's acquisition — the same requesters, its ladder moves to
  « arrivé », « ajouté dans qBittorrent » as the release's origin; never two cards, never a second take; « Suivre » is
  absent (already followed). An exception to ruling 1 for this case alone. Backend demand: matching by identity after
  identification (DESIGN § 6.2).
- **Q2 = A**: taking a season of an owned, UNFOLLOWED series creates a ONE-OFF acquisition, never a follow; its card
  offers « Suivre » (the phase-17 offer, R229). L21's form « Série suivie et saison N demandée » is REOPENED — its
  readers (`season_grab_unfollowed.py` among them) re-aimed OUT LOUD. The backend demand « starts a follow » is amended
  by the auditor.
- **Points ≈ 16** (Q1 ≈ 8: the mock's join 3, the origin line 1, the hold + mutation 3, state 1; Q2 ≈ 8: the season verb
  re-wired 2, the L21 readers re-aimed 2, the hold + mutation 3, state 1) → **likely cut**.

## Red today

A rule: a hand-added arrival of a followed item is ONE card, on the follow's acquisition, with the hand-added origin and
no « Suivre »; a season taken on an unfollowed series creates no follow and its card offers « Suivre ».

## Mutation

Two cards for the matched arrival → falls; the season verb creates a follow → falls.

## Commit

`feat(maquette-l22): one-off acquisitions join the follow they match, and never start one`
