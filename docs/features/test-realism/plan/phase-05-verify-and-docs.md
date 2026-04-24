# Phase 05 — Verify & document

**Goal**: certify the refactor against coverage + runtime gates and publish the three-tier convention. `docs/reference/testing.md` is **expanded**, not created (the file already exists).

## Gate (from Phase 04)

- Hotspot `@patch` counts ≤ 52 (15 + 25 + 12).
- `tests/integration/` green; `tests/e2e/` diff zero.

## Sub-phase 5.1 — Coverage & runtime gates

- Run `pytest --cov=personalscraper --cov-branch tests/` on `main`; snapshot line + branch numbers.
- Run the same on `feat/test-realism`; compare. Expected: ≥ on both line and branch coverage.
- Run `pytest --durations=20 tests/`; verify no single test > 5 s, full default suite ≤ 30 s.
- Record the before/after numbers in the phase commit body:
  - Line coverage: `X.XX% → Y.YY%` (delta).
  - Branch coverage: `X.XX% → Y.YY%` (delta).
  - Runtime: `A.A s → B.B s` (full suite, default markers).
  - Hotspot `@patch` total: `145 → N` (% reduction).
- Fail the phase if any gate regresses.

### Commit

`test: verify coverage and runtime budget after realism refactor`

## Sub-phase 5.2 — Documentation

- **Expand** `docs/reference/testing.md` (currently 54 lines, documents only the manual tier). Target structure:
  1. **Three-tier taxonomy** — unit (`tests/<module>/`), integration (`tests/integration/`), manual E2E (`tests/e2e/`).
  2. **Decision tree for new tests** — "what do you mock?":
     - Network/subprocess only → integration.
     - Single function / class, pure logic → unit.
     - Real qBit, real torrents, real APIs, real disks → manual E2E.
  3. **Runtime budget per tier** — unit ≤ 10 s, integration ≤ 20 s, total default ≤ 30 s.
  4. **How to run each tier** — `make test` (unit + integration, the default), `pytest -m e2e_torrent` (manual), `pytest -m roundtrip` (manual).
  5. **Fixture reference** — brief pointer to `tests/integration/conftest.py` and `tests/fixtures/config.py`.
- Keep the existing "Golden Files" and "Testing Requirement" sections at the end.
- Update `CLAUDE.md` Reference Index row for testing: already points to `docs/reference/testing.md` — no change needed, just verify after the expansion.
- Add a one-line decision pointer in `CLAUDE.md`'s "Code Conventions" section:
  > New tests: choose unit / integration / manual E2E — see `docs/reference/testing.md`.

### Commit

`docs(testing): publish three-tier convention and decision tree`

## Exit criteria

- `tests/integration/` contains ≥ 15 passing tests collected by default `pytest`.
- Hotspot `@patch` total ≤ 58 (≥ 60 % reduction from 145 baseline).
- Default suite runtime ≤ 30 s; no single test > 5 s.
- Coverage (line + branch) ≥ baseline measured against `main`.
- `docs/reference/testing.md` contains the three-tier taxonomy and decision tree.
- `CLAUDE.md` "Code Conventions" has the one-line pointer.
- `tests/e2e/` diff across the entire branch: zero changes.
