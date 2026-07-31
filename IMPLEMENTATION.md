# Implementation Progress — provenance

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Acquisition provenance spine (F0 of the tracking-spine epic) — advisory
per-hash registry linking grab→ingest→sort→scrape→dispatch; delivers #30 (deterministic
scrape identity, films + séries), zero regression on manual/direct grabs.
**Type**: feat
**Version bump**: 0.66.2 → 0.67.0 (minor)
**Branch**: feat/provenance
**Ticket**: #356 — claimed
**PR merge**: manual
**Design**: docs/features/provenance/DESIGN.md
**Epic roadmap**: docs/features/provenance/EPIC-ROADMAP.md (F0 → F5)

## Non-negotiable invariants (advisory overlay)

- FS + existing stores stay the source of truth; the registry is a fail-soft hint.
- Wiped registry ⇒ exactly today's behaviour (ACC-01).
- **Manual/direct grabs (no wanted row) create NO row and are byte-for-byte unaffected** (ACC-06).
- No DB consolidation: acquire.db + library.db stay separate; joins at read time (future features).

## Phases

| #   | Phase                                   | File                            | Status |
| --- | --------------------------------------- | ------------------------------- | ------ |
| 1   | Schema + ProvenanceStore                | phase-01-schema-store.md        | [ ]    |
| 2   | Grab + ingest write points              | phase-02-grab-ingest.md         | [ ]    |
| 3   | Sort/rename + dispatch write points     | phase-03-sort-dispatch.md       | [ ]    |
| 4   | #30 consumer — scrape identity resolver | phase-04-scrape-consumer.md     | [ ]    |
| 5   | Reconcile + advisory-overlay hardening  | phase-05-reconcile-hardening.md | [ ]    |

**Master plan**: docs/features/provenance/plan/INDEX.md
**Next action**: run `/implement:phase` to execute phase 1.

> Note: the provenance READ surface (« vue parcours ») is deferred to F1 (next feature
> of the epic), not F0.
