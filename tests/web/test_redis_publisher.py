"""Unit tests for :class:`RedisEventPublisher` (tm-shell feature).

Exercises the producer side of the event relay with ``fakeredis``:

- ``XADD`` lands the ``{envelope, type}`` fields on the stream;
- ``MAXLEN`` trimming keeps the stream bounded;
- fail-soft: a Redis error never raises and warns ``redis_publish_failed`` once;
- queue-full: a saturated in-memory queue drops the event and warns once;
- ``close()`` stops the daemon worker thread and is idempotent;
- an event survives ``event_from_envelope(event_to_envelope(e))`` intact.

Injection seam: the publisher creates its sync Redis lazily via ``_get_redis``,
which returns ``self._redis`` when already set.  Tests assign a ``fakeredis``
(or a broken mock) to that attribute directly, so the ``redis`` library is
never imported or patched.

See docs/features/tm-shell/plan/phase-03-event-relay.md §3.4.
"""

from __future__ import annotations

import json
import queue
import time
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from personalscraper.conf.models.web import WebConfig
from personalscraper.core.event_bus import EventBus, event_from_envelope
from personalscraper.indexer.events import BackfillCompleted
from personalscraper.subscribers import redis_stream
from personalscraper.subscribers.redis_stream import RedisEventPublisher

#: Default stream key used across the producer tests (matches ``WebConfig``).
STREAM_KEY = "personalscraper:events"


def _make_event(scope: str = "full", scanned: int = 1) -> BackfillCompleted:
    """Build a minimal :class:`BackfillCompleted` event for test purposes.

    Args:
        scope: Backfill scope label.
        scanned: Number of items scanned.

    Returns:
        A frozen ``BackfillCompleted`` with default-zero metrics.
    """
    return BackfillCompleted(
        scope=scope,
        scanned=scanned,
        updated=0,
        skipped=0,
        failed=0,
        ids_added_count=0,
        ratings_added_count=0,
    )


def _poll_until(predicate: Callable[[], bool], timeout: float = 5.0, interval: float = 0.02) -> bool:
    """Poll *predicate* until it is truthy or *timeout* elapses.

    Generous polling (rather than a fixed sleep) keeps the daemon-thread
    assertions stable under the ``xdist`` + coverage load the suite runs under.

    Args:
        predicate: A zero-argument callable returning a bool.
        timeout: Maximum seconds to wait.
        interval: Sleep between polls.

    Returns:
        The final value of *predicate* (True if it became truthy in time).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _warning_event_names(mock_warning: MagicMock) -> list[str]:
    """Extract the structlog event names passed to a patched ``log.warning``.

    Args:
        mock_warning: The mock replacing ``redis_stream.log.warning``.

    Returns:
        The first positional argument of every recorded call (the event name).
    """
    return [call.args[0] for call in mock_warning.call_args_list if call.args]


@pytest.fixture
def event_bus() -> EventBus:
    """Return a fresh, empty :class:`EventBus` for each test."""
    return EventBus()


@pytest.fixture
def web_config() -> WebConfig:
    """Return a default :class:`WebConfig` (Redis URL unused — fakeredis injected)."""
    return WebConfig.model_validate({})


def test_full_emit_path_xadds_envelope_and_type(
    event_bus: EventBus, web_config: WebConfig, fake_redis: fakeredis.FakeRedis
) -> None:
    """A bus emit flows through the daemon thread and lands one stream entry."""
    publisher = RedisEventPublisher(event_bus, web_config)
    publisher._redis = fake_redis  # inject before any emit  # noqa: SLF001
    try:
        event_bus.emit(_make_event(scope="full", scanned=10))

        assert _poll_until(lambda: fake_redis.xlen(STREAM_KEY) == 1)
        entries = fake_redis.xrange(STREAM_KEY, min="-", max="+")
        assert len(entries) == 1

        _entry_id, fields = entries[0]
        assert fields["type"] == "BackfillCompleted"
        envelope = json.loads(fields["envelope"])
        assert envelope["_type"] == "BackfillCompleted"
        assert envelope["data"]["scope"] == "full"
        assert envelope["data"]["scanned"] == 10
    finally:
        publisher.close()


def test_envelope_round_trip(event_bus: EventBus, web_config: WebConfig, fake_redis: fakeredis.FakeRedis) -> None:
    """A real event survives ``event_from_envelope(event_to_envelope(e))`` intact."""
    publisher = RedisEventPublisher(event_bus, web_config)
    publisher._redis = fake_redis  # noqa: SLF001
    try:
        original = _make_event(scope="provider_ids", scanned=100)
        # Publish synchronously in the test thread for determinism.
        publisher._publish(original)  # noqa: SLF001

        entries = fake_redis.xrange(STREAM_KEY, min="-", max="+")
        _entry_id, fields = entries[0]
        envelope = json.loads(fields["envelope"])

        reconstructed = event_from_envelope(envelope)
        assert isinstance(reconstructed, BackfillCompleted)
        # Frozen-dataclass __eq__ compares every field, including the inherited
        # event_id / timestamp / correlation_id — a full round-trip must match.
        assert reconstructed == original
    finally:
        publisher.close()


def test_maxlen_trims_stream(event_bus: EventBus, fake_redis: fakeredis.FakeRedis) -> None:
    """A small ``stream_maxlen`` keeps the stream length bounded under many adds."""
    cfg = WebConfig.model_validate({"stream_maxlen": 3})
    publisher = RedisEventPublisher(event_bus, cfg)
    publisher._redis = fake_redis  # noqa: SLF001
    try:
        for i in range(20):
            publisher._publish(_make_event(scope=f"round_{i}", scanned=i))  # noqa: SLF001

        length = fake_redis.xlen(cfg.stream_key)
        assert 0 < length <= 3
    finally:
        publisher.close()


def test_fail_soft_redis_down_warns_once(event_bus: EventBus, web_config: WebConfig) -> None:
    """A raising ``XADD`` never propagates and warns ``redis_publish_failed`` once."""
    publisher = RedisEventPublisher(event_bus, web_config)
    broken = MagicMock()
    broken.xadd.side_effect = ConnectionError("redis down")
    publisher._redis = broken  # noqa: SLF001
    try:
        with patch.object(redis_stream.log, "warning") as mock_warning:
            # Neither call may raise — fail-soft contract.
            publisher._publish(_make_event())  # noqa: SLF001
            publisher._publish(_make_event())  # noqa: SLF001

        names = _warning_event_names(mock_warning)
        assert names.count("redis_publish_failed") == 1
    finally:
        publisher.close()


def test_queue_full_drops_and_warns_once(
    event_bus: EventBus, web_config: WebConfig, fake_redis: fakeredis.FakeRedis
) -> None:
    """A saturated in-memory queue drops the event and warns ``redis_publish_queue_full``."""
    publisher = RedisEventPublisher(event_bus, web_config)
    publisher._redis = fake_redis  # noqa: SLF001
    # Stop the worker cleanly so it cannot drain the (soon-tiny) queue mid-test.
    publisher.close()

    publisher._queue = queue.Queue(maxsize=1)  # noqa: SLF001
    publisher._queue.put_nowait(object())  # occupy the single slot  # noqa: SLF001

    with patch.object(redis_stream.log, "warning") as mock_warning:
        # Must not raise even though the queue is full.
        publisher._on_event(_make_event())  # noqa: SLF001

    names = _warning_event_names(mock_warning)
    assert names.count("redis_publish_queue_full") == 1
    assert publisher._queue_full_warned is True  # noqa: SLF001


def test_close_stops_worker_thread(event_bus: EventBus, web_config: WebConfig, fake_redis: fakeredis.FakeRedis) -> None:
    """``close()`` joins the daemon worker thread so it is no longer alive."""
    publisher = RedisEventPublisher(event_bus, web_config)
    publisher._redis = fake_redis  # noqa: SLF001
    assert publisher._worker.is_alive()  # noqa: SLF001

    publisher.close()

    assert _poll_until(lambda: not publisher._worker.is_alive(), timeout=6)  # noqa: SLF001


def test_close_is_idempotent(event_bus: EventBus, web_config: WebConfig, fake_redis: fakeredis.FakeRedis) -> None:
    """Calling ``close()`` twice does not raise."""
    publisher = RedisEventPublisher(event_bus, web_config)
    publisher._redis = fake_redis  # noqa: SLF001

    publisher.close()
    publisher.close()  # second close must be a no-op, not an error
