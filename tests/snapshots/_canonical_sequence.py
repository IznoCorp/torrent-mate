"""Canonical event sequence for the RichConsoleObserver baseline.

Pre-flight #7 (see ``docs/features/event-bus/plan/INDEX.md``).

The sequence is replayed in order through a :class:`RichConsoleObserver`
to produce a byte-identical baseline of CLI output. It is consumed by:

* Phase 2 sub-phase 2.4 visual smoke (replay through legacy observer
  after the ``Pipeline`` refactor and compare against the baseline).
* Phase 3 sub-phase 3.5 RichConsoleSubscriber rewrite (replay through
  the new subscriber via ``EventBus.emit`` and compare bytes-identical).
* Phase 3 sub-phase 3.9 phase-gate visual regression check.

The sequence MUST exercise every code path of
``personalscraper/observers/rich_console.py`` (100% line coverage). To
cover both ``_dry_run`` and ``_verbose`` branches plus the empty
``run_id`` fallback in ``on_pipeline_start``, the recorder replays the
sequence through two observer configurations into a single Console
buffer (see ``test_record_baseline.py``). All payloads are concrete
literals — no ``MagicMock``, no real I/O, no live ``datetime.utcnow``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from personalscraper.models import PipelineReport, StepReport

UTC = timezone.utc


@dataclass(frozen=True)
class _CanonicalProgress:
    """Lightweight progress record used by the canonical sequence.

    Carries ``.step``, ``.item``, ``.status`` and ``.details``. Consumers
    translate it into the corresponding bus event in one line.
    """

    step: str
    item: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


# Deterministic timestamps — anchor the baseline so it never drifts.
_T0 = datetime(2026, 5, 11, 10, 0, 0, tzinfo=UTC)
_T0_PLUS_45S = _T0 + timedelta(seconds=45)
_T0_PLUS_5MIN_30S = _T0 + timedelta(minutes=5, seconds=30)


def _start_report() -> PipelineReport:
    """Build the pipeline start report (no finished_at, no steps)."""
    return PipelineReport(started_at=_T0, steps={}, finished_at=None)


def _end_report_ok_seconds() -> PipelineReport:
    """Pipeline end with no errors and a sub-minute duration."""
    return PipelineReport(
        started_at=_T0,
        finished_at=_T0_PLUS_45S,
        steps={"ingest": StepReport(name="ingest", success_count=5, skip_count=0, error_count=0)},
    )


def _end_report_errors_minutes() -> PipelineReport:
    """Pipeline end with errors and a multi-minute duration."""
    return PipelineReport(
        started_at=_T0,
        finished_at=_T0_PLUS_5MIN_30S,
        steps={"sort": StepReport(name="sort", success_count=3, skip_count=1, error_count=2)},
    )


def _step_report_ingest() -> StepReport:
    return StepReport(
        name="ingest",
        success_count=5,
        skip_count=1,
        error_count=0,
        warnings=[],
        details=["downloaded movie1"],
    )


def _step_report_sort() -> StepReport:
    return StepReport(
        name="sort",
        success_count=3,
        skip_count=2,
        error_count=0,
        warnings=["unknown extension .xyz"],
        # "skipped_already_done" detail triggers the continue branch in on_step_end.
        details=["skipped_already_done movie2", "moved movie3"],
    )


def _step_report_clean_empty() -> StepReport:
    """All counters zero — exercises the "nothing to do" branch."""
    return StepReport(name="clean")


def _step_report_scrape() -> StepReport:
    return StepReport(
        name="scrape",
        success_count=2,
        skip_count=0,
        error_count=1,
        warnings=["TMDB rate limit hit"],
        details=["scraped movie4", "skipped_already_done movie5"],
    )


def _step_report_cleanup() -> StepReport:
    return StepReport(
        name="cleanup",
        success_count=1,
        skip_count=1,
        error_count=0,
        warnings=[],
        details=["cleaned movie6"],
    )


def _step_report_enforce() -> StepReport:
    return StepReport(
        name="enforce",
        success_count=4,
        skip_count=0,
        error_count=0,
        warnings=[],
        details=["enforced movie7"],
    )


def _step_report_verify() -> StepReport:
    return StepReport(
        name="verify",
        success_count=2,
        skip_count=1,
        error_count=1,
        warnings=["nfo missing on movie8"],
        details=["verified movie9"],
    )


def _step_report_trailers() -> StepReport:
    return StepReport(
        name="trailers",
        success_count=3,
        skip_count=0,
        error_count=2,
        warnings=[],
        details=["trailer fetched movie10"],
    )


def _step_report_dispatch() -> StepReport:
    return StepReport(
        name="dispatch",
        success_count=5,
        skip_count=2,
        error_count=1,
        warnings=["disk almost full"],
        details=["dispatched movie11"],
    )


def _step_report_unknown() -> StepReport:
    """Used with an unknown step name to exercise the icon-default branch."""
    return StepReport(
        name="unknown_step",
        success_count=1,
        skip_count=0,
        error_count=0,
        warnings=[],
        details=["handled unknown1"],
    )


def _ev(step: str, item: str, status: str) -> _CanonicalProgress:
    return _CanonicalProgress(step=step, item=item, status=status)


# The canonical sequence: a list of (callback_name, args_tuple) pairs.
# Every code path of RichConsoleObserver is exercised here OR by replaying
# the sequence through a second observer configuration in the recorder
# (verbose=False to hit ``on_progress`` early-return, run_id="" to hit the
# isoformat fallback branch in ``on_pipeline_start``).
CANONICAL_SEQUENCE: list[tuple[str, tuple[Any, ...]]] = [
    # First pipeline frame — exercises start banner, all 9 step icons,
    # the unknown step icon-default branch, all 10 status values, and the
    # full StepReport variety (mixed counters, empty counters, errors,
    # warnings, "skipped_already_done" filter).
    ("on_pipeline_start", (_start_report(),)),
    # ingest — status "started"
    ("on_step_start", ("ingest",)),
    ("on_progress", (_ev("ingest", "movie1.mkv", "started"),)),
    ("on_step_end", ("ingest", _step_report_ingest(), 12.3)),
    # sort — status "completed"
    ("on_step_start", ("sort",)),
    ("on_progress", (_ev("sort", "movie2.mkv", "completed"),)),
    ("on_step_end", ("sort", _step_report_sort(), 5.0)),
    # clean — status "skipped" + empty step report (nothing to do)
    ("on_step_start", ("clean",)),
    ("on_progress", (_ev("clean", "movie3.mkv", "skipped"),)),
    ("on_step_end", ("clean", _step_report_clean_empty(), 0.1)),
    # scrape — status "failed" + errors + warnings + skipped_already_done
    ("on_step_start", ("scrape",)),
    ("on_progress", (_ev("scrape", "movie4.mkv", "failed"),)),
    ("on_step_end", ("scrape", _step_report_scrape(), 7.0)),
    # cleanup — status "moved"
    ("on_step_start", ("cleanup",)),
    ("on_progress", (_ev("cleanup", "movie5.mkv", "moved"),)),
    ("on_step_end", ("cleanup", _step_report_cleanup(), 3.0)),
    # enforce — status "copied"
    ("on_step_start", ("enforce",)),
    ("on_progress", (_ev("enforce", "movie6.mkv", "copied"),)),
    ("on_step_end", ("enforce", _step_report_enforce(), 4.0)),
    # verify — status "fixed" + errors + warnings
    ("on_step_start", ("verify",)),
    ("on_progress", (_ev("verify", "movie7.mkv", "fixed"),)),
    ("on_step_end", ("verify", _step_report_verify(), 5.0)),
    # trailers — status "blocked"
    ("on_step_start", ("trailers",)),
    ("on_progress", (_ev("trailers", "movie8.mkv", "blocked"),)),
    ("on_step_end", ("trailers", _step_report_trailers(), 6.0)),
    # dispatch — status "cleaned" + errors + warnings
    ("on_step_start", ("dispatch",)),
    ("on_progress", (_ev("dispatch", "movie9.mkv", "cleaned"),)),
    ("on_step_end", ("dispatch", _step_report_dispatch(), 8.0)),
    # unknown step — exercises the icon dict default branch
    ("on_step_start", ("unknown_step",)),
    ("on_progress", (_ev("unknown_step", "movie10.mkv", "error"),)),
    ("on_step_end", ("unknown_step", _step_report_unknown(), 1.0)),
    # Fatal step error
    ("on_step_error", ("scrape", RuntimeError("boom"))),
    # Pipeline end — OK status, sub-minute duration (seconds-only path)
    ("on_pipeline_end", (_end_report_ok_seconds(),)),
    # Second pipeline frame — exercises the ERRORS status, multi-minute
    # duration (minutes+seconds path), and a step with error_count > 0 in
    # the summary table (red-style branch in ``on_pipeline_end``).
    ("on_pipeline_start", (_start_report(),)),
    ("on_pipeline_end", (_end_report_errors_minutes(),)),
]


# Observer configurations replayed by the recorder. Together they cover:
#   * LIVE banner (dry_run=False) and DRY-RUN banner (dry_run=True).
#   * Explicit run_id (skips the ``isoformat`` fallback in
#     ``on_pipeline_start``) and empty run_id (hits the fallback).
#   * verbose=True (prints ``on_progress`` and per-item details/warnings in
#     ``on_step_end``) and verbose=False (early-returns from
#     ``on_progress`` and skips the verbose block in ``on_step_end``).
CANONICAL_OBSERVER_CONFIGS: list[dict[str, Any]] = [
    {"dry_run": False, "verbose": True, "run_id": "canonical-live"},
    {"dry_run": True, "verbose": False, "run_id": ""},
]
