# Phase 04 — Final gate

**Goal**: Full quality gate, version bump, production-ready verification. No code changes —
this phase validates all previous phases together and ships.

## Surface

| File                                         | Action                          |
| -------------------------------------------- | ------------------------------- |
| `pyproject.toml`                             | Bump version to `0.52.0`        |
| `docs/features/pipeline-panel/ACCEPTANCE.md` | Write ACC criteria (executable) |

## Sub-phases

### 4.1 — Version bump + full gate suite

**Commit**: `chore(pipeline-panel): bump version to 0.52.0`

- `pyproject.toml`: version `"0.52.0"` (patch bump over 0.51.x, operator directive).
- Run complete gate:
  ```bash
  make lint && make test
  cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run
  ```
- All must be green (0 errors, 0 failures). Expected test count: ~6000+ (backend) + ~1556+
  (frontend, before migration additions).
- Verify `GET /api/version` returns `0.52.0` at boot (the cached BUILD_COMMIT).
- Confirm `git diff origin/main --stat` shows ONLY frontend files + pyproject.toml + docs
  (no backend `.py` changes).

### 4.2 — OpenAPI drift check + ACC criteria

**Commit**: `docs(pipeline-panel): ACC criteria for stepper + history + redirect`

- Run `make openapi` and assert `git diff --exit-code` on `openapi.json` and `schema.d.ts`
  — must be clean (no backend route change).
- Write `docs/features/pipeline-panel/ACCEPTANCE.md` with executable criteria:

```
ACC-01: red anomaly always visible (desktop)
  cd frontend && npx vitest run --reporter=verbose 2>&1 | grep "FlowBoard"
  Expected: all FlowBoard tests pass, including compact-variant + blocked-step-expanded

ACC-02: mobile vertical list (390px iframe)
  # Manual: open /pipeline in 390px iframe, assert document.documentElement.scrollWidth <= 390

ACC-03: history repatriated
  curl -s http://localhost:PORT/pipeline | grep -c "Historique des exécutions"
  Expected: 1 (history table renders on Pipeline)

ACC-04: maintenance cleaned
  curl -s http://localhost:PORT/maintenance | grep -c "Historique des exécutions"
  Expected: 1 (only maintenance-run table remains)

ACC-05: ?run= opens RunDetail on Pipeline
  curl -s http://localhost:PORT/pipeline?run=<test-uid> | grep "Exécution"
  Expected: RunDetail card renders

ACC-06: /maintenance?run= redirects
  curl -sI http://localhost:PORT/maintenance?run=<test-uid> | grep "HTTP/.* 30[12]"
  Expected: redirect status

ACC-07: /maintenance alone renders
  curl -s http://localhost:PORT/maintenance | grep "Maintenance"
  Expected: page heading present

ACC-08: legend popover accessible
  # Manual: tap legend trigger on /pipeline (mobile 390px), assert popover opens
```

- Note: ACC-02 and ACC-08 are manual (no Chrome-MCP automation — matrix is via the
  real 390px iframe harness protocol from `feedback_test_mobile_at_real_width_iframe_harness`).

## Gate

- [ ] `make lint` → 0 errors
- [ ] `make test` → all 6000+ tests pass, 0 failures
- [ ] `make check` → lint + test + module-size + typed-api all green
- [ ] `python -c "import personalscraper"` → clean import
- [ ] `cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run` → all green
- [ ] `make openapi && git diff --exit-code -- openapi.json frontend/src/api/schema.d.ts` → clean
- [ ] `git diff origin/main -- '*.py'` → empty (zero backend changes)
- [ ] `/api/version` serves `0.52.0`
- [ ] All 8 ACC criteria exercised (2 manual via iframe harness)
