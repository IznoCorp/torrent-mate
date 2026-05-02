# Phase 7 — `StepReport` Tier A typed details

**Goal:** Make the per-step `StepReport.details` contract explicit. Add typed `*Details` dataclasses under `personalscraper/reports/` (one per step), a `STEP_REPORT_CONTRACT` registry, and a new `StepReport.details_payload: Any | None = None` field. Each step constructs and returns its typed payload alongside the existing untyped `details: list[str]`. **Additive — no consumer break.**

**Risk:** Low. Tier A is strictly additive — `details: list[str]` is preserved, `details_payload` defaults to `None`, all existing consumers (HTML report, notifier, CLI display) continue to work unchanged.

**Files affected (estimate):**

- Create: `personalscraper/reports/{ingest,sort,clean,scrape,cleanup,enforce,verify,trailers,dispatch}.py`
- Modify: `personalscraper/reports/__init__.py` (populate `STEP_REPORT_CONTRACT`), `personalscraper/models.py` (add `details_payload` field), each `personalscraper/<domain>/run.py` or equivalent that emits `StepReport`
- Test: `tests/reports/test_*.py` (one per step), `tests/reports/test_contract_registry.py`

## Sub-phases

### 7.1 — Add `StepReport.details_payload` field (TDD)

**Files:**

- Modify: `personalscraper/models.py`
- Create: `tests/test_step_report_payload.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_step_report_payload.py
"""StepReport.details_payload must default to None and accept any object."""
from dataclasses import dataclass

from personalscraper.models import StepReport


def test_step_report_details_payload_defaults_to_none():
    r = StepReport(name="x")
    assert r.details_payload is None


def test_step_report_details_payload_accepts_arbitrary_object():
    @dataclass
    class FakeDetails:
        value: int

    r = StepReport(name="x", details_payload=FakeDetails(value=42))
    assert r.details_payload.value == 42


def test_step_report_legacy_details_field_still_exists():
    r = StepReport(name="x", details=["one", "two"])
    assert r.details == ["one", "two"]
    assert r.details_payload is None  # additive, no implicit migration
```

- [ ] **Step 2: Run, FAIL**.

- [ ] **Step 3: Add the field to `StepReport`**

```python
# personalscraper/models.py — inside StepReport dataclass, after `unmatched_paths: list[str]`
details_payload: Any | None = None
"""Optional typed payload for this step. See personalscraper/reports/."""
```

Add `from typing import Any` at top.

- [ ] **Step 4: Run, expect 3/3 PASS**.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(arch-cleanup): add StepReport.details_payload field (additive)"
```

### 7.2 — Define typed details for each step (TDD per step)

For each of the 9 steps, write a small `*Details` dataclass with the fields each step actually emits today. The implementer extracts these from the current `details: list[str]` parsing logic in the consumers.

Repeat the following pattern for each step:

#### Pattern (example for `trailers`)

**Files:**

- Create: `personalscraper/reports/trailers.py`
- Create: `tests/reports/test_trailers_details.py`

- [ ] **Step 1: Write tests asserting field shape**

```python
# tests/reports/test_trailers_details.py
from personalscraper.reports.trailers import TrailersDetails


def test_trailers_details_default_empty():
    d = TrailersDetails()
    assert d.downloaded == []
    assert d.bot_detected == []
    assert d.skipped_existing == []
    assert d.failed == []


def test_trailers_details_serialisable_to_dict():
    from dataclasses import asdict
    d = TrailersDetails(downloaded=["movie1", "movie2"], bot_detected=["movie3"])
    out = asdict(d)
    assert out["downloaded"] == ["movie1", "movie2"]
    assert out["bot_detected"] == ["movie3"]
```

- [ ] **Step 2: Implement `personalscraper/reports/trailers.py`**

```python
# personalscraper/reports/trailers.py
"""Typed details payload for the trailers step."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrailersDetails:
    """Per-item outcomes of the trailers step.

    Attributes:
        downloaded: Items where a trailer was successfully downloaded.
        bot_detected: Items where YouTube returned bot-detection (will retry next run).
        skipped_existing: Items already having a trailer locally.
        failed: List of (item_id, error_reason) pairs.
    """

    downloaded: list[str] = field(default_factory=list)
    bot_detected: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


__all__ = ["TrailersDetails"]
```

- [ ] **Step 3: Run, PASS, commit**

```bash
git commit -m "feat(arch-cleanup): add TrailersDetails typed payload"
```

#### Field shape per step

The implementer infers fields from current code. Suggested skeletons:

| Step       | Module                | Fields (refine from code)                                                                                                                                       |
| ---------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ingest`   | `reports/ingest.py`   | `IngestDetails(copied: list[str], skipped_already_present: list[str], failed: list[tuple[str,str]])`                                                            |
| `sort`     | `reports/sort.py`     | `SortDetails(moved: list[SortResult], skipped: list[SortResult], errored: list[SortResult])`                                                                    |
| `clean`    | `reports/clean.py`    | `CleanDetails(removed_dirs: list[str], removed_files: list[str], renamed: dict[str,str])`                                                                       |
| `scrape`   | `reports/scrape.py`   | `ScrapeDetails(scraped: list[str], skipped_low_confidence: list[str], existing_validated: list[str], failed: list[tuple[str,str]], unmatched_paths: list[str])` |
| `cleanup`  | `reports/cleanup.py`  | `CleanupDetails(removed: list[str], errors: list[tuple[str,str]])`                                                                                              |
| `enforce`  | `reports/enforce.py`  | `EnforceDetails(corrected: list[str], already_compliant: list[str], failed: list[tuple[str,str]])`                                                              |
| `verify`   | `reports/verify.py`   | `VerifyDetails(verified: list[str], issues: list[VerifyIssue], fixed: list[str])`                                                                               |
| `trailers` | `reports/trailers.py` | (above)                                                                                                                                                         |
| `dispatch` | `reports/dispatch.py` | `DispatchDetails(moved_to_disk: dict[str,list[str]], merged: list[str], replaced: list[str], failed: list[tuple[str,str]])`                                     |

Each gets its own sub-phase commit:

- 7.2.1 ingest, 7.2.2 sort, ..., 7.2.9 dispatch.

### 7.3 — Populate `STEP_REPORT_CONTRACT` registry

**Files:**

- Modify: `personalscraper/reports/__init__.py`
- Create: `tests/reports/test_contract_registry.py`

- [ ] **Step 1: Write tests**

```python
# tests/reports/test_contract_registry.py
from personalscraper.reports import STEP_REPORT_CONTRACT


def test_contract_has_nine_entries():
    assert len(STEP_REPORT_CONTRACT) == 9
    assert set(STEP_REPORT_CONTRACT) == {
        "ingest", "sort", "clean", "scrape", "cleanup",
        "enforce", "verify", "trailers", "dispatch",
    }


def test_contract_values_are_dataclasses():
    from dataclasses import is_dataclass
    for name, cls in STEP_REPORT_CONTRACT.items():
        assert is_dataclass(cls), f"{name} -> {cls.__name__} is not a dataclass"
```

- [ ] **Step 2: Implement**

```python
# personalscraper/reports/__init__.py
"""Per-step typed details payloads + contract registry."""
from __future__ import annotations

from personalscraper.reports.cleanup import CleanupDetails
from personalscraper.reports.clean import CleanDetails
from personalscraper.reports.dispatch import DispatchDetails
from personalscraper.reports.enforce import EnforceDetails
from personalscraper.reports.ingest import IngestDetails
from personalscraper.reports.scrape import ScrapeDetails
from personalscraper.reports.sort import SortDetails
from personalscraper.reports.trailers import TrailersDetails
from personalscraper.reports.verify import VerifyDetails


STEP_REPORT_CONTRACT: dict[str, type] = {
    "ingest": IngestDetails,
    "sort": SortDetails,
    "clean": CleanDetails,
    "scrape": ScrapeDetails,
    "cleanup": CleanupDetails,
    "enforce": EnforceDetails,
    "verify": VerifyDetails,
    "trailers": TrailersDetails,
    "dispatch": DispatchDetails,
}


__all__ = [
    "STEP_REPORT_CONTRACT",
    "CleanDetails", "CleanupDetails", "DispatchDetails", "EnforceDetails",
    "IngestDetails", "ScrapeDetails", "SortDetails", "TrailersDetails", "VerifyDetails",
]
```

- [ ] **Step 3: Run, PASS, commit**

```bash
git commit -m "feat(arch-cleanup): populate STEP_REPORT_CONTRACT registry"
```

### 7.4 — Wire each step's `run_*()` to populate `details_payload`

**Files:**

- Modify: each domain's `run_*` entry point (current locations include `personalscraper/ingest/ingest.py`, `sorter/run.py`, `process/run.py`, `scraper/run.py` or post-phase-5 `scraper/orchestrator.py`, `enforce/run.py`, `verify/run.py`, `trailers/step.py`, `dispatch/run.py`)

For each step, find the `StepReport(...)` construction site and add the typed payload:

```python
# Example — personalscraper/trailers/step.py
from personalscraper.reports.trailers import TrailersDetails

def run_trailers(...) -> StepReport:
    # ... existing logic populating downloaded, bot_detected, skipped_existing, failed ...
    payload = TrailersDetails(
        downloaded=downloaded,
        bot_detected=bot_detected,
        skipped_existing=skipped_existing,
        failed=failed,
    )
    return StepReport(
        name="trailers",
        success_count=len(downloaded),
        skip_count=len(skipped_existing),
        error_count=len(failed),
        warnings=warnings,
        details=existing_string_list,
        status="success" if not failed else "partial",
        details_payload=payload,  # NEW — additive
    )
```

Each step gets its own sub-phase commit:

- 7.4.1 ingest, 7.4.2 sort, ..., 7.4.9 dispatch.

After each: `pytest tests/<domain>/ -v` to confirm no regression.

```bash
git commit -m "refactor(arch-cleanup): populate details_payload in <step> run_*"
```

### 7.5 — Phase gate

```bash
make check
pytest tests/reports/ -v
pytest tests/ -v -k "details_payload"
git commit --allow-empty -m "chore(arch-cleanup): phase 7 gate — StepReport Tier A complete"
```

## Quality gate

```bash
make check
pytest tests/reports/ -v
pytest tests/integration -v
```

## Success criteria

- `StepReport.details_payload: Any | None = None` field exists
- 9 typed `*Details` dataclasses live under `personalscraper/reports/`
- `STEP_REPORT_CONTRACT` maps each step name to its typed Details class
- Every `run_*()` populates `details_payload` alongside the legacy `details` list
- Existing consumers (`PipelineReport.to_html`, notifier, CLI display) work unchanged because `details_payload` is optional
- Coverage delta ≥ 0

## Rollback plan

Phase 7 is purely additive. Reverting any sub-phase removes a typed payload but leaves the legacy `details: list[str]` flow intact — zero impact on production.

## Estimated effort

5-7 commits (1 for the field add, 1 for registry, 9 for per-step wiring — but wiring sub-phases can be batched in 2-3 commits if changes are small), ~5 hours.
