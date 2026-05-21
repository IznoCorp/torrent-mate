# Implementation Plan — tech-debt

**Codename** : `tech-debt`
**Branch** : `fix/tech-debt`
**Design** : `docs/features/tech-debt/DESIGN.md`
**Type** : bugfix (0.15.0 → 0.15.1)

4 phases, 22 sub-phases. Each sub-phase = 1 commit with scope `(tech-debt)`.

## Phases

| #   | Phase                            | File                              | Status |
| --- | -------------------------------- | --------------------------------- | ------ |
| 1   | Critical bug fixes               | phase-01-critical-bugs.md         | [ ]    |
| 2   | Design vs reality reconciliation | phase-02-design-reconciliation.md | [ ]    |
| 3   | Cross-feature tech debt          | phase-03-tech-debt.md             | [ ]    |
| 4   | Polish + final ACCEPTANCE pass   | phase-04-polish.md                | [ ]    |

## Phase summaries

### Phase 1 — Critical bug fixes (1-2 days)

Closes Pattern A findings : library/rescraper DEV #2 vector still alive (C1), missing CLI for backfill-ids (C2), library-index concurrent-migration race (C5), `.env.example` drift (C6). High-impact, low-risk fixes that restore the trust-but-verify claims in provider-ids' ACCEPTANCE.md.

### Phase 2 — Design vs reality reconciliation (1-2 days)

Closes the gap between provider-ids documentation and code reality. Monolithic Protocol cleanup decision (C3), ACCEPTANCE.md truth-up with verifiable commands (I3), DEVIATIONS.md gitignore policy. Auto-backfill trigger after process step (I5) — wires the post-scrape hook the DESIGN promised but never landed.

### Phase 3 — Cross-feature tech debt (2-3 days)

The systemic debt accumulated across multiple features. Module-size splits to clear the 5-versions-overdue hard-block (I1), narrow/justify the 44 broad `except Exception` (I2), migrate `library/recommender.py` off legacy flat IDs, integration-test scaffold (I4). Sets up the mock-realism sweep to catch future API drift.

### Phase 4 — Polish + final ACCEPTANCE pass (½-1 day)

Documentation hygiene (N1-N7) : module docstrings sweep, retired-version refs cleanup, doc inconsistencies, env var documentation, `personalscraper info` test, deprecation cleanup. Closes with a full re-run of provider-ids' ACCEPTANCE table on the live instance to verify every criterion now holds.
