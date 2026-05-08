# Test Coverage & Design-Contract Testing — Design

**Status**: Approved — awaiting implementation
**Codename**: `test-coverage`
**Version bump**: 0.11.0 → 0.12.0 (minor — new `tests/feature_map/` artifact, new scripts, new Makefile/CI surface)
**Design date**: 2026-05-08
**Trigger**: ROADMAP — raise branch coverage to 90 % with documentation traceability before scaling new features (originally framed against a 44 % line-coverage entry point; rescaled at Phase 1 to start from the actual 80.48 % branch baseline measured on `feat/test-coverage`).

## Changelog

| Date       | Change                                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| 2026-05-08 | Initial design.                                                                                                    |
| 2026-05-08 | Cross-review #1 — applied 7 critical + 11 important fixes (`docs(coverage): apply full review fixes`).             |
| 2026-05-08 | Cross-review #2 — applied 8 critical + 13 important fixes (this rewrite). Moved to `docs/features/test-coverage/`. |

## Glossary

| Term                     | Meaning                                                                                                                       |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| **Coverage**             | Line + branch coverage (`--cov-branch`) measured by `coverage.py` via `pytest-cov`.                                           |
| **Design-contract test** | Integration test whose docstring carries both `Design:` and `Contract:` markers. Maps a behavior to a documented section.     |
| **Anchor**               | GitHub-style URL fragment derived from a Markdown heading (e.g. `#circuit-breaker-opens-after-3-failures`).                   |
| **Feature map**          | One JSON file per feature codename at `tests/feature_map/<codename>.json` mapping anchors to test IDs.                        |
| **Skip-audit**           | List of anchors intentionally excluded from the coverage audit (untestable content like Purpose, Non-Goals).                  |
| **Codename**             | Stable feature identifier derived from a design doc path; shared with `/implement:feature` branch naming (`feat/<codename>`). |

## 1. Goals & Non-Goals

### 1.1 Goals

- Raise unit + integration **branch** coverage from the rebaselined value (80 %) to 90 %, enforced in CI.
- Every integration test under `tests/integration/test_design_*.py` traces to a documented behavior in a `DESIGN.md` or reference doc via stable docstring markers.
- Per-feature JSON map files at `tests/feature_map/<codename>.json` — eliminates merge conflicts.
- Two scripts: `scripts/update_feature_map.py` (scan + regenerate) and `scripts/audit_design_coverage.py` (orphan section detection, both directions).
- Pre-commit hook + CI both enforce map freshness and coverage threshold.
- Staged `fail_under` ratchet — monotonic increases enforced by CI.
- Tests for the scripts themselves (memory rule "regression test per bug").
- Compatibility with the existing `/implement:feature` workflow — DESIGN/plan layout matches `docs/features/<codename>/`.

### 1.2 Non-Goals

- 100 % coverage. The last 10 % is `__repr__`, defensive `raise NotImplementedError` in Protocol stubs, etc.
- Rewriting / deleting existing tests. Retain unless they encode wrong behavior.
- Modifying E2E test infrastructure (already comprehensive — 2600+ tests).
- Retroactive marker addition on existing tests. Only new tests written during feature cycles carry markers.
- Phantom-path detection (the original `coverage_gap_report.py`). Demoted — requires design-section-to-source-line mapping that doesn't exist yet. Revisit post-90 %.
- Per-module coverage thresholds. We measure global only. Per-module floors deferred.

### 1.3 Success Criteria

| Metric                                                   | Target                                                                                                    |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `make test`                                              | green (`-n auto`, no coverage overhead)                                                                   |
| `make test-cov`                                          | green at the current `fail_under`, branch coverage on                                                     |
| `make check` (lint + test-cov + module-size + typed-api) | green                                                                                                     |
| `make lint`                                              | green (ruff + mypy)                                                                                       |
| `python3 scripts/audit_design_coverage.py --strict`      | green from Phase 8 onward (`design-gaps` job promoted to hard error in `bed40c8`)                         |
| Final `fail_under`                                       | 90                                                                                                        |
| Threshold ratchet                                        | monotonic; CI rejects PRs that lower `fail_under`                                                         |
| Scripts test coverage                                    | `tests/unit/test_update_feature_map.py` + `tests/unit/test_audit_design_coverage.py` cover the algorithms |

## 2. Current State

- **Default suite**: 411 tests (~370 unit + 21 integration), runs in ~5 s via `make test`.
- **Full repo**: 2920 tests (most are manual E2E, deselected by default markers `e2e | e2e_torrent | e2e_idempotence | slow | network`).
- **Coverage**: 43.77 % line coverage measured without branch. Branch coverage will be re-baselined in Phase 1.
- **CI**: `.github/workflows/ci.yml` already runs `--cov-fail-under=80` in the `test` job. **This job currently fails on `main`** and on every PR — must be unblocked in Phase 1.
- **Biggest gaps**: `trailers/cli.py` (0 %), `scraper/tv_service.py` (15 %), `scraper/trailer_finder.py` (27 %), `scraper/ytdlp_downloader.py` (34 %), `verify/fixer.py` (26 %).

## 3. Architecture — Four Pillars

### 3.1 Pillar 1 — Feature-Anchored Coverage Cycles

Each major feature gets its own test improvement cycle: audit gaps → write design-contract integration tests against the feature's DESIGN.md → fill unit gaps → bump global `fail_under`.

Coverage is measured **globally** (`--cov=personalscraper`). Cycles do not introduce per-module thresholds — success is the global ratchet bump. Per-module floors are deferred (cf. Non-Goals).

### 3.2 Pillar 2 — Design-Contract Integration Tests

Each integration test maps to a section in a design or reference doc via docstring markers:

```python
def test_circuit_breaker_opens_after_3_failures(staging_dir, mock_api_server):
    """Circuit breaker opens after 3 consecutive failures.

    Design: docs/features/api-unify/DESIGN.md#circuit-breaker-opens-after-3-failures
    Contract: After 3 consecutive failures the circuit breaker enters OPEN state
    and rejects subsequent requests with CircuitOpenError until the cooldown
    expires.
    """
    ...
```

Anchor stability — when a heading is renamed, only the `Design:` line changes; the test function name is unaffected.

A test is "design-contract" iff it has BOTH `Design:` and `Contract:` markers in the **function docstring** (not class/module). Markers on multiple `Design:` lines in one docstring are allowed (cross-cutting tests). Markers parsed via `ast.get_docstring(node, clean=True)`.

#### 3.2.1 Anchor algorithm

The script and the spec MUST produce identical anchors for the same heading. The algorithm matches GitHub's `jch/html-pipeline TableOfContentsFilter` semantics:

1. NFC-normalize the heading (`unicodedata.normalize("NFC", heading)`) — guards against NFD copies from macOS Finder.
2. Lowercase.
3. Strip characters not in `[\w\s-]` Python regex class. `\w` is **Unicode-aware** in Python 3 — it keeps `_`, accented letters (`é`, `ñ`), CJK, and other Unicode word characters. Punctuation, emoji, brackets, parentheses are stripped.
4. Replace runs of whitespace by a single hyphen.
5. Collapse runs of multiple hyphens into one.
6. Strip leading/trailing hyphens.
7. Skip empty results (heading consisting only of stripped chars produces no anchor).
8. Duplicate anchors are disambiguated by appending `-1`, `-2`, … starting at `-1` for the first duplicate (matches GitHub).

Reference cases (must be covered by `tests/unit/test_audit_design_coverage.py::TestGithubAnchor`):

| Heading                                   | Expected anchor                                                             |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| `Circuit Breaker — Open After 3 Failures` | `circuit-breaker--open-after-3-failures` (em-dash stripped, runs collapsed) |
| `Use \`MediaType\` enum`                  | `use-mediatype-enum`                                                        |
| `🔴 Critical Issues`                      | `critical-issues`                                                           |
| `Café (déjà vu)`                          | `café-déjà-vu`                                                              |
| `中文 标题`                               | `中文-标题`                                                                 |
| `Function (deprecated)`                   | `function-deprecated`                                                       |
| 2× `## Title`                             | `title`, then `title-1`                                                     |
| `   ` (whitespace only)                   | (empty — skipped)                                                           |
| `snake_case_name`                         | `snake_case_name` (underscore preserved)                                    |

The DESIGN explicitly DOES NOT match the legacy "strip non-alphanumeric ASCII" rule — that would break accents and CJK and produce divergent anchors from GitHub for any non-ASCII heading.

### 3.3 Pillar 3 — Per-Feature Mapping Files

`tests/feature_map/<codename>.json` — one file per feature, mapping each design section to its tests.

#### 3.3.1 Codename derivation rule + override table

Default rule: codename is the directory name immediately following `features/` in the design doc path. If no `features/` segment exists, the document stem is used.

| Design doc path                           | Codename        |
| ----------------------------------------- | --------------- |
| `docs/features/api-unify/DESIGN.md`       | `api-unify`     |
| `docs/archive/features/trailer/DESIGN.md` | `trailer`       |
| `docs/features/test-coverage/DESIGN.md`   | `test-coverage` |

Reference docs are mapped through an explicit override table (canonical source: `scripts/_codename_overrides.py`):

| Reference doc                           | Codename              |
| --------------------------------------- | --------------------- |
| `docs/reference/scraping.md`            | `scraper`             |
| `docs/reference/storage.md`             | `dispatch`            |
| `docs/reference/pipeline-internals.md`  | `pipeline`            |
| `docs/reference/trailers.md`            | `trailers`            |
| `docs/reference/indexer.md`             | `indexer`             |
| `docs/reference/indexer-json-shapes.md` | `indexer-json-shapes` |
| `docs/reference/architecture.md`        | `architecture`        |
| `docs/reference/<provider>-api.md`      | `<provider>`          |

Collision policy: if two design docs would resolve to the same codename, the script logs an error and exits non-zero. The override table is the disambiguator.

#### 3.3.2 Map file format

Files use the `.json` extension and standard JSON content. JSON5 was considered for line comments but the existing `json5` dep is reserved for config files — map files are machine-generated, not hand-edited (except `skip_audit` entries).

```json
{
  "feature": "api-unify",
  "design": "docs/features/api-unify/DESIGN.md",
  "sections": {
    "circuit-breaker-opens-after-3-failures": {
      "tests": [
        "tests/integration/test_design_api_transport.py::test_circuit_breaker_opens_after_3_failures"
      ]
    }
  },
  "skip_audit": [
    {
      "anchor": "purpose",
      "category": "documentation_only",
      "reason": "Non-functional content (intent statement).",
      "expires": "2028-05-08"
    },
    {
      "anchor": "tv-merge-on-rename",
      "category": "deferred_promotion",
      "reason": "Behavior planned for follow-up — TV merge keys on (season, episode), see _tv.purge_episode_conflicts.",
      "expires": "2026-11-08"
    }
  ]
}
```

`skip_audit` entries are objects with four fields:

| Field      | Required | Meaning                                                                         |
| ---------- | -------- | ------------------------------------------------------------------------------- |
| `anchor`   | yes      | GitHub-style anchor of the design section being waived.                         |
| `category` | yes      | One of `documentation_only` or `deferred_promotion` (see below).                |
| `reason`   | yes      | Free-form explanation. Should justify the chosen `category`.                    |
| `expires`  | yes      | ISO date after which the audit emits a warning (or error with `--strict-skip`). |

Categories:

- **`documentation_only`** — the section is reference / ops / intent / glossary content with no closed behavioral contract. These have a long expiry (typically two years) because we don't expect to ever promote them to a contract test; the expiry exists so a maintenance pass periodically re-confirms the section hasn't drifted into something that _can_ be pinned.
- **`deferred_promotion`** — the section describes behavior that should eventually be pinned by a contract test, but the test hasn't been written yet. Expiry is tighter (six months) so the entry resurfaces and forces either promotion or formal re-waiving.

`audit_design_coverage.py` warns on entries past their `expires` date — forces periodic re-evaluation. A `--strict-skip` mode (post-90 %) promotes that warning to an error.

### 3.4 Pillar 4 — Staged Coverage Thresholds (Monotonic Ratchet)

`fail_under` in `pyproject.toml` lowered to the rebaselined value, then bumped progressively. Branch coverage is enabled from the start so we don't need to re-baseline later.

Progression: `baseline (80) → 82 → 85 → 87 → 90`.

> **Baseline note (2026-05-08).** The original DESIGN assumed a ~44 % line-coverage
> entry point. Actual measured _branch_ coverage on `feat/test-coverage` (after
> the api-unify merge) is **80.48 %**, so Phase 1 set `fail_under = 80`. The
> ratchet was rescaled to `80 → 82 → 85 → 87 → 90` and the bumps were assigned
> to the cycles that ship the most new tests (scraper / dispatch+verify /
> trailers / indexer). Phase 5 (api-unify) keeps its role as the marker-format
> bootstrap and does **not** bump the threshold; Phase 10 (cleanup) remains at
> 90 for audit + skip_audit review. The `design-gaps` promotion still happens
> at the cycle-4 boundary (Phase 8 — trailers).

**Monotonic enforcement.** A CI job `coverage-monotonic` reads `fail_under` from `pyproject.toml` on the PR's HEAD and from `main`, and fails if HEAD `<` main. Prevents accidental revert regressions and a malicious / mistaken PR that lowers the gate.

## 4. Feature Cycle Order

| #   | Cycle                 | Design / Reference                                                      | Rationale                                                                         |
| --- | --------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1   | **api-unify**         | `docs/features/api-unify/DESIGN.md`                                     | Active branch, 27 phases done. Establishes the marker template.                   |
| 2   | **scraper**           | `docs/reference/scraping.md`                                            | Core pipeline. Critical gaps (`tv_service.py` 15 %, `trailer_finder.py` 27 %).    |
| 3   | **dispatch + verify** | `docs/reference/storage.md`, `docs/reference/pipeline-internals.md`     | Movement to permanent storage. Already 70-80 %. Shorter cycle.                    |
| 4   | **trailers**          | `docs/reference/trailers.md`, `docs/archive/features/trailer/DESIGN.md` | Worst coverage. Pipeline-critical.                                                |
| 5   | **indexer**           | `docs/reference/indexer.md`, `docs/reference/indexer-json-shapes.md`    | Large, complex. Decently tested. Deep domain knowledge needed for remaining gaps. |
| 6   | **remaining cleanup** | `docs/reference/architecture.md` + relevant reference docs              | sorter, ingest, process, library, conf — mixed bag.                               |

Each cycle bumps `fail_under` once. Coverage cycles on existing features (cycles 2-6) do **not** require `/implement:feature` — they follow a simplified workflow: audit → add tests → bump threshold → PR. The full `/implement:feature` lifecycle applies only when the cycle coincides with active feature work (cycle 1 — api-unify).

## 5. CI Enforcement (GitHub Actions)

### 5.1 Job topology

```
lint (ruff + mypy)  ────┬── test-cov (coverage gate, --cov-fail-under, upload coverage.xml)
                        ├── coverage-monotonic (fail_under does not decrease vs main)
                        └── design-gaps (audit_design_coverage.py --strict)
                              └── needs: nothing (reads tests/feature_map/ + design docs only;
                                  does NOT consume the .coverage artifact)
```

### 5.2 test-cov job

Runs `make test-cov`, which invokes pytest with `-n auto`, `--cov=personalscraper`, `--cov-branch`, `--cov-report=xml`, `--cov-report=term`, `--cov-fail-under=$THRESHOLD`. Threshold is read via the dedicated helper script, NOT inline in the Makefile (cf. §8.2 — Makefile shell substitution gotcha).

`-n auto` is **kept on** with `xdist`. `pytest-cov` automatically configures `[run] parallel = true` and merges per-worker `.coverage.<worker>` files at session end. The previous design's "no `-n auto` to avoid data race" was incorrect — it cost ~5× CI time for nothing.

`pyproject.toml` additions:

```toml
[tool.coverage.run]
branch = true
parallel = true
concurrency = ["multiprocessing"]
source = ["personalscraper"]
omit = ["personalscraper/__main__.py"]
```

### 5.3 coverage-monotonic job

```yaml
coverage-monotonic:
  needs: []
  steps:
    - uses: actions/checkout@v4
      with: { fetch-depth: 0 }
    - run: |
        head_threshold=$(python3 scripts/get_coverage_threshold.py)
        main_threshold=$(git show origin/main:pyproject.toml | python3 scripts/get_coverage_threshold.py --stdin)
        if [ "$head_threshold" -lt "$main_threshold" ]; then
          echo "::error::fail_under decreased ($main_threshold → $head_threshold). Ratchet must be monotonic."
          exit 1
        fi
```

### 5.4 design-gaps job

Runs `python3 scripts/audit_design_coverage.py --strict` and `python3 scripts/update_feature_map.py --check`. The latter ensures the committed map files match what `update_feature_map.py` would generate from the test tree — protects against developers committing without the pre-commit hook.

Initially `continue-on-error: true`. **Promoted to hard error** in cycle 4 (trailers, post-`fail_under = 80`). Promotion is a dedicated task in that phase, not a side note.

### 5.5 Codecov action token

`codecov-action@v4` requires `CODECOV_TOKEN` even for public repos since 2024-02. The plan verifies the secret is set in repo settings during Phase 2; otherwise `fail_ci_if_error: false` for forks (PRs from forks don't inherit secrets).

## 6. Design-Contract Test Format

### 6.1 File naming

`tests/integration/test_design_<module>.py` — alongside existing integration tests.

### 6.2 Structure rules

1. One test = one contract clause. 3 clauses → 3 tests.
2. Test name encodes behavior, not section number. `test_circuit_breaker_opens_after_3_failures`, NOT `test_s3_2_1`.
3. Mandatory `Design:` and `Contract:` markers in the **function** docstring.
4. Prefer integration tier with mocked external services (mock*api_server, dependency injection). Contracts that \_require* live services live in `tests/e2e/` and are excluded from the `fail_under` gate.

### 6.3 Test quality criteria

- **Behavioral**: assert observable outcomes, not internal call patterns or log messages.
- **Minimally mocked**: mock at module boundaries (I/O, external APIs).
- **Single concern**: one assertion family per test. "Circuit opens AND raises CircuitOpenError" = OK (same observable). "Circuit opens AND cache evicts" = two tests.
- **Readable as specification**: the test name + assertions describe the contract without reading the design doc.

Enforced during code review. The 7th `/implement:check` step verifies that contract tests exist and pass; review enforces quality.

### 6.4 e2e-only-code policy

Code reachable only from `tests/e2e/` paths is excluded from the `fail_under` gate. To prevent unreachable-by-unit-or-integration code from blocking the 90 % target, modules that fall in this category are listed in `[tool.coverage.report].omit` with a `# reason:` comment. The list is reviewed at each cycle.

If a module would otherwise be permanently uncoverable (e.g. `cli.py` entry points), it is added to `omit` with justification. This is opt-in, not automatic.

## 7. Tooling & Scripts

### 7.1 `scripts/update_feature_map.py`

Scans `tests/` for `Design:` markers on `ast.FunctionDef` / `ast.AsyncFunctionDef` docstrings. Resolves codenames via the override table + default rule. Writes `tests/feature_map/<codename>.json`. Ships with `--check` mode for CI freshness verification.

Marker regex: `^Design:\s*(\S+)#(.+)$` (multiline). Requires a corresponding `^Contract:\s*(.+)$` line in the same docstring (else the test is skipped with a warning).

### 7.2 `scripts/audit_design_coverage.py`

Two-direction audit:

1. **Orphan sections** (existing): design sections with zero tests. Severity: Warning until `fail_under = 80`, then Error.
2. **Stale references** (new): tests with `Design:` markers pointing to anchors that no longer exist in any design doc. Severity: Error from day 1 — the test doesn't compile against documentation.

### 7.3 `scripts/get_coverage_threshold.py`

Helper that reads `[tool.coverage.report].fail_under` from `pyproject.toml`. Has a `--stdin` mode to read from stdin (used by the `coverage-monotonic` job to evaluate `main`'s threshold without a checkout). Handles Python 3.10 via `tomli` fallback (added to dev deps).

### 7.4 `hooks/pre-commit` + `core.hooksPath`

The hook directory is at `hooks/`. We use `git config core.hooksPath hooks/` (set by `hooks/install.sh`) instead of a single symlink at `.git/hooks/pre-commit` — this is **critical** because the project already uses `.claude/hooks/` for `block_ai_attribution.py`, `block_curl_without_timeout.py`, `block_background_pipeline.py`. Symlinking `.git/hooks/pre-commit` would erase those guards.

`core.hooksPath` lets multiple hooks coexist and is per-clone (not global), so contributors keep their personal Claude / IDE hooks intact.

The `pre-commit` hook detects staged `test_design_*.py` files via `git diff --cached --name-only --diff-filter=ACM` and runs `update_feature_map.py`. It then re-stages the updated/created map files using `git status --porcelain tests/feature_map/` (which lists both modified AND untracked entries — `git diff` would miss new files).

### 7.5 Makefile

```makefile
THRESHOLD := $(shell python3 scripts/get_coverage_threshold.py)

test-unit:
	python3 -m pytest tests/ --ignore=tests/integration --ignore=tests/e2e -q -n auto

test-integration:
	python3 -m pytest tests/integration/ -q -n auto

test-cov:
	python3 -m pytest tests/ --ignore=tests/e2e -q --no-header -n auto \
		--cov=personalscraper --cov-branch --cov-report=xml --cov-report=term \
		--cov-fail-under=$(THRESHOLD)
```

`make check` keeps composing `lint test-cov module-size typed-api`. The existing `make gate` target (residual import audits) is preserved unchanged.

## 8. Integration with `/implement:feature`

| Phase                   | Coverage action                                                                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/implement:brainstorm` | Stub map file at `tests/feature_map/<codename>.json` listing section anchors, empty test arrays, common untestable anchors in `skip_audit`.      |
| `/implement:plan`       | Each phase file lists which DESIGN.md sections it implements + estimated test count.                                                             |
| `/implement:sub-phase`  | Design-contract tests written alongside implementation. Same commit. Pre-commit hook updates the map.                                            |
| `/implement:check`      | 7th check (added in Phase 4): for each section the phase claims, ≥ 1 matching test exists and passes; `audit_design_coverage.py --strict` clean. |
| `/implement:feature-pr` | CI coverage job enforces `fail_under`. Monotonic check protects against ratchet rollback.                                                        |
| Merge                   | `fail_under` bumped if the cycle warrants (manual edit during squash-merge).                                                                     |

For coverage-only cycles on existing features (cycles 2-6 — no new feature branch), skip `brainstorm`/`plan`. Work directly: audit gaps, add tests, bump threshold, PR. A stub map file is created manually if missing.

### 8.1 New-code coverage policy

A PR that introduces production code must include corresponding tests so the global `fail_under` gate doesn't regress. There is **no per-module check** — the global gate is the only gate. Per-module floors are deferred (cf. Non-Goals).

Diff-coverage (codecov patch %, threshold 80 % on the diff) is enabled in cycle 4 alongside the strict global gate. Diff-coverage catches regressions that the global gate would miss when the codebase is large (1 % drop hidden in 100 k LOC).

### 8.2 Threshold helper script (Makefile gotcha)

Inline `$(shell python3 -c "try: ...except ...")` with `\n` does NOT work — Make passes the literal `\n` to the shell, and `python3 -c` does not expand it. The script `scripts/get_coverage_threshold.py` exists explicitly to sidestep this.

### 8.3 Duplicate test policy

When a new design-contract test overlaps with an existing legacy test, both are kept. The contract test provides traceability the legacy test lacks.

## 9. Risks & Mitigations

| #   | Risk                                                                         | Likelihood | Impact | Mitigation                                                                                                                                  |
| --- | ---------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | Monotonic ratchet blocks legitimate revert                                   | Low        | Medium | `coverage-monotonic` job is informational on PRs labeled `coverage-rollback` (manual override path).                                        |
| R2  | `fail_under` drift between local and CI (different `pyproject.toml`)         | Low        | Low    | `make test-cov` reads from the same `pyproject.toml` via `get_coverage_threshold.py`. Single source of truth.                               |
| R3  | Anchor algorithm divergence (NFD copy from Finder, etc.)                     | Medium     | High   | NFC normalization in `github_anchor()`. Unit tests cover NFD, accents, CJK, duplicates.                                                     |
| R4  | Pre-commit hook bypassed (`--no-verify` or hook not installed)               | High       | Medium | CI runs `update_feature_map.py --check` independently. Catches drift even when the hook is bypassed.                                        |
| R5  | `skip_audit` becomes a permanent dumping ground                              | Medium     | Medium | Mandatory `reason` + `expires` fields. Audit warns on expired entries. Periodic review (cycle gate).                                        |
| R6  | Codecov v4 token not set → CI breaks on all PRs                              | Medium     | High   | Phase 2 explicitly verifies `CODECOV_TOKEN` is set; otherwise `fail_ci_if_error: false`. Forks always treated as `fail_ci_if_error: false`. |
| R7  | Coverage data race with `xdist` parallel mode                                | Low        | Medium | `[tool.coverage.run].parallel = true` + `concurrency = ["multiprocessing"]`. `pytest-cov` handles per-worker file merge.                    |
| R8  | E2E-only code blocks the 90 % target                                         | High       | Medium | Explicit `omit` list in `[tool.coverage.report]` with `# reason:` comments, reviewed each cycle.                                            |
| R9  | Codename collision (`scraping.md` vs hypothetical `docs/features/scraping/`) | Low        | High   | Override table in `_codename_overrides.py` is the disambiguator. Script exits non-zero on unmapped collisions.                              |
| R10 | Heading rename breaks all `Design:` markers pointing to it                   | Medium     | Low    | `audit_design_coverage.py` reports stale references (Error severity). PR review catches at the same time as the rename.                     |

## 10. Open Questions

- **Q1** — Should diff-coverage be enabled in cycle 4 or earlier? Defer to the cycle-4 gate review.
- **Q2** — Should `make test` (no coverage) keep `-n auto` or unify with `test-cov`? Keep `-n auto` for both — `make test` is the fast feedback loop and gets no coverage overhead.
- **Q3** — Is 90 % the right end target or should we stop at 85 %? Decide post-cycle-5 with measured data.

### Retrospective answers (Phase 11, 2026-05-08)

- **Q1 (diff-coverage timing)**: planned for Phase 8. The infrastructure PR ships the `coverage-monotonic` job and a strict `design-gaps` job; the codecov diff-patch step is left as a follow-up because it depends on `CODECOV_TOKEN` being verified in repo settings (Phase 2 task).
- **Q2 (`-n auto` for `make test`)**: kept `-n auto` for both `test` and `test-cov`. `pytest-cov` handles per-worker `.coverage.<id>` files via `concurrency = ["multiprocessing"]`; the parallel-mode merge is automatic at session end. No data race observed.
- **Q3 (90 % vs 85 % end target)**: **90 % chosen and shipped**. The cycle-by-cycle bumps `80 → 82 → 85 → 87 → 90` planned for Phases 6–9 were consolidated into a single end-of-feature ratchet bump (`71c8926` — "apply ratchet 80→90 — final gate, target reached"). Measured branch coverage at the final gate is 91 %, so the gate sits at 90 % with ~1 % headroom. The post-cycle-5 measurement that this question deferred to is therefore the final ratchet: the data clearly cleared 85 % well before the last cycle, so the original 90 % target was kept.

## 11. Owner & Maintenance

- **Owner**: project maintainer (LounisBou). Coverage cycles are tracked in `IMPLEMENTATION.md` per phase.
- **6-month audit**: scheduled via `cron` on the maintainer's calendar. Runs `audit_design_coverage.py --strict` + reviews `skip_audit` `expires` dates. Output committed as `docs/features/test-coverage/audit-YYYY-MM-DD.md`.
- **Onboarding**: a dev wanting to add a contract test follows `docs/features/test-coverage/HOWTO.md` (created in Phase 4). Three-step quick-start: write the test → `git add` → commit (the hook handles the map).

## 12. Future Enhancements (post-90 %)

- `scripts/coverage_gap_report.py` — detect sections whose tests exist but don't exercise the target source lines. Requires section-to-source mapping.
- Per-module coverage floors for files ≥ 500 LOC.
- Migration of `tests/e2e/` to in-process fixtures where feasible (lift the 90 % wall on currently-omitted modules).
