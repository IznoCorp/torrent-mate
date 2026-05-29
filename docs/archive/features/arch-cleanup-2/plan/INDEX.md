# arch-cleanup-2 — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan phase-by-phase.
> Each phase file is self-contained and bounded for a single agent context window.

**Feature:** Architecture Cleanup Round 2 (Web-Facing Enablers)
**Branch:** `feat/arch-cleanup-2`
**Codename:** `arch-cleanup-2`
**Version bump:** 0.16.0 → 0.17.0 (minor, Y+1)
**Commit scope:** `(arch-cleanup-2)` on every commit

---

## Goal

Remove the four concrete architectural defects that block web-facing roadmap items
(Web Management UI, Watcher Service, Web UI Registry Consumer):

1. 5 registry events bypass the `Event` base contract — no `correlation_id`, not
   round-trippable, dropped by base-`Event` subscribers.
2. No `schema_version` on the `Event` envelope — first cross-process consumer
   will break silently on a shape change.
3. `core/` and `conf/` have upward import leaks into `api/` — inverting the
   documented acyclic direction.
4. `sorter.file_type` is an undeclared utility dependency of ~10 non-sorter
   packages — turns a pipeline step into a shared utility.

---

## Phase Table

| #   | Phase                                            | File                                                     | Status |
| --- | ------------------------------------------------ | -------------------------------------------------------- | ------ |
| 1   | Event contract: schema_version + registry events | [phase-01-event-contract.md](phase-01-event-contract.md) | [ ]    |
| 2   | Layering: relocate shared primitives down        | [phase-02-layering.md](phase-02-layering.md)             | [ ]    |
| 3   | media_types promotion                            | [phase-03-media-types.md](phase-03-media-types.md)       | [ ]    |
| 4   | Docs + feature PR                                | [phase-04-docs-pr.md](phase-04-docs-pr.md)               | [ ]    |

---

## Constraints (apply to every phase)

- **No migration scripts.** Pre-1.0, single mono-user instance — shapes evolve in place.
- **Module-size ceiling:** hard block at 1000 non-blank LOC (excludes `__init__.py`).
  Run `python3 scripts/check-module-size.py` after every phase.
- **Regression-test-per-bug:** any surfaced bug gets a reproducer test landed with the fix.
- **Google-style docstrings** on all new modules, classes, and functions.
- **Comments in English.**
- **`rg` type filter mandatory:** every `rg` command MUST include `-t py` or `-g '*.py'`.
  The repo has 14 GB of binary fixtures under `tests/e2e/perf/.fixture/` that will
  crash the machine without a type filter.
- **Commit per sub-task.** Format: `{type}(arch-cleanup-2): description`.

## Non-goals (HARD — do not pull in)

- `lib-fold` feature
- `multi-filesystem` feature
- DI container / `ServiceContainer`
- Any Web UI / FastAPI code
- Logger relocation (logger is allow-listed as a leaf utility for `core`/`conf`)

## Full Acceptance Suite (all 17 criteria must pass before PR merge)

See each phase file's **Acceptance** section for the subset relevant to that phase.
The complete suite lives in `docs/features/arch-cleanup-2/DESIGN.md §6`.

```bash
make check          # ACC-01 — exit 0
cat VERSION         # ACC-15 — stdout: 0.17.0
grep -c '^## \[0.17.0\]' CHANGELOG.md   # ACC-16 — stdout: 1
python -c "import personalscraper; print('ok')"  # ACC-17 — stdout: ok
```
