# tracker-economy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `TrackerProviderConfig` with an optional `TrackerEconomyConfig` data-carrier (ratio policy + seed-time fields) and a non-gating `resolve_optional_secret()` helper for announce passkeys; no runtime consumers added (Vague 5 deferred).

**Architecture:** Purely additive config-schema extension. A new `TrackerEconomyConfig` Pydantic model and `parse_duration()` helper live in `conf/models/`; a sibling `PROVIDER_OPTIONAL_SECRETS` map and `resolve_optional_secret()` live in `api/_activation.py` alongside the existing `PROVIDER_CREDS` / `resolve_active()`. Config files and reference docs are updated in place (no back-compat shims — pre-1.0 single instance).

**Tech Stack:** Python 3.11+, Pydantic v2 (`_StrictModel`, `field_validator`, `model_validator`), `json5`, `pytest`, `make check` (ruff + mypy + tests + module-size + typed-api).

---

## Phases

| #   | Phase                                                 | File                                                       | Status |
| --- | ----------------------------------------------------- | ---------------------------------------------------------- | ------ |
| 1   | Duration parser (`_duration.py`) + unit tests         | [phase-01-duration-parser.md](phase-01-duration-parser.md) | [ ]    |
| 2   | Economy schema model                                  | [phase-02-schema-model.md](phase-02-schema-model.md)       | [ ]    |
| 3   | Economy schema unit tests                             | [phase-03-schema-tests.md](phase-03-schema-tests.md)       | [ ]    |
| 4   | Optional-secret resolver + non-gating regression test | [phase-04-optional-secret.md](phase-04-optional-secret.md) | [ ]    |
| 5   | Config files + .env.example + reference doc           | [phase-05-config-files.md](phase-05-config-files.md)       | [ ]    |
| 6   | ACCEPTANCE.md + `make check` gate                     | [phase-06-acceptance.md](phase-06-acceptance.md)           | [ ]    |

## Dependency graph

```
Phase 1 (duration parser + tests)
    └── Phase 2 (economy schema model — uses parse_duration)
            └── Phase 3 (economy schema unit tests)
                    └── Phase 4 (optional-secret resolver + non-gating test)
                            └── Phase 5 (config files + .env.example + docs)
                                    └── Phase 6 (ACCEPTANCE + make check gate)
```

## Files touched

| File                                          | Action     | Phase |
| --------------------------------------------- | ---------- | ----- |
| `personalscraper/conf/models/_duration.py`    | **Create** | 1     |
| `tests/unit/test_duration.py`                 | **Create** | 1     |
| `personalscraper/conf/models/api_config.py`   | **Modify** | 2     |
| `tests/unit/test_tracker_economy_schema.py`   | **Create** | 3     |
| `personalscraper/api/_activation.py`          | **Modify** | 4     |
| `tests/unit/test_activation.py`               | **Modify** | 4     |
| `config.example/tracker.json5`                | **Modify** | 5     |
| `config/tracker.json5`                        | **Modify** | 5     |
| `.env.example`                                | **Modify** | 5     |
| `docs/reference/config-overlay-layout.md`     | **Modify** | 5     |
| `docs/features/tracker-economy/ACCEPTANCE.md` | **Create** | 6     |

## Commit convention

All commits use scope `tracker-economy`:

```
feat(tracker-economy): <description>
fix(tracker-economy): <description>
docs(tracker-economy): <description>
test(tracker-economy): <description>
```
