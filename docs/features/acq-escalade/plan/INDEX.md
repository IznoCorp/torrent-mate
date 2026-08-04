# acq-escalade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the acquisition queue converge on the media instead of retrying a query that
provably cannot succeed, and stop it asserting progress that is not happening.

**Architecture:** Four independent defects in the acquire lobe, fixed in dependency order. The
post-dispatch scan gets the process event bus so the reconcile subscriber can hear it (D4). The
search verdict grows an honest "degraded" path so a tracker outage stops being written as an
absence (D2) — which in turn makes `attempts` a count of *concluded* searches, the counter D1's
threshold reads. D1 then arms the episode→season escalation on that evidence. Finally the
operator's season-grab action triggers a run instead of waiting for cron (D3), after a
behaviour-constant extraction that makes room under the module-size ceiling.

**Tech Stack:** Python 3.12, SQLite (WAL), FastAPI + Pydantic, pytest, structlog, ruff + mypy.

## Global Constraints

- **TDD is mandatory** (explicit operator requirement): every phase writes its failing test
  before any implementation code, and runs it to observe the failure.
- **`event_bus` is a REQUIRED parameter** on every emit site — never `| None`, never a default.
  A default is exactly what produced D4.
- **`SearchVerdict.found` is NEVER `0`** on a non-concluded path (panne ≠ absence).
- **§6**: a legitimate operator action never answers 409. It executes, or it queues visibly.
  The only permitted refusal is idempotence on the same target.
- **Module size**: hard ceiling 1000 non-blank LOC. Current: `web/routes/acquisition.py` = 995,
  `acquire/orchestrator.py` = 956. Check with `python3 scripts/check-module-size.py`.
- **Google-style docstrings** on every module, class, function, method. Comments in English.
- **Any FastAPI route/model change** ⇒ `make openapi` + commit `frontend/openapi.json` and
  `frontend/src/api/schema.d.ts`.
- **Per-phase gate**: `make lint`, `make test`, `make check` all green before the phase commit.
- **Baseline**: 10257 passed, 7 skipped, 1 xfailed, 0 failed.
- **Conventional commits** with `(acq-escalade)` scope.

## Concurrency warning

A parallel feature `fix/media-sheet-data` is in flight in another worktree (created 2026-08-04
14:10, version 0.78.1, not merged). It touches `personalscraper/__init__.py`,
`frontend/openapi.json`, `frontend/src/api/schema.d.ts` and
`frontend/src/components/acquisition/FollowedPanel.tsx`. This feature took **0.78.2** to avoid
the version collision. Re-check the regenerated frontend artifacts before merge — resolve by
re-running `make openapi`, never by hand-merging generated files.

## Phases

| # | Phase | File | Defect | Status |
| --- | --- | --- | --- | --- |
| 1 | Propagate the process event bus into the post-dispatch scan | `phase-01-event-bus-propagation.md` | D4 | [ ] |
| 2 | `trackers_degraded` — a partial outage is not an absence | `phase-02-trackers-degraded.md` | D2 | [ ] |
| 3 | Escalate episode→season on search-failure evidence | `phase-03-starvation-escalation.md` | D1 | [ ] |
| 4 | Extract the season-grab route (behaviour-constant) | `phase-04-extract-season-grab-route.md` | — | [ ] |
| 5 | The operator action triggers the pass | `phase-05-operator-trigger.md` | D3 | [ ] |

**Order is load-bearing.** Phase 1 first because D4 masks the observable effect of everything
else (wanted rows never close, so no end-to-end proof is trustworthy). Phase 2 before phase 3
because it changes the meaning of `attempts`, which is phase 3's threshold. Phase 4 before
phase 5 because `acquisition.py` has 5 lines of headroom and phase 5 cannot fit in them.

## Known limitation of this plan

Several test bodies are specified as **name + docstring + assertions**, with an explicit
`...` where the arrange step goes and a pointer to the existing fixture module to reuse. That
is a deliberate, declared gap: inventing a parallel harness for `tests/acquire/` would be worse
than reusing the one those tests already share, and the exact fixture names must be read from
the tree at implementation time rather than guessed here.

The **assertions are complete and binding** — an implementer may fill the arrange step, never
weaken an assertion. If an assertion cannot be satisfied with the existing fixtures, that is a
finding to raise, not a licence to rewrite the test.

## ACCEPTANCE

Run from the repo root. Every criterion is an executable command with a documented expectation.

| ID | Command | Expected |
| --- | --- | --- |
| ACC-01 | `python scripts/check-acquisition-coherence.py; echo $?` | `0` — zero anomalies (**blocking**) |
| ACC-02 | `make lint` | exit 0, no ruff/mypy error |
| ACC-03 | `make test` | `NNNN passed`, 0 failed, 0 error |
| ACC-04 | `make check` | exit 0 |
| ACC-05 | `python3 scripts/check-module-size.py` | `web/routes/acquisition.py` absent from findings |
| ACC-06 | `make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts` | exit 0, no drift |
| ACC-07 | Dated real run proving the escalation on a genuinely starved season | season row enqueued + episodes absorbed, transcript pasted into `ACCEPTANCE.md` |

ACC-07 requires an executed, dated run — prose is not admissible (§méthode).
