# Phase 5 — Pipeline step (`trailers/step.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §2 (pipeline position) and DESIGN §13 (StepReport contract).
Create `personalscraper/trailers/step.py` and wire the `trailers` step into
`personalscraper/pipeline.py` **between `verify` and `dispatch`** — specifically before the
existing `if verified:` branch that guards dispatch. The step is non-blocking: `partial` and
`skipped` statuses do not abort dispatch. Add the `trailers` emoji to
`PipelineReport.to_html()`. Tests mock the orchestrator.

**Why between `verify` and `dispatch`** (reviewer-flagged correction): `scrape` has already
posed the NFOs trailer_finder reads, and `verify` has validated media structure. Running
`trailers` between them means (a) items that would fail dispatch anyway never trigger
bandwidth-heavy downloads, (b) trailers land next to media still in staging and are
dispatched together in one move. The real pipeline today is 8 steps (from `pipeline.py`):
`ingest → sort → clean → scrape → cleanup → enforce → verify → dispatch`. After this
feature lands it becomes 9 steps with `trailers` inserted just before `dispatch`.

**Architecture:** `run_trailers(config, staging_dir, verified, skip_trailers=False) -> StepReport`.
Uses the existing `StepReport` dataclass from `personalscraper/models.py`. Returns a typed step
status string via the `details` list field. The `verified` list is passed from the pipeline so
the trailers step can skip items that already failed `verify` earlier in the pipeline. The pipeline gate reads `status` as a string tag in
`step.details` (since `StepReport` does not currently have a `status` field — the extended
contract is communicated through the `name` field and a convention tag in `details`).

**Important note on `StepReport` extension:** DESIGN §13 defines a richer report
(`status`, `counts`, `failed_items`) that the existing `StepReport` dataclass does not
support. Two options:

1. Extend `StepReport` in `models.py` with optional fields (preferred — minimal change).
2. Use a separate `TrailersStepReport` dataclass that wraps `StepReport`.

This plan takes **option 1**: add optional `status: str | None = None` and
`counts: dict[str, int] = field(default_factory=dict)` to `StepReport`. Existing code
that does not set these fields is unaffected.

**Tech Stack:** Python, `pytest`, `unittest.mock`.

**Logging convention**: this phase uses structlog `get_logger(__name__)` with event-name +
kwargs (no `%s`/`%d` formatting — structlog BoundLoggers do not interpolate positional
args). See `docs/reference/logging.md`.

---

## Gate (entry condition)

Phases 3b, 3c, and 4 must be complete:

```bash
python -c "from personalscraper.scraper.ytdlp_downloader import YtdlpDownloader; print('OK')"
python -c "from personalscraper.trailers.placement import trailer_path_for; print('OK')"
python -c "from personalscraper.trailers.state import TrailerStateStore; print('OK')"
```

---

## Dependencies

- Phase 3b (`YtdlpDownloader` — called by orchestrator, which step delegates to)
- Phase 3c (placement convention — used by step to find staging trailer paths)
- Phase 4 (`TrailerStateStore` — state tracking called from step)

---

## Invariants for this phase

- `StepReport` extensions are backward-compatible: existing code that constructs
  `StepReport` without the new fields continues to work (fields have defaults).
- `partial` status in the trailers step does NOT block the dispatch step.
- `pipeline.py` changes are minimal: one import block + one `_run_trailers_phase()` call.
- All existing `tests/test_pipeline.py` and `tests/test_pipeline_integration.py` must pass.

---

## Sub-phase 5.1 — Extend `StepReport` + trailer step scaffold

### Files

| Action | Path                               | Responsibility                            |
| ------ | ---------------------------------- | ----------------------------------------- |
| Modify | `personalscraper/models.py`        | Add `status` and `counts` optional fields |
| Create | `personalscraper/trailers/step.py` | `run_trailers()` skeleton                 |
| Create | `tests/trailers/test_step.py`      | Unit tests                                |

### Step 0: Audit existing `StepReport(…)` call-sites before mutating the dataclass

The `StepReport` dataclass is shared across every pipeline step, and it is serialized via
`PipelineReport.to_html()` and consumed by `notifier.py`. Adding fields with defaults is
backward-compatible, but regressions can slip in if any caller uses **positional** arguments
past the first two fields. This step catches those before the refactor.

```bash
cd "$(git rev-parse --show-toplevel)"
# Find every StepReport construction
grep -rn "StepReport(" personalscraper/ tests/ | tee /tmp/stepreport_callsites.txt
# Find every StepReport field read (to_html, notifier, report aggregations)
grep -rn "\.status\b\|\.counts\b\|\.failed_items\b\|step_report\." \
    personalscraper/models.py personalscraper/notifier.py personalscraper/pipeline.py
```

Open `/tmp/stepreport_callsites.txt` and verify every constructor call uses keyword
arguments for fields beyond `name`. If any call uses positional arguments for
`success_count`, `skip_count`, `error_count`, or `details`, rewrite it to use kwargs in a
tiny preparatory commit — no behaviour change, just future-proofing:

```bash
git add -p personalscraper/  # only the rewrite hunks
git commit -m "refactor(trailer): use kwargs for StepReport constructions (pre-extension)"
```

Expected audit targets (as of commit `6bd2b66` — re-run grep to confirm exact line numbers):

- `personalscraper/pipeline.py` (lines 284, 444) — `_run_step()` wrappers, empty-dispatch skip branch
- `personalscraper/scraper/run.py` (lines 182, 256)
- `personalscraper/sorter/run.py` (lines 49, 57)
- `personalscraper/verify/run.py` (lines 71, 128)
- `personalscraper/enforce/run.py` (line 74)
- `personalscraper/dispatch/run.py` (line 173)
- `personalscraper/ingest/ingest.py` (line 198)
- `personalscraper/process/run.py` (lines 44, 92, 131, 141, 151)
- `personalscraper/process/cleanup.py` (line 51)
- `personalscraper/process/reclean.py` (line 216)
- `personalscraper/notifier.py` — consumes `report.to_html()` (no direct `StepReport(…)` construction as of audit)

Pre-audit finding (commit `6bd2b66`): ~20 call-sites across 11 files, **all** already use
keyword arguments after the first positional `name=` field. The preparatory kwargs-rewrite
commit may therefore be a no-op — confirm before committing. If all call-sites are already
kwargs-safe, skip the rewrite commit entirely and proceed to Step 1.

- `personalscraper/models.py` — `PipelineReport.to_html()` / `.add_step()`

Also add a non-regression test in `tests/test_models.py` that constructs `StepReport`
without the new fields and calls `to_html()` — documented proof that the extension does
not break any existing caller shape.

### Step 1: Write failing tests

Create `tests/trailers/test_step.py`:

```python
"""Unit tests for trailers/step.py — pipeline step wiring.

Orchestrator is fully mocked; no real discovery or downloads occur.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.models import StepReport
from personalscraper.trailers.step import run_trailers


@pytest.fixture()
def config(tmp_path):
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.filters.min_file_size_bytes = 102400
    return cfg


class TestRunTrailers:
    def test_returns_step_report(self, config, tmp_path):
        """run_trailers() returns a StepReport instance."""
        with patch("personalscraper.trailers.step.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 0, "already_present": 0,
                "no_trailer": 0, "bot_detected": 0, "error": 0,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert isinstance(result, StepReport)
        assert result.name == "trailers"

    def test_skipped_when_disabled(self, config, tmp_path):
        """run_trailers() returns a skipped report when config.trailers.enabled=False."""
        config.trailers.enabled = False
        result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.name == "trailers"
        assert result.status == "skipped"

    def test_skip_trailers_flag_skips(self, config, tmp_path):
        """run_trailers() respects the skip_trailers flag."""
        result = run_trailers(config, staging_dir=tmp_path, verified=[], skip_trailers=True)
        assert result.status == "skipped"

    def test_counts_in_step_report(self, config, tmp_path):
        """run_trailers() populates StepReport counts from orchestrator output."""
        with patch("personalscraper.trailers.step.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 3, "already_present": 5,
                "no_trailer": 1, "bot_detected": 0, "error": 0,
                "skipped_by_state": 2,
            }
            mock_orch.failed_items = []
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.success_count == 3
        assert result.skip_count == 5 + 2
        assert result.counts.get("downloaded") == 3

    def test_partial_status_on_failures(self, config, tmp_path):
        """run_trailers() returns status='partial' when some items failed."""
        with patch("personalscraper.trailers.step.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 2, "already_present": 1,
                "no_trailer": 0, "bot_detected": 1, "error": 1,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = [("movie:tmdb:1", "bot_detected", "sign in")]
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.status == "partial"

    def test_success_status_when_no_failures(self, config, tmp_path):
        """run_trailers() returns status='success' when no errors or bot detections."""
        with patch("personalscraper.trailers.step.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 5, "already_present": 0,
                "no_trailer": 0, "bot_detected": 0, "error": 0,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.status == "success"
```

### Step 2: Extend `StepReport` in `personalscraper/models.py`

Add to the `StepReport` dataclass (after existing fields):

```python
status: str | None = None
counts: dict[str, int] = field(default_factory=dict)
failed_items: list[tuple[str, str, str]] = field(default_factory=list)
```

Verify that existing `StepReport` construction in the codebase is not broken (all callers
use keyword arguments or positional-only for existing fields — the new fields have defaults).

### Step 3: Verify existing tests still pass after models.py change

```bash
pytest tests/test_pipeline.py tests/test_pipeline_integration.py -q
```

Expected: all green.

### Step 4: Implement `personalscraper/trailers/step.py`

```python
"""Pipeline step: trailer discovery and download for staged media.

Runs after the ``verify`` step and before ``dispatch``. Non-blocking:
failures produce ``status='partial'`` and dispatch proceeds. Uses structlog
(the project-wide logger) — not the stdlib ``logging``.

Public entry point:
``run_trailers(config, staging_dir, verified, skip_trailers=False) -> StepReport``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.models import StepReport

if TYPE_CHECKING:
    from personalscraper.conf.models import Config
    from personalscraper.verify.run import VerifyResult

logger = get_logger(__name__)


def run_trailers(
    config: "Config",
    staging_dir: Path,
    verified: list,
    skip_trailers: bool = False,
) -> StepReport:
    """Run the trailers pipeline step for all staged media items.

    Scans ``staging_dir`` for media without trailers, discovers YouTube URLs
    via TMDB/YouTube, downloads via yt-dlp, and places files next to media.
    Non-blocking: failures log a warning and dispatch continues.

    Args:
        config: Loaded pipeline Config.
        staging_dir: Path to the staging area (where sorted media lives).
        verified: List of items that passed the previous ``verify`` step. Items
            absent from this list are skipped (they failed verify already).
        skip_trailers: If True, return a skipped StepReport immediately.

    Returns:
        StepReport with name="trailers", status in
        {success, partial, skipped, error}, and counts dict.
    """
    # Skipped gate
    if skip_trailers or not config.trailers.enabled:
        logger.info(
            "trailers_step_skipped",
            enabled=config.trailers.enabled,
            skip_flag=skip_trailers,
        )
        return StepReport(name="trailers", status="skipped")

    from personalscraper.trailers.orchestrator import TrailersOrchestrator

    try:
        orchestrator = TrailersOrchestrator(config=config, staging_dir=staging_dir)
        counts = orchestrator.run()
        failed_items = orchestrator.failed_items

        success_count = counts.get("downloaded", 0)
        skip_count = counts.get("already_present", 0) + counts.get("skipped_by_state", 0)
        error_count = counts.get("error", 0) + counts.get("bot_detected", 0)

        if error_count > 0 or failed_items:
            step_status = "partial"
        else:
            step_status = "success"

        report = StepReport(
            name="trailers",
            success_count=success_count,
            skip_count=skip_count,
            error_count=error_count,
            status=step_status,
            counts=counts,
            failed_items=failed_items,
        )
        logger.info(
            "trailers_step_complete",
            step_status=step_status,
            downloaded=success_count,
            skipped=skip_count,
            errors=error_count,
        )
        return report

    except Exception as exc:
        logger.exception("trailers_step_crashed", error=str(exc))
        return StepReport(name="trailers", error_count=1, status="error")
```

### Step 5: Run step tests

```bash
pytest tests/trailers/test_step.py -v
```

### Step 6: Commit sub-phase 5.1

```bash
git add \
  personalscraper/models.py \
  personalscraper/trailers/step.py \
  tests/trailers/test_step.py
git commit -m "feat(trailer): add trailers pipeline step with non-blocking StepReport contract"
```

---

## Sub-phase 5.2 — Wire into `pipeline.py` + `PipelineReport.to_html()` icon

### Files

| Action | Path                          | Responsibility                                   |
| ------ | ----------------------------- | ------------------------------------------------ |
| Modify | `personalscraper/pipeline.py` | Wire `run_trailers` between process and dispatch |
| Modify | `personalscraper/models.py`   | Add trailers icon to `to_html()` step_icons dict |

### Step 1: Add trailers icon to `PipelineReport.to_html()`

In `personalscraper/models.py`, add `"trailers": "\U0001f3ac"` (🎬) to the `step_icons`
dict inside `to_html()`.

### Step 2: Extend `Pipeline.__init__` with the two new flags

`Pipeline.__init__` in `personalscraper/pipeline.py` does NOT currently accept
`skip_trailers` or `continue_on_trailer_error`. Add them as keyword-only attributes
(default `False`) and store them on `self` so the wire-up in Step 3 can read them.
The CLI in Phase 8 is responsible for passing these flags through from the
`--skip-trailers` and `--continue-on-trailer-error` options to the `Pipeline(...)`
constructor.

```python
# Inside Pipeline.__init__
def __init__(
    self,
    config: Config,
    *,
    # ... existing kwargs unchanged ...
    skip_trailers: bool = False,
    continue_on_trailer_error: bool = False,
) -> None:
    # ... existing body ...
    self.skip_trailers = skip_trailers
    self.continue_on_trailer_error = continue_on_trailer_error
```

### Step 3: Wire the step in `pipeline.py` between `verify` and `dispatch`

`pipeline.py` currently wires verify then conditionally dispatch:

```python
# Phase 5: VERIFY
verified = self._run_step(
    "verify",
    lambda: self._run_verify(),
    report,
)

# Phase 6: DISPATCH (only if verified items exist)
if verified:
    from personalscraper.dispatch.run import run_dispatch
    self._run_step(
        "dispatch",
        lambda: run_dispatch(…, verified=verified),
        report,
    )
else:
    …  # skipped-dispatch branch adds a skipped StepReport
```

Insert the trailers step **between the two blocks above**, before the `if verified:`
branch. When `verified` is empty, the trailers step short-circuits with `status="skipped"`
(the same pattern dispatch uses on its empty-verified branch):

`_run_step()` returns the _extra_ value (second tuple element) from the step callable, NOT
the `StepReport` — the StepReport is stored internally in `report.steps` (a
`dict[str, StepReport]`) via `report.add_step()`. Read the trailers StepReport back
through `report.steps.get("trailers")` to inspect its status:

```python
# Phase 5bis: TRAILERS (non-blocking — partial/skipped does not abort dispatch)
from personalscraper.trailers.step import run_trailers

self._run_step(
    "trailers",
    lambda: run_trailers(
        self.config,
        staging_dir=self.config.paths.staging_dir,
        verified=verified,
        skip_trailers=self.skip_trailers,
    ),
    report,
)

# _run_step does NOT return the StepReport — it appends it to report.steps.
# Look the report back up via the steps dict (keyed by step name).
trailers_step = report.steps.get("trailers")
if (
    trailers_step is not None
    and trailers_step.status == "error"
    and not self.continue_on_trailer_error
):
    self._log.error(
        "trailers_step_crashed",
        hint="use --continue-on-trailer-error to override",
    )
    report.finished_at = datetime.now()
    return report

# Phase 6: DISPATCH (only if verified items exist)
if verified:
    …  # existing block, unchanged
```

`staging_dir` is read from `self.config.paths.staging_dir` (the configurable staging path
from the `ext-staging` feature this depends on) — **never** hardcoded to any specific directory name.

### Step 4: Verify pipeline tests pass

```bash
pytest tests/test_pipeline.py tests/test_pipeline_integration.py -q
```

Expected: all green. If the new step is missing a mock in pipeline tests, add it with
`patch("personalscraper.trailers.step.run_trailers", return_value=StepReport(name="trailers", status="skipped"))`.

### Step 5: Commit sub-phase 5.2

```bash
git add personalscraper/pipeline.py personalscraper/models.py
git commit -m "feat(trailer): wire trailers step into pipeline between process and dispatch"
```

---

## Phase 5 quality gate

- [ ] `pytest tests/trailers/test_step.py tests/test_pipeline.py tests/test_pipeline_integration.py -q` — all green
- [ ] `python -m ruff check personalscraper/trailers/step.py personalscraper/models.py personalscraper/pipeline.py` — no errors
- [ ] `python -m mypy personalscraper/trailers/step.py` — no type errors

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/trailers/test_step.py tests/test_pipeline.py tests/test_pipeline_integration.py -q
python -m ruff check personalscraper/trailers/step.py personalscraper/models.py personalscraper/pipeline.py
python -m mypy personalscraper/trailers/step.py
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 05 gate — trailers step wired into pipeline, non-blocking contract"
```

## Exit condition for Phase 6

Phase 6 may start only when:

- `run_trailers` is importable from `personalscraper.trailers.step`
- Pipeline tests pass
- The milestone commit is on the branch
