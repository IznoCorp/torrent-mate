"""Test fixtures for the EventBus — Sub-phase 1.6 helper, extended by 1.8.

Sub-phase 1.6 lands ``assert_event_round_trip`` (field-by-field equality
with a 1µs timestamp tolerance) so the envelope tests can verify reconstruction
without hitting the strict dataclass ``__eq__`` (which would compare timestamps
exactly and fail under ISO-8601 microsecond rounding).

Sub-phase 1.8 will add ``CollectingSubscriber`` (subscribe-on-construction
generic helper) and ``EVENT_SAMPLE_FACTORIES`` registry mechanism on top of
this module.
"""

from __future__ import annotations

from dataclasses import fields

from personalscraper.core.event_bus import Event

# 1 microsecond — the smallest unit ISO 8601 strings reliably round-trip.
# Some platforms (notably macOS HFS+/APFS) deliver microsecond-precision
# timestamps via ``datetime.now`` but ISO-8601 ``isoformat`` / ``fromisoformat``
# preserve them exactly. The tolerance is therefore conservative — set higher
# than 0 only because Python's ``datetime`` arithmetic on rounded floats can
# leave a ≤ 1 µs residual depending on the timezone implementation.
_TIMESTAMP_TOLERANCE_SECONDS = 1e-6


def assert_event_round_trip(original: Event, reconstructed: Event) -> None:
    """Compare two events field-by-field, tolerating µs ``timestamp`` drift.

    Required because ``dataclass.__eq__`` compares all fields strictly,
    including ``timestamp``; a µs rounding residual through ISO-8601 makes
    raw ``==`` flaky. This helper:

    1. Asserts both events are of the same concrete type.
    2. For every field except ``timestamp``, asserts strict equality.
    3. For ``timestamp``, asserts the absolute drift is ≤ 1 µs.

    Args:
        original: The event constructed before serialization.
        reconstructed: The event produced by ``event_from_envelope`` after a
            JSON round-trip (or any other equivalent decoding).

    Raises:
        AssertionError: if any field deviates beyond the contract above.
    """
    assert type(original) is type(reconstructed), (
        f"type mismatch: {type(original).__name__} vs {type(reconstructed).__name__}"
    )
    for f in fields(original):
        ov = getattr(original, f.name)
        rv = getattr(reconstructed, f.name)
        if f.name == "timestamp":
            drift = abs((rv - ov).total_seconds())
            assert drift <= _TIMESTAMP_TOLERANCE_SECONDS, (
                f"timestamp drift {drift}s exceeds tolerance {_TIMESTAMP_TOLERANCE_SECONDS}s"
            )
        else:
            assert ov == rv, f"field {f.name!r}: {ov!r} != {rv!r}"
