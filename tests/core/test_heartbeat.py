"""Tests for the structured daemon-heartbeat serialization (#1, DESIGN §5).

Covers the JSON round-trip, backward-compatible parsing of the legacy plain-epoch
marker, the healthy-default fields for a partial/legacy record, and the malformed-input
ValueError so the doctor can degrade to a "cannot parse" note.
"""

from __future__ import annotations

import pytest

from kanbanmate.core.heartbeat import (
    DEFAULT_FAILURE_THRESHOLD,
    Heartbeat,
    parse_heartbeat,
    render_heartbeat,
)


def test_render_parse_round_trip() -> None:
    """A rendered heartbeat parses back to an equal record."""
    hb = Heartbeat(ts=1234.5, last_tick_ok=False, consecutive_failures=4)
    parsed = parse_heartbeat(render_heartbeat(hb))
    assert parsed == hb


def test_render_is_single_line_json() -> None:
    """The marker is one compact, key-sorted JSON line (greppable, stable)."""
    text = render_heartbeat(Heartbeat(ts=1.0))
    assert "\n" not in text
    assert text.startswith("{") and text.endswith("}")
    # Key order is stable (sort_keys) so the body hash is deterministic.
    assert text.index("consecutive_failures") < text.index("last_tick_ok") < text.index("ts")


def test_parse_legacy_plain_epoch_is_healthy() -> None:
    """A legacy plain-epoch marker (old daemon mid-upgrade) parses as fresh + healthy (#1)."""
    parsed = parse_heartbeat("1717000000.123")
    assert parsed.ts == pytest.approx(1717000000.123)
    assert parsed.last_tick_ok is True
    assert parsed.consecutive_failures == 0


def test_parse_partial_json_uses_healthy_defaults() -> None:
    """A JSON record missing the health fields defaults to healthy (forward/back compat)."""
    parsed = parse_heartbeat('{"ts": 99.0}')
    assert parsed.ts == pytest.approx(99.0)
    assert parsed.last_tick_ok is True
    assert parsed.consecutive_failures == 0


def test_parse_failing_record() -> None:
    """A failing record round-trips its failure count."""
    parsed = parse_heartbeat('{"ts": 5.0, "last_tick_ok": false, "consecutive_failures": 7}')
    assert parsed.last_tick_ok is False
    assert parsed.consecutive_failures == 7


@pytest.mark.parametrize("bad", ["", "   ", "not-a-number", "{not json"])
def test_parse_garbage_raises_value_error(bad: str) -> None:
    """Malformed markers raise ``ValueError`` so the caller degrades to a note (not silent OK)."""
    with pytest.raises(ValueError):
        parse_heartbeat(bad)


def test_failure_threshold_is_three() -> None:
    """The doctor-FAIL threshold is the documented 3 (a transient blip never flips doctor red)."""
    assert DEFAULT_FAILURE_THRESHOLD == 3
