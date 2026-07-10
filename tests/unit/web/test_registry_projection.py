"""Unit tests for :class:`RegistryHealthProjection` (S6 reg-health §2.1).

Covers every reducer branch, snapshot independence, and the forward-compatible
ignore of unknown event types.  Uses ``time.time()`` epoch floats throughout
per the web-ui epoch convention.
"""

from __future__ import annotations

import time

from personalscraper.web.registry_projection import RegistryHealthProjection

# ── Helpers ────────────────────────────────────────────────────────────────────


def _approx_now(ts: float, tolerance: float = 2.0) -> bool:
    """Return ``True`` if *ts* is within *tolerance* seconds of now.

    Args:
        ts: Epoch timestamp to check.
        tolerance: Maximum allowed deviation in seconds.

    Returns:
        ``True`` when ``abs(now - ts) <= tolerance``.
    """
    return abs(time.time() - ts) <= tolerance


# ── CircuitBreakerOpened ───────────────────────────────────────────────────────


class TestCircuitBreakerOpened:
    """Reducer behaviour for ``CircuitBreakerOpened`` events."""

    def test_opened_sets_state_and_failure_count(self) -> None:
        """CircuitBreakerOpened → circuit_state="open", failure_count_recent set."""
        projection = RegistryHealthProjection()
        projection.apply(
            "CircuitBreakerOpened",
            {"breaker": "tmdb", "failure_count": 5, "last_error_class": "ApiError", "last_error_message": "500 boom"},
        )

        snap = projection.snapshot()
        assert "tmdb" in snap
        assert snap["tmdb"]["circuit_state"] == "open"
        assert snap["tmdb"]["failure_count_recent"] == 5

    def test_opened_sets_last_failure_at(self) -> None:
        """CircuitBreakerOpened sets ``last_failure_at`` to now (epoch float)."""
        projection = RegistryHealthProjection()
        data = {
            "breaker": "tvdb",
            "failure_count": 3,
            "last_error_class": "Timeout",
            "last_error_message": "read timed out",
        }
        projection.apply("CircuitBreakerOpened", data)

        snap = projection.snapshot()
        assert isinstance(snap["tvdb"]["last_failure_at"], float)
        assert _approx_now(snap["tvdb"]["last_failure_at"])

    def test_opened_preserves_existing_latency(self) -> None:
        """A previous ProviderCallCompleted latency survives an Opened transition."""
        projection = RegistryHealthProjection()
        projection.apply("ProviderCallCompleted", {"provider": "tmdb", "latency_ms": 123.4, "ok": True})
        projection.apply(
            "CircuitBreakerOpened",
            {"breaker": "tmdb", "failure_count": 2, "last_error_class": "ApiError", "last_error_message": "boom"},
        )

        snap = projection.snapshot()
        assert snap["tmdb"]["circuit_state"] == "open"
        assert snap["tmdb"]["last_latency_ms"] == 123.4


# ── CircuitBreakerClosed ───────────────────────────────────────────────────────


class TestCircuitBreakerClosed:
    """Reducer behaviour for ``CircuitBreakerClosed`` events."""

    def test_closed_sets_state_and_resets_failures(self) -> None:
        """CircuitBreakerClosed → circuit_state="closed", failure_count_recent=0."""
        projection = RegistryHealthProjection()
        # First open it, then close.
        projection.apply(
            "CircuitBreakerOpened",
            {
                "breaker": "tmdb",
                "failure_count": 3,
                "last_error_class": "ApiError",
                "last_error_message": "boom",
            },
        )
        projection.apply("CircuitBreakerClosed", {"breaker": "tmdb"})

        snap = projection.snapshot()
        assert snap["tmdb"]["circuit_state"] == "closed"
        assert snap["tmdb"]["failure_count_recent"] == 0

    def test_closed_sets_last_success_at(self) -> None:
        """CircuitBreakerClosed sets ``last_success_at`` to an epoch float."""
        projection = RegistryHealthProjection()
        projection.apply("CircuitBreakerClosed", {"breaker": "tmdb"})

        snap = projection.snapshot()
        assert isinstance(snap["tmdb"]["last_success_at"], float)
        assert _approx_now(snap["tmdb"]["last_success_at"])


# ── CircuitBreakerHalfOpened ───────────────────────────────────────────────────


class TestCircuitBreakerHalfOpened:
    """Reducer behaviour for ``CircuitBreakerHalfOpened`` events."""

    def test_half_opened_sets_state_only(self) -> None:
        """CircuitBreakerHalfOpened → circuit_state="half_open", other fields untouched."""
        projection = RegistryHealthProjection()
        projection.apply(
            "CircuitBreakerOpened",
            {
                "breaker": "tmdb",
                "failure_count": 4,
                "last_error_class": "Timeout",
                "last_error_message": "read timed out",
            },
        )
        projection.apply("CircuitBreakerHalfOpened", {"breaker": "tmdb"})

        snap = projection.snapshot()
        assert snap["tmdb"]["circuit_state"] == "half_open"
        # failure_count and timestamps from the prior Opened survive.
        assert snap["tmdb"]["failure_count_recent"] == 4
        assert snap["tmdb"]["last_failure_at"] is not None


# ── ProviderCallCompleted ──────────────────────────────────────────────────────


class TestProviderCallCompleted:
    """Reducer behaviour for ``ProviderCallCompleted`` events."""

    def test_ok_sets_latency_and_last_success_at(self) -> None:
        """ok=True → latency recorded, last_success_at set to now."""
        projection = RegistryHealthProjection()
        projection.apply("ProviderCallCompleted", {"provider": "tmdb", "latency_ms": 42.5, "ok": True})

        snap = projection.snapshot()
        assert snap["tmdb"]["last_latency_ms"] == 42.5
        assert isinstance(snap["tmdb"]["last_success_at"], float)
        assert _approx_now(snap["tmdb"]["last_success_at"])
        assert snap["tmdb"]["last_failure_at"] is None

    def test_not_ok_sets_latency_and_last_failure_at(self) -> None:
        """ok=False → latency recorded, last_failure_at set to now."""
        projection = RegistryHealthProjection()
        projection.apply("ProviderCallCompleted", {"provider": "tmdb", "latency_ms": 999.9, "ok": False})

        snap = projection.snapshot()
        assert snap["tmdb"]["last_latency_ms"] == 999.9
        assert isinstance(snap["tmdb"]["last_failure_at"], float)
        assert _approx_now(snap["tmdb"]["last_failure_at"])
        assert snap["tmdb"]["last_success_at"] is None

    def test_new_provider_starts_closed(self) -> None:
        """A ProviderCallCompleted for an unseen provider initialises it as closed."""
        projection = RegistryHealthProjection()
        projection.apply("ProviderCallCompleted", {"provider": "newapi", "latency_ms": 10.0, "ok": True})

        snap = projection.snapshot()
        assert snap["newapi"]["circuit_state"] == "closed"
        assert snap["newapi"]["failure_count_recent"] == 0
        assert snap["newapi"]["last_latency_ms"] == 10.0

    def test_latency_overwrites_previous(self) -> None:
        """A second ProviderCallCompleted overwrites the previous latency."""
        projection = RegistryHealthProjection()
        projection.apply("ProviderCallCompleted", {"provider": "tmdb", "latency_ms": 100.0, "ok": True})
        projection.apply("ProviderCallCompleted", {"provider": "tmdb", "latency_ms": 200.0, "ok": True})

        assert projection.snapshot()["tmdb"]["last_latency_ms"] == 200.0


# ── Unknown events ─────────────────────────────────────────────────────────────


class TestUnknownEventIgnored:
    """Forward-compatibility: unknown event types are silently skipped."""

    def test_unknown_event_type_noop(self) -> None:
        """An event type the projection doesn't know about leaves state unchanged."""
        projection = RegistryHealthProjection()
        projection.apply("SomeFutureEvent", {"anything": "value"})

        assert projection.snapshot() == {}

    def test_unknown_event_after_known_does_not_clobber(self) -> None:
        """Known state survives an unknown event arriving afterwards."""
        projection = RegistryHealthProjection()
        projection.apply(
            "CircuitBreakerOpened",
            {
                "breaker": "tmdb",
                "failure_count": 1,
                "last_error_class": "ApiError",
                "last_error_message": "boom",
            },
        )
        projection.apply("SomeFutureEvent", {"breaker": "blah"})

        snap = projection.snapshot()
        assert snap["tmdb"]["circuit_state"] == "open"
        assert "blah" not in snap


# ── Snapshot ───────────────────────────────────────────────────────────────────


class TestSnapshot:
    """``snapshot()`` returns an independent deep copy."""

    def test_snapshot_is_independent(self) -> None:
        """Mutating the snapshot does not change the projection."""
        projection = RegistryHealthProjection()
        projection.apply(
            "CircuitBreakerOpened",
            {
                "breaker": "tmdb",
                "failure_count": 2,
                "last_error_class": "ApiError",
                "last_error_message": "boom",
            },
        )

        snap1 = projection.snapshot()
        snap1["tmdb"]["circuit_state"] = "mutated"
        snap1["fake"] = {"circuit_state": "injected"}

        snap2 = projection.snapshot()
        assert snap2["tmdb"]["circuit_state"] == "open"
        assert "fake" not in snap2

    def test_multiple_providers_independent(self) -> None:
        """Each provider entry in the snapshot is an independent copy."""
        projection = RegistryHealthProjection()
        projection.apply("ProviderCallCompleted", {"provider": "tmdb", "latency_ms": 1.0, "ok": True})
        projection.apply("ProviderCallCompleted", {"provider": "tvdb", "latency_ms": 2.0, "ok": True})

        snap = projection.snapshot()
        snap["tmdb"]["circuit_state"] = "mutated"
        del snap["tvdb"]

        snap2 = projection.snapshot()
        assert snap2["tmdb"]["circuit_state"] == "closed"
        assert "tvdb" in snap2

    def test_empty_projection_returns_empty_dict(self) -> None:
        """A fresh projection's snapshot is an empty dict."""
        assert RegistryHealthProjection().snapshot() == {}


# ── Timestamps are epoch floats ────────────────────────────────────────────────


class TestTimestampsAreEpochFloats:
    """Timestamps use ``time.time()`` epoch floats (web-ui convention)."""

    def test_timestamps_are_float_not_none(self) -> None:
        """Every set timestamp field is a float (not None when the event sets it)."""
        projection = RegistryHealthProjection()
        projection.apply(
            "CircuitBreakerOpened",
            {"breaker": "tmdb", "failure_count": 1, "last_error_class": "E", "last_error_message": "m"},
        )
        projection.apply("ProviderCallCompleted", {"provider": "tmdb", "latency_ms": 5.0, "ok": True})
        projection.apply("CircuitBreakerClosed", {"breaker": "tmdb"})

        snap = projection.snapshot()
        assert isinstance(snap["tmdb"]["last_failure_at"], float)
        assert isinstance(snap["tmdb"]["last_success_at"], float)
        assert isinstance(snap["tmdb"]["last_latency_ms"], float)

    def test_timestamps_are_near_now(self) -> None:
        """Timestamps set by apply() are close to the current wall-clock time."""
        projection = RegistryHealthProjection()
        t0 = time.time()
        projection.apply(
            "CircuitBreakerOpened",
            {"breaker": "x", "failure_count": 1, "last_error_class": "E", "last_error_message": "m"},
        )

        ts = projection.snapshot()["x"]["last_failure_at"]
        assert isinstance(ts, float)
        # Within 2 seconds of the pre-call time (generous to absorb CI load).
        assert abs(ts - t0) <= 2.0


# ── Empty / missing data keys ──────────────────────────────────────────────────


class TestGracefulMissingKeys:
    """The reducer handles missing or empty data keys gracefully."""

    def test_opened_missing_breaker_uses_empty_string(self) -> None:
        """A CircuitBreakerOpened with no ``breaker`` key defaults to ``""``."""
        projection = RegistryHealthProjection()
        projection.apply(
            "CircuitBreakerOpened",
            {"failure_count": 1, "last_error_class": "E", "last_error_message": "m"},
        )

        snap = projection.snapshot()
        assert "" in snap
        assert snap[""]["circuit_state"] == "open"

    def test_call_completed_missing_ok_defaults_falsy(self) -> None:
        """A ProviderCallCompleted with no ``ok`` key defaults to a failure timestamp."""
        projection = RegistryHealthProjection()
        projection.apply("ProviderCallCompleted", {"provider": "x", "latency_ms": 5.0})

        snap = projection.snapshot()
        assert snap["x"]["last_failure_at"] is not None
        assert snap["x"]["last_success_at"] is None
