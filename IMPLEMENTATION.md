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
- **Manual/direct grabs create NO row and are byte-for-byte unaffected** (ACC-06) —
  BOTH senses: torrents added directly in qBittorrent AND any personalscraper grab
  launched without a follow/wanted. Zero provenance code path executes for them.
- No DB consolidation: acquire.db + library.db stay separate; joins at read time.

## Autonomous epic contract (operator-authorized — run F0→F5 without stopping)

- **Auto-merge** each feature's PR the moment my adversarial review is clean (findings
  fixed) AND CI is green. No human gate.
- **Nothing left behind**: every bug/gap discovered mid-epic (small OR large) is fixed
  INLINE. Nothing deferred, ticketed-for-later, or declared out-of-scope. All done.
- **UI placement (F1/F5)**: my judgment per product-intent (mobile 390px); show the render.
- **F2**: MIGRATE the resolution state onto the spine (deep integration), guarded by
  adversarial review + anti-regression tests (do not regress the decisions flow).
- Defaults: F4 = CLI + web buttons; bump = minor per feature (0.67→0.72); prod UI
  verification = deployed-bundle + guarded-endpoints (authed visual is the operator's —
  a capability boundary, I cannot enter prod credentials).
- **Only stop-condition**: an EXTERNAL CI outage (billing/runner, not my code) blocking a
  merge — I do NOT bypass branch protection without sign-off; I surface that one case.
- Per feature loop: kanban claim + heartbeat → DESIGN+plan (just-in-time for F1-F5) →
  phases (rouge-avant) → feature-pr → adversarial pr-review → auto squash-merge → prod
  verify → kanban Done → immediately the next feature.

## Phases

| #   | Phase                                   | File                            | Status |
| --- | --------------------------------------- | ------------------------------- | ------ |
| 1   | Schema + ProvenanceStore                | phase-01-schema-store.md        | [x]    |
| 2   | Grab + ingest write points              | phase-02-grab-ingest.md         | [x]    |
| 3   | Sort/rename + dispatch write points     | phase-03-sort-dispatch.md       | [x]    |
| 4   | #30 consumer — scrape identity resolver | phase-04-scrape-consumer.md     | [x]    |
| 5   | Reconcile + advisory-overlay hardening  | phase-05-reconcile-hardening.md | [ ]    |

**Master plan**: docs/features/provenance/plan/INDEX.md
**Next action**: run `/implement:phase` to execute phase 1.

> Note: the provenance READ surface (« vue parcours ») is deferred to F1 (next feature
> of the epic), not F0.
