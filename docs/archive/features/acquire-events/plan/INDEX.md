# acquire-events — Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan phase-by-phase.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Feature:** RP4 — acquisition event catalog + muted Telegram subscriber (0.26.0 → 0.27.0)
**Design:** `docs/features/acquire-events/DESIGN.md`
**Branch:** `feat/acquire-events`

---

## Phases

| #   | Phase                                                              | File                          | Status |
| --- | ------------------------------------------------------------------ | ----------------------------- | ------ |
| 1   | Event catalog (`acquire/events.py`) + hub registration + factories | `plan/phase-01-events.md`     | [ ]    |
| 2   | Muted Telegram subscriber + config flag + CLI wiring               | `plan/phase-02-subscriber.md` | [ ]    |
| 3   | Docs update + ACCEPTANCE.md + `make check` gate                    | `plan/phase-03-docs-gate.md`  | [ ]    |

---

## Dependency chain

```
Phase 1  ──►  Phase 2  ──►  Phase 3
  (events)    (subscriber)   (docs + gate)
```

Each phase has a **Gate** section (what the previous phase produced).
Each sub-phase produces exactly one commit with scope `(acquire-events)`.
