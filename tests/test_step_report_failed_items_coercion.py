"""Regression test — Sub-phase 3.1 pre-investigation.

``StepReport.failed_items`` was a ``list[tuple[str, str, str]]`` field. The
positional-tuple shape is not handled by ``_decode_field_value`` (which only
supports variadic ``tuple[T, ...]``), so the envelope round-trip in Sub-phase
3.1 would fail any time a trailer step produced a non-empty list. The field
is now ``list[FailedItem]`` with a ``__post_init__`` coercion accepting the
legacy 3-tuple shape from the orchestrator boundary.

This test locks the coercion so the round-trip stays green and the trailers
orchestrator's existing return shape continues to flow through unchanged.
"""

from __future__ import annotations

import dataclasses
import json
import typing

from personalscraper.core.event_bus import _decode_field_value, event_to_dict
from personalscraper.models import FailedItem, StepReport


def test_step_report_coerces_legacy_3_tuple_to_failed_item() -> None:
    """3-tuple entries are coerced to :class:`FailedItem` at construction."""
    report = StepReport(
        name="trailers",
        failed_items=[("movie:tmdb:1", "bot_detected", "sign in")],  # type: ignore[list-item]
    )
    assert report.failed_items == [
        FailedItem(item_id="movie:tmdb:1", reason="bot_detected", detail="sign in"),
    ]


def test_step_report_accepts_failed_item_instances_unchanged() -> None:
    """Constructing with ``FailedItem`` instances is a no-op (idempotent)."""
    items = [FailedItem(item_id="a", reason="b", detail="c")]
    report = StepReport(name="trailers", failed_items=list(items))
    assert report.failed_items == items


def test_failed_item_is_json_safe_via_event_to_dict() -> None:
    """``event_to_dict`` encodes :class:`FailedItem` as a JSON-safe dict."""
    fi = FailedItem(item_id="x", reason="y", detail="z")
    encoded = event_to_dict(fi)
    assert encoded == {"item_id": "x", "reason": "y", "detail": "z"}
    # Round-trips through json without exception.
    json.dumps(encoded)


def test_step_report_failed_items_envelope_roundtrip() -> None:
    """``failed_items`` survives ``event_to_dict`` → JSON → decode cleanly.

    Exercises the decoder path that previously crashed with
    ``ValueError: too many values to unpack`` on ``tuple[str, str, str]``.
    """
    report = StepReport(
        name="trailers",
        failed_items=[
            FailedItem(item_id="a", reason="bot_detected", detail="sign in"),
            FailedItem(item_id="b", reason="timeout", detail=""),
        ],
    )
    encoded = event_to_dict(report)
    raw = json.loads(json.dumps(encoded))

    hints = typing.get_type_hints(StepReport)
    decoded = _decode_field_value(raw["failed_items"], hints["failed_items"])

    assert decoded == report.failed_items
    assert all(isinstance(entry, FailedItem) for entry in decoded)


def test_step_report_is_a_dataclass_with_post_init() -> None:
    """Sanity check: coercion happens via ``__post_init__`` on a dataclass."""
    assert dataclasses.is_dataclass(StepReport)
    assert hasattr(StepReport, "__post_init__")
