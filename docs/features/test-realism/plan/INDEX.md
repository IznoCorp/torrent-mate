# Plan INDEX — Test Realism Refactor (`test-realism`)

**Design**: `docs/superpowers/roadmap/test-realism/specs/DESIGN.md`
**Target version bump**: minor (Y + 1) — no production behaviour change, test-suite reshape
**Branch (future)**: `feat/test-realism`

## Phases

| #   | Phase                                                      | File                           | Commits (target) | Depends on |
| --- | ---------------------------------------------------------- | ------------------------------ | ---------------- | ---------- |
| 1   | E2E scaffolding & shared fixtures                          | `phase-01-e2e-scaffolding.md`  | 1                | —          |
| 2   | E2E tests — ingest / sort / process / scrape               | `phase-02-e2e-early-stages.md` | 3                | 1          |
| 3   | E2E tests — enforce / verify / dispatch / full-run         | `phase-03-e2e-late-stages.md`  | 4                | 1          |
| 4   | Hotspot trimming (dispatcher / cli / pipeline_integration) | `phase-04-hotspot-trim.md`     | 3                | 2, 3       |
| 5   | Coverage check + docs                                      | `phase-05-verify-and-docs.md`  | 2                | 4          |

## Exit criteria

- `pytest tests/e2e -q` collects ≥ 15 tests, all green.
- `pytest tests/ -q` total runtime ≤ 30 s on reference hardware.
- `@patch` count in the three hotspot files ≥ 60% lower than baseline (documented in phase 5 commit body).
- `pytest --cov` shows no regression in line / branch coverage vs `main`.
- `docs/reference/testing.md` published with the unit-vs-E2E decision tree.

## Explicit non-goals

- No production code restructure unless a minimal seam is strictly required for a test.
- No framework change (pytest stays).
- No deletion of unit tests that are still the best vehicle for a given invariant.
- No CI infrastructure change beyond a possible `make test-e2e` target.
