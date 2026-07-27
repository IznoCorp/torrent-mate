"""Tests for :func:`personalscraper.pipeline_protocol.record`.

Covers emission payload shape, one-event-per-call, counter effects per
status group (parametrized), detail/warning appends, and the contract
that ``started`` increments nothing.
"""

from __future__ import annotations

import pytest

from personalscraper.core.event_bus import Event, EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline_events import ItemProgressed, StepItemStatus
from personalscraper.pipeline_protocol import record

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SpyBus:
    """Fake :class:`EventBus` that captures every emitted event in a list."""

    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        """Record *event* in ``self.emitted``."""
        self.emitted.append(event)


def _capture_item_progressed(bus: EventBus) -> list[ItemProgressed]:
    """Subscribe to *bus* and return a list that collects every ItemProgressed.

    A live subscriber is installed on *bus*; every ``ItemProgressed`` event
    emitted after this call (and before the bus is torn down) is appended to
    the returned list.

    Args:
        bus: A real (production) ``EventBus`` instance.

    Returns:
        Mutable list populated by the subscriber callback.
    """
    captured: list[ItemProgressed] = []
    bus.subscribe(ItemProgressed, lambda e: captured.append(e))
    return captured


# ---------------------------------------------------------------------------
# Emission payload shape
# ---------------------------------------------------------------------------


class TestEmissionPayloadShape:
    """The emitted ``ItemProgressed`` carries exactly the supplied fields."""

    def test_step_item_status_preserved(self) -> None:
        """``step``, ``item``, and ``status`` match the call arguments."""
        spy = _SpyBus()
        report = StepReport(name="sort")

        record(report, spy, step="sort", item="Avatar.mp4", status=StepItemStatus.MOVED)

        assert len(spy.emitted) == 1
        event = spy.emitted[0]
        assert isinstance(event, ItemProgressed)
        assert event.step == "sort"
        assert event.item == "Avatar.mp4"
        assert event.status == "moved"

    def test_status_accepts_raw_string(self) -> None:
        """A plain ``str`` status normalises to the same emitted value."""
        spy = _SpyBus()
        report = StepReport(name="dispatch")

        record(report, spy, step="dispatch", item="Foo.S01", status="replaced")

        assert spy.emitted[0].status == "replaced"

    def test_details_are_empty_by_default(self) -> None:
        """Emitted ``ItemProgressed`` has an empty ``details`` dict by default.

        When no `details` kwarg is passed to ``record``, the event carries ``{}``.
        """
        spy = _SpyBus()
        report = StepReport(name="verify")

        record(report, spy, step="verify", item="Bar", status=StepItemStatus.OK)

        assert spy.emitted[0].details == {}


# ---------------------------------------------------------------------------
# One-event-per-call
# ---------------------------------------------------------------------------


class TestOneEventPerCall:
    """Every ``record()`` call emits exactly one ``ItemProgressed``."""

    def test_single_event_on_single_call(self) -> None:
        """One call emits one event."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="a.mkv", status=StepItemStatus.MOVED)
        assert len(spy.emitted) == 1

    def test_single_event_per_call_with_multiple_calls(self) -> None:
        """Three calls emit three events."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="a.mkv", status="started")
        record(report, spy, step="sort", item="a.mkv", status=StepItemStatus.MOVED)
        record(report, spy, step="sort", item="b.mkv", status=StepItemStatus.SKIPPED)
        assert len(spy.emitted) == 3

    def test_real_bus_emits_exactly_one(self) -> None:
        """A real ``EventBus`` delivers exactly one ``ItemProgressed`` per call."""
        bus = EventBus()
        captured = _capture_item_progressed(bus)
        report = StepReport(name="enforce")

        record(report, bus, step="enforce", item="dir", status=StepItemStatus.FIXED)

        assert len(captured) == 1
        assert captured[0].status == "fixed"


# ---------------------------------------------------------------------------
# Counter effects — parametrized over the mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected_counter",
    [
        # success_count group
        (StepItemStatus.COPIED, "success_count"),
        (StepItemStatus.MATCHED, "success_count"),
        (StepItemStatus.MOVED, "success_count"),
        (StepItemStatus.FIXED, "success_count"),
        (StepItemStatus.OK, "success_count"),
        (StepItemStatus.CLEANED, "success_count"),
        (StepItemStatus.REPLACED, "success_count"),
        (StepItemStatus.MERGED, "success_count"),
        (StepItemStatus.REMOVED, "success_count"),
        # skip_count group
        (StepItemStatus.SKIPPED, "skip_count"),
        (StepItemStatus.SKIPPED_LOW_CONFIDENCE, "skip_count"),
        (StepItemStatus.BLOCKED, "skip_count"),
        (StepItemStatus.QUEUED_FOR_DECISION, "skip_count"),
        # error_count group
        (StepItemStatus.FAILED, "error_count"),
        (StepItemStatus.ERROR, "error_count"),
    ],
)
class TestCounterEffects:
    """Every terminal status increments exactly one counter.

    The two counters not targeted by the status remain at zero.
    """

    def test_counter_incremented(self, status: StepItemStatus, expected_counter: str) -> None:
        """The destination counter is incremented by 1."""
        spy = _SpyBus()
        report = StepReport(name="test")
        record(report, spy, step="test", item="x", status=status)
        assert getattr(report, expected_counter) == 1

    def test_other_counters_untouched(self, status: StepItemStatus, expected_counter: str) -> None:
        """Counters not targeted by *status* stay at zero."""
        spy = _SpyBus()
        report = StepReport(name="test")
        record(report, spy, step="test", item="x", status=status)
        all_counters = {"success_count", "skip_count", "error_count"}
        for name in all_counters - {expected_counter}:
            assert getattr(report, name) == 0, f"{name} should be 0"


class TestRawStringCounterEquivalence:
    """Raw ``str`` statuses produce the same counter effects as enum values."""

    @pytest.mark.parametrize(
        "status_str,expected_counter",
        [
            ("copied", "success_count"),
            ("skipped", "skip_count"),
            ("error", "error_count"),
        ],
    )
    def test_raw_string_maps_same_as_enum(self, status_str: str, expected_counter: str) -> None:
        """Raw string status maps to the same counter as the equivalent enum value."""
        spy = _SpyBus()
        report = StepReport(name="test")
        record(report, spy, step="test", item="x", status=status_str)
        assert getattr(report, expected_counter) == 1


# ---------------------------------------------------------------------------
# detail / warning appends
# ---------------------------------------------------------------------------


class TestDetailWarningAppends:
    """``detail`` and ``warning`` are appended to the report lists when given."""

    def test_detail_appended(self) -> None:
        """Passing ``detail=...`` appends to ``report.details``."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(
            report,
            spy,
            step="sort",
            item="x.mkv",
            status=StepItemStatus.MOVED,
            detail="x.mkv -> 001-MOVIES",
        )
        assert report.details == ["x.mkv -> 001-MOVIES"]

    def test_warning_appended(self) -> None:
        """Passing ``warning=...`` appends to ``report.warnings``."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(
            report,
            spy,
            step="sort",
            item="x.mkv",
            status=StepItemStatus.SKIPPED,
            warning="x.mkv: duplicate",
        )
        assert report.warnings == ["x.mkv: duplicate"]

    def test_detail_and_warning_both_appended(self) -> None:
        """Both ``detail`` and ``warning`` can be set in the same call."""
        spy = _SpyBus()
        report = StepReport(name="dispatch")
        record(
            report,
            spy,
            step="dispatch",
            item="BadFile",
            status=StepItemStatus.ERROR,
            detail="action=error BadFile: disk full",
            warning="BadFile: disk full",
        )
        assert report.details == ["action=error BadFile: disk full"]
        assert report.warnings == ["BadFile: disk full"]

    def test_none_detail_not_appended(self) -> None:
        """Passing ``detail=None`` must not mutate ``report.details``."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="x", status=StepItemStatus.MOVED)
        assert report.details == []

    def test_none_warning_not_appended(self) -> None:
        """Passing ``warning=None`` must not mutate ``report.warnings``."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="x", status=StepItemStatus.MOVED)
        assert report.warnings == []

    def test_multiple_details_accumulate(self) -> None:
        """Multiple ``record()`` calls append details in order."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="a.mkv", status=StepItemStatus.MOVED, detail="a.mkv moved")
        record(report, spy, step="sort", item="b.mkv", status=StepItemStatus.MOVED, detail="b.mkv moved")
        assert report.details == ["a.mkv moved", "b.mkv moved"]

    def test_multiple_warnings_accumulate(self) -> None:
        """Multiple ``record()`` calls append warnings in order."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="a", status=StepItemStatus.SKIPPED, warning="a: dup")
        record(report, spy, step="sort", item="b", status=StepItemStatus.SKIPPED, warning="b: dup")
        assert report.warnings == ["a: dup", "b: dup"]


# ---------------------------------------------------------------------------
# started — no counter increment
# ---------------------------------------------------------------------------


class TestStartedNeutral:
    """``started`` is a lifecycle marker that MUST NOT increment any counter."""

    def test_started_increments_nothing(self) -> None:
        """``started`` is neutral — all counters remain 0."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="x", status=StepItemStatus.STARTED)
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0

    def test_started_string_increments_nothing(self) -> None:
        """Raw string status ``started`` is also neutral."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="x", status="started")
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0

    def test_started_does_not_block_detail(self) -> None:
        """``started`` does not block ``detail`` from being appended.

        Callers may want to log the lifecycle event even though no counter changes.
        """
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="x", status="started", detail="begin x")
        assert report.details == ["begin x"]
        assert report.success_count == 0

    def test_unrecognised_status_increments_nothing(self) -> None:
        """An unrecognised status string behaves like ``started`` — neutral."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="x", status="some_future_status")
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0


# ---------------------------------------------------------------------------
# event_details passthrough (structured ItemProgressed.details payload)
# ---------------------------------------------------------------------------


class TestEventDetailsPassthrough:
    """``event_details`` populates the emitted event's ``details`` field only."""

    def test_event_details_attached_to_event(self) -> None:
        """The emitted ``ItemProgressed`` carries the supplied ``event_details``."""
        spy = _SpyBus()
        report = StepReport(name="dispatch")
        record(
            report,
            spy,
            step="dispatch",
            item="Dune (2021)",
            status=StepItemStatus.MOVED,
            event_details={"disk": "disk2", "dest": "/Volumes/disk2/Dune"},
        )
        assert spy.emitted[0].details == {"disk": "disk2", "dest": "/Volumes/disk2/Dune"}

    def test_event_details_copied_not_aliased(self) -> None:
        """The emitted event gets a copy — mutating the source dict later is safe."""
        spy = _SpyBus()
        report = StepReport(name="scrape")
        payload = {"provider": "tmdb", "confidence": 0.95}
        record(report, spy, step="scrape", item="Film", status=StepItemStatus.MATCHED, event_details=payload)
        payload["provider"] = "mutated"
        assert spy.emitted[0].details == {"provider": "tmdb", "confidence": 0.95}

    def test_event_details_does_not_touch_report_lists(self) -> None:
        """``event_details`` never leaks into ``report.details`` / ``report.warnings``."""
        spy = _SpyBus()
        report = StepReport(name="verify")
        record(
            report,
            spy,
            step="verify",
            item="Show",
            status=StepItemStatus.BLOCKED,
            event_details={"errors": ["missing nfo"]},
        )
        assert report.details == []
        assert report.warnings == []
        assert report.skip_count == 1

    def test_none_event_details_leaves_empty_dict(self) -> None:
        """Omitting ``event_details`` leaves the event's ``details`` at ``{}``."""
        spy = _SpyBus()
        report = StepReport(name="sort")
        record(report, spy, step="sort", item="x", status=StepItemStatus.MOVED)
        assert spy.emitted[0].details == {}
