# Implementation Progress — arch-cleanup-2

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Architecture Cleanup Round 2 (Web-Facing Enablers) (minor)
**Version bump**: 0.16.0 → 0.17.0
**Branch**: feat/arch-cleanup-2
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/28
**Design**: docs/features/arch-cleanup-2/DESIGN.md
**Master plan**: docs/features/arch-cleanup-2/plan/INDEX.md

## Phases

| #   | Phase                                            | File                         | Status |
| --- | ------------------------------------------------ | ---------------------------- | ------ |
| 1   | Event contract: schema_version + registry events | phase-01-event-contract.md   | [x]    |
| 2   | Layering: relocate shared primitives down        | phase-02-layering.md         | [x]    |
| 3   | media_types promotion                            | phase-03-media-types.md      | [x]    |
| 4   | Docs + feature PR                                | phase-04-docs-pr.md          | [x]    |
| 5   | PR fixes cycle 1                                 | phase-05-pr-fixes-cycle-1.md | [x]    |

## Review cycles

### Cycle 1 — 2026-05-29 (PR #28, CI green)

5 review agents (code-reviewer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer, comment-analyzer) on `main...feat/arch-cleanup-2`. **Verdict: DO NOT MERGE — 1 critical, then fix cycle.**

**Retained findings → fix phase 5:**

- **CRITICAL** — 3/5 registry events (`ProviderExhaustedEvent`, `RegistryFanOutCompleted`, `LockedCapabilityUnresolved`) raise `NameError` in `event_from_envelope` because `AttemptOutcome`/`ProviderMatch` are `TYPE_CHECKING`-only imports under `from __future__ import annotations`; `get_type_hints` can't resolve them. Breaks the Phase-1 catalog round-trip guarantee. Verified by 4 agents. (+ regression test: round-trip ALL registered events.)
- **MAJOR** — `event-bus.md` prose says 23 events but table lists 22 (`VerifyItemDone` omitted).
- **MAJOR** — layering guard is not self-pinned (no positive-control test that a real upward import IS caught; vacuous-pass risk) + `# layering: allow` marker doesn't enforce the justification comment it documents.
- **MEDIUM** — no identity test for `_contracts` re-exports (`api._contracts.X is core._contracts.X`); invariant is claimed in a comment + relied on by `circuit.py isinstance(exc, ApiError)`.
- **MEDIUM** — `architecture.md` "enforced" claim omits the 2 surviving `# layering: allow` exceptions; `RegistryBootValidated` producer mis-attributed to `_build_app_context` (emitted in `ProviderRegistry.__init__`).
- **MINOR** — heterogeneous-tuple decode branch uses `zip` (silent truncation; latent, no event hits it yet); `is_trailer_filename` case-insensitivity untested; `schema_version` "don't override at call sites" doc; `FileType`/`MediaType` cross-ref doc.

**Ignored/out-of-scope:** lib-fold/multi-filesystem/DI/web-ui absence; `movie_service.py` size (tech-debt-2). **No design contradictions** (the critical is a bug vs the design's intent, not a contradiction → fix, not escalate).

### Cycle 2 — 2026-05-29 (PR #28, CI green @ 203d848d)

Re-review of the cycle-1 fix diff (`dfe23fe5..203d848d`) by code-reviewer + silent-failure-hunter, both with empirical verification (mypy 0/276, `pytest tests/architecture/ tests/event_bus/` 512 passed). **Verdict: CLEAN — 0 critical/major/medium findings. MERGE.**

- CRITICAL resolved & proven: regression test `test_every_registered_event_round_trips_through_json` FAILS pre-fix (3 NameErrors) / PASSES post-fix; `_types.py` is a true leaf (no import cycle, mypy 0/276); single canonical definition + identity-preserving re-exports; all callers on the public path intact.
- Guard self-pin non-vacuous; `zip(strict=True)` cannot break any live decode (homogeneous `tuple[X, ...]` is an earlier branch); docs accurate (event-bus 23 rows, RegistryBootValidated producer, layering exceptions).
- Only minor informational notes (permissive justification heuristic; single round-trip test covers 22 of 23 — VerifyItemDone has its own coverage) — no action.

**Loop exit: Case A.** Merge mode = manual → handed to user. CI 9/9 green; PR #28 OPEN / MERGEABLE / mergeStateStatus CLEAN.

## Next action

Merge PR #28 (squash, manual). After merge, archival of arch-cleanup-2 folds into the next feature's `/implement:create-branch` (prev_codename=arch-cleanup-2).
