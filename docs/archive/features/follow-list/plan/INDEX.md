# follow-list Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the `_FollowSubStore` CRUD, add a title-resolution helper, and ship the `follow add/list/remove` CLI command group.

**Architecture:** Store CRUD lives in `acquire/store.py` + `acquire/_ports.py` (acquisition lobe, imports core/conf/api/events only). Title resolution is a helper in `acquire/` that calls the metadata `provider_registry`. The CLI command group mirrors `commands/grab.py` and is wired into `cli.py`.

**Tech Stack:** Python 3.12+, SQLite (WAL + BEGIN IMMEDIATE via `_write_tx`), Typer, Rich, frozen dataclasses.

---

| #   | Phase                                                 | File                                   | Status |
| --- | ----------------------------------------------------- | -------------------------------------- | ------ |
| 1   | Store CRUD (`_FollowSubStore` completion + Protocol)  | [phase-01-store.md](phase-01-store.md) | [ ]    |
| 2   | Title resolution helper (`acquire/title_resolver.py`) | [phase-02-title.md](phase-02-title.md) | [ ]    |
| 3   | `follow` CLI command group (`commands/follow.py`)     | [phase-03-cli.md](phase-03-cli.md)     | [ ]    |
| 4   | Docs + ACCEPTANCE + phase gate                        | [phase-04-gate.md](phase-04-gate.md)   | [ ]    |
