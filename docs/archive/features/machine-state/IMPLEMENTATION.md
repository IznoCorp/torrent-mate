# Implementation Progress — machine-state

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Unified « état de la machine » overview (F5 capstone of the tracking-spine
epic) — acquisitions + pipeline + décisions + en-attente rolled up on one view, consuming
the F0–F4 spine. Backend aggregate endpoint + « Vue d'ensemble » tab on the Acquisition hub.
**Type**: feat
**Version bump**: 0.71.0 → 0.72.0 (minor)
**Branch**: feat/machine-state
**Ticket**: #366 — claimed
**PR merge**: auto (operator-authorized epic contract)
**Design**: docs/features/machine-state/DESIGN.md
**Epic roadmap**: docs/archive/features/provenance/EPIC-ROADMAP.md (F0 → F5)

## Non-negotiable invariants

- Product-intent (BINDING) §2/§5/§8: rollup of the spine; every tile deep-links to the
  URL-addressable detail view. Counts are an UNCAPPED SQL aggregate (never a frontend count
  over the 200-capped list_journeys — §méthode rule 6).
- awaiting_resolution uses the AUTHORITATIVE scrape_decision pending count (not the advisory
  spine mirror); no DB fusion; no migration (read-only aggregate).
- The overview endpoint is read-only, NOT staging-guarded, side-effect-free (staging-safe).
- No change to existing endpoints / decisions / pipeline flows; stage_counts fail-soft.

## Autonomous epic contract (operator-authorized — run F0→F5 without stopping)

- Auto-merge each feature's PR the moment adversarial review is clean AND CI is green.
- Nothing left behind: every bug/gap found mid-epic is fixed inline. Nothing deferred.
- Only stop-condition: an EXTERNAL CI outage (billing/runner) blocking a merge — surface,
  do not bypass branch protection without sign-off.

## Phases

| #   | Phase                                                                            | File                 | Status |
| --- | -------------------------------------------------------------------------------- | -------------------- | ------ |
| 1   | Backend aggregate (stage_counts + AcquisitionOverviewResponse + GET /overview)   | phase-01-backend.md  | [x]    |
| 2   | Frontend « Vue d'ensemble » tab (OverviewPanel + tiles + deep-links) + gate + PR | phase-02-frontend.md | [x]    |

**Next action**: all phases complete — phase gate + feature-PR.
