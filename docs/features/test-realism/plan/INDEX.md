# Plan INDEX — Test Realism Refactor (`test-realism`)

**Design**: `docs/features/test-realism/DESIGN.md`
**Target version bump**: minor (0.5.0 → 0.6.0) — no production behaviour change, test-suite reshape
**Branch**: `feat/test-realism`

**Plan revision**: 2026-04-24 — revised against baseline `d98ee04`. The new tier is `tests/integration/` (NOT `tests/e2e/`, which already hosts manual-only real-infra tests and must stay untouched).

## Phases

| #   | Phase                                                      | File                           | Commits (target) | Depends on |
| --- | ---------------------------------------------------------- | ------------------------------ | ---------------- | ---------- |
| 1   | Integration scaffolding & shared fixtures                  | `phase-01-e2e-scaffolding.md`  | 1                | —          |
| 2   | Integration tests — ingest / sort / process / scrape       | `phase-02-e2e-early-stages.md` | 3                | 1          |
| 3   | Integration tests — enforce / verify / dispatch / full-run | `phase-03-e2e-late-stages.md`  | 4                | 1          |
| 4   | Hotspot trimming (dispatcher / cli / pipeline_integration) | `phase-04-hotspot-trim.md`     | 3                | 2, 3       |
| 5   | Coverage check + docs expansion                            | `phase-05-verify-and-docs.md`  | 2                | 4          |

## Exit criteria

- `pytest tests/integration -q` collects ≥ 15 tests, all green, within the default pytest invocation.
- `pytest tests/ -q` (default markers) total runtime ≤ 30 s on reference hardware.
- `@patch` count in the three hotspot files ≥ 60 % lower than baseline (145 → ≤ 58; documented in phase 5 commit body).
- `pytest --cov --cov-branch` shows no regression in line or branch coverage vs `main`.
- `docs/reference/testing.md` expanded with the three-tier taxonomy and decision tree.
- `tests/e2e/` untouched (zero-diff across the feature branch).

## Explicit non-goals

- No production code restructure unless a minimal seam is strictly required for a test. Allowed seams (discovered during implementation, aligned with DESIGN §2 "minimal seam allowed for tests"):
  - `IngestConfig.min_ratio: float = 0.0` in `personalscraper/conf/models.py` + ratio-threshold guard in `personalscraper/ingest/ingest.py` (phase 2.1, catalogue #2 — ratio threshold test)
  - `Pipeline(step_overrides=...)` in `personalscraper/pipeline.py` (phase 4.3 — orchestrator unit test)
  - Additional seams may be declared as they are discovered; each must be backward-compatible (default value = no behaviour change) and listed here as it is added.
- No framework change (pytest stays).
- No deletion of unit tests that are still the best vehicle for a given invariant.
- No modification of the existing manual `tests/e2e/` tier.
- No CI infrastructure change — the integration tier runs under the default pytest invocation that CI already executes.
