# Phase 8 — Legacy deprecation pass + final doc realignment + version bump

**Goal:** Audit and act on every legacy compatibility path identified in DESIGN Section 2.4. Final documentation pass to ensure no stale references remain post-decomposition. Bump `VERSION` 0.8.0 → 0.9.0.

**Risk:** Medium. Removing or deprecating legacy paths can surprise external consumers (launchd plists, Home Assistant cron, Makefile targets, scripts/). The grep audit in 8.1 is the primary mitigation — anything found in actual use is downgraded from "remove" to "deprecate".

**Files affected (estimate):**

- Modify: `personalscraper/cli.py` or `commands/library.py` (add `DeprecationWarning` to `library-scan`), various `personalscraper/conf/` modules (v1 config deprecation log), `VERSION`, `docs/reference/commands.md`, `docs/reference/architecture.md`, `docs/reference/pipeline-internals.md`, `docs/reference/trailers.md`, `docs/reference/indexer.md`, `CLAUDE.md`
- Inspect only: `pyproject.toml` currently uses dynamic versioning via `personalscraper.__version__`; update it only if a pinned `version = ...` field is introduced before phase 8.
- Possibly delete: `personalscraper/legacy/media_index_json.py` (or wherever the JSON shim lives) if grep finds zero consumers

## Sub-phases

### 8.1 — Legacy consumer audit

**Files:**

- Create: `docs/superpowers/roadmap/arch-cleanup/plan/phase-08-audit.md` (audit results)

- [ ] **Step 1: Grep every legacy surface for external consumers**

```bash
# library-scan command consumers
grep -rn "library-scan\|library_scan" \
  ~/Library/LaunchAgents/ \
  ~/.config/launchd/ \
  Makefile scripts/ docs/ \
  README.md CLAUDE.md \
  ../*/Makefile ../*/cron* 2>/dev/null

# media_index.json consumers
grep -rn "media_index\.json\|media-index\.json" \
  personalscraper/ tests/ scripts/ docs/ \
  ~/Library/LaunchAgents/ \
  ~/.homeassistant/ 2>/dev/null

# v1 config consumers
grep -rn "config_v1\|configv1\|v1_config" personalscraper/ tests/ docs/ 2>/dev/null

# Already-deprecated CLI flags
grep -rn "DeprecationWarning\|deprecated\b" personalscraper/cli.py personalscraper/commands/ 2>/dev/null
```

- [ ] **Step 2: Document results in phase-08-audit.md**

For each legacy surface, record:

- Internal consumers (test files, other modules) → migrate or deprecate
- External consumers (launchd, Home Assistant, scripts) → **deprecate only**, never remove in 0.9.0
- Zero consumers found → safe to remove

- [ ] **Step 3: Commit audit**

```bash
git commit -m "docs(arch-cleanup): legacy consumer audit results"
```

### 8.2 — `library-scan` deprecation

**Files:**

- Modify: `personalscraper/commands/library.py` (post-phase-2 location)

- [ ] **Step 1: Add deprecation warning at command entry**

```python
import warnings

@app.command()
def library_scan(...) -> None:
    """[DEPRECATED, removal in 0.10.0] Legacy library scan.

    Use `library-index` instead. The two commands maintain different mental
    models; library-index is the SQLite-backed authoritative source.
    """
    warnings.warn(
        "library-scan is deprecated and will be removed in 0.10.0. "
        "Use library-index instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Also surface visibly to the user (warnings are silenced by default in CLI):
    from rich.console import Console
    Console(stderr=True).print(
        "[yellow]library-scan is deprecated and will be removed in 0.10.0. "
        "Use library-index instead.[/]"
    )
    # ... existing body unchanged ...
```

- [ ] **Step 2: Add a test asserting the warning is emitted**

```python
# tests/commands/test_library_scan_deprecation.py
import warnings
import pytest


def test_library_scan_emits_deprecation_warning(...):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # ... invoke library-scan via test runner ...
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert any("0.10.0" in str(w.message) for w in caught)
```

- [ ] **Step 3: Run, expect PASS**, commit

```bash
git commit -m "refactor(arch-cleanup): deprecate library-scan, schedule removal in 0.10.0"
```

### 8.3 — `media_index.json` removal or deprecation

Decision tree based on 8.1 audit:

**Case A — zero external consumers found:**

- [ ] **Step 1: Find the writer + reader code paths.**
- [ ] **Step 2: Delete the writer**, leave the reader as a one-shot migration helper that imports the old JSON into the SQLite indexer on first invocation if both files exist.
- [ ] **Step 3: After 1 release of migration grace, remove the reader in 0.10.0**.
- [ ] **Step 4: Update `docs/reference/indexer.md`** noting the migration path.
- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): remove media_index.json writer; reader becomes one-shot migration"
```

**Case B — external consumers found:**

- [ ] **Step 1: Add a deprecation log line at every read/write**
- [ ] **Step 2: Document the removal target (0.10.0) in `docs/reference/indexer.md`**
- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(arch-cleanup): deprecate media_index.json read/write paths"
```

### 8.4 — v1 config deprecation

**Files:**

- Modify: `personalscraper/conf/loader.py` (or wherever v1→v2 migration lives)

- [ ] **Step 1: Find the v1 detection branch**

```bash
grep -rn "v1\|version\s*[=:]\s*1\b" personalscraper/conf/ 2>/dev/null
```

- [ ] **Step 2: Emit a `DeprecationWarning` and an `info`-level structlog event on every v1 load**

```python
# personalscraper/conf/loader.py — inside the v1 branch
import warnings
warnings.warn(
    "Config v1 format is deprecated; will be removed in 0.10.0. "
    "Run `personalscraper migrate-config` to upgrade.",
    DeprecationWarning,
    stacklevel=2,
)
self._log.warning("config_v1_deprecated", path=str(config_path))
```

- [ ] **Step 3: Document in `docs/reference/architecture.md`** (or `docs/reference/commands.md` under `migrate-config`).

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(arch-cleanup): deprecate v1 config format, schedule removal in 0.10.0"
```

### 8.5 — Audit and normalise existing deprecated CLI flags

- [ ] **Step 1: List currently-deprecated flags**

```bash
grep -rnE 'deprecat|DeprecationWarning' personalscraper/ 2>/dev/null
```

- [ ] **Step 2: For each, ensure**:
  - The deprecation message names the **target removal version** (0.10.0)
  - The deprecation is mentioned in `docs/reference/commands.md` under the relevant command
  - The flag still works (not silently broken)

- [ ] **Step 3: Test + commit**

```bash
git commit -m "refactor(arch-cleanup): normalise deprecation messages with 0.10.0 target"
```

### 8.6 — Final documentation realignment

**Files:**

- Modify: `docs/reference/architecture.md`, `docs/reference/pipeline-internals.md`, `docs/reference/trailers.md`, `docs/reference/indexer.md`, `docs/reference/commands.md`, `CLAUDE.md`

- [ ] **Step 1: `docs/reference/architecture.md`** — refresh module map post-decomposition. Confirm:
  - `personalscraper/commands/{pipeline,library,config,info,diagnose}.py` listed
  - `personalscraper/scraper/{orchestrator,movie_service,tv_service,rename_service,existing_validator,classifier}.py` listed
  - `personalscraper/indexer/scanner/_modes/` (package) listed instead of `_modes.py`
  - `personalscraper/indexer/commands/` listed
  - `personalscraper/reports/` listed
  - `personalscraper/pipeline_protocol.py` and `pipeline_steps.py` listed

- [ ] **Step 2: `docs/reference/pipeline-internals.md`** — verify the PipelineStep Protocol section added in phase 6.5 is still accurate. Add `details_payload` mention from phase 7.

- [ ] **Step 3: `docs/reference/trailers.md`** — ensure trailers semantics (placement before dispatch, non-blocking, skip flags) is documented. If phase 1.3 already corrected step counts, validate.

- [ ] **Step 4: `docs/reference/commands.md`** — list deprecation schedule for library-scan, deprecated flags, v1 config migration.

- [ ] **Step 5: `CLAUDE.md`** — verify the module-size rule (added in phase 1.6) still reflects current thresholds.

- [ ] **Step 6: Commit**

```bash
git commit -m "docs(arch-cleanup): final documentation realignment"
```

### 8.7 — Bump VERSION to 0.9.0

**Files:**

- Modify: `VERSION`
- Modify: `pyproject.toml` only if it contains a pinned `version = ...` field at execution time.

- [ ] **Step 1: Update VERSION**

```bash
echo "0.9.0" > VERSION
```

- [ ] **Step 2: Update pyproject.toml**

```bash
grep -nE '^version\s*=' pyproject.toml
# If no line is found, pyproject uses dynamic versioning and requires no edit.
# If a pinned line exists, edit it to: version = "0.9.0"
```

- [ ] **Step 3: Verify**

```bash
cat VERSION
grep -E '^version' pyproject.toml || true
python3 -c "import personalscraper; print(personalscraper.__version__)" 2>/dev/null || true
```

- [ ] **Step 4: Run full quality gate**

```bash
make check
pytest tests/ -v
python3 scripts/check-module-size.py --strict   # optional pre-check for 0.10.0 readiness
```

- [ ] **Step 5: Commit**

```bash
git commit -m "chore(arch-cleanup): bump VERSION to 0.9.0"
```

### 8.8 — Phase + feature gate

- [ ] **Step 1: Phase milestone commit**

```bash
git commit --allow-empty -m "chore(arch-cleanup): phase 8 gate — legacy deprecation + bump complete"
```

- [ ] **Step 2: Confirm IMPLEMENTATION.md phases all checked**

(This is `/implement:phase` orchestrator territory — automatic at this point.)

- [ ] **Step 3: Final feature-PR is auto-invoked by `/implement:phase`** (lifecycle: `/implement:feature-pr` → push → CI → `/implement:pr-review`).

## Quality gate

```bash
make check
pytest tests/ -v
python3 scripts/check-module-size.py
cat VERSION   # 0.9.0
```

## Success criteria

- 8.1 audit results documented and committed
- `library-scan` emits `DeprecationWarning` with 0.10.0 removal target
- `media_index.json` either removed (Case A) or deprecated (Case B)
- v1 config emits `DeprecationWarning` on every load
- All previously-deprecated flags have normalised messages mentioning 0.10.0
- All `docs/reference/` files reflect current code layout
- `VERSION` = `0.9.0`
- `pyproject.toml` version = `0.9.0` only if pyproject has a pinned version field; otherwise dynamic versioning remains unchanged.
- All tests pass; coverage delta ≥ 0; module-size script reports zero WARN/REPORT entries (success criterion of the entire feature)

## Rollback plan

Each sub-phase is one commit. The bump (8.7) must be the last commit so reverting it leaves the legacy work intact. If 8.3 Case A removal turns out to break a quietly-running consumer post-merge, hot-fix branch (`fix/restore-media-index-json-shim`) is preferable to feature revert.

## Estimated effort

3-5 commits (audit doc + 4 deprecation commits + bump + gate), ~4 hours.
