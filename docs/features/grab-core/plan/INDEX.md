# grab-core Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the RP5b grab orchestrator + acquisition service — hard-filter, cross-tracker
dedup, typed quality vocab, atomic-claim state machine, and `personalscraper grab` CLI.

**Architecture:** Seven phases build bottom-up: typed RP3a vocabulary (phase 01) → dedup engine
(02) → hard-filters (03) → orchestrator chain (04a) → service + state machine + wiring (04b) →
CLI (05) → docs + ACCEPTANCE + gate (06). Each phase is independently committable and leaves the
test suite green.

**Tech Stack:** Python 3.12, SQLite WAL, Typer, pytest, frozen kw_only dataclasses,
`personalscraper.logger.get_logger`, `BEGIN IMMEDIATE` write transactions.

---

## Phases

| #   | Phase                                                                                                           | File                                                   | Status |
| --- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ------ |
| 1   | RP3a vocab — `Resolution` + `QualityProfile` + `SourceCriteria` + json codecs + round-trip tests                | [phase-01-vocab.md](phase-01-vocab.md)                 | [ ]    |
| 2   | Cross-tracker dedup — `search_candidates` seam + token-set normalizer + dedup keys + `-QTZ` golden              | [phase-02-dedup.md](phase-02-dedup.md)                 | [ ]    |
| 3   | Hard-filters — resolution ordinal (fail-open None) + anchored audio regex + `audio` docstring fix               | [phase-03-filters.md](phase-03-filters.md)             | [ ]    |
| 4a  | Orchestrator — `GrabOrchestrator` §1 chain + failure taxonomy + events + adversarial tests                      | [phase-04a-orchestrator.md](phase-04a-orchestrator.md) | [ ]    |
| 4b  | Service + state machine + wiring — `AcquisitionService` + store methods + `GrabCore` handle + concurrency tests | [phase-04b-service.md](phase-04b-service.md)           | [ ]    |
| 5   | CLI — `personalscraper grab` + `--dry-run` + `--limit` + e2e test                                               | [phase-05-cli.md](phase-05-cli.md)                     | [ ]    |
| 6   | Docs + ACCEPTANCE + gate — architecture.md, reference doc, ACCEPTANCE.md, `make check`                          | [phase-06-gate.md](phase-06-gate.md)                   | [ ]    |
