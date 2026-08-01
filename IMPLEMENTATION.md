# Implementation Progress — season-grab

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Season Grab — whole-season acquisition (ticket #378): WantedKind "season",
auto trigger (last episode aired ≥1 week AND ≤ half owned), episode→season conversion
when a pack exists but the episode doesn't, absorption of episode wanteds, cutoff
fallback to episodes, manual per-season grab button, season ranking tiers (#376) live.
**Type**: feat
**Version bump**: 0.74.1 → 0.75.0 (minor)
**Branch**: feat/season-grab
**Ticket**: #378 — claimed (card in Brainstorming → advance per phase)
**PR merge**: auto — standing operator contract: adversarial review(s) + tests before merge.
**PR**: _(created after last phase)_
**Design**: docs/features/season-grab/DESIGN.md
**Master plan**: _(to be defined after /implement:plan)_

## Non-negotiable invariants (operator rules R1-R6 — DESIGN §2, frozen)

- R1 auto trigger: last episode aired ≥ 1 WEEK ago AND owned ≤ HALF the season.
- R2 conversion: episode search 0-exact + season pack present → season wanted, absorb.
- R3 uniformity: grabbing a season replaces ALL owned episodes (existing dispatch TV
  merge rule delivers it — no dispatch change).
- R5 absorption: absorbed episode wanteds get a dedicated traceable status, never
  searched again. R6 fallback at cutoff re-enqueues MISSING episodes only.
- Single-season packs only (v1). No triage changes (#213 owns the split).
- Web: staging-guarded typed route via guarded_api; OpenAPI regen committed.
- event_bus stays a REQUIRED parameter at any new emission site (project contract).

## Phases

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
