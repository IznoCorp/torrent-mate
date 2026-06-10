# acquire-store Implementation Plan — INDEX

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement RP3 — the `acquire.db` SQLite store + single deletion authority that prevents
hit-and-run penalties on private trackers.

**Architecture:** Extract neutral SQLite machinery into `core/sqlite/` (event-free), add
`core/identity.MediaRef` and `core/delete_permit` port types, build the 4-table `acquire.db`
store under a single-writer leaf lock, and wire a fail-open `DeleteAuthority` into `dispatch/` and
`maintenance/` via the composition root — never as a direct import.

**Tech stack:** Python 3.11+, pydantic `_StrictModel`, `sqlite3`, `filelock`, `personalscraper.logger.get_logger`.

---

## Phases

| #   | Phase                                         | File                                | Status |
| --- | --------------------------------------------- | ----------------------------------- | ------ |
| 1   | core/sqlite extraction                        | phase-01-core-sqlite-extraction.md  | [ ]    |
| 2   | core/identity + AcquireConfig + acquire.json5 | phase-02-identity-config.md         | [ ]    |
| 3   | acquire/domain + schema + store               | phase-03-domain-schema-store.md     | [ ]    |
| 4   | core/delete_permit + acquire/delete_authority | phase-04-delete-permit-authority.md | [ ]    |
| 5   | Dispatch-time writer + per-site wiring        | phase-05-dispatch-wiring.md         | [ ]    |
| 6   | Guardrails + docs + gate                      | phase-06-guardrails-docs-gate.md    | [ ]    |

---

## Key invariants (apply throughout all phases)

- **core/ is event-free**: no `EventBus` import, no event emission in any `core/sqlite/` or `core/delete_permit.py` module.
- **Total lock order**: `pipeline.lock` > `indexer_lock` > `acquire.db.lock` (leaf). Never invert.
- **Deleters never import `acquire/`**: `dispatch/` and `maintenance/` import only `core.delete_permit` types; the concrete `DeleteAuthority` is injected at the composition root.
- **Logging**: always `personalscraper.logger.get_logger`, never `structlog.get_logger` directly.
- **`rg` search safety**: every `rg` command MUST include `--type py` or `-g '*.py'` to avoid scanning 14 GB fixtures.
- **Per-bug regression tests**: every bug found during implementation gets a test before or with the fix.

## Dependency chain

```
Phase 1 (core/sqlite)
  └─ Phase 2 (MediaRef + AcquireConfig)
       └─ Phase 3 (domain + store)
            └─ Phase 4 (delete_permit + delete_authority)
                 └─ Phase 5 (dispatch wiring)
                      └─ Phase 6 (guardrails + gate)
```

Each phase file opens with a **Gate** section listing what the previous phase must have produced.
Each sub-phase produces exactly one commit with scope `acquire-store`:
`{type}(acquire-store): description`.
