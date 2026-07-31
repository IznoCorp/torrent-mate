# Implementation Progress — decisions-spine

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Project the scraping-decision / resolution state onto the provenance spine
(F2 of the tracking-spine epic) — an advisory `resolution_state` column on
`staging_provenance` that mirrors the decision lifecycle for follow-driven items;
`scrape_decision` stays authoritative & fail-loud; no DB fusion, no read_model rewrite.
**Type**: feat
**Version bump**: 0.68.0 → 0.69.0 (minor)
**Branch**: feat/decisions-spine
**Ticket**: #360 — claimed
**PR merge**: auto (operator-authorized epic contract)
**Design**: docs/features/decisions-spine/DESIGN.md
**Epic roadmap**: docs/features/provenance/EPIC-ROADMAP.md (F0 → F5)

## Non-negotiable invariants

- Advisory PROJECTION: `scrape_decision` (library.db) stays the authoritative, fail-loud
  system-of-record; the spine column is a best-effort mirror (wipe ⇒ today's behaviour).
- Decisions are the SUPERSET: a manual/direct item (no spine row) writes NOTHING to the
  spine and remains fully resolvable via the existing decisions UI (ACC-06 preserved).
- No DB consolidation (acquire.db + library.db stay separate); no read_model/stages rewrite
  (the "À traiter" control list keeps reading `scrape_decision` directly).
- Every spine write is `_safe_write` (logged + swallowed, never fails a step).

## Autonomous epic contract (operator-authorized — run F0→F5 without stopping)

- Auto-merge each feature's PR the moment adversarial review is clean AND CI is green.
- Nothing left behind: every bug/gap found mid-epic is fixed inline. Nothing deferred.
- Only stop-condition: an EXTERNAL CI outage (billing/runner) blocking a merge — surface,
  do not bypass branch protection without sign-off.

## Phases

| #   | Phase                                                                      | File                     | Status |
| --- | -------------------------------------------------------------------------- | ------------------------ | ------ |
| 1   | Spine schema + store (migration 011, ProvenanceRow, set_resolution, ports) | phase-01-schema-store.md | [ ]    |
| 2   | Write hooks (enqueue / resolve / dismiss) + anti-regression tests          | phase-02-write-hooks.md  | [ ]    |
| 3   | Read surface (JourneyItem + endpoint + ParcoursPanel badge) + gate + PR    | phase-03-read-surface.md | [ ]    |

**Next action**: Phase 1 — spine schema + store.
