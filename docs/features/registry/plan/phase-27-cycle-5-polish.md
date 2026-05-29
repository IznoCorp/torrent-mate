# Phase 27 — Cycle 5 polish + flaky test fix

Generated 2026-05-28 after cycle 5 review (Phase 26 verification) returned
MERGE with 3 minor non-blocking suggestions. User elected to address them
before the final merge for a 100% clean review log. Additionally, the
`test_indexer_budget_resume` flake (acknowledged in cycle 3 with a CI
re-run, then re-fired on the cycle-5 push) is rolled into this phase.

## Gate

- Phases 0–26 complete (all [x] in IMPLEMENTATION.md).
- PR #27 currently `OPEN`. CI red on `test` job due to flaky
  `tests/e2e/test_indexer_budget_resume.py::test_budget_exhaustion_then_resume_completes`
  (got 9 media_file rows, expected 10).

## Goal

Close the 3 cycle-5 suggestions (S1, S2, S3) + stabilize the flaky
indexer-budget-resume test, then re-run `/implement:pr-review` for a
clean cycle-4-of-reset MERGE verdict with no remaining suggestions.

## Scope

### Cycle-5 suggestions

- **S1** Leftover `list[str]` on frozen dataclasses:
  - `personalscraper/api/metadata/registry/_events.py:68` —
    `LockedCapabilityUnresolved.chain_tried: list[str]`
  - `personalscraper/api/metadata/registry/_events.py:98` —
    `RegistryBootValidated.providers: list[str]`
  - `personalscraper/api/metadata/registry/_events.py:99` —
    `RegistryBootValidated.capabilities: dict[str, list[str]]`
- **S2** `personalscraper/api/metadata/registry/__init__.py:493` —
  structlog log key `providers_succeeded=len(eligible)` drifts from
  the renamed event field `RegistryFanOutCompleted.eligible`. Rename to
  `providers_eligible=`.
- **S3** `personalscraper/scraper/tv_service.py` at 922 non-blank LOC after
  Phase 26.2 broadened the chain exception catch. Soft warning fires at 800,
  hard ceiling 1000. Refactor down (extract one or more cohesive blocks to
  a sibling module — e.g. `tv_service_chain.py` or
  `tv_service_assembly.py`).

### Flaky test (pre-existing, but blocks merge)

- **F1** `tests/e2e/test_indexer_budget_resume.py::test_budget_exhaustion_then_resume_completes`
  intermittently asserts `count == 10` but gets `count == 9` on CI
  Ubuntu (passes locally on macOS). Acknowledged flake from cycle 3
  (2026-05-27) when PR was first merged after a CI re-run. Re-firing
  on the cycle-5 push means the resume logic has a real off-by-one
  in some filesystem ordering — investigate and fix, OR mark with
  `@pytest.mark.flaky(reruns=2)` as a pragmatic stopgap with a
  ROADMAP entry for proper investigation.

## Sub-phases

### 27.1 — S1 + S2 (mechanical event polish)

**Changes**:

1. `personalscraper/api/metadata/registry/_events.py:68` —
   `chain_tried: list[str]` → `chain_tried: tuple[str, ...]`.
   Update emission site at `personalscraper/api/metadata/registry/__init__.py`
   (grep for `chain_tried=` construction) to pass `tuple(...)`.
2. `personalscraper/api/metadata/registry/_events.py:98` —
   `providers: list[str]` → `providers: tuple[str, ...]`.
3. `personalscraper/api/metadata/registry/_events.py:99` —
   `capabilities: dict[str, list[str]]` → `capabilities: dict[str, tuple[str, ...]]`.
4. Update the `RegistryBootValidated(...)` construction site
   (grep `RegistryBootValidated\(` in personalscraper/) to pass tuples for
   both fields. The boot emit lives at `personalscraper/api/metadata/registry/__init__.py:398`
   (`registry_boot_loaded` structlog event is adjacent — verify the bus event
   emit site).
5. `personalscraper/api/metadata/registry/__init__.py:493` — rename
   structlog key `providers_succeeded` → `providers_eligible`. Grep for
   `providers_succeeded` across the repo to confirm no consumer parses
   that exact key (event-bus monitor docs, dashboards). Update if needed.

**Acceptance**:

- `make lint` clean (mypy may catch downstream tuple-vs-list type drift
  in tests; update test assertions to use `tuple(...)` or `list(...)`
  consistently).
- New test or expand existing one:
  `test_registry_boot_validated_uses_tuples` — asserts
  `isinstance(event.providers, tuple)` and
  `isinstance(event.capabilities[<some_cap>], tuple)`.

**Commits**:

- `refactor(events): LockedCapabilityUnresolved.chain_tried + RegistryBootValidated → tuple`
- `refactor(registry): rename structlog key providers_succeeded → providers_eligible (S2)`
- `test(registry): regression — RegistryBootValidated payload is tuples`

### 27.2 — S3 tv_service.py refactor

**Goal**: bring `tv_service.py` non-blank LOC from 922 to ≤ 800 (soft
ceiling) without behavior change.

**Approach**:

1. Read the module top-to-bottom. Identify cohesive blocks that can move
   to a sibling file. Candidates (verify by structure):
   - Episode-NFO-generation block (~80-150 LOC if the section is large)
     → `tv_service_episode_nfo.py`.
   - Chain-fallback details-fetch block (the new `except Exception` at
     line 597 lives in this block) → potentially merge into
     `tv_service_episodes.py` if cohesive.
2. Extract via verbatim move + import re-wire. NO logic changes; this is
   a pure structural refactor.
3. Run targeted tests: `pytest tests/scraper/test_tv_service*.py -q`
   must pass with same count.

**Acceptance**:

- `python3 scripts/check-module-size.py` no longer warns on
  `tv_service.py`. Target ≤ 800 LOC.
- `pytest tests/scraper/test_tv_service*.py -q` — same pass count
  pre/post refactor (no test count drift).
- No external consumer of `tv_service` breaks (the public symbols
  remain importable from `personalscraper.scraper.tv_service`).

**Commits**:

- `refactor(scraper): extract <block_name> to tv_service_<block>.py (S3)`
- (optional) `refactor(scraper): extract <second_block> to tv_service_<other>.py`

If a single extraction brings LOC below 800, one commit suffices. If two
are needed, two commits.

### 27.3 — F1 flaky test investigation + fix

**Diagnosis path**:

1. Read `personalscraper/indexer/scanner/_checkpoint.py` `_maybe_checkpoint`
   and `_check_crash_resume` — focus on `last_path` write timing vs the
   actual file just indexed (off-by-one suspected).
2. Read `personalscraper/indexer/scanner/_walker.py` around the three
   call sites of `_maybe_checkpoint` (~lines 350, 518, 758) — the one
   that fires for full-mode scanning.
3. Trace the resume path: `_walker` reads `state.resume_from[0]`
   (populated at `_init`-time by `_check_crash_resume`). The resume
   skips files whose path ≤ resume_from. The bug is likely:
   - `last_path` is written AFTER the file is fully committed to DB,
     but the walker checkpoints BEFORE the next file is opened
     (so `last_path == file_N` means file_N is indexed).
   - Resume starts from `walk` where `path > last_path` — strictly
     greater, so file\_{N+1} should be next.
   - If filesystem walk order differs between phase-1 and phase-2 by
     ONE entry (e.g., one file got re-ordered), one file is skipped.

**Possible fix**:

- Force deterministic walk ordering: `sorted(os.listdir(...))` everywhere
  if not already sorted.
- OR fix the `last_path` boundary: store the last _successful_ file
  index, resume from index+1, NOT from path comparison.

**Pragmatic fallback** (if root cause too deep):

- Mark the test with `@pytest.mark.flaky(reruns=2, reruns_delay=1)`
  (requires `pytest-rerunfailures` — check `pyproject.toml`; add if
  missing).
- OR `@pytest.mark.xfail(strict=False, reason="Phase-27.3 flake")` with
  a ROADMAP entry to fix properly post-merge.

**Acceptance**:

- Run the test 10 times in a row locally (`pytest tests/e2e/test_indexer_budget_resume.py -q --count=10`)
  — all 10 pass. If `pytest-repeat` is unavailable, run a bash loop.
- Run on CI — green on first try.
- If using `@pytest.mark.flaky` fallback: at least the test is no longer
  a release-blocker, and the underlying off-by-one is documented in
  `docs/ROADMAP.md` for proper investigation in a follow-up.

**Commits**:

- (Option A — real fix) `fix(indexer): resume walker — deterministic file ordering (F1)`
- (Option A) `test(indexer): regression — budget-exhaustion resume preserves total count under repeated runs`
- (Option B — pragmatic mark) `test(indexer): mark test_budget_exhaustion_then_resume_completes as flaky pending F1`
- (Option B) `docs(roadmap): add F1 — indexer resume walker off-by-one investigation`

### 27.4 — Phase 27 gate + IMPLEMENTATION.md mark

- Verify `make check` green.
- Verify `pytest -q` 5657+ pass.
- Mark Phase 27 `[x]` in IMPLEMENTATION.md.
- Commit: `chore(registry): phase 27 gate — cycle 5 polish + flaky test stabilized`

## Phase gate

- `make check` exit 0.
- `make test` ALL pass (incl. previously-flaky test, deterministic).
- `tv_service.py` ≤ 800 LOC (S3 closed).
- `grep providers_succeeded personalscraper/` returns 0 matches (S2 closed).
- `grep "list\[str\]" personalscraper/api/metadata/registry/_events.py`
  returns 0 matches in dataclass field declarations (S1 closed).

## ACC criteria touched

None. ACC-07 / ACC-09 baselines stay at 59 / 342 unless 27.1 + 27.2
add net new tests (re-measure at 27.4 if so).

## Cost estimate

- 27.1 (S1 + S2 mechanical + regression test): ~25 min DeepSeek
- 27.2 (S3 tv_service refactor + verification): ~60 min Sonnet OR Opus
  (depends on extraction size; if > 6 files, Opus 1M)
- 27.3 (F1 flaky test): ~30 min (Option A: investigation + fix) OR
  ~10 min (Option B: pragmatic mark + ROADMAP entry)
- 27.4 (gate): ~5 min DeepSeek

Total: ~2h00 best case, ~3h00 with proper F1 investigation.

## Risk

**Medium**. S3 refactor is the most invasive — module extraction crosses
import boundaries. Plan contingency: if `pytest tests/scraper/` shows
ANY new failure after extraction, ROLL BACK the refactor commit and
mark S3 deferred to a separate phase. F1 has its pragmatic fallback path
documented; the real fix may need to land in a dedicated follow-up.
