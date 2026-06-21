# anchor — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repatriate board-view state (columns + card placement + intra-column order) into a native backend behind the existing board port, so the helm/bridge SPA can host the board natively off GitHub Projects v2.

**Architecture:** A `NativeBoardBackend` decorator composes the existing `GithubClient` for all forge ops (issues, comments, PRs) and overrides only placement (`cheap_probe`, `snapshot`, `move_card`) using a new `FsBoardStateStore`. A per-project `board_backend` switch in `WiringConfig` (default `github`) keeps every live daemon byte-identical until an explicit opt-in. A one-way GitHub mirror keeps the GitHub Projects board + status pill + Health field reflecting native placement.

**Tech Stack:** Python 3.11+, stdlib only (`json`, `fcntl`, `os.replace`), FastAPI (already in `[ui]` extra), Typer (already in deps). Zero new third-party dependencies.

## Global Constraints

- `board_backend` defaults to `"github"` — every live daemon is byte-identical until operator opt-in.
- No new third-party dependency: `pyproject.toml` and `.github/workflows/pr.yml` are UNCHANGED.
- `core/` imports nothing with I/O — store lives in `ports/`+`adapters/`, never `core/`.
- All commit scopes: `anchor`. Format: `feat(anchor): <desc>` / `test(anchor): <desc>` / etc.
- No AI attribution in commits (enforced by hook). No `IMPLEMENTATION.md` edits (written by create-branch stage).
- All test assertions on CLI/Rich output are terminal-width and ANSI-independent.
- Column keys in tests use the real HYBRID keys from `core/transitions_defaults`: `Backlog`, `Brainstorming`, `Spec`, `Plan`, `Planned`, `ReadyToDev`, `PrepareFeature`, `InProgress`, `PRCI`, `Review`, `Merge`, `Done`, `Cancel`, `Blocked`.
- `flock` + `os.replace` atomic-write discipline on every `FsBoardStateStore` write (same as `fs_store.py`).
- `make check` (lint + test + module-size guard) must pass green at every phase gate.

---

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | Native board store | phase-01-native-store.md | [ ] |
| 2 | NativeBoardBackend decorator | phase-02-native-backend.md | [ ] |
| 3 | Wiring + registry + daemon switch | phase-03-wiring-registry.md | [ ] |
| 4 | Import migration + CLI | phase-04-import-cli.md | [ ] |
| 5 | helm HTTP API board routes | phase-05-http-routes.md | [ ] |
| 6 | Version bump + final gate | phase-06-version-gate.md | [ ] |
