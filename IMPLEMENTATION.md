# Implementation Progress — spine-actions

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Targeted maintenance actions driven by the provenance spine (F4 of the
tracking-spine epic) — re-scrape a precise grab / resume a stuck item / requeue by
journey state, keyed on `staging_provenance`. CLI + web buttons; reuses forced-scrape +
wanted-requeue seams; advisory + fail-soft.
**Type**: feat
**Version bump**: 0.70.0 → 0.71.0 (minor)
**Branch**: feat/spine-actions
**Ticket**: #364 — claimed
**PR merge**: auto (operator-authorized epic contract)
**Design**: docs/features/spine-actions/DESIGN.md
**Epic roadmap**: docs/features/provenance/EPIC-ROADMAP.md (F0 → F5)

## Non-negotiable invariants

- Reuse, don't rewrite: forced scrape (`scrape_{movie,tvshow}_forced` seeded from the spine
  `media_ref`) + `WantedStore.requeue_missing`; the maintenance registry (+ sync test),
  `library-rescrape`, and the decisions resolve path stay untouched.
- Web actions via the acquisition-trigger pattern (not the `library-*` registry). Every
  mutating endpoint carries `require_not_staging` + `require_x_requested_with` + `guarded_api`.
- Re-scrape holds only the per-item scrape lock (parallel-safe, exclusive with a full run);
  requeue is lock-free. `list_stuck` is fail-soft; manual/direct item (no row) = no-op (ACC-06).

## Autonomous epic contract (operator-authorized — run F0→F5 without stopping)

- Auto-merge each feature's PR the moment adversarial review is clean AND CI is green.
- Nothing left behind: every bug/gap found mid-epic is fixed inline. Nothing deferred.
- Only stop-condition: an EXTERNAL CI outage (billing/runner) blocking a merge — surface,
  do not bypass branch protection without sign-off.

## Phases

| #   | Phase                                                           | File                  | Status |
| --- | --------------------------------------------------------------- | --------------------- | ------ |
| 1   | Spine substrate (list_stuck + stuck flag on JourneyItem)        | phase-01-substrate.md | [x]    |
| 2   | CLI actions (acquisition-rescrape + acquisition-requeue)        | phase-02-cli.md       | [x]    |
| 3   | Web trigger endpoints + ParcoursPanel buttons/badge + gate + PR | phase-03-web.md       | [x]    |

**Next action**: all phases complete — phase gate + feature-PR.
