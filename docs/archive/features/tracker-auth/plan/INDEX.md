# tracker-auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a broken-tracker-credential 401/403 failure observable by emitting a typed `TrackerAuthFailed` event, and fix a latent Transmission `add()` crash at the same grab site.

**Architecture:** Two independently-testable units. Phase 1 adds the `TrackerAuthFailed` event class to the acquisition catalog and wires the six hard-pinned count surfaces (hub re-export, two catalog count-pins, factory, subscriber subscription + token-pin). Phase 2 emits that event from the orchestrator's `except TrackerAuthError` branch and switches the grab from `add(category=None, tags=(provider,))` (which a Transmission client rejects with `ValueError`) to **add-first, then tag** with a non-fatal inner swallow.

**Tech Stack:** Python 3.12, frozen `@dataclass` events over `core.event_bus.Event`, EventBus pub/sub, pytest, `make check` (ruff + mypy + tests + module-size).

**Source of truth:** `docs/features/tracker-auth/DESIGN.md` (code-grounded + adversarially reviewed). This plan transcribes its specifics; do not re-invent.

---

## Conventions

- **One sub-phase = one commit.** Commit format: `<type>(tracker-auth): <description>` (Conventional Commits; types `feat|fix|chore|refactor|test|docs`).
- **Google-style docstrings** mandatory on all new code (modules, classes, functions, methods).
- **Test-per-behaviour.** Tests marked _mutation-checked_ MUST fail when the production change is reverted — verify that during execution.
- **No backcompat / migration** (project < 1.0.0).
- Every count-pin task states the **exact `file:line` and old→new value**.
- `rg` MUST carry `--type py` / `-g '*.py'` (14 GB media fixture under `tests/e2e/perf/.fixture/` crashes the machine if scanned unfiltered).

## Phases

| #   | Phase                                      | File                                   | Status |
| --- | ------------------------------------------ | -------------------------------------- | ------ |
| 1   | TrackerAuthFailed event + catalog plumbing | phase-01-event-catalog-plumbing.md     | [ ]    |
| 2   | Grab emit + Transmission add() fix         | phase-02-grab-emit-transmission-fix.md | [ ]    |

## Dependency order

Phase 2 depends on the `TrackerAuthFailed` symbol produced by Phase 1 — the orchestrator imports and emits it. Execute phases in order. Each phase file opens with a **Gate** section listing what the previous phase produced.
