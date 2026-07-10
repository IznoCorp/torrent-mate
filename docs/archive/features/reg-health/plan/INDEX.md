# reg-health Implementation Plan — INDEX

> **Feature**: S6 Web UI — Registry + Health (`feat/reg-health`, branch `feat/reg-health`)
> **KanbanMate**: ticket #185
> **DESIGN**: `docs/features/reg-health/DESIGN.md` (5 phases, §5)
> **Bump**: minor (`0.45.1 → 0.46.0`) — additive read surface + new page, no breaking change.

## Phases

| N   | Phase name                           | Plan file                                                  | Status |
| --- | ------------------------------------ | ---------------------------------------------------------- | ------ |
| 1   | S6.0 contract freeze + latency field | [phase-01-freeze-latency.md](phase-01-freeze-latency.md)   | [ ]    |
| 2   | REST read route                      | [phase-02-rest-route.md](phase-02-rest-route.md)           | [ ]    |
| 3   | Frontend typed client + hook         | [phase-03-frontend-client.md](phase-03-frontend-client.md) | [ ]    |
| 4   | Frontend page + nav                  | [phase-04-frontend-page.md](phase-04-frontend-page.md)     | [ ]    |
| 5   | Integration + ACC + docs             | [phase-05-integration-acc.md](phase-05-integration-acc.md) | [ ]    |

## Gate sequence

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5
  │            │            │            │            │
  │            │            │            │            └── make check + CI green
  │            │            │            └── npm lint+typecheck+vitest + make openapi drift clean
  │            │            └── npm lint+typecheck+vitest
  │            └── make check + make openapi (commit regen) + route tests
  └── make check + characterization freeze test passes
```

## DESIGN → Phase mapping

| DESIGN §5 item                          | Phase   | What it covers                                                                                                   |
| --------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------- |
| 1. S6.0 contract freeze + latency field | Phase 1 | `last_latency_ms` on ProviderStatus, characterization freeze test, latency instrumentation at transport boundary |
| 2. REST read route                      | Phase 2 | `GET /api/registry/status`, Pydantic models, OpenAPI regen, route tests                                          |
| 3. Frontend typed client + hook         | Phase 3 | `frontend/src/api/registry.ts`, `useRegistryStatus` hook, Vitest                                                 |
| 4. Frontend page + nav                  | Phase 4 | `RegistryPage`, nav enable, stub replacement, Vitest + a11y                                                      |
| 5. Integration + ACC + docs             | Phase 5 | E2E, web-ui.md §registry, ACCEPTANCE.md, final gate                                                              |
