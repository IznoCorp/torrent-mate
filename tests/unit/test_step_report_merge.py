"""Tests for StepReport.merge() and StepItemStatus coverage."""

from __future__ import annotations

import pytest

from personalscraper.models import FailedItem, StepReport
from personalscraper.pipeline_events import StepItemStatus

# ---------------------------------------------------------------------------
# StepItemStatus — completeness check
# ---------------------------------------------------------------------------


def test_step_item_status_covers_all_observed_literals() -> None:
    """StepItemStatus must cover every ItemProgressed status literal in use.

    The expected set is hardcoded from the emission-site inventory (verified
    2026-07-16).  If a new emission site introduces a status NOT listed here,
    the developer MUST add it to StepItemStatus and to this test.

    Emission sites (each listed with its module and line number at inventory time):

    * ``"started"``
        - ingest/ingest.py:346
        - sorter/run.py:106
        - process/run.py:160 (clean)
        - scraper/run.py:231
        - process/run.py:244 (cleanup)
        - enforce/run.py:67,104,130
        - verify/run.py:134
        - trailers/step.py:123
        - dispatch/run.py:165
    * ``"skipped"``
        - ingest/ingest.py:377,408,435,471,499,515
        - trailers/step.py:70
        - scraper/run.py:283
        - dispatch/run.py:183
        - process/run.py:201 (clean cat_status)
        - process/run.py:252 (cleanup terminal_status)
        - sorter/run.py:137
        - enforce/run.py:99,118,142
    * ``"failed"``
        - ingest/ingest.py:484,576,597
        - trailers/step.py:182,204,225
        - scraper/run.py:292
    * ``"copied"`` — ingest/ingest.py:542
    * ``"queued_for_decision"`` — scraper/run.py:243
    * ``"matched"`` — scraper/run.py:256
    * ``"skipped_low_confidence"`` — scraper/run.py:271
    * ``"error"``
        - dispatch/run.py:193
        - sorter/run.py:148
        - process/run.py:196 (clean cat_status)
    * ``"moved"``
        - sorter/run.py:114,125
        - dispatch/run.py:171 (r.action)
    * ``"fixed"`` — enforce/run.py:78,111,136
    * ``"ok"`` — verify/run.py:140
    * ``"blocked"`` — verify/run.py:149
    * ``"cleaned"`` — process/run.py:198 (clean cat_status)
    * ``"replaced"`` — dispatch/run.py:171 (r.action)
    * ``"merged"`` — dispatch/run.py:171 (r.action)
    * ``"removed"`` — process/run.py:250 (cleanup terminal_status)
    """
    expected = {
        "started",
        "skipped",
        "failed",
        "copied",
        "queued_for_decision",
        "matched",
        "skipped_low_confidence",
        "error",
        "moved",
        "fixed",
        "ok",
        "blocked",
        "cleaned",
        "replaced",
        "merged",
        "removed",
    }

    actual = {member.value for member in StepItemStatus}
    missing = expected - actual
    extra = actual - expected

    assert not missing, f"StepItemStatus is missing values: {missing}"
    assert not extra, f"StepItemStatus has unexpected extra values: {extra}"


# ---------------------------------------------------------------------------
# StepReport.merge() — identity
# ---------------------------------------------------------------------------


def test_merge_identity_with_empty_report() -> None:
    """Merging with an empty (all-default) StepReport returns a copy of self."""
    report = StepReport(
        name="ingest",
        success_count=5,
        skip_count=2,
        error_count=1,
        warnings=["w1"],
        details=["d1"],
        status="partial",
        counts={"downloaded": 3, "bot_detected": 1},
        failed_items=[FailedItem(item_id="x", reason="r")],
        renames={"new": "old"},
        unmatched_paths=["p1"],
        details_payload={"k": "v"},
    )
    empty = StepReport(name="ingest")

    merged = report.merge(empty)

    # Counters unchanged (added 0).
    assert merged.success_count == 5
    assert merged.skip_count == 2
    assert merged.error_count == 1

    # Lists unchanged (empty appended).
    assert merged.warnings == ["w1"]
    assert merged.details == ["d1"]
    assert merged.failed_items == [FailedItem(item_id="x", reason="r")]
    assert merged.unmatched_paths == ["p1"]

    # Dicts unchanged (empty merged).
    assert merged.status == "partial"
    assert merged.counts == {"downloaded": 3, "bot_detected": 1}
    assert merged.renames == {"new": "old"}
    assert merged.details_payload == {"k": "v"}


def test_merge_empty_into_report_is_identity() -> None:
    """Empty.merge(report) returns a copy of the non-empty report."""
    empty = StepReport(name="scrape")
    report = StepReport(
        name="scrape",
        success_count=3,
        skip_count=1,
        error_count=0,
        warnings=["w"],
        details=["d"],
        status="success",
        counts={"a": 1},
        failed_items=[FailedItem(item_id="y", reason="s")],
        renames={"x": "y"},
        unmatched_paths=["u"],
        details_payload={"z": "0"},
    )

    merged = empty.merge(report)

    # All values come from `report` because `empty` is all-default.
    assert merged.success_count == 3
    assert merged.skip_count == 1
    assert merged.error_count == 0
    assert merged.warnings == ["w"]
    assert merged.details == ["d"]
    assert merged.status == "success"
    assert merged.counts == {"a": 1}
    assert merged.failed_items == [FailedItem(item_id="y", reason="s")]
    assert merged.renames == {"x": "y"}
    assert merged.unmatched_paths == ["u"]
    assert merged.details_payload == {"z": "0"}


# ---------------------------------------------------------------------------
# Counter sums
# ---------------------------------------------------------------------------


def test_merge_counter_sums() -> None:
    """Integer counters (success, skip, error) are summed."""
    a = StepReport(name="sort", success_count=3, skip_count=1, error_count=2)
    b = StepReport(name="sort", success_count=4, skip_count=0, error_count=1)

    merged = a.merge(b)

    assert merged.success_count == 7
    assert merged.skip_count == 1
    assert merged.error_count == 3


def test_merge_counts_dict_sums_shared_keys() -> None:
    """Counts dict values are summed for shared keys, copied for unique keys."""
    a = StepReport(name="trailers", counts={"downloaded": 3, "bot_detected": 1})
    b = StepReport(name="trailers", counts={"downloaded": 2, "already_present": 4})

    merged = a.merge(b)

    assert merged.counts == {"downloaded": 5, "bot_detected": 1, "already_present": 4}


# ---------------------------------------------------------------------------
# List concat order
# ---------------------------------------------------------------------------


def test_merge_list_concat_order() -> None:
    """List fields preserve self-first-then-other concatenation order."""
    a = StepReport(
        name="enforce",
        details=["d1", "d2"],
        warnings=["w1"],
        failed_items=[FailedItem(item_id="a", reason="r1")],
        unmatched_paths=["p1"],
    )
    b = StepReport(
        name="enforce",
        details=["d3"],
        warnings=["w2", "w3"],
        failed_items=[FailedItem(item_id="b", reason="r2")],
        unmatched_paths=["p2", "p3"],
    )

    merged = a.merge(b)

    assert merged.details == ["d1", "d2", "d3"]
    assert merged.warnings == ["w1", "w2", "w3"]
    assert merged.failed_items == [
        FailedItem(item_id="a", reason="r1"),
        FailedItem(item_id="b", reason="r2"),
    ]
    assert merged.unmatched_paths == ["p1", "p2", "p3"]


# ---------------------------------------------------------------------------
# Dict combine — details_payload
# ---------------------------------------------------------------------------


def test_merge_details_payload_other_wins_on_conflict() -> None:
    """On key collision, other.details_payload wins."""
    a = StepReport(name="verify", details_payload={"k1": "v1", "k2": "old"})
    b = StepReport(name="verify", details_payload={"k2": "new", "k3": "v3"})

    merged = a.merge(b)

    assert merged.details_payload == {"k1": "v1", "k2": "new", "k3": "v3"}


def test_merge_details_payload_none_safe() -> None:
    """Merging when one or both details_payload is None works."""
    a = StepReport(name="clean", details_payload={"a": 1})
    b = StepReport(name="clean")  # details_payload is None

    merged_ab = a.merge(b)
    assert merged_ab.details_payload == {"a": 1}

    merged_ba = b.merge(a)
    assert merged_ba.details_payload == {"a": 1}

    c = StepReport(name="clean")
    merged_cc = c.merge(StepReport(name="clean"))
    assert merged_cc.details_payload is None


def test_merge_renames_other_wins_on_conflict() -> None:
    """Renames dict: other wins on key conflict (same semantics as details_payload)."""
    a = StepReport(name="cleanup", renames={"a": "old_a", "b": "old_b"})
    b = StepReport(name="cleanup", renames={"b": "new_b", "c": "new_c"})

    merged = a.merge(b)

    assert merged.renames == {"a": "old_a", "b": "new_b", "c": "new_c"}


# ---------------------------------------------------------------------------
# Status merge
# ---------------------------------------------------------------------------


def test_merge_status_uses_other_when_set() -> None:
    """When other.status is set, it replaces self.status."""
    a = StepReport(name="dispatch", status="partial")
    b = StepReport(name="dispatch", status="success")

    assert a.merge(b).status == "success"


def test_merge_status_falls_back_to_self() -> None:
    """When other.status is None, self.status is kept."""
    a = StepReport(name="dispatch", status="partial")
    b = StepReport(name="dispatch")  # status is None

    assert a.merge(b).status == "partial"


def test_merge_status_both_none() -> None:
    """When both statuses are None, merged status is also None."""
    a = StepReport(name="ingest")
    b = StepReport(name="ingest")

    assert a.merge(b).status is None


# ---------------------------------------------------------------------------
# Name mismatch
# ---------------------------------------------------------------------------


def test_merge_name_mismatch_raises_valueerror() -> None:
    """Merging reports with different names raises ValueError."""
    a = StepReport(name="ingest")
    b = StepReport(name="sort")

    with pytest.raises(ValueError, match="Cannot merge StepReports with different names"):
        a.merge(b)


def test_merge_name_mismatch_error_message_contains_both_names() -> None:
    """The ValueError message includes both mismatched names for debugging."""
    a = StepReport(name="scrape")
    b = StepReport(name="clean")

    with pytest.raises(ValueError) as exc_info:
        a.merge(b)
    assert "'scrape'" in str(exc_info.value)
    assert "'clean'" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Associativity (three-report merge)
# ---------------------------------------------------------------------------


def test_merge_associativity_on_counters() -> None:
    """(a.merge(b)).merge(c) produces the same totals as a.merge(b.merge(c))."""
    a = StepReport(name="t", success_count=1, skip_count=0, error_count=2)
    b = StepReport(name="t", success_count=3, skip_count=1, error_count=0)
    c = StepReport(name="t", success_count=0, skip_count=2, error_count=1)

    left = a.merge(b).merge(c)
    right = a.merge(b.merge(c))

    assert left.success_count == right.success_count == 4
    assert left.skip_count == right.skip_count == 3
    assert left.error_count == right.error_count == 3
