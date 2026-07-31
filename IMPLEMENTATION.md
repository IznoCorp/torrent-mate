# Implementation Progress — run-linkage

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Link each `pipeline_run` to the acquisitions it processed (F3 of the
tracking-spine epic) — per-stage nullable `*_run_uid` columns on `staging_provenance`
stamped fail-soft from the run correlation; `pipeline_run` stays authoritative & unchanged.
**Type**: feat
**Version bump**: 0.69.0 → 0.70.0 (minor)
**Branch**: feat/run-linkage
**Ticket**: #362 — claimed
**PR merge**: auto (operator-authorized epic contract)
**Design**: docs/features/run-linkage/DESIGN.md
**Epic roadmap**: docs/features/provenance/EPIC-ROADMAP.md (F0 → F5)

## Non-negotiable invariants

- Per-stage columns (grab/ingest/scrape/dispatch run uids): an acquisition is advanced by
  DIFFERENT runs at different stages (grab = its own maintenance run, OUTSIDE the full run).
- Grab stamp reads the `CliRunRecorder.run_uid` handle (its ContextVar is misaligned);
  ingest/scrape/dispatch read `current_correlation_id` → `.hex` (== pipeline_run.run_uid).
- Cross-DB back-link, NO FK; `pipeline_run`/PipelineRunWriter/steps_json untouched.
- Every column nullable + every write `_safe_write` (advisory; wipe ⇒ today's behaviour);
  manual/direct item (no spine row) gets no run stamp (ACC-06).

## Autonomous epic contract (operator-authorized — run F0→F5 without stopping)

- Auto-merge each feature's PR the moment adversarial review is clean AND CI is green.
- Nothing left behind: every bug/gap found mid-epic is fixed inline. Nothing deferred.
- Only stop-condition: an EXTERNAL CI outage (billing/runner) blocking a merge — surface,
  do not bypass branch protection without sign-off.

## Phases

| #   | Phase                                                                                           | File                     | Status |
| --- | ----------------------------------------------------------------------------------------------- | ------------------------ | ------ |
| 1   | Schema + store (migration 012, run_uid params, set_scrape_run, list_journeys_for_run)           | phase-01-schema-store.md | [x]    |
| 2   | Wire the 4 stages (grab/ingest/scrape/dispatch) + integration tests                             | phase-02-wire-stages.md  | [x]    |
| 3   | Read surface (JourneyItem run fields + ?run_uid= filter + ParcoursPanel deep-links) + gate + PR | phase-03-read-surface.md | [x]    |

**Next action**: all phases complete — phase gate + feature-PR.
