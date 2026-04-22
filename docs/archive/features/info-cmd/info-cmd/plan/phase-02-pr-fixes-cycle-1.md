# Phase 02 — PR fixes cycle 1

## Context

Fixes identified during PR review cycle 1. Coherent with DESIGN.md scope (the design example showed an `archive: …/Done` line but the project's V15 `PathConfig` has no `archive_dir` field — the path was a fabrication).

## Sub-phases

### 2.1 — Remove hardcoded "Done" archive path from InfoReport

**Finding**: `personalscraper/info/run.py:107` — `archive_path = config.paths.staging_dir / "Done"` hardcodes a magic string, contradicting V15 config-driven principle. Reviewer classification: medium.

**Location**: `personalscraper/info/run.py` (InfoReport dataclass + collect_info + format_info)

**Severity**: medium

**Acceptance**: no hardcoded `"Done"` (or any other magic path) in `personalscraper/info/run.py`. `InfoReport` no longer has an `archive_path` field. `format_info` output no longer shows an `archive:` line. Tests updated to match. Quality gate green.

**Implementation steps**:

- [ ] **Step 1: Remove `archive_path` field from `InfoReport`**

  Edit `personalscraper/info/run.py`:
  - Remove `archive_path: Path` from the `InfoReport` dataclass
  - Remove the `archive_path = config.paths.staging_dir / "Done"` computation in `collect_info`
  - Remove the `archive:` line from `format_info` output

- [ ] **Step 2: Update unit tests**

  Edit `tests/info/test_run.py`:
  - Remove any assertion on `archive_path` / `archive:` from InfoReport construction tests
  - Remove `archive:` line from format_info expected output tests
  - Remove the `archive_path` kwarg from `_make_report()` helper if present

- [ ] **Step 3: Update DESIGN.md**

  Edit `docs/features/info-cmd/DESIGN.md`:
  - Remove the `archive:` example line from section 2 "Comportement"
  - Remove the `archive_path` field from the `InfoReport` dataclass example in section 3
  - Add a note clarifying that archive path is NOT exposed by the current `PathConfig`, and re-adding it would require a separate feature bumping PathConfig

- [ ] **Step 4: Quality gate + commit**

  ```bash
  python -m ruff check personalscraper/info/ tests/info/
  python -m ruff format --check personalscraper/info/ tests/info/
  python -m mypy personalscraper/info/
  python -m pytest tests/info/ tests/test_cli.py -v
  ```

  All must pass.

  ```bash
  git add personalscraper/info/run.py tests/info/test_run.py docs/features/info-cmd/DESIGN.md
  git commit -m "fix(info-cmd): remove hardcoded archive path (no archive_dir in PathConfig)"
  ```

## Coherence gate

- [ ] `grep -n "archive" personalscraper/info/run.py` returns 0 matches (no archive_path anywhere)
- [ ] `grep -n "archive:" tests/info/test_run.py` returns 0 matches
- [ ] `make test` exits 0
- [ ] `make lint` exits 0
